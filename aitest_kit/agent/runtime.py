"""Install, validate, and resolve the user-level Pi Worker runtime."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aitest_kit.agent.protocol import redact
from aitest_kit.agent.seed import RuntimeSeedError, validate_runtime_seed


RUNTIME_HOME_ENV = "AITEST_RUNTIME_HOME"
INSTALL_MANIFEST_NAME = "install-manifest.json"
SETUP_COMMAND = "aitest agent setup"
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
CommandRunner = Callable[[list[str], Path, float], subprocess.CompletedProcess[str]]
ProgressSink = Callable[[str], None]


class AgentRuntimeError(RuntimeError):
    """Stable runtime installation or resolution failure."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = dict(redact(details or {}))


def default_seed_dir() -> Path:
    return Path(__file__).resolve().parent / "runtime_seed" / "pi_worker"


def default_source_worker_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "agent_runtime" / "pi_worker"


def runtime_home(environ: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get(RUNTIME_HOME_ENV)
    return Path(configured).expanduser().resolve() if configured else Path.home() / ".aitest" / "runtimes"


def runtime_setup_command() -> list[str]:
    return [sys.executable, "-m", "aitest_kit.cli", "agent", "setup"]


def resolve_worker_dir(
    explicit_dir: str | Path | None = None,
    *,
    seed_dir: str | Path | None = None,
    source_dir: str | Path | None = None,
    runtime_home_dir: str | Path | None = None,
) -> Path:
    seed, manifest = _validated_seed(seed_dir)
    if explicit_dir is not None:
        explicit = Path(explicit_dir).expanduser().resolve()
        _require_worker_tree(explicit, manifest, installed=False)
        return explicit
    source = Path(source_dir).resolve() if source_dir is not None else default_source_worker_dir()
    if _worker_tree_ready(source, manifest, installed=False):
        return source
    destination = _runtime_destination(manifest, runtime_home_dir)
    if _worker_tree_ready(destination, manifest, installed=True):
        return destination
    if destination.exists():
        raise AgentRuntimeError(
            "AGENT_RUNTIME_INVALID",
            f"已安装的 Pi Runtime 不完整，请重新运行 {SETUP_COMMAND}",
            details={"runtime_dir": str(destination)},
        )
    raise AgentRuntimeError(
        "AGENT_RUNTIME_NOT_INSTALLED",
        f"Pi Agent Runtime 尚未安装，请运行 {SETUP_COMMAND}",
        details={"seed_dir": str(seed)},
    )


def runtime_status(
    *,
    seed_dir: str | Path | None = None,
    source_dir: str | Path | None = None,
    runtime_home_dir: str | Path | None = None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    runner = command_runner or _run_command
    try:
        _, manifest = _validated_seed(seed_dir)
    except AgentRuntimeError as exc:
        return _status_document("invalid", None, str(exc))
    destination = _runtime_destination(manifest, runtime_home_dir)
    base = {
        "runtime_dir": str(destination),
        "bundle_hash": manifest["bundle_hash"],
        "minimum_node_version": manifest["minimum_node_version"],
        "dependencies": [
            {"name": name, "version": version}
            for name, version in sorted(manifest["dependencies"].items())
        ],
    }
    node = _tool_version("node", runner)
    if node is None:
        return _status_document("node_missing", None, "未找到 Node.js", **base)
    base["node_version"] = node
    if _version_tuple(node) < _version_tuple(manifest["minimum_node_version"]):
        return _status_document(
            "node_unsupported",
            None,
            f"Node {node} 低于最低版本 {manifest['minimum_node_version']}",
            **base,
        )
    npm = _tool_version("npm", runner)
    if npm is None:
        return _status_document("invalid", None, "未找到 npm", **base)
    base["npm_version"] = npm
    base["registry"] = _npm_registry(runner)
    source = Path(source_dir).resolve() if source_dir is not None else default_source_worker_dir()
    if _worker_tree_ready(source, manifest, installed=False):
        return _status_document(
            "ready",
            "source",
            "Pi Runtime 已从源码 checkout 就绪",
            **{**base, "runtime_dir": str(source)},
        )
    if _worker_tree_ready(destination, manifest, installed=True):
        return _status_document("ready", "user", "Pi Runtime 已安装", **base)
    if destination.exists():
        return _status_document("invalid", None, f"已安装 Runtime 不完整，请重新运行 {SETUP_COMMAND}", **base)
    return _status_document("missing", None, f"Pi Runtime 尚未安装，请运行 {SETUP_COMMAND}", **base)


def install_runtime(
    *,
    seed_dir: str | Path | None = None,
    runtime_home_dir: str | Path | None = None,
    command_runner: CommandRunner | None = None,
    progress: ProgressSink | None = None,
) -> dict[str, Any]:
    runner = command_runner or _run_command
    notify = progress or (lambda _message: None)
    seed, manifest = _validated_seed(seed_dir)
    minimum = manifest["minimum_node_version"]
    node = _tool_version("node", runner)
    if node is None:
        raise AgentRuntimeError("AGENT_NODE_NOT_FOUND", "未找到 Node.js；请先安装 Node.js 24 LTS")
    if _version_tuple(node) < _version_tuple(minimum):
        raise AgentRuntimeError("AGENT_NODE_UNSUPPORTED", f"Node {node} 低于最低版本 {minimum}")
    npm = _tool_version("npm", runner)
    if npm is None:
        raise AgentRuntimeError("AGENT_NPM_NOT_FOUND", "未找到 npm；请检查 Node.js 安装")
    registry = _npm_registry(runner)
    destination = _runtime_destination(manifest, runtime_home_dir)
    notify(f"Node: {node}; npm: {npm}")
    notify(f"Registry: {registry or 'unknown'}")
    notify(f"Runtime: {destination}")
    for name, version in sorted(manifest["dependencies"].items()):
        notify(f"Dependency: {name}@{version}")
    if _worker_tree_ready(destination, manifest, installed=True):
        notify("Pi Agent Runtime is already installed and valid.")
        return _install_result(destination, manifest, node, npm, registry, installed=False)

    parent = destination.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=parent))
    except OSError as exc:
        raise AgentRuntimeError("AGENT_RUNTIME_INSTALL_FAILED", f"无法创建 Runtime 安装目录: {exc}") from exc
    try:
        _copy_seed(seed, staging, manifest)
        notify("Installing locked npm dependencies...")
        completed = runner(["npm", "ci", "--omit=dev", "--ignore-scripts"], staging, 600)
        if completed.returncode != 0:
            raise _install_failure("npm ci", completed)
        _require_worker_tree(staging, manifest, installed=False)
        notify("Running Pi Worker self-test...")
        entrypoint = staging / manifest["entrypoint"]
        completed = runner(["node", "--experimental-strip-types", str(entrypoint), "--self-test"], staging, 30)
        if completed.returncode != 0:
            raise _install_failure("Worker self-test", completed)
        try:
            self_test = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as exc:
            raise AgentRuntimeError("AGENT_RUNTIME_INSTALL_FAILED", "Worker self-test 未返回合法 JSON") from exc
        if self_test != {"runtime": "pi", "status": "ok"}:
            raise AgentRuntimeError("AGENT_RUNTIME_INSTALL_FAILED", "Worker self-test 返回内容不符合协议")
        _write_install_manifest(staging, manifest, node)
        _replace_destination(staging, destination)
        notify("Pi Agent Runtime installed successfully.")
    except AgentRuntimeError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise AgentRuntimeError("AGENT_RUNTIME_INSTALL_FAILED", f"Pi Runtime 安装失败: {exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return _install_result(destination, manifest, node, npm, registry, installed=True)


def _validated_seed(seed_dir: str | Path | None) -> tuple[Path, dict[str, Any]]:
    seed = Path(seed_dir).resolve() if seed_dir is not None else default_seed_dir()
    try:
        manifest = validate_runtime_seed(seed)
    except RuntimeSeedError as exc:
        raise AgentRuntimeError("AGENT_RUNTIME_SEED_INVALID", str(exc)) from exc
    bundle_hash = manifest.get("bundle_hash")
    if not isinstance(bundle_hash, str) or _HASH.fullmatch(bundle_hash) is None:
        raise AgentRuntimeError("AGENT_RUNTIME_SEED_INVALID", "Pi Runtime bundle hash 无效")
    return seed, manifest


def _runtime_destination(manifest: Mapping[str, Any], runtime_home_dir: str | Path | None) -> Path:
    root = Path(runtime_home_dir).expanduser().resolve() if runtime_home_dir is not None else runtime_home()
    return root / "pi-worker" / str(manifest["bundle_hash"])


def _worker_tree_ready(root: Path, manifest: Mapping[str, Any], *, installed: bool) -> bool:
    try:
        _require_worker_tree(root, manifest, installed=installed)
    except AgentRuntimeError:
        return False
    return True


def _require_worker_tree(root: Path, manifest: Mapping[str, Any], *, installed: bool) -> None:
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentRuntimeError("AGENT_RUNTIME_INVALID", f"无法读取 Pi Runtime metadata: {exc}") from exc
    dependencies = manifest["dependencies"]
    locked = lock.get("packages", {}).get("", {}).get("dependencies", {})
    if package.get("dependencies") != dependencies or locked != dependencies:
        raise AgentRuntimeError("AGENT_RUNTIME_INVALID", "Pi Runtime package/lock 与 seed 不一致")
    if not (root / str(manifest["entrypoint"])).is_file():
        raise AgentRuntimeError("AGENT_RUNTIME_INVALID", "Pi Runtime 缺少 Worker entrypoint")
    missing = [
        name for name in dependencies
        if not (root / "node_modules" / Path(*name.split("/"))).is_dir()
    ]
    if missing:
        raise AgentRuntimeError("AGENT_RUNTIME_INVALID", "Pi Runtime 缺少依赖: " + ", ".join(sorted(missing)))
    if installed:
        _validate_install_manifest(root, manifest)
        try:
            installed_seed = json.loads((root / "runtime-manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentRuntimeError("AGENT_RUNTIME_INVALID", f"无法读取 Runtime seed manifest: {exc}") from exc
        if installed_seed != manifest:
            raise AgentRuntimeError("AGENT_RUNTIME_INVALID", "Runtime seed manifest 与当前 bundle 不匹配")
        files = manifest.get("files", {})
        for relative, expected_hash in files.items():
            path = root / relative
            if not path.is_file():
                raise AgentRuntimeError("AGENT_RUNTIME_INVALID", f"Pi Runtime 缺少 seed 文件: {relative}")
            try:
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                raise AgentRuntimeError("AGENT_RUNTIME_INVALID", f"无法读取 Pi Runtime 文件: {relative}") from exc
            if actual_hash != expected_hash:
                raise AgentRuntimeError("AGENT_RUNTIME_INVALID", f"Pi Runtime 文件 hash 不匹配: {relative}")


def _validate_install_manifest(root: Path, manifest: Mapping[str, Any]) -> None:
    try:
        installed = json.loads((root / INSTALL_MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentRuntimeError("AGENT_RUNTIME_INVALID", f"无法读取 install manifest: {exc}") from exc
    if (
        installed.get("schema_version") != 1
        or installed.get("runtime") != "pi"
        or installed.get("bundle_hash") != manifest["bundle_hash"]
    ):
        raise AgentRuntimeError("AGENT_RUNTIME_INVALID", "Pi Runtime install manifest 不匹配")


def _copy_seed(seed: Path, staging: Path, manifest: Mapping[str, Any]) -> None:
    for relative in [*manifest["files"], "runtime-manifest.json"]:
        source = seed / relative
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _write_install_manifest(root: Path, manifest: Mapping[str, Any], node: str) -> None:
    document = {
        "schema_version": 1,
        "runtime": "pi",
        "bundle_hash": manifest["bundle_hash"],
        "node_version": node,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    (root / INSTALL_MANIFEST_NAME).write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _replace_destination(staging: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup")
    if backup.exists():
        shutil.rmtree(backup)
    moved_existing = False
    try:
        if destination.exists():
            destination.replace(backup)
            moved_existing = True
        staging.replace(destination)
    except OSError:
        if moved_existing and backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _tool_version(tool: str, runner: CommandRunner) -> str | None:
    try:
        completed = runner([tool, "--version"], Path.cwd(), 5)
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and _VERSION.fullmatch(value) else None


def _npm_registry(runner: CommandRunner) -> str:
    try:
        completed = runner(["npm", "config", "get", "registry"], Path.cwd(), 5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return _safe_registry(completed.stdout.strip()) if completed.returncode == 0 else ""


def _safe_registry(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    netloc = parsed.hostname
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path or "/", "", ""))


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _install_failure(stage: str, completed: subprocess.CompletedProcess[str]) -> AgentRuntimeError:
    stderr = _redacted_runtime_text(completed.stderr.strip())[-2000:]
    return AgentRuntimeError(
        "AGENT_RUNTIME_INSTALL_FAILED",
        f"{stage} 失败（退出码 {completed.returncode}）" + (f": {stderr}" if stderr else ""),
        details={"stage": stage, "exit_code": completed.returncode},
    )


def _run_command(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True, timeout=timeout)


def _redacted_runtime_text(value: str, environ: Mapping[str, str] | None = None) -> str:
    rendered = str(redact(value))
    values = os.environ if environ is None else environ
    for name, secret in values.items():
        sensitive_name = any(
            part in name.upper()
            for part in ("KEY", "PASSWORD", "SECRET", "TOKEN")
        )
        if secret and len(secret) >= 4 and sensitive_name:
            rendered = rendered.replace(secret, "[REDACTED]")
    return rendered


def _status_document(state: str, source: str | None, message: str, **overrides: Any) -> dict[str, Any]:
    document = {
        "state": state,
        "source": source,
        "message": message,
        "runtime_dir": "",
        "bundle_hash": "",
        "minimum_node_version": "22.19.0",
        "node_version": "",
        "npm_version": "",
        "registry": "",
        "dependencies": [],
        "setup_command": SETUP_COMMAND,
    }
    document.update(overrides)
    return document


def _install_result(
    destination: Path,
    manifest: Mapping[str, Any],
    node: str,
    npm: str,
    registry: str,
    *,
    installed: bool,
) -> dict[str, Any]:
    return {
        "installed": installed,
        "runtime_dir": str(destination),
        "bundle_hash": manifest["bundle_hash"],
        "node_version": node,
        "npm_version": npm,
        "registry": registry,
    }
