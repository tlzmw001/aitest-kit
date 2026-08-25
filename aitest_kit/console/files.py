from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from aitest_kit.console.errors import ConsoleError
from aitest_kit.console.workspace import WorkspaceState
from aitest_kit.runtime_variables import ProfileVariableError, _parse_dotenv


_SENSITIVE_ENV_MARKERS = (
    "TOKEN",
    "KEY",
    "PASSWORD",
    "SECRET",
    "AUTH",
    "URL",
    "URI",
    "CREDENTIAL",
    "COOKIE",
    "SESSION",
    "PRIVATE",
    "CERT",
)


def read_workspace_file(state: WorkspaceState, raw_path: str) -> dict[str, Any]:
    path = state.resolve_inside(raw_path)
    if _is_env_path(state, path):
        raise ConsoleError(
            "ENV_ACCESS_REQUIRED",
            "Env 文件只能通过敏感环境接口访问",
            status_code=403,
        )
    _ensure_console_file_scope(state, path)
    content = _read_utf8(path)
    owner, read_only = classify_file(state, path)
    return _file_payload(state, path, content, owner=owner, read_only=read_only)


def save_workspace_file(
    state: WorkspaceState,
    *,
    raw_path: str,
    content: str,
    expected_sha256: str,
) -> dict[str, Any]:
    path = state.resolve_inside(raw_path)
    if _is_env_path(state, path):
        raise ConsoleError("ENV_ACCESS_REQUIRED", "Env 文件只能通过敏感环境接口保存", status_code=403)
    _ensure_console_file_scope(state, path)
    owner, read_only = classify_file(state, path)
    if read_only:
        raise ConsoleError("FILE_READ_ONLY", "该文件是只读产物", status_code=403)
    _atomic_write(
        state.root,
        path,
        content,
        expected_sha256=expected_sha256,
        create_mode=0o644,
    )
    return _file_payload(state, path, content, owner=owner, read_only=False)


def environment_metadata(state: WorkspaceState) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for path in state.env_paths():
        exists = path.exists() and path.is_file()
        keys: list[str] = []
        error = ""
        if exists:
            try:
                keys = sorted(_parse_dotenv(path))
            except ProfileVariableError as exc:
                error = str(exc)
        sources.append({
            "path": state.relative(path),
            "absolute_path": str(path) if not _inside(state.root, path) else None,
            "exists": exists,
            "external": not _inside(state.root, path),
            "active": state.active_env_file == path or (state.active_env_file is None and path == state.root / ".env"),
            "keys": keys,
            "error": error,
            "git_status": _git_status(state.root, path),
        })
    shell_keys = sorted(
        key for key in os.environ if "AITEST" in key.upper() or _is_sensitive_env_key(key)
    )
    return {"sources": sources, "shell_keys": shell_keys, "precedence": ["shell", "explicit_env_files", "workspace_dotenv"]}


def reveal_env(state: WorkspaceState, *, raw_path: str, confirmed: bool) -> dict[str, Any]:
    _require_confirmation(confirmed)
    path = state.resolve_env(raw_path, allow_missing=True)
    if not path.exists():
        content = ""
    else:
        content = _read_utf8(path)
    payload = _file_payload(state, path, content, owner="ENV", read_only=False)
    payload["exists"] = path.exists()
    payload["external"] = not _inside(state.root, path)
    return payload


def save_env(
    state: WorkspaceState,
    *,
    raw_path: str,
    content: str,
    expected_sha256: str,
    confirmed: bool,
) -> dict[str, Any]:
    _require_confirmation(confirmed)
    path = state.resolve_env(raw_path, allow_missing=True)
    _validate_dotenv_content(content)
    write_root = state.root if _inside(state.root, path) else path.parent
    _atomic_write(
        write_root,
        path,
        content,
        expected_sha256=expected_sha256,
        create_mode=0o600,
    )
    return _file_payload(state, path, content, owner="ENV", read_only=False)


