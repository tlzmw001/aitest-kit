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


def _log_aliases(workspace):
    module = workspace / "test_workspace/targets/demo/modules/log_demo/module.yaml"
    module.write_text(module.read_text().replace(
        "  source_id: demo\n  sources:\n    perf: {source_id: demo-perf}\n",
        "  source_id: demo\n  sources:\n"
        "    performance: {source_id: demo-perf}\n"
        "    performance_copy: {source_id: demo-perf}\n"
        "    lake: {source_id: demo-lake}\n",
    ))
    return module


def _disable_grouped_recorder(workspace):
    (workspace / "conftest.py").write_text(
        "from aitest_kit.log_assertions.runtime import SQLiteRecorder\n"
        "SQLiteRecorder.supports_multiple_log_sources = False\n"
    )


def test_grouped_log_sources_compile_discover_and_guard(example, monkeypatch, capfd):
    from aitest_kit.log_assertions import scope
    from aitest_kit.log_assertions.discovery import plan_sources, planned_steps
    import ast
    import sqlite3

    runner, args, profile, workspace = example
    assert runner.invoke(main, args).exit_code == 0
    generated, = (workspace / "test_workspace/generated").rglob("test_*.py")
    legacy = generated.read_bytes()
    module_config = _log_aliases(workspace)
    assert runner.invoke(main, args + ["--check"]).exit_code == 0
    assert generated.read_bytes() == legacy

    profile.write_text(profile.read_text().replace(
        "    steps:\n", "    steps:\n      - call: harness.prepare\n",
    ).replace(
        "\n```\n",
        "\n      - request_step: reply\n        source: performance\n"
        "        checks: ['assert len(events) == 2']\n"
        "      - request_step: reply\n"
        "        checks: ['assert len(events) == 1']\n```\n",
    ))
    for flags in (["--validate-profile"], ["--dump-ir"], ["--explain", "TC-DEMO-001"], [], ["--check"]):
        result = runner.invoke(main, args + flags)
        assert result.exit_code == 0, result.output
        if flags == ["--dump-ir"]:
            assert '"source_id": "demo-perf"' in result.output
        if flags[:1] == ["--explain"]:
            assert "group[1] source='demo-perf' actions=read" in result.output
            assert "group[2] source='demo' actions=read, cleanup" in result.output
    tree = ast.parse(generated.read_text())
    assert plan_sources(tree) == {"demo": True, "demo-perf": False}
    plans, = planned_steps(generated).values()
    assert [(plan["source"], [rule["group_index"] for rule in plan["rules"]]) for plan in plans] == [
        ("demo", [0, 2]), ("demo-perf", [1]),
    ]

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(filter(None, [str(root), os.getenv("PYTHONPATH")])))
    monkeypatch.setenv("AITEST_LOG_DEMO_URL", "http://localhost:1/business")
    _disable_grouped_recorder(workspace)
    result = runner.invoke(main, ["run", *args[1:]])
    assert result.exit_code == 4
    assert "current executor does not support grouped log sources" in capfd.readouterr().err
    database, = (workspace / ".aitest/runs").rglob("log-assertions.sqlite3")
    with sqlite3.connect(database) as db:
        for table in ("request", "cleanup"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)

    monkeypatch.syspath_prepend(str(workspace))
    namespace = runpy.run_path(str(generated))
    case_class = next(value for name, value in namespace.items() if name.startswith("Test"))
    body = case_class().test_tc_demo_001
    calls = []

    class Harness:
        def prepare(self):
            calls.append("prepare")

        def query(self):
            calls.append("request")
            assert bind_log_request("demo", "event")
            return {"code": 200, "score": 0.7}

    class Recorder:
        supports_multiple_log_sources = True

        def register(self, step, source, rules, inputs):
            calls.append("register")
            assert (step, source) == ("reply", "demo")
            assert [(group["group_index"], group["source_id"]) for group in rules] == [
                (0, "demo"), (1, "demo-perf"), (2, "demo"),
            ]
            return object()

        def bind(self, handle, value):
            calls.append("bind")
            assert value == "event"

        def freeze(self, handle, inputs):
            calls.append("freeze")
            assert inputs == [{"keyword": "命中", "minimum": 0.5, "response_score": 0.7}, {}, {}]

    with use_request_recorder(Recorder()):
        with monkeypatch.context() as old_runtime:
            old_runtime.delattr(scope, "supports_multiple_log_sources")
            with pytest.raises(LogBindingError, match="does not support grouped log sources"):
                body(Harness())
        assert calls == []
        body(Harness())
    assert calls == ["prepare", "register", "request", "bind", "freeze"]

    module_config.write_text(module_config.read_text().replace("source_id: demo-perf", "source_id: changed"))
    assert runner.invoke(main, args + ["--check"]).exit_code != 0


