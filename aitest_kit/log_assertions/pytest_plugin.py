"""Worker-side preflight, request recorder and pytest phase facts."""
import ast
import inspect
import json
import os
import sqlite3
from pathlib import Path
from threading import Event, Thread
import textwrap
import time
import uuid

import pytest

from .discovery import iter_log_steps, source_permissions
from .runtime import SQLiteRecorder
from .scope import GROUPED_SOURCES_UNSUPPORTED, use_request_recorder
from .store import RunStore

SESSION_ENV = "AITEST_INTERNAL_LOG_SESSION"
_DISTRIBUTED = ("--numprocesses", "--dist", "--max-worker-restart", "--tx",
                "--px", "--rsyncdir", "--rsyncignore", "--maxschedchunk", "--distload")


def distributed_args(args):
    return [arg for arg in args if arg in ("-d", "-f")
            or arg.startswith("-n") or arg.split("=", 1)[0] in _DISTRIBUTED]


def pytest_load_initial_conftests(early_config, parser, args):
    data = os.environ.get(SESSION_ENV)
    if data is None:
        return
    session = json.loads(data)
    expected = ["-n", "--dist", "--max-worker-restart"] if session["case_concurrency"] > 1 else []
    if distributed_args(args) != expected:
        raise pytest.UsageError("pytest distributed options conflict with Kit case concurrency (CLI, PYTEST_ADDOPTS or addopts)")


def pytest_configure(config):
    data = os.environ.get(SESSION_ENV)
    if not data:
        return
    state = config._aitest_log_session = json.loads(data)
    store = config._aitest_log_store = RunStore(state["path"], state["epoch"])
    done = Event()
    controller = not hasattr(config, "workerinput")

    def supervise_owner():
        while not done.wait(.2):
            parent_gone = controller and os.name == "posix" and os.getppid() != state["parent_pid"]
            try:
                stale_epoch = store.run()["epoch"] != state["epoch"]
            except sqlite3.Error:
                stale_epoch = False
            if parent_gone or stale_epoch:
                os.write(2, b"pytest stopped because its log assertion run owner exited or changed\n")
                os._exit(2)

    guard = Thread(target=supervise_owner, name="aitest-log-owner", daemon=True)
    config._aitest_log_supervision = (guard, done)
    guard.start()


def pytest_unconfigure(config):
    supervision = getattr(config, "_aitest_log_supervision", None)
    if supervision is not None:
        guard, done = supervision
        done.set()
        guard.join(timeout=1)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    config = session.config
    state = getattr(config, "_aitest_log_session", None)
    if state is None or config.option.collectonly:
        return
    store = config._aitest_log_store
    plans = []
    declared = []
    report_nodes = []
    for item in session.items:
        if not isinstance(item, pytest.Function):
            continue
        file = Path(os.path.relpath(item.path)).as_posix()
        qualified_name = item.nodeid.split("::", 1)[1]
        report_nodes.append((state["unit"], item.nodeid, f"{file}::{qualified_name}"))
        try:
            source = inspect.getsource(item.function)
        except (OSError, TypeError):
            continue
        tree = ast.parse(textwrap.dedent(source))
        try:
            steps = list(iter_log_steps(tree))
        except ValueError as exc:
            _reject_preflight(config, state["unit"], f"{item.nodeid}: {exc}")
            return
        if (getattr(SQLiteRecorder, "supports_multiple_log_sources", False) is not True
                and any("source_id" in step["rules"][0] for step in steps)):
            sources = ", ".join(source_permissions(steps))
            _reject_preflight(config, state["unit"], f"{item.nodeid}: {GROUPED_SOURCES_UNSUPPORTED} ({sources})")
            return
        plans.extend(steps)
        declared.extend((state["unit"], item.nodeid, step["step"], step["source"]) for step in steps)
    sources = source_permissions(plans)
    key = uuid.uuid4().hex
    with store.write() as db:
        db.executemany("INSERT OR IGNORE INTO report_node VALUES(?,?,?)", report_nodes)
        if not sources:
            return
        db.executemany("INSERT OR IGNORE INTO declared_source VALUES(?,?,?,?)", declared)
        db.execute("INSERT INTO preflight(id,unit,sources) VALUES(?,?,?)", (key, state["unit"], json.dumps(sources)))
    deadline = time.monotonic() + state["preflight_timeout"]
    while time.monotonic() < deadline:
        result = store.read("SELECT state,reason FROM preflight WHERE id=?", (key,))[0]
        if result["state"] == "ok":
            return
        if result["state"] == "error":
            if not hasattr(config, "workerinput"):
                raise pytest.UsageError(result["reason"])
            return
        if store.run()["epoch"] != state["epoch"]:
            raise pytest.UsageError("log assertion run owner changed")
        time.sleep(.05)
    _reject_preflight(config, state["unit"], "log platform preflight timed out")


def _reject_preflight(config, unit, reason):
    config._aitest_log_store.update(
        "INSERT INTO preflight(id,unit,sources,state,reason) VALUES(?,?,'{}','error',?)",
        (uuid.uuid4().hex, unit, reason),
    )
    if not hasattr(config, "workerinput"):
        raise pytest.UsageError(reason)


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node, ids):
    config = node.config
    state = getattr(config, "_aitest_log_session", None)
    if state is None:
        return
    errors = config._aitest_log_store.read(
        "SELECT reason FROM preflight WHERE unit=? AND state='error' ORDER BY rowid LIMIT 1",
        (state["unit"],),
    )
    if errors:
        pytest.exit(errors[0]["reason"], returncode=pytest.ExitCode.USAGE_ERROR)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_protocol(item):
    state = getattr(item.config, "_aitest_log_session", None)
    if state is None:
        return (yield)
    store = item.config._aitest_log_store
    attempt = store.start_attempt(state["unit"], item.nodeid, os.environ.get("PYTEST_XDIST_WORKER", "main"))
    item._aitest_log_attempt = attempt
    item._aitest_log_has_setup = False
    recorder = item._aitest_log_recorder = SQLiteRecorder(store, attempt, state["request_timeout"], state["pending_limit"])
    with use_request_recorder(recorder):
        result = yield
    store.update("INSERT OR IGNORE INTO case_closed VALUES(?,?)", (state["unit"], item.nodeid))
    return result


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    report = yield
    attempt = getattr(item, "_aitest_log_attempt", None)
    if attempt is not None:
        item.config._aitest_log_store.phase(attempt, report.when, report.outcome)
        report.user_properties.append(("aitest_nodeid", item.nodeid))
    return report

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    recorder = getattr(item, "_aitest_log_recorder", None)
    if recorder is None:
        return
    if getattr(item, "_aitest_log_has_setup", False):
        state = item.config._aitest_log_session
        attempt = recorder.store.start_attempt(state["unit"], item.nodeid, os.environ.get("PYTEST_XDIST_WORKER", "main"))
        item._aitest_log_attempt = recorder.attempt = attempt
    item._aitest_log_has_setup = True
