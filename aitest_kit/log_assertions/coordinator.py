"""Run-wide polling and bounded evidence validation."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
import hashlib
import hmac
import json
import multiprocessing
import time

import httpx

from .cleanup import next_cleanup, settle, submit_available
from .projection import publish
from .client import LogPlatformClient, LogPlatformError
from .rules import evaluate_request


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
        child.start()
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
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aitest-log-db")

    async def db(self, function, *args, **kwargs):
        return await asyncio.get_running_loop().run_in_executor(self.executor, partial(function, *args, **kwargs))

    async def credentials(self, env):
        url, token = env.get(self.settings.base_url_env), env.get(self.settings.token_env)
        if not url or not token:
            raise ValueError(f"log platform requires {self.settings.base_url_env} and {self.settings.token_env}")
        normalized = str(httpx.URL(url).copy_with(path=httpx.URL(url).path.rstrip("/") + "/"))
        row = await self.db(self.store.run)
        salt = bytes.fromhex(row["salt"])
        url_hash = hashlib.sha256(normalized.encode()).hexdigest()
        token_hash = hmac.new(salt, token.encode(), hashlib.sha256).hexdigest()
        if row["url_hash"] is not None and row["url_hash"] != url_hash:
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
            await self.db(self.store.update, "UPDATE run SET url_hash=?,token_hash=COALESCE(token_hash,?)", self.binding)
        return self.client

    async def preflight(self, row, env):
        try:
            client = await self.credentials(env)
            deadline = asyncio.get_running_loop().time() + self.settings.http_timeout_seconds
            sources = {item["source_id"]: item for item in await client.list_sources(deadline=deadline)}
            await client.get_limits(deadline=deadline)
            for source, cleanup in json.loads(row["sources"]).items():
                item = sources.get(source)
                required = {"read", "cleanup"} if cleanup else {"read"}
                if (item is None or not item["enabled"] or not item["completion_supported"]
                        or not required.issubset(item["actions"])):
                    raise ValueError("log source is missing required capability or authorization")
        except LogPlatformError as exc:
            outcome = ("error", str(exc))
        except (ValueError, httpx.InvalidURL):
            outcome = ("error", "log platform precondition failed (credentials, URL or source capabilities)")
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
        sources = sorted({row["source"] for row in waiting})
        source = self.cursor = next((source for source in sources if self.cursor is None or source > self.cursor), sources[0])
        rows = sorted((row for row in waiting if row["source"] == source), key=_deadline)[:self.client.batch_size]
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0, min(_deadline(row) for row in rows) - time.time())
        try:
            statuses = await self.client.get_statuses(source, [row["correlation"] for row in rows], deadline=deadline)
        except LogPlatformError as exc:
            if exc.limit is not None and exc.limit < len(rows):
                self.client.batch_size = exc.limit
                return
            for row in rows:
                if exc.retryable or exc.code == "DEADLINE_EXCEEDED":
                    await self.again(row["id"], max(self.settings.poll_interval_seconds, exc.retry_after or 0))
                elif row["state"] == "PREPARED":
                    await self.again(row["id"], self.settings.poll_interval_seconds)
                else:
                    await self.error(row["id"], exc.code)
            return
        for row, status in zip(rows, statuses):
            entry = status["request"]
            if entry is None:
                await self.again(row["id"], self.settings.poll_interval_seconds)
                continue
            capture, availability = entry.get("capture_state"), entry["availability"]
            if availability != "AVAILABLE" or capture not in ("COMPLETE", "COLLECTING"):
                if row["state"] == "PREPARED":
                    await self.again(row["id"], self.settings.poll_interval_seconds)
                else:
                    await self.error(row["id"], "LOG_EVIDENCE_UNAVAILABLE")
                continue
            raw_expiry = entry.get("expires_at")
            expires = None
            if raw_expiry is not None:
                try:
                    date = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
                    if date.tzinfo is None:
                        raise ValueError()
                    expires = date.timestamp()
                except (ValueError, TypeError, AttributeError, OverflowError):
                    if row["state"] == "PREPARED":
                        await self.again(row["id"], self.settings.poll_interval_seconds)
                    else:
                        await self.error(row["id"], "PLATFORM_PROTOCOL_ERROR")
                    continue
            await self.db(
                self.store.update,
                """UPDATE request SET version=?, expires=COALESCE(?, expires), next_poll=?,
                state=CASE WHEN state='WAITING' AND ?='COMPLETE' THEN 'READY' ELSE state END
                WHERE id=? AND state IN ('WAITING','PREPARED')""",
                (entry["version"], expires, time.time() + self.settings.poll_interval_seconds, capture, row["id"]),
            )

    async def verify(self, row, claim):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0, _deadline(row) - time.time())
        try:
            evidence = await self.client.read_snapshot(row["source"], row["correlation"], row["version"], deadline=deadline)
        except LogPlatformError as exc:
            if exc.retryable or exc.refresh_snapshot:
                await self.again(row["id"], max(self.settings.poll_interval_seconds, exc.retry_after or 0), claim)
            else:
                await self.error(row["id"], exc.code, claim)
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
                waiting = await self.db(self.store.read, "SELECT id,source FROM request WHERE state='WAITING'")
                try:
                    client = await self.credentials(resume_env)
                except (ValueError, httpx.InvalidURL):
                    if waiting:
                        raise
                    await self.db(self.store.update, "UPDATE cleanup SET state='unknown',reason='ORIGINAL_TOKEN_UNAVAILABLE' WHERE state='queued'")
            else:
                waiting = []
            if waiting:
                deadline = asyncio.get_running_loop().time() + self.settings.http_timeout_seconds
                sources = {item["source_id"]: item for item in await client.list_sources(deadline=deadline)}
                await client.get_limits(deadline=deadline)
                for row in waiting:
                    item = sources.get(row["source"])
                    if not item or not item["enabled"] or not item["completion_supported"] or "read" not in item["actions"]:
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
                    SELECT id,source,correlation,deadline,expires,state,next_poll,version FROM request WHERE state IN
                    ('PREPARED','WAITING','READY','RUNNING') ORDER BY source,deadline
                """)
                if cleanup is not None and cleanup.done():
                    cleanup.result()
                    cleanup = None
                await self.db(settle, self.store, self.settings.submit_timeout_seconds)
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
                for row in sorted(rows, key=_deadline):
                    if row["state"] == "RUNNING":
                        continue
                    if now >= _deadline(row):
                        if row["state"] != "PREPARED":
                            await self.error(row["id"], "LOG_EVIDENCE_TIMEOUT")
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


def _deadline(row):
    return min(row["deadline"], row["expires"] if row["expires"] is not None else row["deadline"])
