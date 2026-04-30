"""Deterministic pytest code emitter.

Transforms ParseResult (from parser.py) into pytest .py files using
rule-based assertion matching. Module-specific rules are loaded from
codegen_profile YAML blocks; everything else uses built-in patterns.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.codegen.parser import ParseResult, SharedConfig, TestCase, parse_case_file


# ---------------------------------------------------------------------------
# Project-level configuration (override when switching projects)
# ---------------------------------------------------------------------------

@dataclass
class ProjectConfig:
    helper_import: str = "from test_workspace.tests.helpers import http as http_helper"
    api_path: str = "/api/v1/recommend"
    helper_call: str = "http_helper.post"
    grpc_helper_import: str = "from test_workspace.tests.helpers import grpc_ops"
    grpc_helper_call: str = "grpc_ops.recommend"
    var_map: dict[str, str] = field(default_factory=lambda: {
        "s": 'resp["results"][0]["score"]',
        "cal": 'resp["results"][0]["calibrated_score"]',
    })
    module_abbrevs: dict[str, str] = field(default_factory=lambda: {
        "calibration": "cal",
        "ab_experiment": "ab",
        "ab_service": "abs",
        "feature_scoring": "feat",
        "issuance": "issue",
        "logging": "log",
        "rough_ranking": "rank",
        "scene_routing": "route",
        "validation_ratelimit": "val",
        "e2e": "e2e",
    })


DEFAULT_PROJECT = ProjectConfig()


# ---------------------------------------------------------------------------
# Profile rule loading
# ---------------------------------------------------------------------------

@dataclass
class AssertionRule:
    pattern: str
    template: str
    extract_vars: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


def _load_profile_yaml(profile_path: str | Path) -> dict:
    """Extract the first YAML block from a codegen_profile."""
    path = Path(profile_path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    m = re.search(
        r"```ya?ml\s*\n(.*?)```",
        text,
        re.DOTALL,
    )
    if not m:
        return {}

    try:
        import yaml
        data = yaml.safe_load(m.group(1))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def load_profile_rules(profile_path: str | Path) -> list[AssertionRule]:
    """Extract assertion_rules from a codegen_profile's ```yaml block."""
    data = _load_profile_yaml(profile_path)
    if not data:
        return []

    rules = []
    for item in data.get("assertion_rules", []):
        rules.append(AssertionRule(
            pattern=item.get("pattern", ""),
            template=item.get("template", ""),
            extract_vars=item.get("extract_vars", []),
            params=item.get("params", {}),
        ))
    return rules


