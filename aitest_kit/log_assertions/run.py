"""Own and drive a deferred log assertion run around existing pytest entry points."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import threading
import time

import click

from .cleanup import cancel_cleanup, next_cleanup, settle
from .projection import publish, save_base
from .config import RunSettings, load_settings, state_root
from .coordinator import Coordinator
from .discovery import has_log_plans
from .pytest_plugin import SESSION_ENV, distributed_args
from .store import RunStore

CURRENT = ContextVar("aitest_log_run", default=None)


@contextmanager
def owner_lock(directory):
    lock_path = directory / ".owner.lock"
    if lock_path.is_symlink():
        raise ValueError("log run lock cannot be a symlink")
    with lock_path.open("a+b") as lock:
        try:
            if os.name == "nt":
                import msvcrt
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("log assertion run is owned by another process") from exc
        yield


def reclaim_published(root, retention):
    cutoff = time.time() - retention
    if not root.is_dir():
        return
    with owner_lock(root):
        cursor_path = root / ".reclaim-cursor"
        cursor = cursor_path.read_text(encoding="ascii").strip() if cursor_path.is_file() and not cursor_path.is_symlink() else ""
        candidates = sorted(
            directory for directory in root.iterdir()
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", directory.name)
            and not directory.is_symlink() and (directory / "log-assertions.sqlite3").is_file()
        )
        after = [directory for directory in candidates if directory.name > cursor]
        batch = (after or candidates)[:100]
        if batch and not cursor_path.is_symlink():
            cursor_path.write_text(batch[-1].name, encoding="ascii")
    for directory in batch:
        path = directory / "log-assertions.sqlite3"
        if directory.is_symlink() or path.is_symlink() or not path.is_file():
            continue
        try:
            with owner_lock(directory):
                store = RunStore(path)
                if store.read(
                    "SELECT id FROM run WHERE id=? AND state IN ('FINISHED','CANCELLED') AND published=1 AND finished<?",
                    (directory.name, cutoff),
                ):
                    # Keep the lock inode stable while deleting the database.
                    # The final report writer owns the publication marker.
                    targets = [entry for entry in directory.glob("pytest-*.xml")
                               if re.fullmatch(r"pytest-[0-9]+\.xml", entry.name)]
                    for target in (*targets, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm"), path):
                        target.unlink(missing_ok=True)
        except ValueError:
            continue  # Active owner or a directory outside the state contract.
        except (OSError, sqlite3.Error):
            click.echo(f"Could not reclaim published log state for run {directory.name}", err=True)


class LogRun:
    def __init__(self, workspace, settings, metadata=None):
        self.workspace = workspace
        self.settings = settings
        self.metadata = metadata or {}
        self.root = state_root(workspace, settings)
        self.store = None
        self.lock = None
        self.thread = None
        self.failure = None
        self.draining = threading.Event()
        self.stopping = threading.Event()
        self.environments = {}
        self.report_plan = None

    def open(self, run_id, resume=False):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id):
            raise ValueError("invalid log assertion run ID")
        directory = self.root / run_id
        if resume:
            if not directory.is_dir() or directory.is_symlink():
                raise ValueError("log assertion run was not found in this workspace")
        else:
            self.root.mkdir(parents=True, exist_ok=True)
            try:
                reclaim_published(self.root, self.settings.retention_seconds)
            except (OSError, ValueError):
                click.echo("Could not scan log state for retention", err=True)
            directory.mkdir(mode=0o700)
        path = directory / "log-assertions.sqlite3"
        if path.is_symlink():
            raise ValueError("log assertion state file cannot be a symlink")
        lock = owner_lock(directory)
        lock.__enter__()
        self.lock = lock
        self.store = RunStore(path)
        try:
            if resume:
                row = self.store.run()
                if row["workspace"] != str(self.workspace) or row["id"] != run_id:
                    raise ValueError("log assertion run identity mismatch")
                self.settings = RunSettings(**json.loads(row["settings"]))
                if state_root(self.workspace, self.settings) != self.root:
                    raise ValueError("log assertion run state location differs from saved settings")
            else:
                self.store.create(run_id, self.workspace, asdict(self.settings), self.metadata)
                click.echo(f"Log assertion run: {run_id}")
            self.store.own()
            self.store.ensure_projection_tables()
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.lock is not None:
            lock, self.lock = self.lock, None
            lock.__exit__(None, None, None)

    def start(self, resume_env=None):
        async def coordinate():
            coordinator = Coordinator(self.store, self.settings, self.environments, self.draining, self.stopping)
            task = asyncio.create_task(coordinator.run(resume_env))
            while not task.done() and not self.stopping.is_set():
                await asyncio.wait((task,), timeout=.05)
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                if not self.stopping.is_set():
                    raise

        def run():
            try:
                asyncio.run(coordinate())
            except Exception as exc:
                self.failure = str(exc) if type(exc) is ValueError else type(exc).__name__

        self.thread = threading.Thread(target=run, name="aitest-log-coordinator")
        self.thread.start()

    def execute(self, command, env, files, report_path, report_id, selected, external_args, env_files, unit_index, report_factory=None):
        candidate = has_log_plans(files)
        if self.store is None and not candidate and not self.settings.concurrency_configured:
            return subprocess.run(command, text=True, env=env)
        count = self.settings.case_concurrency
        if distributed_args(external_args):
            raise click.ClickException("pytest distributed options conflict with Kit case concurrency")
        if count > 1 and importlib.util.find_spec("xdist") is None:
            raise click.ClickException("case concurrency requires aitest-kit[parallel]")
        if self.store is None:
            self.open(report_id)
            if self.report_plan is not None:
                self.store.update("INSERT INTO report_plan VALUES(?)", (json.dumps(self.report_plan),))
            self.start()
        index = unit_index
        self.store.update("INSERT INTO unit VALUES(?,?,?,?)", (
            index, str(report_path.resolve()), json.dumps(selected),
            json.dumps([str(path.resolve()) for path in env_files or ()]),
        ))
        self.environments[index] = env
        if report_factory is not None:
            base = report_factory()
            save_base(self.store, report_path, base)
            if self.report_plan is None:
                root = str(report_path.resolve())
                self.report_plan = {"root": root, "bucket": str(report_path.resolve().parents[1]),
                                    "base": base, "units": [[index, root]]}
                self.store.update("INSERT INTO report_plan VALUES(?)", (json.dumps(self.report_plan),))
            command = [f"--junitxml={self.raw_junit(index)}" if arg.startswith("--junitxml=") else arg
                       for arg in command]
        data = {
            "path": str(self.store.path), "epoch": self.store.epoch, "unit": index,
            "request_timeout": self.settings.request_timeout_seconds,
            "pending_limit": self.settings.pending_request_limit,
            "preflight_timeout": max(30, 2 * self.settings.http_timeout_seconds * count),
            "case_concurrency": count, "parent_pid": os.getpid(),
        }
        cmd = [*command[:3], "-p", "aitest_kit.log_assertions.pytest_plugin"]
        if count > 1:
            cmd.extend(["-n", str(count), "--dist", "load", "--max-worker-restart", "0"])
        cmd.extend(command[3:])
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        with subprocess.Popen(cmd, text=True, env={**env, SESSION_ENV: json.dumps(data)}, **options) as process:
            try:
                while True:
                    if self.failure is not None:
                        raise click.ClickException(f"log coordinator failed: {self.failure}")
                    try:
                        returncode = process.wait(.1)
                    except subprocess.TimeoutExpired:
                        continue
                    self.store.close_prepared(index)
                    self.store.update("UPDATE attempt SET state='INTERRUPTED' WHERE unit=? AND state='RUNNING'", (index,))
                    self.store.update("UPDATE run SET pytest_exit=CASE WHEN COALESCE(pytest_exit,0) != 0 THEN pytest_exit ELSE ? END",
                                      (returncode,))
                    return subprocess.CompletedProcess(cmd, returncode)
            except BaseException:
                self.terminate(process)
                raise

    def raw_junit(self, index):
        return self.store.path.with_name(f"pytest-{index}.xml")

    def terminate(self, process):
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(self.settings.cancel_grace_seconds)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        except ProcessLookupError:
            process.wait()

    def finish(self, pytest_code):
        if self.store is None:
            return pytest_code
        self.store.update("UPDATE run SET state='DRAINING',pytest_exit=?", (pytest_code,))
        self.draining.set()
        if self.thread is not None:
            while self.thread.is_alive():
                self.thread.join(.1)
        if self.failure is not None:
            raise click.ClickException(f"log coordinator failed: {self.failure}")
        counts = {row["state"]: row["count"] for row in self.store.read(
            "SELECT state,COUNT(*) AS count FROM request GROUP BY state")}
        interrupted = self.store.read("SELECT 1 FROM attempt WHERE state='INTERRUPTED' LIMIT 1")
        has_projection = bool(self.store.read("SELECT 1 FROM report_plan"))
        code = pytest_code
        if not has_projection and not code and (interrupted or counts.get("ERROR") or counts.get("FAILED")):
            code = 1
        with self.store.write() as db:
            pending = db.execute("SELECT 1 FROM request WHERE state IN ('PREPARED','WAITING','READY','RUNNING') LIMIT 1")
            if pending.fetchone():
                raise click.ClickException("log assertions remain unfinished")
        try:
            code = publish(self.store, self.settings, final=True, prior_code=code)
        except OSError as exc:
            raise click.ClickException("could not publish the final log report; retry with aitest run --resume") from exc
        self.store.update("""UPDATE run SET state='FINISHED',finished=?,exit_code=?,
                          published=EXISTS(SELECT 1 FROM report_revision)""", (time.time(), code))
        click.echo(f"Log checks: passed={counts.get('PASSED', 0)}, failed={counts.get('FAILED', 0)}, error={counts.get('ERROR', 0)}")
        return code

    def stop(self, cancelled):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join()
        if self.store is None:
            return
        if cancelled:
            for row in self.store.read("SELECT id FROM request WHERE state IN ('PREPARED','WAITING','READY','RUNNING')"):
                self.store.complete(row["id"], "CANCELLED", {"state": "CANCELLED"})
        self.store.update("UPDATE attempt SET state='INTERRUPTED' WHERE state='RUNNING'")
        with self.store.write() as db:
            if cancelled:
                cancel_cleanup(db)
            db.execute("UPDATE run SET state=?,finished=?,exit_code=?",
                       ("CANCELLED" if cancelled else "INTERRUPTED", time.time(), 2 if cancelled else None))
        if cancelled:
            publish(self.store, self.settings, final=True, prior_code=2, cancelled=True)
            self.store.update("UPDATE run SET published=EXISTS(SELECT 1 FROM report_revision)")
        else:
            publish(self.store, self.settings)


@contextmanager
def cancellation_signal():
    previous_term = signal.getsignal(signal.SIGTERM)

    def interrupt(signum, frame):
        raise KeyboardInterrupt()

    install_signal = threading.current_thread() is threading.main_thread()
    if install_signal:
        signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        if install_signal:
            signal.signal(signal.SIGTERM, previous_term)


@contextmanager
def log_run(workspace, case_concurrency, log_concurrency, metadata):
    session = LogRun(workspace, load_settings(workspace, case_concurrency, log_concurrency), metadata)
    token = CURRENT.set(session)
    try:
        try:
            yield session
        except SystemExit as exc:
            raise SystemExit(session.finish(int(exc.code or 0))) from None
        else:
            code = session.finish(0)
            if code:
                raise SystemExit(code)
    except KeyboardInterrupt:
        session.stop(True)
        raise SystemExit(2) from None
    except Exception:
        if session.store is None or session.store.run()["state"] != "DRAINING":
            session.stop(False)
        else:
            session.stopping.set()
            if session.thread is not None:
                session.thread.join()
        raise
    finally:
        session.close()
        CURRENT.reset(token)


def resume(workspace, run_id, env_loader):
    session = LogRun(workspace, load_settings(workspace, state_only=True))
    try:
        session.open(run_id, resume=True)
        row = session.store.run()
        if row["state"] in ("FINISHED", "CANCELLED"):
            repaired = False
            if row["state"] == "CANCELLED":
                with session.store.write() as db:
                    repaired = bool(cancel_cleanup(db))
                    if repaired:
                        db.execute("UPDATE run SET published=0")
            if (repaired or not row["published"]) and session.store.read("SELECT 1 FROM report_plan"):
                code = publish(session.store, session.settings, final=True, prior_code=row["exit_code"],
                               cancelled=row["state"] == "CANCELLED")
                session.store.update("UPDATE run SET published=1,exit_code=?", (code,))
                return code
            return row["exit_code"]
        session.store.update("UPDATE preflight SET state='error',reason='previous run interrupted' WHERE state='pending'")
        session.store.recover()
        session.store.expire_waiting(time.time())
        versions = session.store.read("SELECT rules FROM request WHERE state='WAITING'")
        if any(group.get("executor_version") != 1 for row_rules in versions for group in json.loads(row_rules["rules"])):
            raise ValueError("unsupported saved log rule executor version")
        settle(session.store, session.settings.queue_timeout_seconds)
        next_cleanup(session.store)
        waiting = session.store.read(
            """SELECT DISTINCT unit.env_files FROM request
            JOIN attempt ON attempt.id=request.attempt JOIN unit ON unit.idx=attempt.unit
            WHERE request.state='WAITING' OR EXISTS(SELECT 1 FROM cleanup WHERE cleanup.request=request.id AND cleanup.state='queued')""",
        )
        resume_env = None
        if waiting:
            try:
                configs = [env_loader([Path(path) for path in json.loads(unit["env_files"])]) for unit in waiting]
                if len(configs) > 1 and len({session.settings.platform_credentials(env) for env in configs}) != 1:
                    raise ValueError("saved units resolve to different log platform credentials")
                resume_env = configs[0]
            except ValueError:
                if session.store.read("SELECT 1 FROM request WHERE state='WAITING' LIMIT 1"):
                    raise
                session.store.update(
                    "UPDATE cleanup SET state='unknown',reason='ORIGINAL_TOKEN_UNAVAILABLE' WHERE state='queued'"
                )
        session.start(resume_env)
        code = row["pytest_exit"]
        return session.finish(code if code is not None and (code != 0 or row["state"] == "DRAINING") else 1)
    except KeyboardInterrupt:
        session.stop(True)
        return 2
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        session.stopping.set()
        if session.thread is not None:
            session.thread.join()
        session.close()
