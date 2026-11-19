#!/usr/bin/env python3
"""Verify log assertions from isolated basic and parallel wheel installations."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET
import tarfile
import zipfile

from verify_wheel_install import clean_environment, select_wheel, verify_archive

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "aitest_kit/log_assertions/coordinator.py",
    "aitest_kit/templates/project_workspace/examples/log_assertions/README.md",
    "aitest_kit/templates/project_workspace/examples/log_assertions/test_workspace/suites/demo/log_multi_request/suite.yaml",
    "aitest_kit/templates/project_workspace/aitest_config/schemas/codegen_profile.schema.json",
    "aitest_kit/templates/project_workspace/aitest_config/refs/log-assertions.md",
    "aitest_kit/templates/project_workspace/skills/test-codegen/SKILL.md",
]


def inspect_archive(path):
    verify_archive(path)
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    else:
        with tarfile.open(path, "r:gz") as archive:
            names = {name.partition("/")[2] for name in archive.getnames()}
    if missing := set(REQUIRED) - names:
        raise ValueError(f"Missing distribution members: {', '.join(sorted(missing))}")


def invoke(args, root, env, record, timeout=180):
    result = subprocess.run(args, cwd=root, env=env, text=True, capture_output=True, timeout=timeout)
    record.append({"command": list(map(str, args)), "exit_code": result.returncode})
    if result.returncode:
        print(result.stdout, result.stderr, file=sys.stderr)
    result.check_returncode()
    return result.stdout



def install_wheel(venv, wheel, env, commands, constraints=None):
    root = venv.parent
    invoke([sys.executable, "-I", "-m", "venv", venv], root, env, commands)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    options = ["-r", constraints] if constraints else []
    invoke([python, "-I", "-m", "pip", "install", *options, wheel], root, env, commands, 360)
    invoke([python, "-I", "-m", "pip", "check"], root, env, commands)
    return python


def agent_probe(agent_root, python, root, env, commands, output, report):
    source = agent_root / "naiyue_test_agent/cloud_runner/preflight.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "script" for target in node.targets))
    script = ast.literal_eval(assignment.value)
    test = root / "preflight_case.py"
    test.write_text("def test_preflight():\n    assert 1 + 2 == 3\n", encoding="utf-8")
    junit = root / "preflight.xml"
    invoke([python, "-I", "-m", "pytest", test, "-q", f"--junitxml={junit}"], root, env, commands)
    invoke([python, "-I", "-c", script, junit, test, output / "agent-preflight-report.md"], root, env, commands)
    locks = write_candidate_locks(output, report)
    return {"status": "passed", "agent_head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=agent_root, text=True).strip(),
        "candidate_locks": locks.name}


def write_candidate_locks(output, report):
    packages = report["checks"]["parallel"]["packages"]
    version = next(item["version"] for item in packages if item["name"].lower() == "aitest-kit")
    locks = output / "agent-candidate-locks"
    locks.mkdir(exist_ok=True)
    (locks / "cloud-test-toolchain.json").write_text(json.dumps({
        "schema_version": 1, "aitest_kit": {"version": version, "wheel_sha256": report["sha256"]},
    }, indent=2) + "\n", encoding="utf-8")
    requirements = "\n".join(
        f"{item['name'].lower().replace('_', '-')}=={item['version']}"
        for item in packages if item["name"].lower() != "pip"
    )
    (locks / "cloud-test-requirements.txt").write_text(requirements + "\n", encoding="utf-8")
    return locks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-wheel", type=Path)
    parser.add_argument("--agent-root", type=Path)
    args = parser.parse_args()
    wheel = select_wheel(args.wheel_dir.resolve())
    sdist = wheel.with_name(wheel.name.removesuffix("-py3-none-any.whl") + ".tar.gz")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"status": "failed", "platform": platform.platform(), "wheel": wheel.name,
              "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
              "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_has_local_changes": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "checks": {}}
    try:
        for artifact in (wheel, sdist):
            inspect_archive(artifact)
        with tempfile.TemporaryDirectory(prefix="aitest-log-wheel-") as directory:
            root = Path(directory)
            baseline = None
            if args.baseline_wheel:
                baseline = install_wheel(root / "baseline", str(args.baseline_wheel.resolve()),
                                         clean_environment(root, dict(os.environ)), report.setdefault("baseline_commands", []))
            for mode in ("basic", "parallel"):
                env = clean_environment(root, dict(os.environ))
                commands = []
                report["checks"][mode] = {"commands": commands}
                install = str(wheel) + ("[parallel]" if mode == "parallel" else "")
                constraints = None
                if mode == "parallel" and args.agent_root:
                    origin = args.agent_root / "release/cloud-test-requirements.txt"
                    constraints = root / "agent-constraints.txt"
                    constraints.write_text("\n".join(line for line in origin.read_text().splitlines()
                                                     if not line.startswith("aitest-kit==")) + "\n", encoding="utf-8")
                python = install_wheel(root / mode, install, env, commands, constraints)
                installed = invoke([python, "-I", "-m", "pip", "list", "--format=json"], root, env, commands)
                report["checks"][mode]["packages"] = json.loads(installed)
                env.update(AITEST_ACCEPTANCE_PYTHON=str(python), AITEST_ACCEPTANCE_MODE=mode)
                if baseline:
                    env["AITEST_ACCEPTANCE_BASELINE_PYTHON"] = str(baseline)
                if constraints:
                    report["agent_probe"] = agent_probe(args.agent_root, python, root, env, commands, output, report)

                junit = output / f"{mode}.xml"
                invoke([python, "-I", "-m", "pytest", ROOT / "tests/log_assertions_acceptance", "-q",
                        "--junitxml", junit, "--basetemp", root / f"{mode}-runs"], root, env, commands)
                artifacts = output / mode
                for index, latest in enumerate(sorted((root / f"{mode}-runs").glob("test_*[0-9]/**/latest/result.json"))):
                    target = artifacts / str(index)
                    target.mkdir(parents=True, exist_ok=True)
                    for name in ("result.json", "report.md", "junit.xml"):
                        source = latest.with_name(name)
                        if source.is_file():
                            shutil.copyfile(source, target / name)
                suite = ET.parse(junit).find(".//testsuite")
                report["checks"][mode].update(junit=junit.name, results=dict(suite.attrib))
        report["status"] = "passed"
    finally:
        (output / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output / "acceptance.json")


if __name__ == "__main__":
    main()
