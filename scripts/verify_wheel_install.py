#!/usr/bin/env python3
"""Exercise the distributable in an unrelated, disposable venv (no model calls)."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


def clean_environment(root: Path, source: dict[str, str]) -> dict[str, str]:
    allowed = {
        "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
        "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL",
        "SYSTEMDRIVE", "NUMBER_OF_PROCESSORS",
    }
    env = {key: value for key, value in source.items() if key.upper() in allowed}
    env.update({
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


def verify_archive(path: Path) -> None:
    """Reject removed runtime files by manifest only; never extract or execute members."""
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            names = archive.getnames()
    else:
        raise ValueError("Expected a wheel or source distribution")
    forbidden = (
        "/aitest_kit/agent/",
        "/aitest_kit/console/agent_",
        "/agent_runtime/pi_worker/",
        "/runtime_seed/pi_worker/",
        "/aitest_kit/console/web/assets/Agent",
        "/node_modules/",
    )
    paths = ("/" + name.replace("\\", "/") + "/" for name in names)
    leaked = sum(any(marker in name for marker in forbidden) for name in paths)
    if leaked:
        raise ValueError(
            f"Distribution includes {leaked} removed Agent/Runtime entries; "
            "rebuild from a clean checkout or worktree"
        )


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
        stage = "inspect_wheel"
        verify_archive(wheel)
        report.update(wheel_contents="passed", embedded_agent="absent")
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
        if stage == "inspect_wheel":
            report["diagnostic"] = "Archive inspection failed; rebuild from a clean checkout or worktree."
        if isinstance(exc, subprocess.CalledProcessError):
            report["exit_code"] = exc.returncode
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
