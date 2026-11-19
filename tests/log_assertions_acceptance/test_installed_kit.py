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
        result = subprocess.run([python, "-I", "-X", "utf8", "-m", "aitest_kit.cli", *args], cwd=tmp_path,
                                check=False, encoding="utf-8", capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    cli(baseline, "init", "--target", str(tmp_path))
    sample = tmp_path / "candidate-sample"
    cli(candidate, "init", "--target", str(sample))
    shutil.copytree(sample / "examples/log_assertions/test_workspace", tmp_path / "test_workspace", dirs_exist_ok=True)
    profile = tmp_path / suite.replace("suite.yaml", "profile_log_assertions_suite.md")
    profile.write_text(profile.read_text(encoding="utf-8").split("    log_assertions:")[0] + "```\n", encoding="utf-8")
    module = tmp_path / "test_workspace/targets/demo/modules/log_demo"
    module_spec = module / "module.yaml"
    module_spec.write_text(module_spec.read_text(encoding="utf-8").replace("log_capture:\n  source_id: demo\n", ""))
    (module / "harness.py").write_text("class LogDemoHarness:\n    def query(self):\n        return {'code': 200}\n")
    (module / "fixture.py").write_text("import pytest\nfrom .harness import LogDemoHarness\n\n"
                                      "@pytest.fixture\ndef setup_log_demo() -> LogDemoHarness:\n    return LogDemoHarness()\n")
    cli(baseline, "codegen", "--suite-file", suite)
    cli(baseline, "run", "--suite-file", suite)
    old, = tmp_path.glob("test_workspace/reports/**/runs/*/result.json")
    old_id = json.loads(old.read_text(encoding="utf-8"))["run_id"]
    old_hash = hashlib.sha256(old.read_bytes()).hexdigest()
    schema = tmp_path / "aitest_config/schemas/codegen_profile.schema.json"
    schema_data = json.loads(schema.read_text(encoding="utf-8"))
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
