"""Run-wide polling and bounded evidence validation."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import hmac
import json
import multiprocessing
import time

import httpx

from .cleanup import next_cleanup, settle, submit_available
from .projection import publish
from .client import LogPlatformClient, LogPlatformError, request_expiry, source_evidence_view
from .rules import evaluate_request
from .status import evidence_deadline as _deadline, observation_for


def _evaluate(sender, rules, events, inputs):
    with sender:
        sender.send(evaluate_request(rules, events, inputs))


async def evaluate_isolated(rules, events, inputs, timeout):
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    child = context.Process(target=_evaluate, args=(sender, rules, events, inputs), daemon=True)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    try:
        starting = asyncio.create_task(asyncio.to_thread(child.start))
        try:
            await asyncio.shield(starting)
        except asyncio.CancelledError:
            await starting
            raise
        sender.close()
        while loop.time() < deadline:
            if receiver.poll():
                try:
                    return await asyncio.wait_for(asyncio.to_thread(receiver.recv), max(0, deadline - loop.time()))
                except asyncio.TimeoutError:
                    return {"state": "ERROR", "code": "RULE_TIMEOUT"}
                except EOFError:
                    break
            if not child.is_alive():
                break
            await asyncio.sleep(.02)
        return {"state": "ERROR", "code": "RULE_PROCESS_ERROR" if not child.is_alive() else "RULE_TIMEOUT"}
    finally:
        sender.close()
        if child.pid is not None:
            if child.is_alive():
                child.kill()
            await asyncio.to_thread(child.join)
            child.close()
        receiver.close()


class Coordinator:
    def __init__(self, store, settings, environments, draining, stopping):
        self.store = store
        self.settings = settings
        self.environments = environments
        self.draining = draining
        self.stopping = stopping
        self.client = None
        self.tasks = set()
        self.cursor = None
        self.evidence_views = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aitest-log-db")

    async def db(self, function, *args, **kwargs):
        return await asyncio.get_running_loop().run_in_executor(self.executor, partial(function, *args, **kwargs))

    async def credentials(self, env):
        url, token = self.settings.platform_credentials(env)
        if not token:
            raise ValueError(f"log platform requires {self.settings.token_env}")
        row = await self.db(self.store.run)
        salt = bytes.fromhex(row["salt"])
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        token_hash = hmac.new(salt, token.encode(), hashlib.sha256).hexdigest()
        saved_settings = json.loads(row["settings"])
        legacy = "base_url" not in saved_settings
        if row["url_hash"] is not None and row["url_hash"] != url_hash:
            parsed = httpx.URL(url)
            old_url = str(parsed.copy_with(path=parsed.path.rstrip("/") + "/"))
            if (not legacy or row["token_hash"] != token_hash
                    or row["url_hash"] != hashlib.sha256(old_url.encode()).hexdigest()):
                raise ValueError("log platform URL differs from the saved run")
        if self.client is not None and self.binding != (url_hash, token_hash):
            raise ValueError("log platform credentials differ between units")
        if self.client is None:
            self.client = LogPlatformClient(
                url, token, http_timeout_seconds=self.settings.http_timeout_seconds,
                snapshot_max_bytes=self.settings.snapshot_max_bytes,
                snapshot_max_events=self.settings.snapshot_max_events,
                snapshot_max_pages=self.settings.snapshot_max_pages,
            )
            self.binding = (url_hash, token_hash)
            if legacy:
                saved_settings["base_url"] = None
            await self.db(
                self.store.update, "UPDATE run SET url_hash=?,token_hash=COALESCE(token_hash,?),settings=?",
                (*self.binding, json.dumps(saved_settings)),
            )
        return self.client

    async def preflight(self, row, env):
        try:
            client = await self.credentials(env)
            deadline = asyncio.get_running_loop().time() + self.settings.http_timeout_seconds
            sources = {item["source_id"]: item for item in await client.list_sources(deadline=deadline)}
            await client.get_limits(deadline=deadline)
            selected = {}
            for source, cleanup in json.loads(row["sources"]).items():
                item = sources.get(source)
                required = {"read", "cleanup"} if cleanup else {"read"}
                view = source_evidence_view(item)
                if item is None or not item["enabled"]:
                    raise ValueError(f"log source {source!r} is unavailable")
                if view is None or self.evidence_views.get(source, view) != view:
                    raise ValueError(f"log source {source!r} lacks the required evidence view")
                missing = required.difference(item["actions"])
                if missing:
                    raise ValueError(f"log source {source!r} lacks actions: {', '.join(sorted(missing))}")
                selected[source] = view
            views = {**self.evidence_views, **selected}
            if views != self.evidence_views:
                saved = json.loads((await self.db(self.store.run))["metadata"])
                saved["log_evidence_views"] = views
                await self.db(self.store.update, "UPDATE run SET metadata=?", (json.dumps(saved),))
                self.evidence_views = views
        except LogPlatformError as exc:
            outcome = ("error", str(exc))
        except ValueError as exc:
            outcome = ("error", str(exc))
        else:
            outcome = ("ok", None)
        await self.db(self.store.update, "UPDATE preflight SET state=?,reason=? WHERE id=?", (*outcome, row["id"]))

    async def error(self, request, code, claim=None):
        await self.db(self.store.complete, request, "ERROR", {"state": "ERROR", "code": code}, claim=claim)

    async def again(self, request, delay, claim=None):
        if claim is None:
            await self.db(self.store.update, "UPDATE request SET next_poll=? WHERE id=? AND state IN ('PREPARED','WAITING')",
                              (time.time() + delay, request))
        else:
            await self.db(self.store.update, "UPDATE request SET state='WAITING',claim=NULL,next_poll=? WHERE id=? AND claim=?",
                              (time.time() + delay, request, claim))

    async def poll(self, waiting):
        mixed = self.client.readiness_batch_supported
        if not mixed:
            sources = sorted({row["source"] for row in waiting})
            self.cursor = next((source for source in sources if self.cursor is None or source > self.cursor), sources[0])
            waiting = [row for row in waiting if row["source"] == self.cursor]
        rows = sorted(waiting, key=lambda row: (row.get("next_poll", 0), _deadline(row)))[:self.client.batch_size]
        loop = asyncio.get_running_loop()
        shortest = min(map(_deadline, rows))
        deadline = loop.time() + max(0, shortest - time.time())
        try:
            if mixed:
                statuses = await self.client.get_readiness(
                    [(row["source"], row["correlation"]) for row in rows], deadline=deadline)
            else:
                statuses = await self.client.get_statuses(
                    self.cursor, [row["correlation"] for row in rows], deadline=deadline)
        except LogPlatformError as exc:
            if exc.limit is not None and exc.limit < len(rows):
                self.client.batch_size = exc.limit
                return
            now = time.time()
            delay = max(self.settings.poll_interval_seconds, exc.retry_after or 0)
            for row in rows:
                if exc.code == "DEADLINE_EXCEEDED" and _deadline(row) > shortest:
                    # A shorter-lived peer used up the HTTP budget for this batch.
                    continue
                await self.db(self.store.poll_error, row["id"], exc.code, now, delay,
                              exc.retryable or exc.code == "DEADLINE_EXCEEDED")
            return
        now = time.time()
        entries = [(row["id"], observation_for(status, now), request_expiry(status["request"] or {}))
                   for row, status in zip(rows, statuses)]
        await self.db(self.store.observe, entries, now, self.settings.poll_interval_seconds)

    async def verify(self, row, claim):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0, _deadline(row) - time.time())
        try:
            evidence = await self.client.read_snapshot(
                row["source"], row["correlation"], row["version"], deadline=deadline,
                evidence_view=row["evidence_view"])
        except LogPlatformError as exc:
            if exc.retryable or exc.refresh_snapshot:
                await self.again(row["id"], max(self.settings.poll_interval_seconds, exc.retry_after or 0), claim)
            else:
                await self.error(row["id"], exc.code, claim)
            return
        if loop.time() >= deadline:
            await self.error(row["id"], "LOG_EVIDENCE_TIMEOUT", claim)
            return
        result = await evaluate_isolated(json.loads(row["rules"]), evidence["items"], json.loads(row["inputs"]),
                                         self.settings.check_timeout_seconds)
        result.update(capture_state=evidence["request"]["capture_state"], availability=evidence["request"]["availability"])
        await self.db(self.store.complete, row["id"], result["state"], result, claim=claim)

    async def run(self, resume_env=None):
        poll = preflight = cleanup = None
        last_projection = 0
        try:
            if resume_env is not None:
                waiting = await self.db(self.store.read, "SELECT id,source,evidence_view FROM request WHERE state='WAITING'")
                try:
                    client = await self.credentials(resume_env)
                except ValueError:
                    if waiting:
                        raise
                    await self.db(self.store.update, "UPDATE cleanup SET state='unknown',reason='ORIGINAL_TOKEN_UNAVAILABLE' WHERE state='queued'")
            else:
                waiting = []
            if waiting:
                deadline = asyncio.get_running_loop().time() + self.settings.http_timeout_seconds
                sources = {item["source_id"]: item for item in await client.list_sources(deadline=deadline)}
                await client.get_limits(deadline=deadline)
                saved = json.loads((await self.db(self.store.run))["metadata"])
                self.evidence_views = saved.get("log_evidence_views", {})
                for row in waiting:
                    item = sources.get(row["source"])
                    view = row["evidence_view"]
                    if (not item or not item["enabled"] or source_evidence_view(item) != view
                            or "read" not in item["actions"]):
                        await self.error(row["id"], "LOG_SOURCE_UNAVAILABLE")
            while not self.stopping.is_set():
                for task in tuple(self.tasks):
                    if task.done():
                        self.tasks.remove(task)
                        task.result()
                if poll is not None and poll.done():
                    poll.result()
                    poll = None
                if preflight is not None and preflight.done():
                    preflight.result()
                    preflight = None
                if preflight is None:
                    gates = await self.db(self.store.read, "SELECT * FROM preflight WHERE state='pending' ORDER BY rowid LIMIT 1")
                    if gates and not self.stopping.is_set():
                        gate = gates[0]
                        preflight = asyncio.create_task(self.preflight(gate, self.environments[gate["unit"]]))
                draining = self.draining.is_set()
                rows = await self.db(self.store.read, """
                    SELECT id,source,correlation,deadline,expires,state,next_poll,version,evidence_view FROM request WHERE state IN
                    ('PREPARED','WAITING','READY','RUNNING') ORDER BY source,deadline
                """)
                if cleanup is not None and cleanup.done():
                    cleanup.result()
                    cleanup = None
                await self.db(settle, self.store, self.settings.queue_timeout_seconds)
                if cleanup is None and not self.stopping.is_set():
                    queued = await self.db(next_cleanup, self.store)
                    if queued and self.client is not None:
                        cleanup = asyncio.create_task(submit_available(self))
                if not rows and draining and cleanup is None and not await self.db(
                    self.store.read, "SELECT 1 FROM cleanup WHERE state='queued' LIMIT 1"
                ):
                    break
                now_monotonic = time.monotonic()
                if now_monotonic - last_projection >= .25:
                    await self.db(publish, self.store, self.settings)
                    last_projection = now_monotonic
                ready_slots = self.settings.log_concurrency - len(self.tasks)
                waiting = []
                now = time.time()
                if any(row["state"] == "READY" or (row["state"] == "WAITING" and poll is None)
                       for row in rows if now >= _deadline(row)):
                    await self.db(self.store.expire_waiting, now, include_waiting=poll is None)
                for row in sorted(rows, key=_deadline):
                    if row["state"] == "RUNNING":
                        continue
                    if now >= _deadline(row):
                        continue
                    if row["state"] == "READY" and ready_slots > 0:
                        claim = await self.db(self.store.claim, row["id"])
                        if claim:
                            payload, = await self.db(self.store.read, "SELECT rules,inputs FROM request WHERE id=?", (row["id"],))
                            self.tasks.add(asyncio.create_task(self.verify({**row, **payload}, claim)))
                            ready_slots -= 1
                    if row["state"] in ("PREPARED", "WAITING") and row["correlation"] and row["next_poll"] <= now:
                        waiting.append(row)
                if waiting and poll is None:
                    poll = asyncio.create_task(self.poll(waiting))
                await asyncio.sleep(.05 if rows else .1)
        finally:
            pending = [*self.tasks, *(task for task in (poll, preflight, cleanup) if task is not None)]
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            if self.client is not None:
                await self.client.aclose()
            self.executor.shutdown(wait=True)
