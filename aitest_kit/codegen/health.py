"""Codegen health and maturity reporting."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.codegen.ir import AssertionIR, FileIR
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.profile_validator import (
    ProfileValidationReport,
    validate_profile_suite,
)
from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.codegen.suite import SuiteContext, parse_suite_case_file


@dataclass
class ModuleHealth:
    module: str
    suite: str | None = None
    case_count: int = 0
    file_count: int = 0
    profile_errors: int = 0
    profile_warnings: int = 0
    strategy_counts: Counter[str] = field(default_factory=Counter)
    protocol_counts: Counter[str] = field(default_factory=Counter)
    assertion_kind_counts: Counter[str] = field(default_factory=Counter)
    assertion_resolved_by_counts: Counter[str] = field(default_factory=Counter)
    structured_assertion_target_counts: Counter[str] = field(default_factory=Counter)
    request_binding_counts: Counter[str] = field(default_factory=Counter)
    unparsed_cases: list[dict[str, Any]] = field(default_factory=list)
    manual_cases: list[dict[str, Any]] = field(default_factory=list)
    case_body_cases: list[dict[str, Any]] = field(default_factory=list)
    structured_assertion_cases: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
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


def build_suite_codegen_health_report(
    context: SuiteContext,
    *,
    project: Any | None = None,
) -> CodegenHealthReport:
    project = project or load_project_config()
    validation = validate_profile_suite(
        context.suite_dir,
        profile_dir=context.module_profile_path.parent,
        project=project,
    )
    file_irs = _build_suite_file_irs(context, project)
    return CodegenHealthReport([
        _module_health(context.module, validation, file_irs, suite=context.suite)
    ])


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
        module_name = f"{module.module}/{module.suite}" if module.suite else module.module
        lines.append(
            f"| `{module_name}` | {module.case_count} | {module.maturity} | "
            f"{module.case_flow_count} | {module.case_body_count} | "
            f"{module.unparsed_count} | {profile} |"
        )

    lines.extend(["", "## Strategy Counts", ""])
    for module in report.modules:
        module_name = f"{module.module}/{module.suite}" if module.suite else module.module
        lines.append(f"### {module_name}")
        lines.append("")
        lines.extend(_counter_lines("strategy", module.strategy_counts))
        lines.extend(_counter_lines("assertion", module.assertion_kind_counts))
        if module.assertion_resolved_by_counts:
            lines.append("- resolved_by:")
            for key, value in sorted(module.assertion_resolved_by_counts.items()):
                lines.append(f"  - `{key}`: {value}")
        if module.structured_assertion_target_counts:
            lines.append("- structured_assertion_targets:")
            for key, value in sorted(module.structured_assertion_target_counts.items()):
                lines.append(f"  - `{key}`: {value}")
        if module.request_binding_counts:
            lines.append("- request_bindings:")
            for key, value in sorted(module.request_binding_counts.items()):
                lines.append(f"  - `{key}`: {value}")
        lines.append("")
        if module.unparsed_cases:
            lines.append("#### UNPARSED Cases")
            lines.append("")
            for item in module.unparsed_cases:
                lines.append(f"- `{item['case_id']}`: {item['source']}")
            lines.append("")
        if module.manual_cases:
            lines.append("#### Manual Cases")
            lines.append("")
            for item in module.manual_cases:
                lines.append(f"- `{item['case_id']}`: {item['title']}")
            lines.append("")
        if module.case_body_cases:
            lines.append("#### Case Body Cases")
            lines.append("")
            for item in module.case_body_cases:
                lines.append(f"- `{item['case_id']}`: {item['title']}")
            lines.append("")
        if module.next_actions:
            lines.append("#### Next Actions")
            lines.append("")
            for action in module.next_actions:
                lines.append(f"- {action}")
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


def _build_suite_file_irs(
    context: SuiteContext,
    project: Any,
) -> list[FileIR]:
    file_irs: list[FileIR] = []
    for md_path in context.case_files:
        file_irs.append(build_file_ir(
            parse_suite_case_file(md_path, context.module),
            md_path.stem,
            profile_path=context.runtime_profile,
            project=project,
        ))
    return file_irs


def _module_health(
    module: str,
    validation: ProfileValidationReport,
    file_irs: list[FileIR],
    *,
    suite: str | None = None,
) -> ModuleHealth:
    health = ModuleHealth(
        module=module,
        suite=suite,
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
            _count_case_attention(health, case_ir)
            _count_request_bindings(health, case_ir)
            for assertion in case_ir.assertions:
                _count_assertion(health, assertion)
            if case_ir.case_flow:
                for step in case_ir.case_flow.steps:
                    if step.assertion:
                        _count_assertion(health, step.assertion)
    health.maturity = _maturity_for(health)
    health.next_actions = _next_actions_for(health)
    return health


def _count_assertion(health: ModuleHealth, assertion: AssertionIR) -> None:
    health.assertion_kind_counts[assertion.kind] += 1
    if assertion.resolved_by:
        health.assertion_resolved_by_counts[assertion.resolved_by] += 1
    if assertion.kind == "structured_assertion":
        target = _structured_assertion_target(assertion)
        if target:
            health.structured_assertion_target_counts[target] += 1


def _count_case_attention(health: ModuleHealth, case_ir: Any) -> None:
    if case_ir.strategy == "manual":
        health.manual_cases.append(_case_ref(case_ir))
    if case_ir.strategy == "custom_case_body":
        health.case_body_cases.append(_case_ref(case_ir))

    structured_count = sum(
        1 for assertion in case_ir.assertions
        if assertion.kind == "structured_assertion"
    )
    if structured_count:
        item = _case_ref(case_ir)
        item["count"] = structured_count
        health.structured_assertion_cases.append(item)

    for source in _unparsed_sources(case_ir):
        item = _case_ref(case_ir)
        item["source"] = source
        health.unparsed_cases.append(item)


def _count_request_bindings(health: ModuleHealth, case_ir: Any) -> None:
    if not case_ir.request_bindings:
        health.request_binding_counts["none"] += 1
        return
    for binding in case_ir.request_bindings.values():
        if binding.auto_fields:
            health.request_binding_counts["default_request.auto_fields"] += 1
        if binding.overrides:
            health.request_binding_counts["profile.requests.overrides"] += 1
        if binding.patches:
            health.request_binding_counts["profile.requests.patches"] += 1
        if not binding.auto_fields and not binding.overrides and not binding.patches:
            health.request_binding_counts["base_only"] += 1


def _case_ref(case_ir: Any) -> dict[str, Any]:
    return {
        "case_id": case_ir.case_id,
        "title": case_ir.title,
        "source_file": case_ir.source_file,
    }


def _unparsed_sources(case_ir: Any) -> list[str]:
    sources = [
        assertion.source for assertion in case_ir.assertions
        if assertion.kind == "unparsed"
    ]
    if case_ir.case_flow:
        sources.extend(
            step.assertion.source
            for step in case_ir.case_flow.steps
            if step.assertion is not None and step.assertion.kind == "unparsed"
        )
    return sources


def _structured_assertion_target(assertion: AssertionIR) -> str:
    target = assertion.metadata.get("target")
    return str(target) if target else ""


def _next_actions_for(health: ModuleHealth) -> list[str]:
    actions: list[str] = []
    if health.profile_errors:
        actions.append("P0: fix profile errors before codegen.")
    if health.unparsed_cases:
        actions.append(
            f"P0: fix {len(health.unparsed_cases)} UNPARSED assertion(s) in "
            "Markdown/profile/assertion rules."
        )
    if health.case_body_cases:
        actions.append(
            f"P1: review {len(health.case_body_cases)} case_body case(s); keep as "
            "escape hatch or move stable parts to case_flow/helper."
        )
    if health.manual_cases:
        actions.append(
            f"P1: review {len(health.manual_cases)} manual case(s) and confirm they "
            "should remain manual."
        )
    if not actions:
        actions.append("OK: no immediate codegen health action.")
    return actions


def _maturity_for(health: ModuleHealth) -> str:
    if health.profile_errors:
        return "L0"
    if health.unparsed_count:
        return "L1"
    if health.case_flow_count:
        return "L3"
    return "L2"


def _module_health_to_dict(module: ModuleHealth) -> dict[str, Any]:
    result = {
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
        "structured_assertion_target_counts": dict(sorted(module.structured_assertion_target_counts.items())),
        "request_binding_counts": dict(sorted(module.request_binding_counts.items())),
        "unparsed_cases": module.unparsed_cases,
        "manual_cases": module.manual_cases,
        "case_body_cases": module.case_body_cases,
        "structured_assertion_cases": module.structured_assertion_cases,
        "next_actions": module.next_actions,
    }
    if module.suite:
        result["suite"] = module.suite
    return result


def _counter_lines(label: str, counter: Counter[str]) -> list[str]:
    if not counter:
        return [f"- {label}: none"]
    return [f"- {label}.{key}: {value}" for key, value in sorted(counter.items())]
