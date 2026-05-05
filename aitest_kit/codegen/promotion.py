"""Read-only promotion analysis for profile case_bodies."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from aitest_kit.codegen.profile import (
    load_profile_case_bodies,
    load_profile_case_fixtures,
    load_profile_case_flows,
)


@dataclass
class PromotionCase:
    case_id: str
    objects: list[str]
    methods: list[str]
    flags: list[str] = field(default_factory=list)
    line_count: int = 0


@dataclass
class PromotionGroup:
    target: str
    signature: str
    reason: str
    case_ids: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    candidate: bool = False


@dataclass
class PromotionReport:
    module: str
    total_case_bodies: int
    groups: list[PromotionGroup] = field(default_factory=list)


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CALL_EXPR = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_SETUP_ASSIGN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*setup_[A-Za-z_][A-Za-z0-9_]*\s*\(")
_LOOP = re.compile(r"^\s*(?:for|while)\b", re.MULTILINE)
_DEFAULT_OBJECT_NAMES = frozenset({"case", "issue", "ab", "client", "sdk"})


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _valid_object_name(name: object) -> bool:
    return isinstance(name, str) and bool(_IDENT.match(name))


def _profile_object_names(
    case_fixtures: dict[str, list[str]],
    case_flows: dict[str, dict],
) -> set[str]:
    names = set(_DEFAULT_OBJECT_NAMES)
    for fixtures in case_fixtures.values():
        for fixture in fixtures:
            if _valid_object_name(fixture):
                names.add(fixture)
    for flow in case_flows.values():
        if not isinstance(flow, dict):
            continue
        obj_name = flow.get("object")
        if _valid_object_name(obj_name):
            names.add(obj_name)
        steps = flow.get("steps", [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            call = step.get("call")
            if not isinstance(call, str) or "." not in call:
                continue
            first = call.split(".", 1)[0]
            if _valid_object_name(first):
                names.add(first)
    return names


def _calls(text: str, object_names: set[str]) -> list[tuple[str, str]]:
    names = set(object_names)
    names.update(_SETUP_ASSIGN.findall(text))
    return [
        (obj_name, method) for obj_name, method in _CALL_EXPR.findall(text)
        if obj_name in names
    ]


def _flags(text: str, methods: list[str]) -> list[str]:
    flags: list[str] = []
    if "ThreadPoolExecutor" in text or ".submit(" in text:
        flags.append("concurrency")
    if _LOOP.search(text):
        flags.append("loop")
    if "subprocess" in text or "Popen(" in text:
        flags.append("subprocess")
    if {"start_with_info_logging", "stop_and_logs"} & set(methods):
        flags.append("service_lifecycle")
    if any(token in text for token in ("tmp_path", "Path(", "write_text(", "build_isolated_client")):
        flags.append("file_lifecycle")
    if any(token in text for token in (".pop(", ".append(", ".extend(")):
        flags.append("body_mutation")
    if "monkeypatch" in text or "MockTransport" in text:
        flags.append("mocking")
    return flags


def _target(methods: list[str], flags: list[str]) -> tuple[str, str]:
    blocking = {"concurrency", "loop", "subprocess", "service_lifecycle", "file_lifecycle", "mocking"}
    if blocking & set(flags):
        return "keep_case_body", "contains lifecycle, concurrency, loop, file, subprocess, or mock behavior"
    if "body_mutation" in flags:
        return "promote_to_case_flow", "stable request mutation followed by call/assert pattern"
    if len(methods) >= 2:
        return "promote_to_case_flow", "multiple helper calls can be represented as ordered steps"
    if len(methods) == 1:
        return "promote_to_case_flow", "single helper call can be represented as a simple structured step"
    return "keep_case_body", "no stable helper-call shape detected"


def _signature(target: str, methods: list[str], flags: list[str]) -> str:
    method_part = ",".join(methods) if methods else "no_methods"
    flag_part = ",".join(sorted(flags)) if flags else "no_flags"
    return f"{target}|methods={method_part}|flags={flag_part}"


def analyze_case_body_promotion(module: str, profile_path: str | Path) -> PromotionReport:
    """Analyze profile case_bodies and group promotion candidates.

    This function is intentionally read-only. It never edits profile YAML.
    """
    bodies = load_profile_case_bodies(profile_path)
    case_fixtures = load_profile_case_fixtures(profile_path)
    case_flows = load_profile_case_flows(profile_path)
    object_names = _profile_object_names(case_fixtures, case_flows)
    grouped: dict[str, list[PromotionCase]] = {}
    group_meta: dict[str, tuple[str, str, list[str], list[str]]] = {}

    for case_id, lines in sorted(bodies.items()):
        text = "\n".join(lines)
        calls = _calls(text, object_names)
        objects = _unique([obj_name for obj_name, _ in calls])
        methods = _unique([method for _, method in calls])
        flags = _flags(text, methods)
        target, reason = _target(methods, flags)
        signature = _signature(target, methods, flags)
        grouped.setdefault(signature, []).append(PromotionCase(
            case_id=case_id,
            objects=objects,
            methods=methods,
            flags=flags,
            line_count=len(lines),
        ))
        group_meta[signature] = (target, reason, methods, flags)

    groups: list[PromotionGroup] = []
    for signature, cases in sorted(grouped.items()):
        target, reason, methods, flags = group_meta[signature]
        case_ids = [case.case_id for case in cases]
        objects = _unique([obj for case in cases for obj in case.objects])
        groups.append(PromotionGroup(
            target=target,
            signature=signature,
            reason=reason,
            case_ids=case_ids,
            objects=objects,
            methods=methods,
            flags=flags,
            candidate=target != "keep_case_body" and len(case_ids) >= 3,
        ))

    return PromotionReport(
        module=module,
        total_case_bodies=len(bodies),
        groups=groups,
    )


def promotion_to_dict(report: PromotionReport) -> dict:
    return asdict(report)


def render_promotion_report_markdown(report: PromotionReport) -> str:
    """Render a human-readable promotion analysis report."""
    candidate_groups = [group for group in report.groups if group.candidate]
    keep_groups = [group for group in report.groups if group.target == "keep_case_body"]
    lines = [
        f"# Codegen Promotion Report: {report.module}",
        "",
        f"- **Module**: `{report.module}`",
        f"- **Total case_bodies**: {report.total_case_bodies}",
        f"- **Candidate groups**: {len(candidate_groups)}",
        f"- **Keep groups**: {len(keep_groups)}",
        "",
    ]

    if not report.groups:
        lines.extend([
            "## Groups",
            "",
            "No profile case_bodies were found.",
            "",
        ])
        return "\n".join(lines)

    lines.extend(["## Groups", ""])
    for group in report.groups:
        marker = "candidate" if group.candidate else "review"
        lines.extend([
            f"### {group.target} ({marker})",
            "",
            f"- **Signature**: `{group.signature}`",
            f"- **Reason**: {group.reason}",
            f"- **Objects**: `{', '.join(group.objects) or '-'}`",
            f"- **Methods**: `{', '.join(group.methods) or '-'}`",
            f"- **Flags**: `{', '.join(group.flags) or '-'}`",
            f"- **Cases**: {', '.join(group.case_ids)}",
            f"- **Next action**: {_next_action(group)}",
            "",
        ])
    return "\n".join(lines)


def render_promotion_patch_markdown(report: PromotionReport) -> str:
    """Render a review-only promotion patch draft."""
    candidate_groups = [group for group in report.groups if group.candidate]
    lines = [
        f"# Codegen Promotion Patch Draft: {report.module}",
        "",
        "This file is a review draft. It does not modify the codegen profile.",
        "",
        "## Summary",
        "",
        f"- **Module**: `{report.module}`",
        f"- **Candidate groups**: {len(candidate_groups)}",
        "- **Apply policy**: manual review required before editing `codegen_profile`",
        "",
    ]

    if not candidate_groups:
        lines.extend([
            "## Patch Draft",
            "",
            "No safe case_flow promotion candidates were found in this run.",
            "",
        ])
        return "\n".join(lines)

    lines.extend([
        "## Patch Draft",
        "",
        "For each candidate group, review the original verified pytest body, add an equivalent `case_flows` entry, then remove the same case_id from `case_bodies`.",
        "",
    ])
    for group in candidate_groups:
        lines.extend([
            f"### {group.signature}",
            "",
            f"- **Target**: `{group.target}`",
            f"- **Reason**: {group.reason}",
            f"- **Objects**: `{', '.join(group.objects) or '-'}`",
            f"- **Methods**: `{', '.join(group.methods) or '-'}`",
            f"- **Cases to convert**: {', '.join(group.case_ids)}",
            "",
            "Review checklist:",
            "",
            "- Confirm each original generated pytest case has passed.",
            "- Encode only stable helper calls as `call` steps.",
            "- Write assertions as executable Python `assert ...` strings.",
            "- Remove converted case_ids from `case_bodies` in the same profile edit.",
            "",
        ])
    return "\n".join(lines)


def render_promotion_patch_diff(report: PromotionReport, profile_path: str | Path | None = None) -> str:
    """Render a conservative diff draft.

    The analyzer does not infer exact case_flow steps from arbitrary Python.
    The diff is intentionally a review note, not an auto-applicable profile rewrite.
    """
    candidate_groups = [group for group in report.groups if group.candidate]
    profile = Path(profile_path).as_posix() if profile_path else f"codegen_profile_{report.module}.md"
    if not candidate_groups:
        return "# No profile diff generated: no safe case_flow promotion candidates in this run.\n"

    lines = [
        f"--- a/{profile}",
        f"+++ b/{profile}",
        "@@",
    ]
    lines.extend([
        "# Review-only promotion notes:",
        "# Add equivalent case_flows entries and remove matching case_bodies after review.",
    ])
    for group in candidate_groups:
        lines.append(f"# - {group.target}: {', '.join(group.case_ids)} ({group.reason})")
    return "\n".join(lines) + "\n"


def write_promotion_report(report: PromotionReport, output_dir: str | Path) -> dict[str, Path]:
    """Write promotion report Markdown and JSON artifacts."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = out / f"{report.module}_promotion_report"
    md_path = base.with_suffix(".md")
    json_path = base.with_suffix(".json")
    md_path.write_text(render_promotion_report_markdown(report) + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(promotion_to_dict(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"markdown": md_path, "json": json_path}


def write_promotion_patch(
    report: PromotionReport,
    output_dir: str | Path,
    *,
    profile_path: str | Path | None = None,
) -> dict[str, Path]:
    """Write review-only promotion patch artifacts."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = out / f"{report.module}_promotion_patch"
    md_path = base.with_suffix(".md")
    diff_path = base.with_suffix(".diff")
    md_path.write_text(render_promotion_patch_markdown(report) + "\n", encoding="utf-8")
    diff_path.write_text(
        render_promotion_patch_diff(report, profile_path=profile_path),
        encoding="utf-8",
    )
    return {"markdown": md_path, "diff": diff_path}


def _next_action(group: PromotionGroup) -> str:
    if group.candidate:
        return "review for case_flow promotion"
    if group.target == "keep_case_body":
        return "keep case_body"
    return "wait for more similar verified cases"
