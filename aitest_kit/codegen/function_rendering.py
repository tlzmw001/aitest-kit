"""Shared rendering for generated pytest test functions."""
from __future__ import annotations

from typing import Any

from aitest_kit.codegen.render_utils import render_assignment, tc_func_name


def render_case_function(
    *,
    case_id: str,
    title: str,
    fixtures: list[str],
    manual: bool,
    metadata: dict[str, Any],
    body_lines: list[str],
) -> list[str]:
    """Render a generated pytest test function with case identity context."""
    lines: list[str] = []
    if manual:
        lines.append("    @pytest.mark.manual")

    signature = ", ".join(["self", *fixtures])
    lines.append(f"    def {tc_func_name(case_id)}({signature}):")
    lines.append(f'        """{case_id}：{title}"""')
    lines.extend(render_assignment("__tc_meta__", metadata, indent=2))
    lines.append(
        '        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)'
    )
    lines.append("        try:")
    rendered_body = [_indent_try_body_line(line) for line in body_lines]
    if any(line.strip() for line in rendered_body):
        lines.extend(rendered_body)
    else:
        lines.append("            pass")
    lines.append("        finally:")
    lines.append("            reset_case_context(__aitest_ctx_token)")
    return lines


def _indent_try_body_line(line: str) -> str:
    if not line:
        return ""
    return f"    {line}"
