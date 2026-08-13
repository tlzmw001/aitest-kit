"""Rendering helpers for generated pytest files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aitest_kit.codegen.render_utils import dict_to_python


def render_header(
    ctx: Any,
    *,
    has_profile_variables: bool = False,
    has_structured_assertions: bool = False,
    has_default_http: bool = False,
    has_case_context: bool = False,
    has_module_harness: bool = False,
) -> list[str]:
    regenerate_hint = _regenerate_hint(ctx)
    lines = [
        f"# Auto-generated from {ctx.source_path}",
        f"# DO NOT EDIT — regenerate with: {regenerate_hint}",
    ]
    lines.extend([
        "import pytest",
        ctx.project.helper_import,
    ])
    if ctx.shared_config.base_request_http:
        lines.append("from aitest_kit.helpers.request_binding import build_request")
    if has_default_http:
        lines.append("from aitest_kit.helpers.capture import capture_io")
    if has_case_context:
        lines.append("from aitest_kit.runtime_context import reset_case_context, set_case_context")
    if has_profile_variables:
        lines.append("from aitest_kit.runtime_variables import resolve_profile_variables")
    if has_structured_assertions:
        lines.append("from aitest_kit.helpers import structured_assertions as aitest_assertions")
    if has_module_harness and ctx.module_binding:
        if ctx.module_binding.fixture_module:
            lines.append(
                f'pytest_plugins = ["{ctx.module_binding.fixture_module}"]'
            )
        elif ctx.module_binding.fixture_import:
            lines.append(ctx.module_binding.fixture_import)
    lines.extend(ctx.extra_imports)
    return lines


def render_base_request(ctx: Any) -> list[str]:
    body = ctx.shared_config.base_request_http
    if not body:
        return []
    lines = ["", ""]
    sanitized = dict(body)
    for key in ctx.project.default_request.auto_fields:
        if key in sanitized:
            sanitized[key] = None
    lines.append(f"BASE_REQUEST = {dict_to_python(sanitized)}")
    return lines


def render_req_helper() -> list[str]:
    return [
        "",
        "",
        "def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:",
        "    return build_request(",
        "        BASE_REQUEST,",
        "        auto_fields=auto_fields or {},",
        "        overrides=overrides or {},",
        "        patches=patches or [],",
        "    )",
    ]


def _regenerate_hint(ctx: Any) -> str:
    suite_manifest = Path(ctx.source_path).parent / "suite.yaml"
    if suite_manifest.exists():
        return f"aitest codegen --suite-file {suite_manifest}"
    return "aitest codegen --suite-file <suite.yaml>"
