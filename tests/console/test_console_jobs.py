from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from aitest_kit.console.jobs import (
    JobManager,
    Selector,
    _kill_process_group,
    _popen_group_options,
    _terminate_process_group,
    build_aitest_command,
)


def test_build_command_uses_structured_suite_and_case_selector(console_workspace: Path):
    command = build_aitest_command(
        root=console_workspace,
        operation="run",
        selector=Selector(
            type="case",
            suite_file="test_workspace/suites/demo/orders_smoke/suite.yaml",
            case_ids=["TC-ORD-001"],
        ),
    )

    assert command == [
        sys.executable,
        "-m",
        "aitest_kit.cli",
        "run",
        "--suite-file",
        str(console_workspace / "test_workspace/suites/demo/orders_smoke/suite.yaml"),
        "--case-id",
        "TC-ORD-001",
    ]


@pytest.mark.parametrize(
    ("operation", "suffix"),
    [
        ("validate_profile", ["--validate-profile"]),
        ("codegen", []),
        ("freshness", ["--check"]),
    ],
)
def test_build_codegen_commands(console_workspace: Path, operation: str, suffix: list[str]):
    command = build_aitest_command(
        root=console_workspace,
        operation=operation,
        selector=Selector(type="suite", suite_file="test_workspace/suites/demo/orders_smoke/suite.yaml"),
    )

    assert command[-len(suffix):] == suffix if suffix else command[-1].endswith("suite.yaml")
    assert "--skip-codegen-check" not in command


def test_build_command_rejects_path_outside_workspace(console_workspace: Path, tmp_path: Path):
    outside = tmp_path / "outside.yaml"
    outside.write_text("suite: outside\n", encoding="utf-8")
    with pytest.raises(ValueError, match="workspace"):
        build_aitest_command(
            root=console_workspace,
            operation="run",
            selector=Selector(type="suite", suite_file=str(outside)),
        )


def test_build_module_command_uses_configured_profile_directory(console_workspace: Path):
    config = console_workspace / "aitest_config" / "aitest.yaml"
    config.write_text(
        """workspace:
  paths:
    profile_dir: custom/targets
""",
        encoding="utf-8",
    )
    custom = console_workspace / "custom" / "targets"
    custom.parent.mkdir()
    (console_workspace / "test_workspace" / "targets").rename(custom)
    module_dir = console_workspace / "custom" / "modules" / "orders"
    module_dir.parent.mkdir()
    (custom / "demo" / "modules" / "orders").rename(module_dir)
    (custom / "demo" / "target.yaml").write_text(
        """target: demo
defaults:
  module_dir: custom/modules
""",
        encoding="utf-8",
    )

    command = build_aitest_command(
        root=console_workspace,
        operation="run",
        selector=Selector(type="module", target="demo", module="orders"),
    )

    assert command[-4:] == ["--target", "demo", "--module", "orders"]


def test_job_manager_collects_output_and_enforces_one_active_job(console_workspace: Path):
    manager = JobManager(console_workspace, max_output_chars=4000)
    first = manager.start_argv(
        operation="test",
        command=[sys.executable, "-c", "import time; print('started', flush=True); time.sleep(0.3); print('done')"],
        command_summary="test command",
    )

    with pytest.raises(RuntimeError, match="already running"):
        manager.start_argv(
            operation="test",
            command=[sys.executable, "-c", "print('second')"],
            command_summary="second command",
        )

    deadline = time.time() + 2
    while "started" not in manager.get(first.id).output and time.time() < deadline:
        time.sleep(0.02)
    assert manager.list()[0]["status"] == "running"

    deadline = time.time() + 3
    while manager.get(first.id).status in {"queued", "running"} and time.time() < deadline:
        time.sleep(0.02)

    job = manager.get(first.id)
    assert job.status == "succeeded"
    assert "started" in job.output
    assert "done" in job.output
    assert job.exit_code == 0


def test_job_manager_cancels_child_process(console_workspace: Path):
    manager = JobManager(console_workspace, cancel_timeout=0.2)
    job = manager.start_argv(
        operation="test",
        command=[sys.executable, "-c", "import time; print('ready', flush=True); time.sleep(30)"],
        command_summary="long command",
    )
    deadline = time.time() + 2
    while "ready" not in manager.get(job.id).output and time.time() < deadline:
        time.sleep(0.02)

    manager.cancel(job.id)
    deadline = time.time() + 2
    while manager.get(job.id).status in {"queued", "running"} and time.time() < deadline:
        time.sleep(0.02)

    assert manager.get(job.id).status == "cancelled"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal behavior")
def test_job_manager_escalates_when_child_ignores_terminate(console_workspace: Path):
    manager = JobManager(console_workspace, cancel_timeout=0.15)
    job = manager.start_argv(
        operation="test",
        command=[
            sys.executable,
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); time.sleep(30)",
        ],
        command_summary="stubborn command",
    )
    deadline = time.time() + 2
    while "ready" not in manager.get(job.id).output and time.time() < deadline:
        time.sleep(0.02)

    manager.cancel(job.id)
    deadline = time.time() + 2
    while manager.get(job.id).status in {"queued", "running"} and time.time() < deadline:
        time.sleep(0.02)

    assert manager.get(job.id).status == "cancelled"


def test_windows_process_group_helpers_do_not_use_posix_apis(monkeypatch):
    class FakeProcess:
        pid = 42

        def __init__(self):
            self.signals = []
            self.terminated = False
            self.killed = False

        def send_signal(self, value):
            self.signals.append(value)

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    process = FakeProcess()
    monkeypatch.setattr("aitest_kit.console.jobs._IS_WINDOWS", True)
    monkeypatch.setattr("aitest_kit.console.jobs.signal.CTRL_BREAK_EVENT", 123, raising=False)

    assert "creationflags" in _popen_group_options()
    _terminate_process_group(process)
    _kill_process_group(process)

    assert process.signals == [123]
    assert process.killed is True
