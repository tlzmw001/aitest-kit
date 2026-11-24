"""Workspace and command-line settings for a deferred assertion run."""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Optional

import httpx
import yaml


@dataclass(frozen=True)
class RunSettings:
    case_concurrency: int = 1
    log_concurrency: int = 1
    request_timeout_seconds: float = 120
    poll_interval_seconds: float = 1
    http_timeout_seconds: float = 5
    check_timeout_seconds: float = 2
    cancel_grace_seconds: float = 5
    pending_request_limit: int = 5000
    snapshot_max_bytes: int = 8000000
    snapshot_max_events: int = 10000
    snapshot_max_pages: int = 1000
    base_url_env: str = "AITEST_LOG_BASE_URL"
    token_env: str = "AITEST_LOG_TOKEN"
    directory: str = ".aitest/runs"
    retention_seconds: float = 86400
    submit_timeout_seconds: float = 15
    queue_timeout_seconds: float = 120
    cleanup_concurrency: int = 4
    retry_initial_seconds: float = .5
    retry_max_seconds: float = 3
    concurrency_configured: bool = False
    base_url: Optional[str] = None

    def platform_credentials(self, env):
        field = "platform.base_url" if self.base_url is not None else self.base_url_env
        url = self.base_url if self.base_url is not None else env.get(self.base_url_env)
        return normalize_platform_url(url, field), env.get(self.token_env)


def normalize_platform_url(value, field="platform.base_url"):
    message = f"{field} must be an absolute HTTP(S) URL without credentials, query or fragment"
    if (not isinstance(value, str) or not value
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
            or any(char in value for char in ("?", "#", "\\"))):
        raise ValueError(message)
    try:
        url = httpx.URL(value)
    except (httpx.InvalidURL, ValueError):
        raise ValueError(message) from None
    authority = value.partition("://")[2].split("/", 1)[0]
    if (url.scheme not in ("http", "https") or not authority or not url.host or "@" in authority
            or (url.port is not None and not 1 <= url.port <= 65535)):
        raise ValueError(message)
    return str(url.copy_with(raw_path=url.raw_path.rstrip(b"/") + b"/"))


_SECTIONS = {
    "platform": {"base_url", "base_url_env", "token_env"},
    "state": {"directory", "retention_seconds"},
    "cleanup": {"submit_timeout_seconds", "queue_timeout_seconds", "cleanup_concurrency",
                "retry_initial_seconds", "retry_max_seconds"},
}
_SECTIONS["execution"] = set(asdict(RunSettings())) - set().union(*_SECTIONS.values()) - {"concurrency_configured"}
_INTEGER = {"case_concurrency", "log_concurrency", "pending_request_limit",
            "snapshot_max_bytes", "snapshot_max_events", "snapshot_max_pages", "cleanup_concurrency"}


def load_settings(workspace, case_concurrency=None, log_concurrency=None, *, state_only=False):
    path = workspace / "aitest_config/log_assertions.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML in aitest_config/log_assertions.yaml") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict) or data.keys() - {"schema_version", *_SECTIONS}:
        raise ValueError("invalid log_assertions.yaml sections")
    if type(data.get("schema_version", 1)) is not int or data.get("schema_version", 1) != 1:
        raise ValueError("unsupported log assertion configuration version")
    values = {}
    defaults = RunSettings()
    for section, fields in _SECTIONS.items():
        if state_only and section != "state":
            continue
        current = data.get(section, {})
        if not isinstance(current, dict) or current.keys() - fields:
            raise ValueError(f"invalid log assertion {section} configuration")
        values.update(current)
    for name, value in (("case_concurrency", case_concurrency), ("log_concurrency", log_concurrency)):
        if value is not None:
            values[name] = value
    for key, value in values.items():
        if key == "base_url":
            values[key] = normalize_platform_url(value)
            continue
        if key in {"base_url_env", "token_env"}:
            valid = isinstance(value, str) and value.isascii() and value.isidentifier()
        elif key == "directory":
            valid = isinstance(value, str) and bool(value.strip())
        elif key in _INTEGER:
            valid = type(value) is int and value > 0
            if key.startswith("snapshot_"):
                valid = valid and value <= getattr(defaults, key)
        else:
            valid = type(value) in (int, float) and 0 < value < float("inf")
        if not valid:
            raise ValueError(f"invalid log assertion setting {key}")
    settings = replace(defaults, concurrency_configured=bool({"case_concurrency", "log_concurrency"} & values.keys()), **values)
    if settings.retry_initial_seconds > settings.retry_max_seconds:
        raise ValueError("cleanup retry_initial_seconds exceeds retry_max_seconds")
    state_root(workspace, settings)
    return settings


def state_root(workspace, settings):
    directory = Path(settings.directory)
    if directory.is_absolute() or ".." in directory.parts or directory == Path("."):
        raise ValueError("log state directory must be inside the workspace")
    path = workspace
    for part in directory.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("log state directory cannot use symlinks")
    return path