@pytest.mark.parametrize("alias,cleanup,expected", [
    ("missing", "retain", "unknown log source alias"),
    ("performance_copy", "retain", "conflicting policy for source 'demo-perf'"),
    ("lake", "retain", None),
])
def test_grouped_source_validation_uses_real_source_identity(example, alias, cleanup, expected):
    runner, args, profile, workspace = example
    _log_aliases(workspace)
    content = profile.read_text().replace("      - request_step: reply\n",
                                          "      - request_step: reply\n        source: performance\n")
    profile.write_text(content.replace("\n```\n", f"\n      - request_step: reply\n        source: {alias}\n"
                                      f"        cleanup: {cleanup}\n        checks: ['assert len(events) > 0']\n```\n"))
    result = runner.invoke(main, args + ["--validate-profile"])
    if expected:
        assert result.exit_code != 0
        assert "E536" in result.output and expected in result.output
        assert "case_flows.TC-DEMO-001.log_assertions[1]" in result.output
    else:
        assert result.exit_code == 0, result.output


def test_only_selected_log_source_requires_permissions():
    import ast
    from aitest_kit.log_assertions.discovery import plan_sources

    tree = ast.parse("__aitest_log_step(request_step='reply', source_id='demo', "
                     "rules=[{'source_id': 'demo-perf', 'cleanup': 'retain'}])")
    assert plan_sources(tree) == {"demo-perf": False}

    broken = ast.parse("__aitest_log_step(request_step='reply', source_id='demo', "
                       "rules=[{'source_id': 'demo-perf'}, {'cleanup': 'retain'}])")
    with pytest.raises(ValueError, match="invalid generated log step metadata"):
        plan_sources(broken)


def test_legacy_profile_can_use_grouped_guard_local_name(example):
    runner, args, profile, _ = example
    profile.write_text(profile.read_text().replace("reply", "__aitest_log_runtime"))
    result = runner.invoke(main, args + ["--validate-profile"])
    assert result.exit_code == 0, result.output


def test_grouped_guard_can_use_getattr_as_step_name(example, monkeypatch):
    runner, args, profile, workspace = example
    _log_aliases(workspace)
    profile.write_text(profile.read_text().replace("reply", "getattr").replace(
        "request_step: getattr", "request_step: getattr\n        source: performance",
    ))
    result = runner.invoke(main, args)
    assert result.exit_code == 0, result.output
    generated, = (workspace / "test_workspace/generated").rglob("test_*.py")
    monkeypatch.syspath_prepend(str(workspace))
    namespace = runpy.run_path(str(generated))
    case_class = next(value for name, value in namespace.items() if name.startswith("Test"))
    with pytest.raises(LogBindingError, match="does not support grouped log sources"):
        case_class().test_tc_demo_001(object())


@pytest.mark.parametrize("workers", [1, 2])
def test_grouped_preflight_failure_is_visible_in_task_units(example, workers, capfd):
    import json
    if workers == 2:
        pytest.importorskip("xdist")
    runner, args, profile, workspace = example
    _log_aliases(workspace)
    profile.write_text(profile.read_text().replace(
        "request_step: reply", "request_step: reply\n        source: performance",
    ))
    assert runner.invoke(main, args).exit_code == 0
    task = workspace / "test_workspace/tasks/grouped.yaml"
    task.parent.mkdir(exist_ok=True)
    task.write_text("schema_version: 1\nname: grouped\nunits:\n"
                    "  - suite_file: ../suites/demo/log_assertions/suite.yaml\n")
    env = {"PYTHONPATH": os.pathsep.join(filter(None, [
        str(Path(__file__).resolve().parents[1]), os.getenv("PYTHONPATH"),
    ]))}
    _disable_grouped_recorder(workspace)
    outcome = runner.invoke(main, ["run", "--workspace", str(workspace), "--task-file", str(task),
                                   "--case-concurrency", str(workers)], env=env)
    capfd.readouterr()
    assert outcome.exit_code == 4
    root, = workspace.glob("test_workspace/reports/tasks/grouped/latest/result.json")
    child, = root.parent.glob("units/*/result.json")
    for report in (root, child):
        payload = json.loads(report.read_text())
        assert payload["status"] == "BLOCKED_RUN"
        assert payload["log_validation"]["exit_code"] != 0
        assert "demo-perf" in payload["log_validation"]["issues"][0]["message"]
