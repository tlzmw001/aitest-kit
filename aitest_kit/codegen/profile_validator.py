"""Pre-generation validation for codegen profiles."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from aitest_kit.codegen.parser import parse_case_file
from aitest_kit.codegen.profile import (
    validate_case_flows,
    validate_profile_strategy_conflicts,
)
from aitest_kit.codegen.project_config import ProjectConfig, load_project_config


_YAML_BLOCK_RE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)
_CASE_ID_RE = re.compile(r"^TC-[A-Z0-9]+-\d+$")
_PROFILE_SCHEMA_RELATIVE_PATH = Path("aitest_config/schemas/codegen_profile.schema.json")
_REPO_PROFILE_SCHEMA_PATH = Path(__file__).resolve().parents[2] / _PROFILE_SCHEMA_RELATIVE_PATH
_PACKAGE_PROFILE_SCHEMA = "aitest_kit.templates.project_workspace"
_TOP_LEVEL_KEYS = {
    "module_type",
    "assertion_rules",
    "request_overrides",
    "extra_imports",
    "case_fixtures",
    "case_bodies",
    "case_flows",
}


@dataclass(frozen=True)
class ProfileValidationDiagnostic:
    code: str
    severity: str
    message: str
    source: str = ""

    def format(self) -> str:
        location = f" {self.source}" if self.source else ""
        return f"[{self.severity}] {self.code}:{location} {self.message}"


@dataclass
class ProfileValidationReport:
    module: str
    profile_path: Path
    case_files: list[Path] = field(default_factory=list)
    case_ids: set[str] = field(default_factory=set)
    case_markers: dict[str, list[str]] = field(default_factory=dict)
    diagnostics: list[ProfileValidationDiagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[ProfileValidationDiagnostic]:
        return [diag for diag in self.diagnostics if diag.severity == "ERROR"]

    @property
    def warnings(self) -> list[ProfileValidationDiagnostic]:
        return [diag for diag in self.diagnostics if diag.severity == "WARNING"]


def profile_validation_to_dict(report: ProfileValidationReport) -> dict[str, Any]:
    return {
        "module": report.module,
        "profile_path": str(report.profile_path),
        "case_files": [str(path) for path in report.case_files],
        "case_count": len(report.case_ids),
        "case_ids": sorted(report.case_ids),
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "diagnostics": [
            {
                "code": diag.code,
                "severity": diag.severity,
                "message": diag.message,
                "source": diag.source,
            }
            for diag in report.diagnostics
        ],
    }


def render_profile_validation_markdown(report: ProfileValidationReport) -> str:
    lines = [
        f"# Profile Validation Report: {report.module}",
        "",
        f"- Profile: `{report.profile_path}`",
        f"- Case files: {len(report.case_files)}",
        f"- Cases: {len(report.case_ids)}",
        f"- Errors: {len(report.errors)}",
        f"- Warnings: {len(report.warnings)}",
        "",
        "## Diagnostics",
        "",
    ]
    if report.diagnostics:
        lines.extend(f"- {diag.format()}" for diag in report.diagnostics)
    else:
        lines.append("- OK")
    lines.extend(["", "## Case Files", ""])
    if report.case_files:
        lines.extend(f"- `{path}`" for path in report.case_files)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_profile_validation_report(
    report: ProfileValidationReport,
    output_dir: str | Path,
) -> dict[str, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{report.module}_profile_validation.md"
    json_path = out_dir / f"{report.module}_profile_validation.json"
    md_path.write_text(render_profile_validation_markdown(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(profile_validation_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"markdown": md_path, "json": json_path}


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

    for message in validate_profile_strategy_conflicts(case_bodies, case_flows):
        _error(report, "E502", message)
    for message in validate_case_flows(case_flows):
        _error(report, "E503", message)

    _validate_case_references(report, "case_bodies", case_bodies)
    _validate_case_references(report, "case_flows", case_flows)
    _validate_case_references(report, "case_fixtures", case_fixtures)
    _validate_case_references(report, "request_overrides", request_overrides)
    _warn_feasibility_suspect_strategies(report, case_bodies, case_flows)
    _warn_fixture_reinvocation(report, case_flows)
    _validate_module_type(report, data, project_config, case_bodies, case_flows)
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


def _load_profile_yaml_strict(report: ProfileValidationReport) -> dict[str, Any] | None:
    text = report.profile_path.read_text(encoding="utf-8")
    match = _YAML_BLOCK_RE.search(text)
    if not match:
        _error(report, "E501", "profile must contain one YAML code block", str(report.profile_path))
        return None

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        _error(report, "E501", f"profile YAML is invalid: {exc}", str(report.profile_path))
        return None

    if data is None:
        return {}
    if not isinstance(data, dict):
        _error(report, "E501", "profile YAML root must be a mapping", str(report.profile_path))
        return None
    return data


def _profile_schema_validator() -> Draft202012Validator:
    schema_text, _ = _profile_schema_source()
    schema = json.loads(schema_text)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _profile_schema_path() -> Path:
    cwd_schema = _PROFILE_SCHEMA_RELATIVE_PATH
    return cwd_schema if cwd_schema.exists() else _REPO_PROFILE_SCHEMA_PATH


def _profile_schema_source() -> tuple[str, str]:
    cwd_schema = _PROFILE_SCHEMA_RELATIVE_PATH
    if cwd_schema.exists():
        return cwd_schema.read_text(encoding="utf-8"), str(cwd_schema)
    if _REPO_PROFILE_SCHEMA_PATH.exists():
        return _REPO_PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"), str(_REPO_PROFILE_SCHEMA_PATH)
    resource = resources.files(_PACKAGE_PROFILE_SCHEMA).joinpath(
        "aitest_config",
        "schemas",
        "codegen_profile.schema.json",
    )
    return resource.read_text(encoding="utf-8"), str(resource)


def _validate_profile_schema(report: ProfileValidationReport, data: dict[str, Any]) -> None:
    try:
        validator = _profile_schema_validator()
    except Exception as exc:
        try:
            _, source = _profile_schema_source()
        except Exception:
            source = str(_profile_schema_path())
        _error(report, "E501", f"profile JSON Schema is unavailable: {exc}", source)
        return

    for error in sorted(validator.iter_errors(data), key=_schema_error_sort_key):
        _error(report, "E501", _format_schema_error(error), _schema_error_source(error))


def _schema_error_sort_key(error: ValidationError) -> tuple[str, str]:
    return (_schema_error_source(error), error.message)


def _schema_error_source(error: ValidationError) -> str:
    parts: list[str] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{part}]"
            else:
                parts.append(f"[{part}]")
        else:
            parts.append(str(part))
    return ".".join(parts) or "<root>"


def _format_schema_error(error: ValidationError) -> str:
    return f"profile schema violation: {error.message}"


def _validate_top_level_shape(report: ProfileValidationReport, data: dict[str, Any]) -> None:
    for key in data:
        if key not in _TOP_LEVEL_KEYS:
            _error(report, "E501", f"unknown top-level field {key}", key)

    _expect_mapping(report, data, "request_overrides")
    _expect_mapping(report, data, "case_fixtures")
    _expect_mapping(report, data, "case_bodies")
    _expect_mapping(report, data, "case_flows")
    _expect_string_list(report, data, "extra_imports")
    _expect_rule_list(report, data)
    _expect_case_fixture_values(report, _mapping(data, "case_fixtures"))
    _expect_case_body_values(report, _mapping(data, "case_bodies"))
    _expect_request_override_values(report, _mapping(data, "request_overrides"))


def _expect_mapping(report: ProfileValidationReport, data: dict[str, Any], key: str) -> None:
    if key in data and not isinstance(data[key], dict):
        _error(report, "E501", f"{key} must be a mapping", key)


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
