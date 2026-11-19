"""Exercise installed-style CLI invocations and actual pytest work through loopback."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from threading import Event, Lock, Thread
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUITE = "test_workspace/suites/demo/log_assertions/suite.yaml"


@pytest.fixture
def service():
    calls = []
    second_call = Event()
    first_polled = Event()
    business_ready = Event()
    logs_ready = Event()
    next_unit_started = Event()
    guard = Lock()
    state = {"calls": calls, "case_concurrency": 1, "log_concurrency": 1,
             "business_active": 0, "business_peak": 0, "log_active": 0, "log_peak": 0, "cleanup": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def reply(self, payload, status=200):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path == "/business":
                assert self.headers["X-Demo-Capture"] == "true"
                with guard:
                    calls.append("business")
                    number = len(calls)
                    state["business_active"] += 1
                    state["business_peak"] = max(state["business_peak"], state["business_active"])
                    if state["business_active"] >= state["case_concurrency"]:
                        business_ready.set()
                assert business_ready.wait(7)
                if number == 5:
                    next_unit_started.set()
                if number == 2:
                    if state["case_concurrency"] == 1:
                        assert first_polled.wait(7)
                    second_call.set()
                with guard:
                    state["business_active"] -= 1
                self.reply({"code": 200, "score": .8, "trace_id": f"demo-{number}"})
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/v1/cleanup":
                state["cleanup"].append((body["reqIds"], self.headers["Idempotency-Key"]))
                if state.get("reject_cleanup"):
                    self.send_error(403)
                else:
                    payload = dict(source_id="demo", job_id="cleanup-" + body["reqIds"][0],
                                   state="ACCEPTED", accepted_at="2026-11-19T00:00:00Z", target_count=1)
                    self.reply(payload, status=202)
                return
            if "demo-1" in body["reqIds"] and not second_call.is_set():
                first_polled.set()
            self.reply({"items": [
                {"reqId": req, "result": "FOUND", "request": self.request_meta(req)}
                for req in body["reqIds"]
            ]})

        def request_meta(self, req):
            return {"source_id": "demo", "reqId": req, "version": state.get("versions", {}).get(req, 1), "availability": "AVAILABLE",
                    "capture_state": "COMPLETE" if second_call.is_set() else "COLLECTING",
                    "event_count": 2 if state.get("pagination") else 1}

        def do_GET(self):
            if self.path == "/v1/sources":
                self.reply({"items": [{"source_id": "demo", "enabled": True, "completion_supported": True,
                                       "actions": ["read", "cleanup"]}]})
            elif self.path == "/v1/ui-settings":
                self.reply({"batch_reqids_max": 10, "page_size_max": 10})
            else:
                request = self.path.split("/")[3]
                with guard:
                    state["log_active"] += 1
                    state["log_peak"] = max(state["log_peak"], state["log_active"])
                    if state["log_active"] >= state["log_concurrency"]:
                        logs_ready.set()
                assert logs_ready.wait(7)
                if state.get("cross_suite"):
                    assert next_unit_started.wait(7)
                with guard:
                    state["log_active"] -= 1
                if state.get("pagination"):
                    params = parse_qs(urlsplit(self.path).query)
                    version = self.request_meta(request)["version"]
                    assert params["expected_version"] == [str(version)]
                    index = 2 if params.get("cursor") == ["next"] else 1
                    state.setdefault("pages", []).append((request, version, index))
                    if request == "demo-1" and version == 1 and index == 2:
                        state["versions"] = {"demo-1": 2}
                        self.reply({"error": {"code": "VERSION_CONFLICT"}}, status=409)
                        return
                    self.reply({"request": self.request_meta(request), "upper_offset": "2",
                                "next_cursor": "next" if index == 1 else None, "items": [
                        {"event_id": f"{request}-{index}", "offset": str(index), "partition": 0,
                         "eventType": "SCENE_HIT", "data": {"score": .7 if request == "demo-1" and version == 1 else .8, "message": "命中",
                          "counter": 9007199254740993, "disabled": False, "detail": None}},
                    ]})
                    return
                self.reply({"request": self.request_meta(request), "upper_offset": "1", "next_cursor": None,
                            "items": [{"event_id": request, "offset": "1", "partition": 0, "eventType": "SCENE_HIT",
                                       "data": {"score": .7 if state.get("bad_log") == request else .8, "message": "命中"}}]})


    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", state
        finally:
            server.shutdown()
            thread.join()


def invoke(workspace, env, *args):
    installed = os.environ.get("AITEST_ACCEPTANCE_PYTHON")
    python = [installed, "-I", "-X", "utf8"] if installed else [sys.executable]
    return subprocess.run([*python, "-m", "aitest_kit.cli", *args],
                          cwd=workspace, env=env, encoding="utf-8", capture_output=True, timeout=30)


@pytest.mark.parametrize("case_slots,log_slots,cases,task,scenario", [
    (1, 1, 2, False, "ok"), (4, 2, 6, False, "ok"), (1, 1, 2, True, "ok"),
    (1, 1, 2, True, "assertion"), (1, 1, 2, False, "cleanup_403"),
    (4, 2, 8, True, "ok"),
])
def test_real_fixture_run_and_resume_without_replaying_requests(
    tmp_path, service, case_slots, log_slots, cases, task, scenario,
):
    mode = os.environ.get("AITEST_ACCEPTANCE_MODE")
    if (mode == "basic" and case_slots > 1) or (mode == "parallel" and case_slots == 1):
        pytest.skip("covered in the other wheel installation")
    if mode is None and case_slots > 1 and importlib.util.find_spec("xdist") is None:
        pytest.skip("optional parallel extra")

    url, state = service
    state.update(case_concurrency=case_slots, log_concurrency=log_slots, cross_suite=task and case_slots > 1,
                 bad_log="demo-1" if scenario == "assertion" else None, reject_cleanup=scenario == "cleanup_403")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")])), "AITEST_LOG_BASE_URL": url,
           "AITEST_LOG_TOKEN": "fixture-only", "AITEST_LOG_DEMO_URL": f"{url}/business"}
    assert invoke(tmp_path, env, "init", "--target", str(tmp_path)).returncode == 0
    shutil.copytree(tmp_path / "examples/log_assertions/test_workspace", tmp_path / "test_workspace", dirs_exist_ok=True)
    paths = (tmp_path / SUITE).parent
    business = paths / "business.md"
    first = business.read_text(encoding="utf-8")
    business.write_text(first + "".join(
        "\n" + first[first.index("###"):].replace("TC-DEMO-001", f"TC-DEMO-{index:03d}")
        for index in range(2, cases + 1)
    ), encoding="utf-8")
    profile = paths / "profile_log_assertions_suite.md"
    first = profile.read_text(encoding="utf-8")
    marker = chr(96) * 3
    start = first.index("  TC-DEMO-001:")
    profile.write_text(first[:first.rindex(marker)] + "".join(
        first[start:first.rindex(marker)].replace("TC-DEMO-001", f"TC-DEMO-{index:03d}")
        for index in range(2, cases + 1)
    ) + marker + "\n", encoding="utf-8")
    (tmp_path / "aitest_config/log_assertions.yaml").write_text("execution:\n  poll_interval_seconds: 0.05\n")
    if not task and case_slots == 1 and scenario == "ok":
        credentials_file = tmp_path / "isolated-log-credentials.env"
        credentials_file.write_text(
            f"AITEST_LOG_BASE_URL={env.pop('AITEST_LOG_BASE_URL')}\n"
            f"AITEST_LOG_TOKEN={env.pop('AITEST_LOG_TOKEN')}\n"
        )
        env["AITEST_ENV_FILE"] = str(credentials_file)
    if mode:
        for option in ("--validate-profile", "--dump-ir", "--explain"):
            args = ["TC-DEMO-001"] if option == "--explain" else []
            gate = invoke(tmp_path, env, "codegen", "--suite-file", SUITE, option, *args)
            assert gate.returncode == 0, gate.stdout + gate.stderr
    generated = invoke(tmp_path, env, "codegen", "--suite-file", SUITE)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    if mode:
        multi = invoke(tmp_path, env, "codegen", "--suite-file",
                       "test_workspace/suites/demo/log_multi_request/suite.yaml")
        assert multi.returncode == 0, multi.stdout + multi.stderr
        doctor = invoke(tmp_path, env, "doctor")
        assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    selector = ["--suite-file", SUITE]
    if task:
        task_path = tmp_path / "test_workspace/tasks/repeated_suite.yaml"
        groups = [range(1, cases // 2 + 1), range(cases // 2 + 1, cases + 1)]
        task_path.write_text(
            "schema_version: 1\nname: repeated_suite\nunits:\n"
            + "".join("  - suite_file: ../suites/demo/log_assertions/suite.yaml\n"
                      + "    case_ids: [" + ", ".join(f"TC-DEMO-{index:03d}" for index in group) + "]\n"
                      for group in groups)
        )
        selector = ["--task-file", str(task_path)]
    result = invoke(tmp_path, env, "run", *selector,
                    "--case-concurrency", str(case_slots), "--log-concurrency", str(log_slots))
    assert result.returncode == (0 if scenario == "ok" else 1), result.stdout + result.stderr
    final, = tmp_path.glob("test_workspace/reports/**/latest/result.json")
    report = json.loads(final.read_text(encoding="utf-8"))
    if mode:
        offline = invoke(tmp_path, env, "report", *selector)
        assert offline.returncode == 0, offline.stdout + offline.stderr
    assert report["log_validation"]["final"] and report["summary"]["pending"] == 0
    assert report["summary"]["failed"] == int(scenario == "assertion")
    assert report["summary"]["passed"] == cases - int(scenario == "assertion")
    assert len(state["cleanup"]) == report["summary"]["passed"]
    assert all(key for _, key in state["cleanup"])
    from xml.etree import ElementTree as ET
    junit = ET.parse(final.with_name("junit.xml")).getroot()
    assert junit.get("failures") == str(int(scenario == "assertion"))
    if scenario == "assertion":
        failed, = [case for case in report["cases"] if case["outcome"] == "failed"]
        assert failed["failure"]["phase"] == "log_assertion"
        assert "assert" in failed["failure"]["message"]
        assert [item[0] for item in state["cleanup"]] == [["demo-2"]]
        assert "cleanup-demo-2" in final.with_name("report.md").read_text(encoding="utf-8")
    if scenario == "cleanup_403":
        assert len(report["log_validation"]["issues"]) == 2
        assert junit.get("errors") == "2"
    if scenario != "ok":
        return
    assert f"Log checks: passed={cases}" in result.stdout
    assert state["business_peak"] == case_slots and state["log_peak"] == log_slots
    assert len(state["calls"]) == cases
    db_path, = tmp_path.glob(".aitest/runs/*/log-assertions.sqlite3")
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT DISTINCT outcome FROM phase").fetchall() == [("passed",)]
        assert db.execute("SELECT DISTINCT unit FROM attempt ORDER BY unit").fetchall() == (
            [(1,), (2,)] if task else [(0,)]
        )
        request, = db.execute("SELECT MIN(id) FROM request").fetchone()
        db.execute("UPDATE run SET state='DRAINING', finished=NULL, exit_code=NULL, published=0")
        db.execute("DELETE FROM result WHERE request=?", (request,))
        db.execute("UPDATE request SET state='RUNNING', claim='abandoned' WHERE id=?", (request,))
    resume_env = env.copy()
    resume_env.pop("AITEST_ENV_FILE", None)
    resumed = invoke(tmp_path, resume_env, "run", "--resume", db_path.parent.name)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert len(state["calls"]) == cases
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT state,COUNT(*) FROM request GROUP BY state").fetchall() == [("PASSED", cases)]


def test_packaged_multiple_requests_and_pages(tmp_path, service):
    url, state = service
    state["pagination"] = True
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")])),
           "AITEST_LOG_BASE_URL": url, "AITEST_LOG_TOKEN": "fixture-only", "AITEST_LOG_DEMO_URL": f"{url}/business"}
    assert invoke(tmp_path, env, "init", "--target", str(tmp_path)).returncode == 0
    shutil.copytree(tmp_path / "examples/log_assertions/test_workspace", tmp_path / "test_workspace", dirs_exist_ok=True)
    suite = "test_workspace/suites/demo/log_multi_request/suite.yaml"
    generated = invoke(tmp_path, env, "codegen", "--suite-file", suite)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    result = invoke(tmp_path, env, "run", "--suite-file", suite)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(state["pages"]) == [
        ("demo-1", 1, 1), ("demo-1", 1, 2), ("demo-1", 2, 1), ("demo-1", 2, 2),
        ("demo-2", 1, 1), ("demo-2", 1, 2),
    ]
    assert state["cleanup"] == []
    final, = tmp_path.glob("test_workspace/reports/**/latest/result.json")
    case, = json.loads(final.read_text(encoding="utf-8"))["cases"]
    assert [(item["request_step"], item["reqId"]) for item in case["log_validation"]["requests"]] == [
        ("first", "demo-1"), ("second", "demo-2"),
    ]

    profile = tmp_path / suite.replace("suite.yaml", "profile_log_multi_request_suite.md")
    original = profile.read_text(encoding="utf-8")
    profile.write_text(original.replace("len(events) == 2", "len(events) >= 2", 1), encoding="utf-8")
    freshness = invoke(tmp_path, env, "codegen", "--suite-file", suite, "--check")
    assert freshness.returncode != 0 and "stale" in freshness.stdout.lower()
    profile.write_text(original.replace('expected["score"]', 'reply["score"]', 1), encoding="utf-8")
    invalid = invoke(tmp_path, env, "codegen", "--suite-file", suite, "--validate-profile")
    assert invalid.returncode != 0 and "E534" in invalid.stdout and "TC-DEMO-002" in invalid.stdout
    assert len(state["calls"]) == 2
