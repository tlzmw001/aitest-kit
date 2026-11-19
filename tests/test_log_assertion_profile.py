import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

import pytest
from click.testing import CliRunner

from aitest_kit.cli import main
from aitest_kit.log_assertions import LogBindingError, bind_log_request, log_capture_requested
from aitest_kit.log_assertions.scope import use_request_recorder


@pytest.fixture
def example(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", "--target", str(tmp_path)])
    assert result.exit_code == 0, result.output
    shutil.copytree(
        tmp_path / "examples/log_assertions/test_workspace", tmp_path / "test_workspace",
        dirs_exist_ok=True,
    )
    suite = tmp_path / "test_workspace/suites/demo/log_assertions/suite.yaml"
    args = ["codegen", "--workspace", str(tmp_path), "--suite-file", str(suite)]
    return runner, args, suite.with_name("profile_log_assertions_suite.md"), tmp_path


def test_example_generates_collects_and_tracks_freshness(example, monkeypatch):
    runner, args, profile, workspace = example
    for flags in [
        ["--validate-profile"], ["--dump-ir"], ["--explain", "TC-DEMO-001"], [], ["--check"],
    ]:
        result = runner.invoke(main, args + flags)
        assert result.exit_code == 0, result.output
        if flags == ["--dump-ir"]:
            assert "rule_sha256" in result.output
        if flags[:1] == ["--explain"]:
            assert "deferred log assertions for reply" in result.output
    generated = workspace / "test_workspace/generated"
    files = list(generated.rglob("test_*.py"))
    assert len(files) == 1
    assert "expected_inputs=__tc_vars__" in files[0].read_text()
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", str(generated), "--collect-only", "-q"],
        cwd=workspace, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    monkeypatch.syspath_prepend(str(workspace))
    module = runpy.run_path(str(files[0]))
    test_case = next(item for name, item in module.items() if name.startswith("Test"))
    body = test_case().test_tc_demo_001

    calls = []

    class Harness:
        def query(self):
            assert log_capture_requested()
            calls.append("request")
            assert bind_log_request("demo", "example-id")
            return {"code": 200, "score": 0.7}

    class Recorder:
        def register(self, step, source, rules, inputs):
            assert (step, source, inputs) == ("reply", "demo", [{"keyword": "命中", "minimum": 0.5}])
            assert rules[0]["executor_version"] == 1
            calls.append("register")
            return step

        def bind(self, step, value):
            assert (step, value) == ("reply", "example-id")
            calls.append("bind")

        def freeze(self, step, inputs):
            assert step == "reply" and inputs[0]["response_score"] == 0.7
            calls.append("freeze")

    with pytest.raises(LogBindingError, match="coordinator"):
        body(Harness())
    assert calls == []
    with use_request_recorder(Recorder()):
        body(Harness())
    assert calls == ["register", "request", "bind", "freeze"]
    profile.write_text(profile.read_text().replace('len(events) == 1', 'len(events) == 2'))
    assert runner.invoke(main, args + ["--check"]).exit_code != 0


@pytest.mark.parametrize("old,new,code", [
    ("request_step: reply", "request_step: other", "E533"),
    ("len(events) == 1", "len(reply) == 1", "E534"),
    ("from_var: minimum_score", "from_var: missing", "E535"),
    ("from_response: /score", "from_response: score", "E535"),
])
def test_invalid_rules_fail_gate_with_location(example, old, new, code):
    runner, args, profile, _ = example
    profile.write_text(profile.read_text().replace(old, new))
    result = runner.invoke(main, args + ["--validate-profile"])
    assert result.exit_code != 0
    assert code in result.output and "case_flows.TC-DEMO-001.log_assertions[0]" in result.output


def test_expected_literals_are_not_scanned_as_request_refs(example):
    runner, args, profile, _ = example
    profile.write_text(profile.read_text().replace(
        'keyword: "命中"', 'keyword: {literal: {request_ref: business_value}}\n          token_count: 50',
    ))
    result = runner.invoke(main, args + ["--validate-profile"])
    assert result.exit_code == 0, result.output
