"""Run only inside the clean venv; import installed aitest-kit, never add repo sys.path."""
from __future__ import annotations

import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def safe_diagnostic(output: str) -> str:
    sensitive = re.compile(r"token|api[_-]?key|password|secret|authorization|session url|sk-", re.I)
    lines = [line for line in output.splitlines() if not sensitive.search(line)]
    return "\n".join(lines[-12:])[-2000:]


class ConsoleStartupError(RuntimeError):
    pass


def session_token(line: str) -> str | None:
    if not line.startswith("Session URL: "):
        return None
    values = parse_qs(urlsplit(line.removeprefix("Session URL: ").strip()).fragment)
    return values.get("token", [None])[0]


def run(command: list[str], cwd: Path, timeout: int = 60) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True,
                            text=True, encoding="utf-8", timeout=timeout)
    return result.stdout


def verify_console(cli: Path, workspace: Path) -> dict:
    import httpx

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen([
        str(cli), "console", "--workspace", str(workspace), "--host", "127.0.0.1",
        "--port", str(port), "--no-open",
    ], cwd=workspace.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
       text=True, encoding="utf-8")
    tokens: queue.Queue[str | None] = queue.Queue()
    diagnostics: deque[str] = deque(maxlen=30)

    def consume() -> None:
        for line in process.stdout:
            diagnostics.append(safe_diagnostic(line))
            token = session_token(line)
            if token:
                tokens.put(token)
        tokens.put(None)

    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    try:
        token = tokens.get(timeout=30)
        if token is None:
            raise ConsoleStartupError(safe_diagnostic("\n".join(diagnostics)))
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=3) as client:
            deadline = time.monotonic() + 30
            last_error = "not started"
            while True:
                try:
                    response = client.get("/")
                    response.raise_for_status()
                    break
                except httpx.HTTPError as exc:
                    last_error = type(exc).__name__
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError(f"Console startup failed: {last_error}") from exc
                    time.sleep(0.1)
            assert client.get("/api/workspace").status_code == 401
            client.headers["X-AITest-Console-Token"] = token
            workspace_response = client.get("/api/workspace")
            workspace_response.raise_for_status()
            assert Path(workspace_response.json()["path"]).resolve() == workspace.resolve()
            runtime_response = client.get("/api/agent/runtime")
            runtime_response.raise_for_status()
            assert runtime_response.json()["state"] == "ready"
            assert runtime_response.json()["source"] == "user"
            assert runtime_response.headers["cache-control"] == "no-store"
            assets = re.findall(r'src="(/assets/[^"\s]+\.js)"', response.text)
            assert assets, "Packaged index must reference JavaScript"
            for asset in assets:
                js = client.get(asset)
                js.raise_for_status()
                assert "javascript" in js.headers["content-type"] and len(js.content) > 0
        return {"console_http": "passed", "console_runtime": "passed",
                "unauthorized_status": 401, "javascript_assets": len(assets)}
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        reader.join(timeout=5)
        process.stdout.close()


def main() -> int:
    report: dict = {"status": "failed"}
    stage = "installed_import"
    try:
        import aitest_kit
        from aitest_kit.agent.runtime import runtime_status

        root = Path(sys.argv[1]).resolve()
        package = Path(aitest_kit.__file__).resolve()
        assert Path(sys.prefix).resolve() in package.parents, "Imported source checkout instead of wheel"
        assert sys.prefix != sys.base_prefix
        cli = Path(sys.executable).parent / ("aitest.exe" if os.name == "nt" else "aitest")
        workspace = root / "workspace with spaces"
        stage = "workspace_init"
        run([str(cli), "init", "--target", str(workspace)], root)
        stage = "workspace_doctor"
        run([str(cli), "doctor", "--workspace", str(workspace)], root)
        stage = "agent_setup"
        run([str(cli), "agent", "setup"], root, timeout=700)
        status = runtime_status()
        assert status["state"] == "ready" and status["source"] == "user"
        runtime = Path(status["runtime_dir"]).resolve()
        assert (root / "runtimes") in runtime.parents
        metadata = {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                    for path in runtime.glob("*.json")}
        stage = "setup_idempotence"
        run([str(cli), "agent", "setup"], root, timeout=700)
        assert metadata == {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                            for path in runtime.glob("*.json")}
        stage = "worker_self_test"
        result = run(["node", "--experimental-strip-types", str(runtime / "src/worker.ts"), "--self-test"], root)
        assert json.loads(result) == {"runtime": "pi", "status": "ok"}
        report.update(runtime_source="user", node=status["node_version"], bundle_hash=status["bundle_hash"],
                      workspace_doctor="passed", setup_idempotence="passed", worker_self_test="passed")
        stage = "console"
        report.update(verify_console(cli, workspace))
        report["status"] = "passed"
    except Exception as exc:
        # Only bounded, filtered diagnostics from this credential-free probe may cross the boundary.
        report.update(stage=stage, error_type=type(exc).__name__)
        if isinstance(exc, subprocess.CalledProcessError):
            report["exit_code"] = exc.returncode
            report["diagnostic"] = safe_diagnostic((exc.stdout or "") + (exc.stderr or ""))
        elif isinstance(exc, ConsoleStartupError):
            report["diagnostic"] = safe_diagnostic(str(exc))
    print(json.dumps(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
