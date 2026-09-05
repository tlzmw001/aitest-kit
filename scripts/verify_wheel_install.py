#!/usr/bin/env python3
"""Exercise the distributable in an unrelated, disposable venv (no model calls)."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def clean_environment(root: Path, source: dict[str, str]) -> dict[str, str]:
    allowed = {
        "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
        "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL",
        "SYSTEMDRIVE", "NUMBER_OF_PROCESSORS",
    }
    env = {key: value for key, value in source.items() if key.upper() in allowed}
    env.update({
        "AITEST_RUNTIME_HOME": str(root / "runtimes"),
        "AITEST_AGENT_SESSION_HOME": str(root / "sessions"),
        "NPM_CONFIG_USERCONFIG": str(root / "empty-user.npmrc"),
        "NPM_CONFIG_GLOBALCONFIG": str(root / "empty-global.npmrc"),
        "NPM_CONFIG_CACHE": str(root / "npm-cache"),
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "NO_PROXY": "127.0.0.1,localhost",
    })
    return env


def select_wheel(directory: Path) -> Path:
    wheels = list(directory.glob("aitest_kit-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected exactly one aitest-kit universal wheel")
    return wheels[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"status": "failed", "os": platform.system(), "python": platform.python_version()}
    stage = "select_wheel"
    try:
        wheel = select_wheel(args.wheel_dir.resolve())
        report["wheel"] = wheel.name
        with tempfile.TemporaryDirectory(prefix="aitest wheel smoke ") as temporary:
            root = Path(temporary).resolve()
            env = clean_environment(root, dict(os.environ))
            venv_dir = root / "clean venv"
            stage = "create_venv"
            subprocess.run([sys.executable, "-I", "-m", "venv", str(venv_dir)],
                           cwd=root, env=env, check=True, capture_output=True, timeout=120)
            python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            stage = "install_wheel"
            subprocess.run([str(python), "-I", "-m", "pip", "install", "--no-cache-dir", f"{wheel}[server]"],
                           cwd=root, env=env, check=True, capture_output=True, timeout=600)
            stage = "probe"
            result = subprocess.run([
                str(python), "-I", str(Path(__file__).with_name("wheel_install_probe.py")), str(root),
            ], cwd=root, env=env, check=False, capture_output=True, text=True, encoding="utf-8", timeout=900)
            # Only the structured probe report crosses this boundary; subprocess logs may contain tokens.
            details = json.loads(result.stdout)
            report.update(details)
            if result.returncode != 0:
                report["status"] = "failed"
    except Exception as exc:
        report.update(status="failed", stage=stage, error_type=type(exc).__name__)
        if isinstance(exc, subprocess.CalledProcessError):
            report["exit_code"] = exc.returncode
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
