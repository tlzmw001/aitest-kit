from __future__ import annotations

import json

import httpx

from aitest_kit.helpers.capture import (
    capture_env,
    capture_file_for_run,
    capture_io,
    load_capture_settings,
)
from aitest_kit.runtime_context import current_case_id, reset_case_context, set_case_context


def test_capture_io_is_noop_when_disabled(tmp_path, monkeypatch):
    capture_file = tmp_path / "capture.jsonl"
    monkeypatch.delenv("AITEST_CAPTURE", raising=False)
    monkeypatch.delenv("AITEST_CAPTURE_FILE", raising=False)

    capture_io("TC-DEMO-001", request={"user_id": "u1"})

    assert not capture_file.exists()


def test_capture_io_writes_jsonl_when_enabled(tmp_path, monkeypatch):
    capture_file = tmp_path / "capture.jsonl"
    monkeypatch.setenv("AITEST_CAPTURE", "1")
    monkeypatch.setenv("AITEST_CAPTURE_FILE", str(capture_file))

    capture_io(
        "TC-DEMO-001",
        label="grpc Demo/Call",
        protocol="grpc",
        request={"user_id": "u1"},
        response={"code": 0},
        metadata={"failure_reason": "manual"},
    )

    records = [json.loads(line) for line in capture_file.read_text(encoding="utf-8").splitlines()]
    assert records == [
        {
            "timestamp": records[0]["timestamp"],
            "case_id": "TC-DEMO-001",
            "label": "grpc Demo/Call",
            "protocol": "grpc",
            "request": {"user_id": "u1"},
            "response": {"code": 0},
            "metadata": {"failure_reason": "manual"},
        }
    ]


def test_runtime_case_context_sets_and_resets_case_id():
    assert current_case_id() is None

    token = set_case_context("TC-DEMO-CTX", {"title": "demo"})
    try:
        assert current_case_id() == "TC-DEMO-CTX"
    finally:
        reset_case_context(token)

    assert current_case_id() is None


def test_capture_io_uses_runtime_case_context(tmp_path, monkeypatch):
    capture_file = tmp_path / "capture.jsonl"
    monkeypatch.setenv("AITEST_CAPTURE", "1")
    monkeypatch.setenv("AITEST_CAPTURE_FILE", str(capture_file))

    token = set_case_context("TC-DEMO-CTX", {"title": "demo"})
    try:
        capture_io(label="ctx capture", request={"x": 1})
    finally:
        reset_case_context(token)

    record = json.loads(capture_file.read_text(encoding="utf-8").strip())
    assert record["case_id"] == "TC-DEMO-CTX"
    assert record["label"] == "ctx capture"
    assert record["request"] == {"x": 1}


def test_capture_io_explicit_case_id_wins_over_runtime_context(tmp_path, monkeypatch):
    capture_file = tmp_path / "capture.jsonl"
    monkeypatch.setenv("AITEST_CAPTURE", "1")
    monkeypatch.setenv("AITEST_CAPTURE_FILE", str(capture_file))

    token = set_case_context("TC-DEMO-CTX")
    try:
        capture_io("TC-EXPLICIT-001", label="explicit")
    finally:
        reset_case_context(token)

    record = json.loads(capture_file.read_text(encoding="utf-8").strip())
    assert record["case_id"] == "TC-EXPLICIT-001"


def test_capture_io_writes_nothing_when_enabled_without_case_identity(tmp_path, monkeypatch):
    capture_file = tmp_path / "capture.jsonl"
    monkeypatch.setenv("AITEST_CAPTURE", "1")
    monkeypatch.setenv("AITEST_CAPTURE_FILE", str(capture_file))

    capture_io(label="missing identity", request={"x": 1})

    assert not capture_file.exists()


def test_capture_io_serializes_http_response_exception_and_truncates(tmp_path, monkeypatch):
    capture_file = tmp_path / "capture.jsonl"
    monkeypatch.setenv("AITEST_CAPTURE", "1")
    monkeypatch.setenv("AITEST_CAPTURE_FILE", str(capture_file))
    monkeypatch.setenv("AITEST_CAPTURE_STRING_LENGTH", "4")
    response = httpx.Response(400, json={"message": "invalid request"})

    capture_io(
        "TC-DEMO-002",
        protocol="http",
        request={"body": "abcdefgh"},
        response=response,
        exception=RuntimeError("request failed"),
    )

    record = json.loads(capture_file.read_text(encoding="utf-8").strip())
    assert record["request"]["body"] == "abcd...<truncated 4 chars>"
    assert record["response"] == {
        "status_code": 400,
        "body": {"message": "inva...<truncated 11 chars>"},
    }
    assert record["exception"] == {
        "type": "RuntimeError",
        "message": "requ...<truncated 10 chars>",
    }


def test_load_capture_settings_reads_optional_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "aitest_config"
    config_dir.mkdir()
    (config_dir / "capture.yaml").write_text(
        """enabled: true
include:
  response: false
limits:
  string_length: 128
output:
  file: run_capture.jsonl
""",
        encoding="utf-8",
    )

    settings = load_capture_settings()

    assert settings.enabled is True
    assert settings.include_request is True
    assert settings.include_response is False
    assert settings.include_exception is True
    assert settings.include_metadata is True
    assert settings.string_length == 128
    assert settings.output_file == "run_capture.jsonl"
    assert capture_file_for_run(tmp_path / "run", settings) == tmp_path / "run" / "run_capture.jsonl"
    assert capture_env(settings, tmp_path / "run" / "run_capture.jsonl")["AITEST_CAPTURE"] == "1"
