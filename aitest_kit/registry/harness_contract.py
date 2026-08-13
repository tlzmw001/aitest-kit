"""Static checks for the canonical module Harness contract."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from aitest_kit.registry.models import ModuleContext


@dataclass
class HarnessContractReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def expected_harness_name(module: str) -> str:
    """Return the public Harness class name for a module identifier."""
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", module) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) + "Harness"


def validate_harness_contract(module: ModuleContext) -> HarnessContractReport:
    """Validate one module package without importing user code."""
    report = HarnessContractReport()
    package_dir = module.package_dir
    required = (
        package_dir / "__init__.py",
        module.fixture_path,
        module.harness_path,
        module.profile_path,
    )
    for path in required:
        if not path.exists():
            report.errors.append(f"required module asset not found: {path}")

    if not module.fixture_path.exists() or not module.harness_path.exists():
        return report

    fixture_tree = _parse_python(module.fixture_path, report)
    harness_tree = _parse_python(module.harness_path, report)
    if fixture_tree is None or harness_tree is None:
        return report

    fixture_name = module.binding.fixture_name
    harness_name = expected_harness_name(module.module)
    fixture_functions = {
        node.name: node
        for node in fixture_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_pytest_fixture(node)
    }
    fixture = fixture_functions.get(fixture_name)
    if fixture is None:
        report.errors.append(
            f"fixture.py must define @pytest.fixture {fixture_name}"
        )
    else:
        if not _function_produces_value(fixture):
            report.errors.append(
                f"{fixture_name} must return or yield {harness_name}"
            )
        annotation = ast.unparse(fixture.returns) if fixture.returns is not None else ""
        if harness_name not in annotation:
            report.errors.append(
                f"{fixture_name} return annotation must reference {harness_name}"
            )

    extra_public = sorted(
        name
        for name in fixture_functions
        if name != fixture_name and not name.startswith("_")
    )
    if extra_public:
        report.errors.append(
            "fixture.py exposes additional public pytest fixtures: "
            + ", ".join(extra_public)
        )

    harness_classes = {
        node.name
        for node in harness_tree.body
        if isinstance(node, ast.ClassDef)
    }
    if harness_name not in harness_classes:
        report.errors.append(
            f"harness.py must define {harness_name}"
        )

    source = (
        module.fixture_path.read_text(encoding="utf-8")
        + "\n"
        + module.harness_path.read_text(encoding="utf-8")
    )
    if re.search(r"\bcase_id\b", source):
        report.warnings.append(
            "fixture/Harness references case_id; keep case-specific data and branching in the suite profile"
        )
    for path in (module.fixture_path, module.harness_path):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 500:
            report.warnings.append(
                f"{path} has {line_count} lines; split module capabilities by responsibility"
            )
    return report


def _parse_python(path: Path, report: HarnessContractReport) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        report.errors.append(f"invalid Python in {path}: {exc.msg} (line {exc.lineno})")
        return None


def _is_pytest_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
    return False


def _function_produces_value(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, (ast.Yield, ast.YieldFrom)):
            return True
        if isinstance(child, ast.Return) and child.value is not None:
            return True
    return False
