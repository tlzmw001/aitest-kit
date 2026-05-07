"""Codegen health and maturity reporting."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.codegen.ir import AssertionIR, FileIR
from aitest_kit.codegen.parser import parse_case_file
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.profile_validator import (
    ProfileValidationReport,
    validate_profile_module,
)
from aitest_kit.codegen.project_config import load_project_config


@dataclass
class ModuleHealth:
    module: str
    case_count: int = 0
    file_count: int = 0
    profile_errors: int = 0
    profile_warnings: int = 0
    strategy_counts: Counter[str] = field(default_factory=Counter)
    protocol_counts: Counter[str] = field(default_factory=Counter)
    assertion_kind_counts: Counter[str] = field(default_factory=Counter)
    assertion_resolved_by_counts: Counter[str] = field(default_factory=Counter)
    diagnostic_count: int = 0
    maturity: str = "L0"

    @property
    def case_body_count(self) -> int:
        return self.strategy_counts.get("custom_case_body", 0)

    @property
    def case_flow_count(self) -> int:
        return self.strategy_counts.get("structured_case_flow", 0)

    @property
    def unparsed_count(self) -> int:
        return self.assertion_kind_counts.get("unparsed", 0)


@dataclass
class CodegenHealthReport:
    modules: list[ModuleHealth]

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def case_count(self) -> int:
        return sum(module.case_count for module in self.modules)

    @property
    def error_count(self) -> int:
        return sum(module.profile_errors for module in self.modules)

    @property
    def warning_count(self) -> int:
        return sum(module.profile_warnings for module in self.modules)


def build_codegen_health_report(
    modules: list[str],
    cases_dir: Path,
    *,
    profile_dir: str | Path = "test_workspace/tests/fixtures",
    project: Any | None = None,
) -> CodegenHealthReport:
    project_config = project or load_project_config()
    profile_root = Path(profile_dir)
    items: list[ModuleHealth] = []
    for module in modules:
        validation = validate_profile_module(
            module,
            cases_dir=cases_dir,
            profile_dir=profile_root,
            project=project_config,
        )
        file_irs = _build_module_file_irs(module, cases_dir, profile_root, project_config)
        items.append(_module_health(module, validation, file_irs))
    return CodegenHealthReport(items)


def codegen_health_to_dict(report: CodegenHealthReport) -> dict[str, Any]:
    return {
        "module_count": report.module_count,
        "case_count": report.case_count,
        "profile_error_count": report.error_count,
        "profile_warning_count": report.warning_count,
        "modules": [_module_health_to_dict(module) for module in report.modules],
    }


def render_codegen_health_markdown(report: CodegenHealthReport) -> str:
    lines = [
        "# Codegen Health Report",
        "",
        f"- Modules: {report.module_count}",
        f"- Cases: {report.case_count}",
        f"- Profile errors: {report.error_count}",
        f"- Profile warnings: {report.warning_count}",
        "",
        "| Module | Cases | Maturity | case_flow | case_body | UNPARSED | Profile |",
        "|--------|-------|----------|-----------|-----------|----------|---------|",
    ]
    for module in report.modules:
        profile = f"{module.profile_errors}E/{module.profile_warnings}W"
        lines.append(
            f"| `{module.module}` | {module.case_count} | {module.maturity} | "
            f"{module.case_flow_count} | {module.case_body_count} | "
            f"{module.unparsed_count} | {profile} |"
        )

    lines.extend(["", "## Strategy Counts", ""])
    for module in report.modules:
        lines.append(f"### {module.module}")
        lines.append("")
        lines.extend(_counter_lines("strategy", module.strategy_counts))
        lines.extend(_counter_lines("assertion", module.assertion_kind_counts))
        if module.assertion_resolved_by_counts:
            lines.append("- resolved_by:")
            for key, value in sorted(module.assertion_resolved_by_counts.items()):
                lines.append(f"  - `{key}`: {value}")
        lines.append("")
    return "\n".join(lines)


def write_codegen_health_report(
    report: CodegenHealthReport,
    output_dir: str | Path,
) -> dict[str, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "codegen_health_report.md"
    json_path = out_dir / "codegen_health_report.json"
    md_path.write_text(render_codegen_health_markdown(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(codegen_health_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"markdown": md_path, "json": json_path}


def _build_module_file_irs(
    module: str,
    cases_dir: Path,
    profile_dir: Path,
    project: Any,
) -> list[FileIR]:
    profile_path = profile_dir / f"codegen_profile_{module}.md"
    if not profile_path.exists():
        profile_path = None
    file_irs: list[FileIR] = []
    for file_type in ("business", "boundary"):
        md_path = cases_dir / module / f"{file_type}.md"
        if md_path.exists():
            file_irs.append(build_file_ir(
                parse_case_file(md_path),
                file_type,
                profile_path=profile_path,
                project=project,
            ))
    return file_irs


def _module_health(
    module: str,
    validation: ProfileValidationReport,
    file_irs: list[FileIR],
) -> ModuleHealth:
    health = ModuleHealth(
        module=module,
        file_count=len(file_irs),
        profile_errors=len(validation.errors),
        profile_warnings=len(validation.warnings),
    )
    for file_ir in file_irs:
        health.diagnostic_count += len(file_ir.diagnostics)
        for case_ir in file_ir.cases:
            health.case_count += 1
            health.strategy_counts[case_ir.strategy] += 1
            health.protocol_counts[case_ir.protocol] += 1
            health.diagnostic_count += len(case_ir.diagnostics)
            for assertion in case_ir.assertions:
                _count_assertion(health, assertion)
            if case_ir.case_flow:
                for step in case_ir.case_flow.steps:
                    if step.assertion:
                        _count_assertion(health, step.assertion)
    health.maturity = _maturity_for(health)
    return health


def _count_assertion(health: ModuleHealth, assertion: AssertionIR) -> None:
    health.assertion_kind_counts[assertion.kind] += 1
    if assertion.resolved_by:
        health.assertion_resolved_by_counts[assertion.resolved_by] += 1


def _maturity_for(health: ModuleHealth) -> str:
    if health.profile_errors:
        return "L0"
    if health.unparsed_count:
        return "L1"
    if health.case_flow_count:
        return "L3"
    return "L2"


def _module_health_to_dict(module: ModuleHealth) -> dict[str, Any]:
    return {
        "module": module.module,
        "case_count": module.case_count,
        "file_count": module.file_count,
        "profile_errors": module.profile_errors,
        "profile_warnings": module.profile_warnings,
        "case_body_count": module.case_body_count,
        "case_flow_count": module.case_flow_count,
        "unparsed_count": module.unparsed_count,
        "diagnostic_count": module.diagnostic_count,
        "maturity": module.maturity,
        "strategy_counts": dict(sorted(module.strategy_counts.items())),
        "protocol_counts": dict(sorted(module.protocol_counts.items())),
        "assertion_kind_counts": dict(sorted(module.assertion_kind_counts.items())),
        "assertion_resolved_by_counts": dict(sorted(module.assertion_resolved_by_counts.items())),
    }


def _counter_lines(label: str, counter: Counter[str]) -> list[str]:
    if not counter:
        return [f"- {label}: none"]
    return [f"- {label}.{key}: {value}" for key, value in sorted(counter.items())]
