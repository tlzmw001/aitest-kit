"""Human-readable Case IR explanation rendering."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aitest_kit.codegen.ir import (
    AssertionIR,
    CaseFlowStepIR,
    CaseIR,
    ProfileVariableIR,
    RequestBindingIR,
    SourceTraceIR,
)


def render_case_explain(
    case_ir: CaseIR,
    *,
    suite: str,
    profile_path: str | Path | None = None,
) -> str:
    """Render one CaseIR as a compact review card."""
    lines: list[str] = []
    lines.extend(_case_header(case_ir, suite=suite, profile_path=profile_path))
    lines.extend(_strategy_section(case_ir))
    lines.extend(_request_section(case_ir))
    lines.extend(_case_flow_section(case_ir))
    lines.extend(_assertion_section(case_ir))
    lines.extend(_diagnostic_section(case_ir))
    lines.extend(_review_hint_section(case_ir))
    return "\n".join(lines).rstrip()


def _case_header(
    case_ir: CaseIR,
    *,
    suite: str,
    profile_path: str | Path | None,
) -> list[str]:
    lines = [
        f"Case: {case_ir.case_id}",
        f"Title: {case_ir.title}",
        "Source:",
        f"  module: {case_ir.module}",
        f"  suite: {suite}",
        f"  file: {case_ir.source_file}",
    ]
    if profile_path:
        lines.append(f"  profile: {profile_path}")
    if case_ir.section:
        lines.append(f"  section: {case_ir.section}")
    if case_ir.priority:
        lines.append(f"  priority: {case_ir.priority}")
    if case_ir.markers:
        lines.append(f"  markers: {', '.join(case_ir.markers)}")
    return lines + [""]


def _strategy_section(case_ir: CaseIR) -> list[str]:
    lines = ["Strategy:"]
    strategy = case_ir.source_trace.get("strategy")
    lines.extend(_trace_lines("  ", "strategy", strategy, fallback=case_ir.strategy))
    protocol = case_ir.source_trace.get("protocol")
    lines.extend(_trace_lines("  ", "protocol", protocol, fallback=case_ir.protocol))
    fixtures = case_ir.source_trace.get("fixtures")
    lines.extend(_trace_lines("  ", "fixtures", fixtures, fallback=case_ir.fixtures))
    if case_ir.skip_reason:
        lines.append(f"  skip_reason: {case_ir.skip_reason}")
    if case_ir.profile_variables:
        lines.append("  profile_variables:")
        for variable in case_ir.profile_variables:
            suffix = f" env={variable.env}" if variable.env else ""
            lines.append(
                f"    - {variable.name}: provider={variable.provider} "
                f"source={variable.source}{suffix}"
            )
    return lines + [""]


def _request_section(case_ir: CaseIR) -> list[str]:
    lines = ["Request bindings:"]
    if not case_ir.request_bindings:
        lines.append("  none")
        return lines + [""]

    variables = _profile_variable_map(case_ir)
    for case_id, binding in sorted(case_ir.request_bindings.items()):
        lines.append(f"  {case_id}:")
        lines.extend(_request_binding_lines(binding, indent="    ", variables=variables))
    review_lines = _request_review_lines(case_ir, variables)
    if review_lines:
        lines.append("")
        lines.append("Request review:")
        lines.extend(f"  - {line}" for line in review_lines)
    return lines + [""]


def _request_binding_lines(
    binding: RequestBindingIR,
    *,
    indent: str,
    variables: dict[str, ProfileVariableIR],
) -> list[str]:
    lines = [
        f"{indent}source: {binding.source}",
        f"{indent}base_source: {binding.base_source}",
    ]
    if binding.auto_fields:
        lines.append(f"{indent}auto_fields: {_compact(binding.auto_fields)}")
    if binding.overrides:
        lines.append(f"{indent}overrides: {_compact(binding.overrides)}")
    if binding.patches:
        lines.append(f"{indent}patches:")
        for patch in binding.patches:
            value = f" value={_compact(patch.value)}" if patch.has_value else ""
            value_from = ""
            if patch.value_from:
                detail = _value_from_detail(patch.value_from, variables)
                value_from = f" value_from={patch.value_from}{detail}"
            lines.append(f"{indent}  - {patch.op} {patch.path}{value}{value_from}")
    return lines


def _profile_variable_map(case_ir: CaseIR) -> dict[str, ProfileVariableIR]:
    return {variable.name: variable for variable in case_ir.profile_variables}


def _value_from_detail(
    name: str,
    variables: dict[str, ProfileVariableIR],
) -> str:
    variable = variables.get(name)
    if variable is None:
        return " (undefined profile variable)"
    parts = [f"provider={variable.provider}"]
    if variable.env:
        parts.append(f"env={variable.env}")
    parts.append(f"source={variable.source}")
    return " (" + " ".join(parts) + ")"


def _request_review_lines(
    case_ir: CaseIR,
    variables: dict[str, ProfileVariableIR],
) -> list[str]:
    patch_count = 0
    override_count = 0
    env_names: set[str] = set()
    value_names: set[str] = set()
    undefined_names: set[str] = set()
    pointer_paths: set[str] = set()

    for binding in case_ir.request_bindings.values():
        if binding.overrides:
            override_count += 1
        for patch in binding.patches:
            patch_count += 1
            if _needs_json_pointer_review(patch.path):
                pointer_paths.add(patch.path)
            if not patch.value_from:
                continue
            variable = variables.get(patch.value_from)
            if variable is None:
                undefined_names.add(patch.value_from)
            elif variable.provider == "env" and variable.env:
                env_names.add(variable.env)
            else:
                value_names.add(variable.name)

    lines: list[str] = []
    if override_count:
        lines.append(f"uses request overrides: {override_count}")
    if patch_count:
        lines.append(f"uses request patches: {patch_count}")
    if env_names:
        lines.append("uses env variables: " + ", ".join(sorted(env_names)))
    if value_names:
        lines.append("uses profile variable values: " + ", ".join(sorted(value_names)))
    if undefined_names:
        lines.append("has undefined value_from variables: " + ", ".join(sorted(undefined_names)))
    if pointer_paths:
        lines.append("review JSON Pointer paths: " + ", ".join(sorted(pointer_paths)))
    return lines


def _needs_json_pointer_review(path: str) -> bool:
    if path.endswith("/-"):
        return True
    parts = [part for part in path.split("/") if part]
    return len(parts) > 1 or any(part.isdigit() for part in parts)


def _case_flow_section(case_ir: CaseIR) -> list[str]:
    lines = ["Case flow:"]
    if not case_ir.case_flow:
        lines.append("  none")
        return lines + [""]

    flow = case_ir.case_flow
    lines.append(f"  source: {flow.source}")
    if flow.fixture:
        lines.append(f"  fixture: {flow.fixture}")
    if flow.object_name:
        lines.append(f"  object: {flow.object_name}")
    if not flow.steps:
        lines.append("  steps: none")
        return lines + [""]

    lines.append("  steps:")
    for index, step in enumerate(flow.steps, start=1):
        lines.append(f"    {index}. {_step_summary(step)}")
        if step.assertion and step.assertion.code_lines:
            for code_line in step.assertion.code_lines:
                lines.append(f"       code: {code_line}")
    return lines + [""]


def _step_summary(step: CaseFlowStepIR) -> str:
    if step.kind == "call":
        args = ", ".join(_compact(arg) for arg in step.args)
        kwargs = ", ".join(f"{key}={_compact(value)}" for key, value in step.kwargs.items())
        params = ", ".join(item for item in [args, kwargs] if item)
        suffix = f" -> {step.save_as}" if step.save_as else ""
        return f"call {step.call}({params}){suffix}"
    if step.kind == "assign":
        return f"assign {step.target} = {step.expr}"
    if step.kind == "assert" and step.assertion:
        return (
            f"assert [{step.assertion.kind}] {step.assertion.source} "
            f"resolved_by={step.assertion.resolved_by}"
        )
    if step.kind == "comment":
        return f"comment {step.comment}"
    return step.kind


def _assertion_section(case_ir: CaseIR) -> list[str]:
    lines = ["Assertions:"]
    assertions = list(case_ir.assertions)
    if not assertions:
        lines.append("  none")
        return lines + [""]

    for assertion in assertions:
        lines.extend(_assertion_lines(assertion, indent="  "))
    return lines + [""]


def _assertion_lines(assertion: AssertionIR, *, indent: str) -> list[str]:
    lines = [
        f"{indent}- kind: {assertion.kind}",
        f"{indent}  source: {assertion.source}",
        f"{indent}  resolved_by: {assertion.resolved_by or 'none'}",
    ]
    if assertion.variables:
        lines.append(f"{indent}  variables: {', '.join(assertion.variables)}")
    if assertion.metadata:
        lines.append(f"{indent}  metadata:")
        for key, value in assertion.metadata.items():
            lines.append(f"{indent}    {key}: {_compact(value)}")
    if assertion.code_lines:
        lines.append(f"{indent}  generated:")
        for code_line in assertion.code_lines:
            lines.append(f"{indent}    {code_line}")
    return lines


def _diagnostic_section(case_ir: CaseIR) -> list[str]:
    lines = ["Diagnostics:"]
    if not case_ir.diagnostics:
        lines.append("  none")
        return lines + [""]
    for diagnostic in case_ir.diagnostics:
        lines.append(f"  - {diagnostic.code} {diagnostic.layer}: {diagnostic.message}")
    return lines + [""]


def _review_hint_section(case_ir: CaseIR) -> list[str]:
    hints: list[str] = []
    if case_ir.diagnostics:
        hints.append("Fix diagnostics before relying on generated pytest.")
    if _has_unparsed(case_ir):
        hints.append(
            "Fix UNPARSED assertions in Markdown/profile. Prefer structured_assertions "
            "for JSONPath/list checks or fixture/helper methods for business logic."
        )
    if case_ir.strategy == "custom_case_body":
        hints.append(
            "Review whether this case_body can stay as an escape hatch or be moved "
            "to case_flow plus fixture/helper calls."
        )
    elif case_ir.strategy == "manual":
        hints.append("Manual case: generated pytest will document it but not automate it by default.")
    elif case_ir.strategy == "skipped":
        hints.append("Skipped case: confirm the skip reason is intentional.")
    elif not hints:
        hints.append("OK: this case has a deterministic codegen path.")
    return ["Review hint:"] + [f"  - {hint}" for hint in hints]


def _has_unparsed(case_ir: CaseIR) -> bool:
    if any(assertion.kind == "unparsed" for assertion in case_ir.assertions):
        return True
    if case_ir.case_flow:
        return any(
            step.assertion is not None and step.assertion.kind == "unparsed"
            for step in case_ir.case_flow.steps
        )
    return False


def _trace_lines(
    indent: str,
    label: str,
    trace: SourceTraceIR | None,
    *,
    fallback: Any,
) -> list[str]:
    if trace is None:
        return [f"{indent}{label}: {_compact(fallback)}"]
    prefix = f"{indent}{label}:"
    lines = [f"{prefix} {_compact(trace.value)}"]
    if trace.source:
        lines.append(f"{indent}{label}_source: {trace.source}")
    if trace.reason:
        lines.append(f"{indent}{label}_reason: {trace.reason}")
    return lines


def _compact(value: Any) -> str:
    if isinstance(value, str):
        return value
    return repr(value)
