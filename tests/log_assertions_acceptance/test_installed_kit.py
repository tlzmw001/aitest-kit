"""Run template and loopback acceptance against the installed candidate."""
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path

import pytest

if not os.environ.get("AITEST_ACCEPTANCE_PYTHON"):
    pytest.skip("Use scripts/verify_log_assertions_wheel.py to provision the candidate", allow_module_level=True)

source = Path(__file__).parents[1] / "log_assertions" / "test_run_integration.py"
spec = spec_from_file_location("aitest_log_acceptance_fixture", source)
fixture_module = module_from_spec(spec)
spec.loader.exec_module(fixture_module)
service = fixture_module.service
test_installed_log_assertions = fixture_module.test_real_fixture_run_and_resume_without_replaying_requests

test_grouped_cli_dispatch_and_case_cleanup = fixture_module.test_grouped_cli_dispatch_and_case_cleanup

test_packaged_multiple_requests_and_pages = fixture_module.test_packaged_multiple_requests_and_pages


def test_legacy_workspace_upgrade(tmp_path):
    import hashlib
    import json
    import shutil
    import subprocess

    baseline = os.environ.get("AITEST_ACCEPTANCE_BASELINE_PYTHON")
    if not baseline or os.environ.get("AITEST_ACCEPTANCE_MODE") != "basic":
        pytest.skip("legacy workspace is tested in the basic installation with a baseline wheel")
    candidate = os.environ["AITEST_ACCEPTANCE_PYTHON"]
    suite = fixture_module.SUITE

    def cli(python, *args):
        result = subprocess.run([python, "-I", "-m", "aitest_kit.cli", *args], cwd=tmp_path,
                                check=False, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    cli(baseline, "init", "--target", str(tmp_path))
    sample = tmp_path / "candidate-sample"
    cli(candidate, "init", "--target", str(sample))
    shutil.copytree(sample / "examples/log_assertions/test_workspace", tmp_path / "test_workspace", dirs_exist_ok=True)
    profile = tmp_path / suite.replace("suite.yaml", "profile_log_assertions_suite.md")
    profile.write_text(profile.read_text().split("    log_assertions:")[0] + "```\n")
    module = tmp_path / "test_workspace/targets/demo/modules/log_demo"
    module_spec = module / "module.yaml"
    module_spec.write_text(module_spec.read_text().replace("log_capture:\n  source_id: demo\n  sources:\n    perf: {source_id: demo-perf}\n", ""))
    (module / "harness.py").write_text("class LogDemoHarness:\n    def query(self):\n        return {'code': 200}\n")
    (module / "fixture.py").write_text("import pytest\nfrom .harness import LogDemoHarness\n\n"
                                      "@pytest.fixture\ndef setup_log_demo() -> LogDemoHarness:\n    return LogDemoHarness()\n")
    cli(baseline, "codegen", "--suite-file", suite)
    cli(baseline, "run", "--suite-file", suite)
    old, = tmp_path.glob("test_workspace/reports/**/runs/*/result.json")
    old_id = json.loads(old.read_text())["run_id"]
    old_hash = hashlib.sha256(old.read_bytes()).hexdigest()
    schema = tmp_path / "aitest_config/schemas/codegen_profile.schema.json"
    schema_data = json.loads(schema.read_text())
    schema_data["title"] = "User-customized schema"
    schema.write_text(json.dumps(schema_data))
    schema_hash = hashlib.sha256(schema.read_bytes()).hexdigest()
    harness_hash = hashlib.sha256((module / "harness.py").read_bytes()).hexdigest()
    cli(candidate, "upgrade", "--check")
    cli(candidate, "upgrade", "--apply")
    assert hashlib.sha256(schema.read_bytes()).hexdigest() == schema_hash
    assert hashlib.sha256((module / "harness.py").read_bytes()).hexdigest() == harness_hash
    cli(candidate, "codegen", "--suite-file", suite, "--check")
    cli(candidate, "report", "--suite-file", suite, old_id)
    assert hashlib.sha256(old.read_bytes()).hexdigest() == old_hash
    cli(candidate, "run", "--suite-file", suite)
    assert not (tmp_path / ".aitest/runs").exists()


def test_070_wheel_report_and_run_migration(tmp_path, service, monkeypatch):
    import json
    import shutil
    import sqlite3

    baseline = os.environ.get("AITEST_ACCEPTANCE_BASELINE_070_PYTHON")
    if not baseline or os.environ.get("AITEST_ACCEPTANCE_MODE") != "basic":
        pytest.skip("0.7.0 migration uses the baseline wheel and basic candidate")
    candidate = os.environ["AITEST_ACCEPTANCE_PYTHON"]
    url, state = service
    env = {**os.environ, "AITEST_LOG_BASE_URL": url, "AITEST_LOG_TOKEN": "fixture-only",
           "AITEST_LOG_DEMO_URL": f"{url}/business"}
    suite = fixture_module.SUITE.replace("/log_assertions/", "/log_multi_request/")

    def cli(python, *args):
        env["AITEST_ACCEPTANCE_PYTHON"] = python
        result = fixture_module.invoke(tmp_path, env, *args)
        assert result.returncode == 0, result.stdout + result.stderr

    monkeypatch.setenv("AITEST_ACCEPTANCE_PYTHON", baseline)
    cli(baseline, "init", "--target", str(tmp_path))
    shutil.copytree(tmp_path / "examples/log_assertions/test_workspace", tmp_path / "test_workspace", dirs_exist_ok=True)
    state["pagination"] = True
    cli(baseline, "codegen", "--suite-file", suite)
    cli(baseline, "run", "--suite-file", suite)
    report, = tmp_path.glob("test_workspace/reports/**/latest/result.json")
    original = report.read_bytes()
    run_id = json.loads(original)["run_id"]
    db_path = tmp_path / ".aitest/runs" / run_id / "log-assertions.sqlite3"

    monkeypatch.setenv("AITEST_ACCEPTANCE_PYTHON", candidate)
    cli(candidate, "codegen", "--suite-file", suite, "--check")
    cli(candidate, "report", "--suite-file", suite, run_id)
    assert report.read_bytes() == original
    with sqlite3.connect(db_path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (1,)
        request, deadline = db.execute("SELECT id,deadline FROM request ORDER BY id LIMIT 1").fetchone()
        db.execute("UPDATE run SET state='DRAINING',finished=NULL,exit_code=NULL,published=0")
        db.execute("DELETE FROM result WHERE request=?", (request,))
        db.execute("UPDATE request SET state='RUNNING',claim='abandoned' WHERE id=?", (request,))
    cli(candidate, "run", "--resume", run_id)
    with sqlite3.connect(db_path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (2,)
        assert db.execute("SELECT state,deadline FROM request WHERE id=?", (request,)).fetchone() == ("PASSED", deadline)
    assert state["calls"] == ["business", "business"]
