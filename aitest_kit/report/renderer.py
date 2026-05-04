"""Render result.json payloads as Markdown reports."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = [
        "# 测试执行报告",
        "",
        f"- **运行 ID**：{result.get('run_id', '')}",
        f"- **运行状态**：{result.get('status', '')}",
        f"- **时间**：{result.get('timestamp', '')}",
        f"- **耗时**：{result.get('duration_seconds', 0)}s",
        f"- **命令**：`{result.get('command', '')}`",
        f"- **Codegen Check**：{result.get('codegen_check', {}).get('status', '')}",
        f"- **Manual 策略**：{result.get('manual_policy', '')}",
        "",
    ]

    if result.get("status") == "BLOCKED_RUN":
        lines.extend(_blocked_section(result))
        return "\n".join(lines) + "\n"

    summary = result.get("summary", {})
    lines.extend([
        "## 执行摘要",
        "",
        "### 自动化结果",
        "",
        "| 状态 | 数量 |",
        "|------|------|",
        f"| 通过 | {summary.get('passed', 0)} |",
        f"| 失败 | {summary.get('failed', 0)} |",
        f"| 错误 | {summary.get('error', 0)} |",
        f"| pytest skipped | {summary.get('pytest_skipped', 0)} |",
        f"| **本次自动化收集** | **{summary.get('auto_collected', 0)}** |",
        "",
        "### 未进入本次自动化执行",
        "",
        "| 类型 | 数量 |",
        "|------|------|",
        f"| manual 总数 | {summary.get('manual_total', 0)} |",
        f"| manual 已执行 | {summary.get('manual_executed', 0)} |",
        f"| manual 未执行 | {summary.get('manual_not_run', 0)} |",
        f"| codegen skipped | {summary.get('codegen_skipped', 0)} |",
        "",
    ])
    lines.extend(_module_section(result.get("modules", {})))
    lines.extend(_failure_sections(result.get("cases", [])))
    lines.extend(_feedback_section(result))
    return "\n".join(lines) + "\n"


def _blocked_section(result: dict[str, Any]) -> list[str]:
    check = result.get("codegen_check", {})
    return [
        "## BLOCKED_RUN",
        "",
        "generated freshness check 失败，pytest 未执行。",
        "",
        f"- **Codegen Check**：{check.get('status', '')}",
        f"- **原因**：{check.get('message', '')}",
        "- **下一步**：先运行 `aitest codegen {modules}`，再运行 `aitest run {modules}`",
        "",
    ]


def _module_section(modules: dict[str, Any]) -> list[str]:
    lines = [
        "## 按模块统计",
        "",
        "| 模块 | business | boundary | 通过率 |",
        "|------|----------|----------|--------|",
    ]
    for module, categories in sorted(modules.items()):
        business = categories.get("business", {})
        boundary = categories.get("boundary", {})
        passed = sum(cat.get("passed", 0) for cat in categories.values())
        total = sum(cat.get("auto_collected", 0) for cat in categories.values())
        rate = f"{(passed / total * 100):.1f}%" if total else "-"
        lines.append(
            f"| {module} | {_passed_total(business)} | {_passed_total(boundary)} | {rate} |"
        )
    lines.append("")
    return lines


def _passed_total(bucket: dict[str, Any]) -> str:
    if not bucket:
        return "-"
    return f"{bucket.get('passed', 0)}/{bucket.get('auto_collected', 0)}"


def _failure_sections(cases: list[dict[str, Any]]) -> list[str]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        failure = case.get("failure")
        if failure:
            groups[failure.get("classification", "UNKNOWN")].append(case)

    lines = ["## 失败详情", ""]
    if not groups:
        lines.extend(["无失败。", ""])
        return lines

    for classification in [
        "ENVIRONMENT_ERROR",
        "FIXTURE_ERROR",
        "CODEGEN_ERROR",
        "ASSERTION_FAILURE",
        "TEARDOWN_ERROR",
        "UNKNOWN",
    ]:
        items = groups.get(classification, [])
        if not items:
            continue
        lines.extend([
            f"### {classification}（{len(items)} 条）",
            "",
            "| TC ID | 模块 | 异常摘要 | 复现命令 |",
            "|-------|------|----------|----------|",
        ])
        for case in items:
            failure = case.get("failure", {})
            lines.append(
                f"| {case.get('tc_id', '')} | {case.get('module', '')} | "
                f"{_cell(failure.get('message', ''))} | `pytest {case.get('nodeid', '')} -v` |"
            )
        lines.append("")
    return lines


def _feedback_section(result: dict[str, Any]) -> list[str]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in result.get("cases", []):
        failure = case.get("failure")
        if failure:
            groups[failure.get("classification", "UNKNOWN")].append(case)

    lines = [
        "## 反哺清单",
        "",
        "### 需要修 fixture / codegen profile",
        "",
    ]
    for classification in ("FIXTURE_ERROR", "CODEGEN_ERROR", "TEARDOWN_ERROR"):
        for case in groups.get(classification, []):
            lines.append(f"- {case.get('tc_id')}：{case.get('failure', {}).get('message', '')}")
    if len(lines) == 4:
        lines.append("- 无")

    lines.extend(["", "### 需要人工判断", ""])
    manual_items = groups.get("ASSERTION_FAILURE", []) + groups.get("UNKNOWN", [])
    for case in manual_items:
        lines.append(f"- {case.get('tc_id')}：{case.get('failure', {}).get('message', '')}")
    if not manual_items:
        lines.append("- 无")

    lines.extend(["", "### 环境问题（重启服务后重试）", ""])
    env_items = groups.get("ENVIRONMENT_ERROR", [])
    if env_items:
        modules = sorted({case.get("module", "") for case in env_items})
        lines.append(f"- {len(env_items)} 条 ENVIRONMENT_ERROR，重试命令：`aitest run {' '.join(modules)}`")
    else:
        lines.append("- 无")

    skipped = result.get("codegen_skipped_cases", [])
    lines.extend(["", "### codegen skipped", ""])
    if skipped:
        for item in skipped:
            lines.append(f"- {item.get('tc_id')}：{item.get('reason', '')}")
    else:
        lines.append("- 无")
    lines.append("")
    return lines


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")

