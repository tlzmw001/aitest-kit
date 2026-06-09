"""Runtime capture helpers for generated tests and user fixtures."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


CAPTURE_CONFIG_PATH = Path("aitest_config/capture.yaml")
_UNSET = object()


@dataclass(frozen=True)
class CaptureSettings:
    enabled: bool = False
    include_request: bool = True
    include_response: bool = True
    include_exception: bool = True
    include_metadata: bool = True
    string_length: int = 4096
    output_file: str = "capture.jsonl"


def load_capture_settings(*, enabled_override: bool = False) -> CaptureSettings:
    """Load optional capture.yaml and apply the CLI enabled override."""
    data: dict[str, Any] = {}
    if CAPTURE_CONFIG_PATH.exists():
        raw = yaml.safe_load(CAPTURE_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise RuntimeError(f"{CAPTURE_CONFIG_PATH} must be a YAML mapping")
        data = raw

    include = data.get("include", {})
    if not isinstance(include, dict):
        include = {}
    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        limits = {}
    output = data.get("output", {})
    if not isinstance(output, dict):
        output = {}

    output_file = str(output.get("file") or "capture.jsonl")
    _validate_output_file(output_file)
    return CaptureSettings(
        enabled=bool(data.get("enabled", False)) or enabled_override,
        include_request=bool(include.get("request", True)),
        include_response=bool(include.get("response", True)),
        include_exception=bool(include.get("exception", True)),
        include_metadata=bool(include.get("metadata", True)),
        string_length=_positive_int(limits.get("string_length"), 4096),
        output_file=output_file,
    )


def capture_env(settings: CaptureSettings, capture_file: str | Path) -> dict[str, str]:
    """Return environment variables consumed by capture_io in pytest subprocesses."""
    if not settings.enabled:
        return {}
    return {
        "AITEST_CAPTURE": "1",
        "AITEST_CAPTURE_FILE": str(capture_file),
        "AITEST_CAPTURE_INCLUDE": json.dumps({
            "request": settings.include_request,
            "response": settings.include_response,
            "exception": settings.include_exception,
            "metadata": settings.include_metadata,
        }),
        "AITEST_CAPTURE_STRING_LENGTH": str(settings.string_length),
    }


def capture_file_for_run(
    run_dir: str | Path,
    settings: CaptureSettings,
    *,
    capture_file: str | Path | None = None,
) -> Path | None:
    """Return the capture file path for a run, or None when capture is disabled."""
    if not settings.enabled:
        return None
    if capture_file is not None:
        return Path(capture_file)
    return Path(run_dir) / settings.output_file


def capture_io(
    case_id: str,
    *,
    label: str = "",
    protocol: str = "",
    request: Any = _UNSET,
    response: Any = _UNSET,
    exception: Any = _UNSET,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one capture record when runtime capture is enabled.

    Capture does not redact. Users should pass already-safe objects when needed.
    Capture failures are intentionally ignored so debugging output cannot fail tests.
    """
    if os.environ.get("AITEST_CAPTURE") != "1":
        return
    capture_path = os.environ.get("AITEST_CAPTURE_FILE", "")
    if not capture_path:
        return

    try:
        include = _include_settings()
        limit = _positive_int(os.environ.get("AITEST_CAPTURE_STRING_LENGTH"), 4096)
        record: dict[str, Any] = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "case_id": str(case_id),
        }
        if label:
            record["label"] = str(label)
        if protocol:
            record["protocol"] = str(protocol)
        if request is not _UNSET and include.get("request", True):
            record["request"] = _to_capture_data(request, string_length=limit)
        if response is not _UNSET and include.get("response", True):
            record["response"] = _to_capture_data(response, string_length=limit)
        if exception is not _UNSET and include.get("exception", True):
            record["exception"] = _to_capture_data(exception, string_length=limit)
        if metadata and include.get("metadata", True):
            record["metadata"] = _to_capture_data(metadata, string_length=limit)

        path = Path(capture_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        return


def _include_settings() -> dict[str, bool]:
    raw = os.environ.get("AITEST_CAPTURE_INCLUDE", "")
    if not raw:
        return {"request": True, "response": True, "exception": True, "metadata": True}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"request": True, "response": True, "exception": True, "metadata": True}
    if not isinstance(data, dict):
        return {"request": True, "response": True, "exception": True, "metadata": True}
    return {
        "request": bool(data.get("request", True)),
        "response": bool(data.get("response", True)),
        "exception": bool(data.get("exception", True)),
        "metadata": bool(data.get("metadata", True)),
    }


def _to_capture_data(value: Any, *, string_length: int, _seen: set[int] | None = None) -> Any:
    seen = _seen if _seen is not None else set()
    obj_id = id(value)
    if obj_id in seen:
        return "<recursive>"

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _limit_string(value, string_length)
    if isinstance(value, bytes):
        try:
            return _limit_string(value.decode("utf-8"), string_length)
        except UnicodeDecodeError:
            return _limit_string(repr(value), string_length)
    if isinstance(value, BaseException):
        return {
            "type": value.__class__.__name__,
            "message": _limit_string(str(value), string_length),
        }

    httpx_response = _httpx_response(value, string_length=string_length)
    if httpx_response is not None:
        return httpx_response

    protobuf_message = _protobuf_message(value)
    if protobuf_message is not None:
        return _to_capture_data(protobuf_message, string_length=string_length, _seen=seen)

    if is_dataclass(value) and not isinstance(value, type):
        return _to_capture_data(asdict(value), string_length=string_length, _seen=seen)

    if isinstance(value, dict):
        seen.add(obj_id)
        try:
            return {
                str(key): _to_capture_data(item, string_length=string_length, _seen=seen)
                for key, item in value.items()
            }
        finally:
            seen.discard(obj_id)

    if isinstance(value, (list, tuple, set)):
        seen.add(obj_id)
        try:
            return [
                _to_capture_data(item, string_length=string_length, _seen=seen)
                for item in value
            ]
        finally:
            seen.discard(obj_id)

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _to_capture_data(model_dump(), string_length=string_length, _seen=seen)
        except Exception:
            pass
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        try:
            return _to_capture_data(dict_method(), string_length=string_length, _seen=seen)
        except Exception:
            pass

    return {"__repr__": _limit_string(repr(value), string_length)}


def _httpx_response(value: Any, *, string_length: int) -> dict[str, Any] | None:
    try:
        import httpx
    except Exception:
        return None
    if not isinstance(value, httpx.Response):
        return None
    body: Any
    try:
        body = value.json()
    except Exception:
        body = value.text
    return {
        "status_code": value.status_code,
        "body": _to_capture_data(body, string_length=string_length),
    }


def _protobuf_message(value: Any) -> dict[str, Any] | None:
    try:
        from google.protobuf.json_format import MessageToDict
        from google.protobuf.message import Message
    except Exception:
        return None
    if not isinstance(value, Message):
        return None
    try:
        return MessageToDict(value, preserving_proto_field_name=True)
    except Exception:
        return {"__repr__": repr(value)}


def _limit_string(value: str, limit: int) -> str:
    if limit <= 0 or len(value) <= limit:
        return value
    return value[:limit] + f"...<truncated {len(value) - limit} chars>"


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _validate_output_file(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or path.parent != Path("."):
        raise RuntimeError("capture output.file must be a file name under the run directory")
