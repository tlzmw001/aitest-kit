"""Pre-generation validation for codegen profiles."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from aitest_kit.codegen.parser import parse_case_file
from aitest_kit.codegen.profile import (
    apply_case_flow_defaults,
    case_flow_defaults_from_yaml,
    load_profile_yaml,
    validate_case_flows,
    validate_profile_strategy_conflicts,
)
from aitest_kit.codegen.profile_variables import (
    validate_case_flow_variable_references,
    validate_profile_variables,
)
from aitest_kit.codegen.project_config import ProjectConfig, load_project_config
from aitest_kit.codegen.profile_schema import profile_schema_diagnostics
from aitest_kit.codegen.profile_validation_report import (
    ProfileValidationDiagnostic,
    ProfileValidationReport,
    profile_validation_to_dict,
    render_profile_validation_markdown,
    write_profile_validation_report,
)
from aitest_kit.codegen.suite import load_suite_context, parse_suite_case_file


_YAML_BLOCK_RE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)
_CASE_ID_RE = re.compile(r"^TC-[A-Z0-9]+-\d+$")
_TOP_LEVEL_KEYS = {
    "module_type",
    "profile_scope",
    "parent_module",
    "parent_profile",
    "suite",
    "knowledge_refs",
    "default_fixture",
    "default_object",
    "default_case_setup",
    "assertion_rules",
    "variables",
    "request_overrides",
    "extra_imports",
    "case_fixtures",
    "case_bodies",
    "case_flows",
}


def validate_profile_module(
    module: str,
    *,
    cases_dir: str | Path = "test_workspace/cases",
    profile_dir: str | Path = "test_workspace/tests/fixtures",
    project: ProjectConfig | None = None,
) -> ProfileValidationReport:
    """Validate one module profile without generating pytest."""
    cases_root = Path(cases_dir)
    profile_path = Path(profile_dir) / f"codegen_profile_{module}.md"
    report = ProfileValidationReport(module=module, profile_path=profile_path)
    project_config = project or load_project_config()

    _collect_markdown_cases(report, cases_root / module)
    if not profile_path.exists():
        _warn(report, "W501", "codegen profile not found", str(profile_path))
        return report

    data = _load_profile_yaml_strict(report)
    if data is None:
        return report

    _validate_profile_schema(report, data)
    _validate_top_level_shape(report, data)
    case_bodies = _mapping(data, "case_bodies")
    case_flows = _mapping(data, "case_flows")
    case_fixtures = _mapping(data, "case_fixtures")
    request_overrides = _mapping(data, "request_overrides")
    variables = _mapping(data, "variables")
    case_flow_defaults = case_flow_defaults_from_yaml(data)
    normalized_case_flows = apply_case_flow_defaults(case_flows, case_flow_defaults)

    for message in validate_profile_strategy_conflicts(case_bodies, case_flows):
        _error(report, "E502", message)
    for message in validate_case_flows(case_flows, case_flow_defaults):
        _error(report, "E503", message)
    for message in validate_profile_variables(variables):
        _error(report, "E501", message)
    for message in validate_case_flow_variable_references(normalized_case_flows, variables):
        _error(report, "E507", message)

    _validate_case_references(report, "case_bodies", case_bodies)
    _validate_case_references(report, "case_flows", case_flows)
    _validate_case_references(report, "case_fixtures", case_fixtures)
    _validate_case_references(report, "request_overrides", request_overrides)
    _validate_case_references(report, "variables.cases", _variable_cases(variables))
    _warn_feasibility_suspect_strategies(report, case_bodies, case_flows)
    _warn_fixture_reinvocation(report, normalized_case_flows)
    _validate_module_type(report, data, project_config, case_bodies, normalized_case_flows)
    return report


def validate_profile_suite(
    cases_path: str | Path,
    *,
    module: str | None = None,
    profile_dir: str | Path = "test_workspace/tests/fixtures",
    project: ProjectConfig | None = None,
) -> ProfileValidationReport:
    """Validate one case suite plus its module and suite profiles."""
    context = load_suite_context(cases_path, module_override=module, profile_dir=profile_dir)
    report = ProfileValidationReport(
        module=context.module or module or "",
        suite=context.suite,
        profile_path=context.suite_profile_path,
    )
    project_config = project or load_project_config()

    _collect_suite_markdown_cases(report, context.case_files, context.module)
    for message in context.diagnostics:
        _error(report, _diagnostic_code(message), message)

    module_data = None
    if context.module_profile_path.exists():
        module_data = _load_profile_yaml_strict_from(report, context.module_profile_path)
        if module_data is not None:
            _validate_profile_schema(report, module_data)
            _validate_top_level_shape(report, module_data)

    suite_data = {}
    if context.suite_profile_path.exists():
        loaded_suite = _load_profile_yaml_strict_from(report, context.suite_profile_path)
        if loaded_suite is not None:
            suite_data = loaded_suite
            _validate_profile_schema(report, suite_data)
            _validate_top_level_shape(report, suite_data)

    runtime_data = context.runtime_profile.data
    if module_data is not None:
        runtime_data = load_profile_yaml(context.runtime_profile)

    suite_case_bodies = _mapping(suite_data, "case_bodies")
    suite_case_flows = _mapping(suite_data, "case_flows")
    suite_case_fixtures = _mapping(suite_data, "case_fixtures")
    suite_request_overrides = _mapping(suite_data, "request_overrides")
    suite_variables = _mapping(suite_data, "variables")
    runtime_case_bodies = _mapping(runtime_data, "case_bodies")
    runtime_case_flows = apply_case_flow_defaults(
        _mapping(runtime_data, "case_flows"),
        case_flow_defaults_from_yaml(runtime_data),
    )
    runtime_variables = _mapping(runtime_data, "variables")

    for message in validate_profile_strategy_conflicts(suite_case_bodies, suite_case_flows):
        _error(report, "E502", message)
    for message in validate_case_flows(runtime_case_flows):
        _error(report, "E503", message)
    for message in validate_profile_variables(suite_variables):
        _error(report, "E501", message)

    _validate_case_references(report, "case_bodies", suite_case_bodies)
    _validate_case_references(report, "case_flows", suite_case_flows)
    _validate_case_references(report, "case_fixtures", suite_case_fixtures)
    _validate_case_references(report, "request_overrides", suite_request_overrides)
    _validate_case_references(report, "variables.cases", _variable_cases(suite_variables))
    _warn_feasibility_suspect_strategies(report, suite_case_bodies, suite_case_flows)
    _warn_fixture_reinvocation(report, runtime_case_flows)
    for message in validate_case_flow_variable_references(runtime_case_flows, runtime_variables):
        _error(report, "E507", message)
    _validate_module_type(report, runtime_data, project_config, runtime_case_bodies, runtime_case_flows)
    _validate_suite_default_coverage(report, context, runtime_case_bodies, runtime_case_flows)
    return report


def _collect_markdown_cases(report: ProfileValidationReport, module_dir: Path) -> None:
    if not module_dir.exists():
        _error(report, "E510", "module case directory not found", str(module_dir))
        return

    for file_type in ("business", "boundary"):
        md_path = module_dir / f"{file_type}.md"
        if not md_path.exists():
            continue
        report.case_files.append(md_path)
        parse_result = parse_case_file(md_path)
        for parser_error in parse_result.errors:
            _error(report, "E001", parser_error, str(md_path))
        for tc in parse_result.cases:
            report.case_ids.add(tc.id)
            report.case_markers[tc.id] = list(tc.markers)

    if not report.case_files:
        _error(report, "E511", "module has no business.md or boundary.md", str(module_dir))


def _collect_suite_markdown_cases(
    report: ProfileValidationReport,
    case_files: list[Path],
    module: str,
) -> None:
    for md_path in case_files:
        report.case_files.append(md_path)
        parse_result = parse_suite_case_file(md_path, module)
        for parser_error in parse_result.errors:
            _error(report, "E001", parser_error, str(md_path))
        for tc in parse_result.cases:
            report.case_ids.add(tc.id)
            report.case_markers[tc.id] = list(tc.markers)

    if not report.case_files:
        _error(report, "E511", "suite has no Markdown case files")


def _diagnostic_code(message: str) -> str:
    match = re.match(r"^(E\d+):", message)
    return match.group(1) if match else "E610"


def _load_profile_yaml_strict(report: ProfileValidationReport) -> dict[str, Any] | None:
    return _load_profile_yaml_strict_from(report, report.profile_path)


def _load_profile_yaml_strict_from(
    report: ProfileValidationReport,
    profile_path: Path,
) -> dict[str, Any] | None:
    text = profile_path.read_text(encoding="utf-8")
    match = _YAML_BLOCK_RE.search(text)
    if not match:
        _error(report, "E501", "profile must contain one YAML code block", str(profile_path))
        return None

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        _error(report, "E501", f"profile YAML is invalid: {exc}", str(profile_path))
        return None

    if data is None:
        return {}
    if not isinstance(data, dict):
        _error(report, "E501", "profile YAML root must be a mapping", str(profile_path))
        return None
    return data


def _validate_profile_schema(report: ProfileValidationReport, data: dict[str, Any]) -> None:
    for message, source in profile_schema_diagnostics(data):
        _error(report, "E501", message, source)


def _validate_top_level_shape(report: ProfileValidationReport, data: dict[str, Any]) -> None:
    for key in data:
        if key not in _TOP_LEVEL_KEYS:
            _error(report, "E501", f"unknown top-level field {key}", key)

    _expect_mapping(report, data, "request_overrides")
    _expect_mapping(report, data, "case_fixtures")
    _expect_mapping(report, data, "case_bodies")
    _expect_mapping(report, data, "case_flows")
    _expect_mapping(report, data, "knowledge_refs")
    _expect_mapping(report, data, "variables")
    _expect_string(report, data, "module_type")
    _expect_string(report, data, "profile_scope")
    _expect_string(report, data, "parent_module")
    _expect_string(report, data, "parent_profile")
    _expect_string(report, data, "suite")
    _expect_string(report, data, "default_fixture")
    _expect_string(report, data, "default_object")
    _expect_mapping(report, data, "default_case_setup")
    _expect_string_list(report, data, "extra_imports")
    _expect_rule_list(report, data)
    _expect_case_fixture_values(report, _mapping(data, "case_fixtures"))
    _expect_case_body_values(report, _mapping(data, "case_bodies"))
    _expect_request_override_values(report, _mapping(data, "request_overrides"))


def _expect_mapping(report: ProfileValidationReport, data: dict[str, Any], key: str) -> None:
    if key in data and not isinstance(data[key], dict):
        _error(report, "E501", f"{key} must be a mapping", key)


def _expect_string(report: ProfileValidationReport, data: dict[str, Any], key: str) -> None:
    if key in data and not isinstance(data[key], str):
        _error(report, "E501", f"{key} must be a string", key)


def _expect_string_list(report: ProfileValidationReport, data: dict[str, Any], key: str) -> None:
    if key not in data:
        return
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _error(report, "E501", f"{key} must be a list of strings", key)


def _expect_rule_list(report: ProfileValidationReport, data: dict[str, Any]) -> None:
    if "assertion_rules" not in data:
        return
    rules = data["assertion_rules"]
    if not isinstance(rules, list):
        _error(report, "E501", "assertion_rules must be a list", "assertion_rules")
        return
    for index, rule in enumerate(rules):
        source = f"assertion_rules[{index}]"
        if not isinstance(rule, dict):
            _error(report, "E501", "assertion rule must be a mapping", source)
            continue
        regex = rule.get("regex")
        if isinstance(regex, str) and regex:
            try:
                re.compile(regex)
            except re.error as exc:
                _error(report, "E501", f"assertion rule regex is invalid: {exc}", source)


def _expect_case_fixture_values(report: ProfileValidationReport, fixtures: dict[str, Any]) -> None:
    for case_id, value in fixtures.items():
        source = f"case_fixtures.{case_id}"
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            _error(report, "E501", "case_fixtures value must be a list of strings", source)


def _expect_case_body_values(report: ProfileValidationReport, bodies: dict[str, Any]) -> None:
    for case_id, value in bodies.items():
        source = f"case_bodies.{case_id}"
        if isinstance(value, str):
            continue
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            continue
        _error(report, "E501", "case_bodies value must be a string or list of strings", source)


def _expect_request_override_values(report: ProfileValidationReport, overrides: dict[str, Any]) -> None:
    for case_id, value in overrides.items():
        if not isinstance(value, dict):
            _error(report, "E501", "request_overrides value must be a mapping", f"request_overrides.{case_id}")


def _validate_case_references(
    report: ProfileValidationReport,
    section: str,
    values: dict[str, Any],
) -> None:
    for case_id in values:
        source = f"{section}.{case_id}"
        if not isinstance(case_id, str) or not _CASE_ID_RE.match(case_id):
            _error(report, "E505", "case id must match ^TC-[A-Z0-9]+-\\d+$", source)
            continue
        if case_id not in report.case_ids:
            _error(report, "E505", "case id does not exist in module markdown cases", source)


def _validate_suite_default_coverage(
    report: ProfileValidationReport,
    context: Any,
    case_bodies: dict[str, Any],
    case_flows: dict[str, Any],
) -> None:
    covered = set(case_bodies) | set(case_flows)
    for md_path in context.case_files:
        parse_result = parse_suite_case_file(md_path, context.module)
        for tc in parse_result.cases:
            if tc.id in covered:
                continue
            if any("可行性存疑" in marker for marker in tc.markers):
                continue
            if parse_result.shared_config.base_request_http is None:
                _error(
                    report,
                    "E506",
                    "suite profile is missing coverage for a case that cannot use "
                    f"default_http without shared base_request_http: {tc.id}",
                    str(md_path),
                )


def _warn_feasibility_suspect_strategies(
    report: ProfileValidationReport,
    case_bodies: dict[str, Any],
    case_flows: dict[str, Any],
) -> None:
    executable_cases = set(case_bodies) | set(case_flows)
    for case_id in sorted(executable_cases):
        markers = report.case_markers.get(case_id, [])
        if not any("可行性存疑" in marker for marker in markers):
            continue
        strategy = "case_bodies" if case_id in case_bodies else "case_flows"
        _warn(
            report,
            "W503",
            "case is marked [!可行性存疑] in Markdown but profile maps it to executable "
            f"{strategy}; prefer leaving it skipped until feasibility is confirmed",
            f"{strategy}.{case_id}",
        )


def _warn_fixture_reinvocation(
    report: ProfileValidationReport,
    case_flows: dict[str, Any],
) -> None:
    for case_id, flow in case_flows.items():
        if not isinstance(flow, dict):
            continue
        fixture = flow.get("fixture")
        steps = flow.get("steps")
        if not isinstance(fixture, str) or not isinstance(steps, list) or not steps:
            continue
        first_step = steps[0]
        if not isinstance(first_step, dict):
            continue
        first_call = first_step.get("call")
        if first_call != fixture:
            continue
        _warn(
            report,
            "W504",
            "case_flow first step calls the declared fixture again; use the injected object "
            "directly, or declare the fixture object as a factory explicitly",
            f"case_flows.{case_id}.steps[0].call",
        )


def _validate_module_type(
    report: ProfileValidationReport,
    data: dict[str, Any],
    project: ProjectConfig,
    case_bodies: dict[str, Any],
    case_flows: dict[str, Any],
) -> None:
    profile_module_type = data.get("module_type")
    if profile_module_type is not None and not isinstance(profile_module_type, str):
        _error(report, "E504", "module_type must be a string", "module_type")
        return

    module_config = project.modules.get(report.module, {})
    config_module_type = (
        module_config.get("module_type")
        if isinstance(module_config, dict)
        else None
    )
    module_type = profile_module_type or config_module_type
    if not module_type:
        _warn(report, "W502", "module_type is not declared in profile or project_config.modules")
        return

    module_type_cfg = project.module_types.get(module_type)
    if module_type_cfg is None:
        _error(report, "E504", f"unknown module_type={module_type}", "module_type")
        return

    for required in module_type_cfg.get("requires", []):
        if required == "case_bodies":
            if not (case_bodies or case_flows):
                _error(
                    report,
                    "E504",
                    f"module_type={module_type} requires case_bodies or case_flows",
                    "module_type",
                )
            continue
        if not data.get(required):
            _error(report, "E504", f"module_type={module_type} requires {required}", "module_type")


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _variable_cases(variables: dict[str, Any]) -> dict[str, Any]:
    cases = variables.get("cases")
    return cases if isinstance(cases, dict) else {}


def _error(
    report: ProfileValidationReport,
    code: str,
    message: str,
    source: str = "",
) -> None:
    report.diagnostics.append(ProfileValidationDiagnostic(code, "ERROR", message, source))


def _warn(
    report: ProfileValidationReport,
    code: str,
    message: str,
    source: str = "",
) -> None:
    report.diagnostics.append(ProfileValidationDiagnostic(code, "WARNING", message, source))