def env_secret_values(state: WorkspaceState, selected_path: str | None = None) -> list[str]:
    paths = [state.resolve_env(selected_path, allow_missing=False)] if selected_path else state.env_paths()
    values: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            values.extend(value for value in _parse_dotenv(path).values() if value)
        except ProfileVariableError:
            continue
    for key, value in os.environ.items():
        if value and _is_sensitive_env_key(key):
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def _is_sensitive_env_key(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in _SENSITIVE_ENV_MARKERS)


def classify_file(state: WorkspaceState, path: Path) -> tuple[str, bool]:
    root = state.root
    roots = state.asset_roots()
    relative = path.resolve(strict=False).relative_to(root).as_posix()
    if any(_under(path, directory) for directory in roots["generated"]):
        return "GENERATED", True
    if any(_under(path, directory) for directory in roots["reports"]):
        return "REPORT", True
    if relative.startswith("test_workspace/results/"):
        return "SUT", True
    if any(_under(path, directory) for directory in roots["suites"]) and path.suffix.lower() == ".md":
        return "CASE", False
    if path.suffix.lower() in {".yaml", ".yml", ".json"}:
        return "CONFIG", False
    if path.suffix.lower() == ".py" or "/modules/" in f"/{relative}":
        return "SCAFFOLD", False
    return "SOURCE", False


