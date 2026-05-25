"""Profile validation report data and rendering."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    suite: str = ""
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
        "suite": report.suite,
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
    title = (
        f"# Profile Validation Report: {report.module}"
        if not report.suite
        else f"# Profile Validation Report: {report.module}/{report.suite}"
    )
    lines = [
        title,
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
    stem = report.module if not report.suite else f"{report.module}_{report.suite}"
    md_path = out_dir / f"{stem}_profile_validation.md"
    json_path = out_dir / f"{stem}_profile_validation.json"
    md_path.write_text(render_profile_validation_markdown(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(profile_validation_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"markdown": md_path, "json": json_path}