def load_profile_request_overrides(profile_path: str | Path) -> dict[str, dict[str, Any]]:
    """Extract explicit case-level request overrides from a profile YAML block."""
    data = _load_profile_yaml(profile_path)
    raw = data.get("request_overrides", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for case_id, overrides in raw.items():
        if isinstance(case_id, str) and isinstance(overrides, dict):
            result[case_id] = dict(overrides)
    return result


def load_profile_extra_imports(profile_path: str | Path) -> list[str]:
    """Extract extra import lines from a profile YAML block."""
    data = _load_profile_yaml(profile_path)
    raw = data.get("extra_imports", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]


def load_profile_case_fixtures(profile_path: str | Path) -> dict[str, list[str]]:
    """Extract per-case fixture signatures from a profile YAML block."""
    data = _load_profile_yaml(profile_path)
    raw = data.get("case_fixtures", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for case_id, fixtures in raw.items():
        if not isinstance(case_id, str) or not isinstance(fixtures, list):
            continue
        result[case_id] = [
            item for item in fixtures
            if isinstance(item, str) and item.strip()
        ]
    return result


def load_profile_case_bodies(profile_path: str | Path) -> dict[str, list[str]]:
    """Extract per-case test body lines from a profile YAML block."""
    data = _load_profile_yaml(profile_path)
    raw = data.get("case_bodies", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for case_id, body in raw.items():
        if not isinstance(case_id, str):
            continue
        if isinstance(body, str):
            result[case_id] = body.splitlines()
        elif isinstance(body, list):
            result[case_id] = [
                item for item in body
                if isinstance(item, str)
            ]
    return result


# ---------------------------------------------------------------------------
# Built-in assertion patterns (priority order, first match wins)
# ---------------------------------------------------------------------------

_BACKTICK = re.compile(r"`([^`]+)`")


def _strip_bt(s: str) -> str:
    """Remove backticks from assertion text."""
    return _BACKTICK.sub(r"\1", s).strip()


def _extract_number(s: str) -> str | None:
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return m.group(0) if m else None


@dataclass
class BuiltinPattern:
    name: str
    match: Any  # callable(assertion_text) -> dict | None
    render: Any  # callable(match_dict, ctx) -> list[str]


def _match_status_code(text: str) -> dict | None:
    t = _strip_bt(text)
    m = re.match(r"response\.(?:body\.)?code\s*==\s*(\d+)", t)
    if m:
        return {"value": int(m.group(1))}
    m = re.match(r"response\.status_code\s*==\s*(\d+)", t)
    if m:
        return {"value": int(m.group(1)), "http_status": True}
    m = re.match(r"status_code\s*==\s*(\d+)", t)
    if m:
        return {"value": int(m.group(1)), "http_status": True}
    return None


def _render_status_code(d: dict, ctx: dict) -> list[str]:
    if d.get("http_status"):
        return [f'assert resp.status_code == {d["value"]}']
    return [f'assert resp["code"] == {d["value"]}']


def _match_full_body(text: str) -> dict | None:
    t = _strip_bt(text)
    m = re.match(r"response\.body\s*==\s*(.+)", t)
    if m:
        return {"value": m.group(1).strip()}
    return None


def _render_full_body(d: dict, ctx: dict) -> list[str]:
    return [f'assert resp == {d["value"]}']


def _match_coupon_null(text: str) -> dict | None:
    t = _strip_bt(text)
    if re.match(r"coupon\s*==\s*null", t, re.IGNORECASE):
        return {}
    if re.match(r"response\.body\.coupon\s*==\s*null", t, re.IGNORECASE):
        return {}
    return None


def _render_coupon_null(d: dict, ctx: dict) -> list[str]:
    return ['assert resp["coupon"] is None']


def _match_coupon_top(text: str) -> dict | None:
    t = _strip_bt(text)
    if "coupon.item_id" in t and "top_result" in t:
        return {}
    if "coupon" in t and "item_id" in t and "max" in t:
        return {}
    return None


def _render_coupon_top(d: dict, ctx: dict) -> list[str]:
    return [
        'assert resp["coupon"]["item_id"] == '
        'max(resp["results"], key=lambda r: r["score"])["item_id"]'
    ]


def _match_set_match(text: str) -> dict | None:
    t = _strip_bt(text)
    m = re.match(r"set\(response\.(.+?)\)\s*==\s*(\{.+\})", t)
    if m:
        return {"path": m.group(1), "expected": m.group(2)}
    return None


def _render_set_match(d: dict, ctx: dict) -> list[str]:
    path_parts = d["path"].replace("[*]", "").split(".")
    accessor = "".join(f'["{p}"]' for p in path_parts if p)
    item_var = "r"
    return [f'assert {{{item_var}{accessor} for {item_var} in resp["results"]}} == {d["expected"]}']


def _match_length(text: str) -> dict | None:
    t = _strip_bt(text)
    m = re.match(r"len\((.+?)\)\s*==\s*(\d+)", t)
    if m:
        return {"expr": m.group(1), "n": int(m.group(2))}
    return None


def _render_length(d: dict, ctx: dict) -> list[str]:
    return [f'assert len({d["expr"]}) == {d["n"]}']


def _match_linear_cal(text: str) -> dict | None:
    t = _strip_bt(text)
    m = re.match(
        r"cal\s*==\s*round\(clamp\(([0-9.]+)\s*\*\s*s\s*(?:\+\s*([0-9.]+))?\)\s*,\s*4\)",
        t,
    )
    if m:
        k = m.group(1)
        b = m.group(2) or "0"
        return {"k": k, "b": b}
    # simpler form: cal == round(clamp(k * s), 4)
    m = re.match(r"cal\s*==\s*round\(clamp\(([0-9.]+)\s*\*\s*s\)\s*,\s*4\)", t)
    if m:
        return {"k": m.group(1), "b": "0"}
    return None


def _render_linear_cal(d: dict, ctx: dict) -> list[str]:
    k, b = d["k"], d["b"]
    expr = f'{k} * s + {b}' if b != "0" else f'{k} * s'
    return [f'assert cal == pytest.approx(max(0, min(1, {expr})), abs=1e-4)']


def _match_no_cal(text: str) -> dict | None:
    t = _strip_bt(text)
    if re.match(r"cal\s*==\s*s\b", t):
        return {}
    return None


def _render_no_cal(d: dict, ctx: dict) -> list[str]:
    return ['assert cal == pytest.approx(s)']


def _match_field_equality(text: str) -> dict | None:
    """Generic response.xxx == value."""
    t = _strip_bt(text)
    m = re.match(r"response\.(?:body\.)?(\S+)\s*==\s*(.+)", t)
    if m:
        return {"path": m.group(1), "value": m.group(2).strip()}
    return None


def _response_path_accessor(path: str) -> str:
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


def _render_field_equality(d: dict, ctx: dict) -> list[str]:
    return [f'assert {_response_path_accessor(d["path"])} == {d["value"]}']


def _match_comparison(text: str) -> dict | None:
    t = _strip_bt(text)
    m = re.match(r"response\.(?:body\.)?(\S+)\s*(>=|<=|>|<)\s*(.+)", t)
    if m:
        return {"path": m.group(1), "op": m.group(2), "value": m.group(3).strip()}
    return None


def _render_comparison(d: dict, ctx: dict) -> list[str]:
    return [f'assert {_response_path_accessor(d["path"])} {d["op"]} {d["value"]}']


BUILTIN_PATTERNS: list[BuiltinPattern] = [
    BuiltinPattern("status_code", _match_status_code, _render_status_code),
    BuiltinPattern("full_body", _match_full_body, _render_full_body),
    BuiltinPattern("coupon_null", _match_coupon_null, _render_coupon_null),
    BuiltinPattern("coupon_top", _match_coupon_top, _render_coupon_top),
    BuiltinPattern("set_match", _match_set_match, _render_set_match),
    BuiltinPattern("length", _match_length, _render_length),
    BuiltinPattern("linear_cal", _match_linear_cal, _render_linear_cal),
    BuiltinPattern("no_cal", _match_no_cal, _render_no_cal),
    BuiltinPattern("comparison", _match_comparison, _render_comparison),
    BuiltinPattern("field_equality", _match_field_equality, _render_field_equality),
]


def _render_piecewise_segments(segments: list, var_k: str = "k_pw", var_b: str = "b_pw") -> list[str]:
    """Render if/elif/else block for piecewise segments."""
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


def _render_named_template(name: str, params: dict) -> list[str]:
    """Render a named template with params from profile rules."""
    segments = params.get("segments", [])

    if name == "piecewise_cascade":
        linear_k = params.get("linear_k", 1.0)
        linear_b = params.get("linear_b", 0.0)
        lines = _render_piecewise_segments(segments, "k_pw", "b_pw")
        lines.append(f"mid = max(0, min(1, k_pw * s + b_pw))")
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


NAMED_TEMPLATES = {"piecewise_cascade", "piecewise_only", "skip"}


# ---------------------------------------------------------------------------
# Assertion resolver
# ---------------------------------------------------------------------------

def resolve_assertion(
    text: str,
    profile_rules: list[AssertionRule],
    ctx: dict,
) -> tuple[list[str], str]:
    """Resolve an assertion text to code lines.

    Returns (code_lines, pattern_name).
    pattern_name is "UNPARSED" if no rule matched.
    """
    clean = _strip_bt(text)

    # Profile rules take priority
    for rule in profile_rules:
        pat = _strip_bt(rule.pattern)
        if pat and pat in clean:
            if rule.template.strip() in NAMED_TEMPLATES:
                lines = _render_named_template(rule.template.strip(), rule.params)
                return lines, f"profile:{rule.template.strip()}"
            lines = []
            for var_line in rule.extract_vars:
                lines.append(var_line)
            lines.append(rule.template.strip())
            return lines, f"profile:{rule.pattern[:30]}"

    # Built-in patterns
    for bp in BUILTIN_PATTERNS:
        match = bp.match(text)
        if match is not None:
            return bp.render(match, ctx), bp.name

    return [f'# UNPARSED ASSERTION: {text}'], "UNPARSED"


# ---------------------------------------------------------------------------
# Code generation context
# ---------------------------------------------------------------------------

@dataclass
class EmitContext:
    module: str
    file_type: str  # "business" or "boundary"
    source_path: str
    shared_config: SharedConfig
    project: ProjectConfig = field(default_factory=ProjectConfig)
    profile_rules: list[AssertionRule] = field(default_factory=list)
    request_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra_imports: list[str] = field(default_factory=list)
    case_fixtures: dict[str, list[str]] = field(default_factory=dict)
    case_bodies: dict[str, list[str]] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# File-level template rendering
# ---------------------------------------------------------------------------

def _module_class_name(module: str, file_type: str) -> str:
    parts = module.split("_")
    camel = "".join(p.capitalize() for p in parts)
    suffix = "Business" if file_type == "business" else "Boundary"
    return f"Test{camel}{suffix}"


def _tc_func_name(tc_id: str) -> str:
    return "test_" + tc_id.lower().replace("-", "_")


def _tc_number(tc_id: str) -> str:
    m = re.search(r"(\d+)$", tc_id)
    return m.group(1) if m else "000"


def _module_abbrev(module: str, project: ProjectConfig) -> str:
    """Short abbreviation for user_id/req_id generation."""
    return project.module_abbrevs.get(module, module[:4])


def _render_header(ctx: EmitContext, has_grpc: bool = False) -> list[str]:
    lines = [
        f"# Auto-generated from {ctx.source_path}",
        f"# DO NOT EDIT — regenerate with: /test-codegen {ctx.module}",
        "import pytest",
        ctx.project.helper_import,
    ]
    if has_grpc:
        lines.append(ctx.project.grpc_helper_import)
    lines.extend(ctx.extra_imports)
    return lines


def _dict_to_python_compact(obj: Any) -> str:
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
        return "[" + ", ".join(_dict_to_python_compact(v) for v in obj) + "]"
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        pairs = [f"{json.dumps(k, ensure_ascii=False)}: {_dict_to_python_compact(v)}" for k, v in obj.items()]
        return "{" + ", ".join(pairs) + "}"
    return repr(obj)


def _dict_to_python(obj: Any, indent: int = 0) -> str:
    """Render a Python dict literal matching the hand-written style."""
    if obj is None:
        return "None"
    if isinstance(obj, bool):
        return "True" if obj else "False"
    if isinstance(obj, (int, float)):
        return repr(obj)
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, list):
        items = [_dict_to_python_compact(v) for v in obj]
        return "[" + ", ".join(items) + "]"
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        pad = "    " * (indent + 1)
        end_pad = "    " * indent
        pairs = []
        for k, v in obj.items():
            pairs.append(f"{pad}{json.dumps(k, ensure_ascii=False)}: {_dict_to_python(v, indent + 1)}")
        return "{\n" + ",\n".join(pairs) + ",\n" + end_pad + "}"
    return repr(obj)


def _render_base_request(ctx: EmitContext) -> list[str]:
    body = ctx.shared_config.base_request_http
    if not body:
        return []
    lines = ["", ""]
    sanitized = dict(body)
    sanitized["user_id"] = None
    sanitized["reqId"] = None
    lines.append(f"BASE_REQUEST = {_dict_to_python(sanitized)}")
    return lines


def _render_req_helper(ctx: EmitContext) -> list[str]:
    return [
        "",
        "",
        "def _req(user_id: str, req_id: str, **overrides) -> dict:",
        '    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}',
        "    body.update(overrides)",
        "    return body",
    ]


def _render_variable_extraction(ctx: EmitContext) -> list[str]:
    """Generate variable extraction lines from shared config variables."""
    lines = []
    for var_name, var_def in ctx.variables.items():
        if var_name in ctx.project.var_map:
            lines.append(f"        {var_name} = {ctx.project.var_map[var_name]}")
    return lines


# ---------------------------------------------------------------------------
# Test function rendering
# ---------------------------------------------------------------------------

def _needs_variables(assertions: list[str], variables: dict[str, str]) -> set[str]:
    """Determine which shared variables are referenced by assertions."""
    needed = set()
    for a in assertions:
        clean = _strip_bt(a)
        for var_name in variables:
            if var_name in ("clamp(x)",):
                continue
            if re.search(rf"\b{re.escape(var_name)}\b", clean):
                needed.add(var_name)
    return needed


def _render_req_call(tc: TestCase, ctx: EmitContext, default_user_id: str, default_req_id: str) -> str:
    """Render _req(...) using optional profile-specified case overrides."""
    configured = dict(ctx.request_overrides.get(tc.id, {}))
    user_id = configured.pop("user_id", default_user_id)
    req_id = configured.pop("reqId", configured.pop("req_id", default_req_id))

    if not configured:
        return f'_req("{user_id}", "{req_id}")'

    return f'_req("{user_id}", "{req_id}", **{_dict_to_python_compact(configured)})'


def _render_test_function(tc: TestCase, ctx: EmitContext) -> list[str]:
    """Render a single test function."""
    abbrev = _module_abbrev(ctx.module, ctx.project)
    num = _tc_number(tc.id)
    func_name = _tc_func_name(tc.id)
    is_manual = any("manual" in m.lower() for m in tc.markers)
    is_grpc = any("gRPC" in v for v in tc.scenario_vars.values())

    lines = []

    # Decorator
    if is_manual:
        lines.append("    @pytest.mark.manual")

    custom_body = ctx.case_bodies.get(tc.id)
    if custom_body is not None:
        fixtures = ctx.case_fixtures.get(tc.id, [f"setup_{ctx.module}"])
        signature = ", ".join(["self", *fixtures])
        lines.append(f"    def {func_name}({signature}):")
        lines.append(f'        """{tc.id}：{tc.title}"""')
        for key, val in tc.scenario_vars.items():
            if key.startswith("_"):
                continue
            lines.append(f"        # SETUP: {key}：{_strip_bt(val)}")
        lines.append("")
        for body_line in custom_body:
            lines.append(f"        {body_line}" if body_line else "")
        return lines, []

    # Function signature
    if is_grpc:
        lines.append(f"    def {func_name}(self, grpc_target, setup_{ctx.module}):")
    else:
        lines.append(f"    def {func_name}(self, http_base_url, setup_{ctx.module}):")
    lines.append(f'        """{tc.id}：{tc.title}"""')

    # Setup comments + fixture call
    for key, val in tc.scenario_vars.items():
        if key.startswith("_"):
            continue
        lines.append(f"        # SETUP: {key}：{_strip_bt(val)}")
    lines.append(f'        setup_{ctx.module}(case_id="{tc.id}")')

    # Request
    user_id = f"u_{abbrev}_{num}"
    req_id = f"req_{abbrev}_{num}"
    req_call = _render_req_call(tc, ctx, user_id, req_id)
    lines.append("")
    if is_grpc:
        lines.append(
            f'        resp = {ctx.project.grpc_helper_call}(grpc_target, '
            f'{req_call})'
        )
    else:
        lines.append(
            f'        resp = {ctx.project.helper_call}(http_base_url, "{ctx.project.api_path}", '
            f'json={req_call})'
        )

    # Common assertions (skip for manual)
    if not is_manual:
        for ca in ctx.shared_config.common_assertions:
            code_lines, _ = resolve_assertion(ca, ctx.profile_rules, {})
            for cl in code_lines:
                lines.append(f"        {cl}")

    # Variable extraction (only if assertions reference them)
    needed_vars = _needs_variables(tc.assertions, ctx.variables)
    for var_name in ctx.project.var_map:
        if var_name in needed_vars:
            lines.append(f"        {var_name} = {ctx.project.var_map[var_name]}")

    # Case-specific assertions
    unparsed = []
    for assertion in tc.assertions:
        if is_manual:
            lines.append(f"        # MANUAL CHECK: {_strip_bt(assertion)}")
            continue

        code_lines, pattern_name = resolve_assertion(
            assertion, ctx.profile_rules, {"tc": tc, "ctx": ctx}
        )
        for cl in code_lines:
            lines.append(f"        {cl}")
        if pattern_name == "UNPARSED":
            unparsed.append(assertion)

    return lines, unparsed


# ---------------------------------------------------------------------------
# File-level emit
# ---------------------------------------------------------------------------

@dataclass
class EmitResult:
    output_path: str
    case_count: int
    skipped: list[tuple[str, str]]  # (tc_id, reason)
    unparsed: list[tuple[str, str]]  # (tc_id, assertion_text)
    manual_count: int


def emit_file(
    parse_result: ParseResult,
    file_type: str,
    profile_path: str | Path | None = None,
    output_dir: str | Path = "test_workspace/tests/generated",
    project: ProjectConfig | None = None,
) -> EmitResult:
    """Emit a pytest file from a ParseResult.

    Args:
        parse_result: Output from parser.parse_case_file()
        file_type: "business" or "boundary"
        profile_path: Path to codegen_profile_{module}.md (optional)
        output_dir: Directory for generated .py files
    """
    module = parse_result.module
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"test_{module}_{file_type}.py"

    profile_rules = load_profile_rules(profile_path) if profile_path else []
    request_overrides = load_profile_request_overrides(profile_path) if profile_path else {}
    extra_imports = load_profile_extra_imports(profile_path) if profile_path else []
    case_fixtures = load_profile_case_fixtures(profile_path) if profile_path else {}
    case_bodies = load_profile_case_bodies(profile_path) if profile_path else {}
    proj = project or DEFAULT_PROJECT

    ctx = EmitContext(
        module=module,
        file_type=file_type,
        source_path=parse_result.source_file,
        shared_config=parse_result.shared_config,
        project=proj,
        profile_rules=profile_rules,
        request_overrides=request_overrides,
        extra_imports=extra_imports,
        case_fixtures=case_fixtures,
        case_bodies=case_bodies,
        variables=parse_result.shared_config.variables,
    )

    all_lines: list[str] = []
    skipped: list[tuple[str, str]] = []
    all_unparsed: list[tuple[str, str]] = []
    manual_count = 0
    case_count = 0

    has_grpc = any(
        any("gRPC" in v for v in tc.scenario_vars.values())
        for tc in parse_result.cases
        if not any("可行性存疑" in m for m in tc.markers)
    )

    # Header
    all_lines.extend(_render_header(ctx, has_grpc=has_grpc))

    # BASE_REQUEST
    all_lines.extend(_render_base_request(ctx))

    # _req helper
    if ctx.shared_config.base_request_http:
        all_lines.extend(_render_req_helper(ctx))

    # Class
    class_name = _module_class_name(module, file_type)
    desc = f"{module} {'业务' if file_type == 'business' else '边界'}测试用例"
    all_lines.extend(["", "", f"class {class_name}:"])
    all_lines.append(f'    """{desc}"""')

    _CN_NUMBERS = "一二三四五六七八九十"

    current_section = ""
    section_idx = 0

    for tc in parse_result.cases:
        # Skip feasibility-questioned cases
        skip_markers = [m for m in tc.markers if "可行性存疑" in m]
        if skip_markers:
            reason = skip_markers[0]
            skipped.append((tc.id, reason))
            continue

        is_manual = any("manual" in m.lower() for m in tc.markers)
        if is_manual:
            manual_count += 1

        # Section comment
        if tc.section and tc.section != current_section:
            current_section = tc.section
            cn_num = _CN_NUMBERS[section_idx] if section_idx < len(_CN_NUMBERS) else str(section_idx + 1)
            section_idx += 1
            all_lines.append("")
            all_lines.append(f"    # ── {cn_num}、{current_section} ──")

        all_lines.append("")
        func_lines, unparsed = _render_test_function(tc, ctx)
        all_lines.extend(func_lines)
        case_count += 1

        for u in unparsed:
            all_unparsed.append((tc.id, u))

    # Footer: TODO + SKIPPED
    all_lines.append("")
    all_lines.append("")
    fixture_path = Path("test_workspace/tests/fixtures") / f"{module}.py"
    if not fixture_path.exists():
        all_lines.append(
            f"# TODO: setup_{module} fixture 需要手写实现（→ tests/fixtures/{module}.py）"
        )

    for tc_id, reason in skipped:
        all_lines.append(f"# SKIPPED: {tc_id} — {reason}")

    all_lines.append("")

    output_path.write_text("\n".join(all_lines), encoding="utf-8")

    return EmitResult(
        output_path=str(output_path),
        case_count=case_count,
        skipped=skipped,
        unparsed=all_unparsed,
        manual_count=manual_count,
    )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def emit_module(
    module: str,
    cases_dir: str | Path = "test_workspace/cases",
    output_dir: str | Path = "test_workspace/tests/generated",
    profile_dir: str | Path = "test_workspace/tests/fixtures",
    project: ProjectConfig | None = None,
) -> list[EmitResult]:
    """Emit all files for a module. Returns list of EmitResult."""
    cases_dir = Path(cases_dir)
    profile_path = Path(profile_dir) / f"codegen_profile_{module}.md"
    if not profile_path.exists():
        profile_path = None

    results = []
    for file_type in ("business", "boundary"):
        md_path = cases_dir / module / f"{file_type}.md"
        if not md_path.exists():
            continue
        parse_result = parse_case_file(str(md_path))
        result = emit_file(
            parse_result,
            file_type,
            profile_path=profile_path,
            output_dir=output_dir,
            project=project,
        )
        results.append(result)

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m aitest_kit.codegen.emitter <module>")
        sys.exit(1)

    module = sys.argv[1]
    results = emit_module(module)
    for r in results:
        print(f"\n{r.output_path}")
        print(f"  Cases: {r.case_count}")
        print(f"  Manual: {r.manual_count}")
        print(f"  Skipped: {len(r.skipped)}")
        if r.skipped:
            for tc_id, reason in r.skipped:
                print(f"    {tc_id}: {reason}")
        print(f"  Unparsed: {len(r.unparsed)}")
        if r.unparsed:
            for tc_id, text in r.unparsed:
                print(f"    {tc_id}: {text}")