def _validate_dotenv_content(content: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / ".env"
        path.write_text(content, encoding="utf-8")
        try:
            _parse_dotenv(path)
        except ProfileVariableError as exc:
            message = str(exc).replace(str(path), ".env")
            raise ConsoleError("ENV_INVALID", message) from exc


def _file_payload(
    state: WorkspaceState,
    path: Path,
    content: str,
    *,
    owner: str,
    read_only: bool,
) -> dict[str, Any]:
    return {
        "path": state.relative(path),
        "name": path.name,
        "content": content,
        "sha256": _sha256(content),
        "owner": owner,
        "read_only": read_only,
    }


def _atomic_write(
    root: Path,
    path: Path,
    content: str,
    *,
    expected_sha256: str,
    create_mode: int,
) -> None:
    if os.name == "posix" and hasattr(os, "O_NOFOLLOW") and os.supports_dir_fd:
        _atomic_write_at(
            root,
            path,
            content,
            expected_sha256=expected_sha256,
            create_mode=create_mode,
        )
        return
    _atomic_write_fallback(
        root,
        path,
        content,
        expected_sha256=expected_sha256,
        create_mode=create_mode,
    )


def _atomic_write_at(
    root: Path,
    path: Path,
    content: str,
    *,
    expected_sha256: str,
    create_mode: int,
) -> None:
    parent_fd = _open_parent_directory(root, path.parent)
    temp_name = f".{path.name}.{uuid4().hex}.tmp"
    temp_fd: int | None = None
    try:
        current, existing_mode = _read_at(parent_fd, path.name, create_mode)
        if _sha256(current) != expected_sha256:
            raise ConsoleError("FILE_CONFLICT", "文件已在 Console 外发生变化", status_code=409)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        temp_fd = os.open(temp_name, flags, create_mode, dir_fd=parent_fd)
        payload = content.encode("utf-8")
        offset = 0
        while offset < len(payload):
            offset += os.write(temp_fd, payload[offset:])
        os.fsync(temp_fd)
        os.fchmod(temp_fd, existing_mode)
        os.close(temp_fd)
        temp_fd = None
        os.replace(temp_name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
    except ConsoleError:
        raise
    except OSError as exc:
        raise ConsoleError("FILE_WRITE_FAILED", "无法安全保存文件", status_code=500) from exc
    finally:
        if temp_fd is not None:
            os.close(temp_fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        except OSError:
            pass
        os.close(parent_fd)


def _open_parent_directory(root: Path, parent: Path) -> int:
    root = root.resolve(strict=True)
    try:
        relative = parent.relative_to(root)
    except ValueError as exc:
        raise ConsoleError("PATH_OUTSIDE_WORKSPACE", "路径不在当前 workspace 内", status_code=403) from exc
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current_fd = os.open(root, flags)
    try:
        for part in relative.parts:
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _read_at(parent_fd: int, name: str, create_mode: int) -> tuple[str, int]:
    try:
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError:
        return "", create_mode
    try:
        with os.fdopen(file_fd, "r", encoding="utf-8", closefd=False) as handle:
            content = handle.read()
        mode = os.fstat(file_fd).st_mode & 0o777
        return content, mode
    except UnicodeError as exc:
        raise ConsoleError("FILE_ENCODING_ERROR", "文件不是有效 UTF-8", status_code=400) from exc
    finally:
        os.close(file_fd)


def _atomic_write_fallback(
    root: Path,
    path: Path,
    content: str,
    *,
    expected_sha256: str,
    create_mode: int,
) -> None:
    _assert_safe_write_path(root, path)
    current = _read_utf8(path) if path.exists() else ""
    if _sha256(current) != expected_sha256:
        raise ConsoleError("FILE_CONFLICT", "文件已在 Console 外发生变化", status_code=409)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = path.stat().st_mode & 0o777 if path.exists() else create_mode
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, existing_mode)
        _assert_safe_write_path(root, path)
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise ConsoleError("FILE_WRITE_FAILED", "无法保存文件", status_code=500) from exc


def _assert_safe_write_path(root: Path, path: Path) -> None:
    resolved_root = root.resolve(strict=True)
    current = resolved_root
    try:
        relative = path.relative_to(resolved_root)
    except ValueError as exc:
        raise ConsoleError("PATH_OUTSIDE_WORKSPACE", "路径不在当前 workspace 内", status_code=403) from exc
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ConsoleError("PATH_OUTSIDE_WORKSPACE", "保存路径包含符号链接", status_code=403)
        if not current.exists():
            break
    if not _inside(resolved_root, path):
        raise ConsoleError("PATH_OUTSIDE_WORKSPACE", "路径不在当前 workspace 内", status_code=403)


def _read_utf8(path: Path) -> str:
    if not path.is_file():
        raise ConsoleError("FILE_NOT_FOUND", "文件不存在", status_code=404)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ConsoleError("FILE_ENCODING_ERROR", "文件不是有效 UTF-8", status_code=400) from exc
    except OSError as exc:
        raise ConsoleError("FILE_READ_FAILED", "无法读取文件", status_code=500) from exc


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _is_env_path(state: WorkspaceState, path: Path) -> bool:
    return path.resolve(strict=False) in set(state.env_paths()) or path.name == ".env"


def _ensure_console_file_scope(state: WorkspaceState, path: Path) -> None:
    root = state.root
    roots = state.asset_roots()
    relative = path.resolve(strict=False).relative_to(root).as_posix()
    allowed_root = any(
        relative == prefix or relative.startswith(f"{prefix}/")
        for prefix in ("aitest_config", "test_workspace", "docs")
    ) or any(_under(path, directory) for directories in roots.values() for directory in directories)
    allowed_suffix = path.suffix.lower() in {".md", ".yaml", ".yml", ".py", ".json", ".jsonl", ".xml"}
    if not allowed_root or not allowed_suffix:
        raise ConsoleError(
            "PATH_NOT_ALLOWED",
            "该文件不属于 Console 可访问的测试资产范围",
            status_code=403,
        )


def _under(path: Path, directory: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(directory.resolve(strict=False))
    except ValueError:
        return False
    return True


def _require_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise ConsoleError("ENV_ACCESS_REQUIRED", "需要用户明确确认敏感 env 访问", status_code=403)


def _git_status(root: Path, path: Path) -> str:
    if not _inside(root, path):
        return "external"
    relative = path.resolve(strict=False).relative_to(root).as_posix()
    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
            check=False,
            capture_output=True,
            timeout=2,
        ).returncode == 0
        if tracked:
            return "tracked"
        ignored = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", "--", relative],
            check=False,
            capture_output=True,
            timeout=2,
        ).returncode == 0
        return "ignored" if ignored else "untracked"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
