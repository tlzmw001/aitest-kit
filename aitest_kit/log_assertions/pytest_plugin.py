"""Worker-side preflight, request recorder and pytest phase facts."""
import ast
import inspect
import json
import os
import sqlite3
from threading import Event, Thread
import textwrap
import time
import uuid

import pytest

from .discovery import plan_sources
from .runtime import SQLiteRecorder
from .scope import use_request_recorder
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


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    config = session.config
    state = getattr(config, "_aitest_log_session", None)
    if state is None or config.option.collectonly:
        return
    sources = {}
    declared = []
    for item in session.items:
        if not isinstance(item, pytest.Function):
            continue
        try:
            source = inspect.getsource(item.function)
        except (OSError, TypeError):
            continue
        tree = ast.parse(textwrap.dedent(source))
        for key, cleanup in plan_sources(tree).items():
            sources[key] = sources.get(key, False) or cleanup
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "__aitest_log_step":
                step = next((kw.value for kw in node.keywords if kw.arg == "request_step"), None)
                if isinstance(step, ast.Constant) and isinstance(step.value, str):
                    declared.append((state["unit"], item.nodeid, step.value))
    if not sources:
        return
    store = config._aitest_log_store
    key = uuid.uuid4().hex
    with store.write() as db:
        db.executemany("INSERT OR IGNORE INTO declared_step VALUES(?,?,?)", declared)
        db.execute("INSERT INTO preflight(id,unit,sources) VALUES(?,?,?)", (key, state["unit"], json.dumps(sources)))
    deadline = time.monotonic() + state["preflight_timeout"]
    while time.monotonic() < deadline:
        result = store.read("SELECT state,reason FROM preflight WHERE id=?", (key,))[0]
        if result["state"] == "ok":
            return
        if result["state"] == "error":
            raise pytest.UsageError(result["reason"])
        if store.run()["epoch"] != state["epoch"]:
            raise pytest.UsageError("log assertion run owner changed")
        time.sleep(.05)
    raise pytest.UsageError("log platform preflight timed out")


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
