"""Rendering helpers for codegen emitter."""
from __future__ import annotations

import json
import re
from typing import Any

from aitest_kit.codegen.project_config import AssertionRule, ProjectConfig


_BACKTICK = re.compile(r"`([^`]+)`")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)?)\}")


def strip_backticks(s: str) -> str:
    """Remove backticks from assertion text."""
    return _BACKTICK.sub(r"\1", s).strip()


def module_class_name(module: str, file_type: str) -> str:
    parts = module.split("_")
    camel = "".join(p.capitalize() for p in parts)
    suffix = "Business" if file_type == "business" else "Boundary"
    return f"Test{camel}{suffix}"


def tc_func_name(tc_id: str) -> str:
    return "test_" + tc_id.lower().replace("-", "_")


def tc_number(tc_id: str) -> str:
    m = re.search(r"(\d+)$", tc_id)
    return m.group(1) if m else "000"


def module_abbrev(module: str, project: ProjectConfig) -> str:
    """Short abbreviation for user_id/req_id generation."""
    return project.module_abbrevs.get(module, module[:4])


def dict_to_python_compact(obj: Any) -> str:
    """Single-line Python repr for items inside lists."""
    if obj is None:
        return "None"
    if isinstance(obj, bool):
        return "True" if obj else "False"
    if isinstance(obj, (int, float)):
        return repr(obj)
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, list):
        return "[" + ", ".join(dict_to_python_compact(v) for v in obj) + "]"
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        pairs = [f"{json.dumps(k, ensure_ascii=False)}: {dict_to_python_compact(v)}" for k, v in obj.items()]
        return "{" + ", ".join(pairs) + "}"
    return repr(obj)


def dict_to_python(obj: Any, indent: int = 0) -> str:
    """Render a Python dict literal matching the generated style."""
    if obj is None:
        return "None"
    if isinstance(obj, bool):
        return "True" if obj else "False"
    if isinstance(obj, (int, float)):
        return repr(obj)
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, list):
        items = [dict_to_python_compact(v) for v in obj]
        return "[" + ", ".join(items) + "]"
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        pad = "    " * (indent + 1)
        end_pad = "    " * indent
        pairs = []
        for k, v in obj.items():
            pairs.append(f"{pad}{json.dumps(k, ensure_ascii=False)}: {dict_to_python(v, indent + 1)}")
        return "{\n" + ",\n".join(pairs) + ",\n" + end_pad + "}"
    return repr(obj)


def render_assignment(name: str, value: Any, indent: int = 0) -> list[str]:
    """Render a Python assignment with the shared generated style."""
    prefix = "    " * indent
    rendered = dict_to_python(value, indent=indent)
    return (f"{prefix}{name} = {rendered}").splitlines()


def response_path_accessor(path: str) -> str:
    """Render a response path like results[0].score as Python accessors."""
    accessor = "resp"
    for part in path.split("."):
        if not part:
            continue
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]", part)
        if m:
            accessor += f'["{m.group(1)}"][{m.group(2)}]'
        elif part.startswith("["):
            accessor += part
        else:
            accessor += f'["{part}"]'
    return accessor


def _result_set_accessor(path: str) -> str:
    path_parts = path.replace("[*]", "").split(".")
    accessor = "".join(f'["{p}"]' for p in path_parts if p)
    return f'{{r{accessor} for r in resp["results"]}}'


def _render_piecewise_segments(segments: list, var_k: str = "k_pw", var_b: str = "b_pw") -> list[str]:
    lines = []
    for i, seg in enumerate(segments):
        threshold, k, b = seg[0], seg[1], seg[2]
        if i == 0:
            lines.append(f"if s < {threshold}:")
            lines.append(f"    {var_k}, {var_b} = {k}, {b}")
        elif i < len(segments) - 1:
            lines.append(f"elif s < {threshold}:")
            lines.append(f"    {var_k}, {var_b} = {k}, {b}")
        else:
            lines.append("else:")
            lines.append(f"    {var_k}, {var_b} = {k}, {b}")
    return lines


def render_named_template(name: str, params: dict) -> list[str]:
    """Render a named template with params from profile rules."""
    segments = params.get("segments", [])

    if name == "piecewise_cascade":
        linear_k = params.get("linear_k", 1.0)
        linear_b = params.get("linear_b", 0.0)
        lines = _render_piecewise_segments(segments, "k_pw", "b_pw")
        lines.append("mid = max(0, min(1, k_pw * s + b_pw))")
        lines.append(
            f"assert cal == pytest.approx(max(0, min(1, {linear_k} * mid + {linear_b})), abs=1e-4)"
        )
        return lines

    if name == "piecewise_only":
        lines = _render_piecewise_segments(segments, "k", "b")
        lines.append("assert cal == pytest.approx(max(0, min(1, k * s + b)), abs=1e-4)")
        return lines

    if name == "skip":
        return []

    return [f"# UNKNOWN TEMPLATE: {name}"]


def _match_rule(rule: AssertionRule, clean_text: str) -> dict[str, str] | None:
    if rule.regex:
        m = re.match(rule.regex, clean_text)
        if not m:
            return None
        values = {k: (v or "") for k, v in m.groupdict().items()}
        for idx, value in enumerate(m.groups(), start=1):
            values[f"g{idx}"] = value or ""
        return values

    pattern = strip_backticks(rule.pattern)
    if pattern and pattern in clean_text:
        return {}
    return None


def _interpolate_template(template: str, values: dict[str, str]) -> str:
    if not values:
        return template

    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if ":" in token:
            transform, key = token.split(":", 1)
            value = values.get(key)
            if value is None:
                return match.group(0)
            if transform == "response_path":
                return response_path_accessor(value)
            if transform == "result_set":
                return _result_set_accessor(value)
            return match.group(0)
        return values.get(token, match.group(0))

    return _PLACEHOLDER.sub(repl, template)


def _render_rule(rule: AssertionRule, match_values: dict[str, str], project: ProjectConfig) -> list[str]:
    template = rule.template.strip()
    if template in project.named_templates:
        return render_named_template(template, rule.params)

    lines = list(rule.extract_vars)
    for template_line in template.splitlines():
        lines.append(_interpolate_template(template_line.strip(), match_values))
    return lines


def resolve_assertion(
    text: str,
    profile_rules: list[AssertionRule],
    project: ProjectConfig,
) -> tuple[list[str], str]:
    """Resolve an assertion text to code lines."""
    clean = strip_backticks(text)

    for rule in profile_rules:
        match_values = _match_rule(rule, clean)
        if match_values is not None:
            return _render_rule(rule, match_values, project), f"profile:{(rule.name or rule.pattern or rule.regex)[:30]}"

    for rule in project.builtin_assertion_rules:
        match_values = _match_rule(rule, clean)
        if match_values is not None:
            return _render_rule(rule, match_values, project), rule.name or rule.regex or "builtin"

    if clean in project.named_templates:
        return render_named_template(clean, {}), clean

    return [f"# UNPARSED ASSERTION: {text}"], "UNPARSED"
