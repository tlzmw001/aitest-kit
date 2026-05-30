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
    ]
    lines.extend(_run_scope_summary(result))
    lines.extend([
        f"- **Codegen Check**：{result.get('codegen_check', {}).get('status', '')}",
        f"- **Manual 策略**：{result.get('manual_policy', '')}",
    ])
    lines.extend(_environment_summary(result.get("environment", {})))
    lines.append("")

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
    lines.extend(_manual_section(result.get("manual_cases", [])))
    lines.extend(_module_section(result.get("modules", {})))
    lines.extend(_failure_sections(result.get("cases", [])))
    lines.extend(_feedback_section(result))
    return "\n".join(lines) + "\n"


def _run_scope_summary(result: dict[str, Any]) -> list[str]:
    if result.get("task_file"):
        return [
            f"- **Task 文件**：{result.get('task_file', '')}",
        ]
    if result.get("suite") or result.get("suite_file"):
        return [
            f"- **Target**：{result.get('target') or '-'}",
            f"- **Module**：{result.get('module') or '-'}",
            f"- **Suite**：{result.get('suite') or '-'}",
            f"- **Suite 文件**：{result.get('suite_file') or '-'}",
        ]
    return []


def _blocked_section(result: dict[str, Any]) -> list[str]:
    check = result.get("codegen_check", {})
    if result.get("blocked_reason") == "env_file":
        environment = result.get("environment", {})
        return [
            "## BLOCKED_RUN",
            "",
            "运行环境文件加载失败，pytest 未执行。",
            "",
            f"- **Env 文件**：{environment.get('env_file', '')}",
            f"- **原因**：{environment.get('env_file_error', '')}",
            "- **下一步**：修正 `AITEST_ENV_FILE` 指向的文件后重新运行 `aitest run`",
            "",
        ]
    return [
        "## BLOCKED_RUN",
        "",
        "generated freshness check 失败，pytest 未执行。",
        "",
        f"- **Codegen Check**：{check.get('status', '')}",
        f"- **原因**：{check.get('message', '')}",
        "- **下一步**：先运行对应的 `aitest codegen --suite-file <suite.yaml>`，再运行 `aitest run --suite-file <suite.yaml>`",
        "",
    ]


def _environment_summary(environment: dict[str, Any]) -> list[str]:
    if not environment:
        return []
    env_file = environment.get("env_file", "")
    if not env_file:
        return ["- **Env 文件**：未加载"]
    loaded = "已加载" if environment.get("env_file_loaded") else "未加载"
    keys = environment.get("env_file_keys", [])
    key_text = ", ".join(keys) if keys else "-"
    return [
        f"- **Env 文件**：{env_file}（{loaded}）",
        f"- **Env 变量名**：{key_text}",
    ]


def _manual_section(manual_cases: list[dict[str, Any]]) -> list[str]:
    lines = ["## Manual 用例", ""]
    if not manual_cases:
        lines.append("- 无")
        lines.append("")
        return lines
    for item in manual_cases:
        lines.append(
            f"- {item.get('tc_id')}：{item.get('title', '')}"
            f"（{item.get('module', '')}/{item.get('suite', '')}）"
        )
    lines.append("")
    return lines


def _module_section(modules: dict[str, Any]) -> list[str]:
    categories_seen = {
        category
        for categories in modules.values()
        for category in categories
    }
    if categories_seen and not categories_seen <= {"business", "boundary"}:
        return _dynamic_module_section(modules)

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


def _dynamic_module_section(modules: dict[str, Any]) -> list[str]:
    lines = [
        "## 按模块统计",
        "",
        "| 模块 | 分类 | 通过 | 失败 | 错误 | skipped | 通过率 |",
        "|------|------|------|------|------|---------|--------|",
    ]
    for module, categories in sorted(modules.items()):
        for category, bucket in sorted(categories.items()):
            total = bucket.get("auto_collected", 0)
            passed = bucket.get("passed", 0)
            rate = f"{(passed / total * 100):.1f}%" if total else "-"
            lines.append(
                f"| {module} | {category} | {passed}/{total} | "
                f"{bucket.get('failed', 0)} | {bucket.get('error', 0)} | "
                f"{bucket.get('pytest_skipped', 0)} | {rate} |"
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
        "PRECONDITION_MISSING",
        "ENVIRONMENT_ERROR",
        "TEST_SCAFFOLD_ERROR",
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
        "### 运行前置条件缺失",
        "",
    ]
    precondition_items = groups.get("PRECONDITION_MISSING", [])
    for case in precondition_items:
        failure = case.get("failure", {})
        missing_env = ", ".join(failure.get("missing_env", []))
        detail = f"缺失 env：{missing_env}" if missing_env else failure.get("message", "")
        lines.append(f"- {case.get('tc_id')}：{detail}")
    if not precondition_items:
        lines.append("- 无")

    lines.extend(["", "### 需要修 scaffold / fixture / helper", ""])
    for classification in ("TEST_SCAFFOLD_ERROR", "FIXTURE_ERROR", "TEARDOWN_ERROR"):
        for case in groups.get(classification, []):
            lines.append(f"- {case.get('tc_id')}：{case.get('failure', {}).get('message', '')}")
    if not any(groups.get(item) for item in ("TEST_SCAFFOLD_ERROR", "FIXTURE_ERROR", "TEARDOWN_ERROR")):
        lines.append("- 无")

    lines.extend(["", "### 需要修 AITest Kit / codegen", ""])
    codegen_items = groups.get("CODEGEN_ERROR", [])
    for case in codegen_items:
        lines.append(f"- {case.get('tc_id')}：{case.get('failure', {}).get('message', '')}")
    if not codegen_items:
        lines.append("- 无")

    lines.extend(["", "### 需要人工判断", ""])
    manual_items = groups.get("ASSERTION_FAILURE", []) + groups.get("UNKNOWN", [])
    for case in manual_items:
        lines.append(f"- {case.get('tc_id')}：{case.get('failure', {}).get('message', '')}")
    if not manual_items:
        lines.append("- 无")

    lines.extend(["", "### 环境问题（检查服务/依赖后重试）", ""])
    env_items = groups.get("ENVIRONMENT_ERROR", [])
    if env_items:
        command = result.get("command") or "aitest run --suite-file <suite.yaml>"
        lines.append(f"- {len(env_items)} 条 ENVIRONMENT_ERROR，重试命令：`{command}`")
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
