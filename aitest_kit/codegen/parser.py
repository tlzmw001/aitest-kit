"""Deterministic Markdown test case parser.

Extracts SharedConfig + TestCase list from business.md / boundary.md files.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SharedConfig:
    interfaces: list[str] = field(default_factory=list)
    base_request_http: dict | None = None
    base_request_grpc: str | None = None
    preconditions: list[str] = field(default_factory=list)
    common_assertions: list[str] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)


@dataclass
class TestCase:
    id: str = ""
    title: str = ""
    priority: str = ""
    scenario_vars: dict[str, str] = field(default_factory=dict)
    assertions: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    section: str = ""


@dataclass
class ParseResult:
    module: str = ""
    source_file: str = ""
    shared_config: SharedConfig = field(default_factory=SharedConfig)
    cases: list[TestCase] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_COLON = re.compile(r"[：:]")
_TC_HEADER = re.compile(r"^###\s+(TC-[A-Z]+-\d+)[：:]\s*(.+)")
_SECTION_HEADER = re.compile(r"^##\s+[一二三四五六七八九十]+[、.．]\s*(.+)")
_FIELD_LINE = re.compile(r"^-\s+\*\*(.+?)\*\*[：:]\s*(.*)")
_LIST_ITEM = re.compile(r"^\s+-\s+(.*)")


def _split_assertions(raw: str) -> list[str]:
    """Split assertion string on ；or ; respecting backtick spans."""
    parts = re.split(r"[；;]", raw)
    return [p.strip() for p in parts if p.strip()]


def _extract_json_block(lines: list[str], start: int) -> tuple[dict | None, int]:
    """Extract a ```json ... ``` code block starting at or after `start`."""
    i = start
    while i < len(lines):
        if lines[i].strip().startswith("```json"):
            break
        i += 1
    else:
        return None, start
    i += 1
    json_lines = []
    while i < len(lines) and not lines[i].strip().startswith("```"):
        json_lines.append(lines[i])
        i += 1
    try:
        return json.loads("\n".join(json_lines)), i + 1
    except json.JSONDecodeError:
        return None, i + 1


def _extract_text_block(lines: list[str], start: int) -> tuple[str | None, int]:
    """Extract a ```text ... ``` or ``` ... ``` code block."""
    i = start
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("```text") or (stripped == "```" and i > start):
            break
        if stripped.startswith("```") and not stripped.startswith("```json"):
            break
        i += 1
    else:
        return None, start
    i += 1
    text_lines = []
    while i < len(lines) and not lines[i].strip().startswith("```"):
        text_lines.append(lines[i])
        i += 1
    return "\n".join(text_lines), i + 1


# ---------------------------------------------------------------------------
# Shared config parsing
# ---------------------------------------------------------------------------

def _parse_shared_config(lines: list[str]) -> tuple[SharedConfig, int]:
    cfg = SharedConfig()
    start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("## 共享配置"):
            start = i + 1
            break
    else:
        return cfg, 0

    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].strip().startswith("---") and i > start + 1:
            end = i
            break
        if lines[i].strip().startswith("## ") and "共享配置" not in lines[i]:
            end = i
            break

    i = start
    while i < end:
        line = lines[i].strip()

        if line.startswith("**接口**"):
            raw = _COLON.split(line, 1)[-1].strip()
            cfg.interfaces = [s.strip().strip("`") for s in raw.split(" / ") if s.strip()]

        elif line.startswith("**基础请求体（HTTP）**") or line.startswith("**基础请求体(HTTP)**"):
            body, i = _extract_json_block(lines, i + 1)
            cfg.base_request_http = body
            continue

        elif line.startswith("**基础请求体（gRPC）**") or line.startswith("**基础请求体(gRPC)**"):
            text, i = _extract_text_block(lines, i + 1)
            cfg.base_request_grpc = text
            continue

        elif line.startswith("**标准前置**"):
            i += 1
            while i < end and lines[i].strip().startswith("- "):
                cfg.preconditions.append(lines[i].strip()[2:])
                i += 1
            continue

        elif line.startswith("**通用断言**"):
            raw = _COLON.split(line, 1)[-1].strip()
            if raw:
                cfg.common_assertions = _split_assertions(raw)
            i += 1
            while i < end and lines[i].strip().startswith("- "):
                cfg.common_assertions.append(lines[i].strip()[2:])
                i += 1
            continue

        elif line.startswith("**变量定义**"):
            i += 1
            while i < end and lines[i].strip().startswith("- "):
                item = lines[i].strip()[2:]
                m = re.match(r"`?([\w()]+)`?\s*=\s*(.+)", item)
                if m:
                    cfg.variables[m.group(1)] = m.group(2).strip()
                i += 1
            continue

        i += 1

    return cfg, end


# ---------------------------------------------------------------------------
# Test case parsing
# ---------------------------------------------------------------------------

def _add_var(d: dict[str, str], key: str, value: str) -> None:
    """Add key:value to dict, appending numeric suffix on duplicate keys."""
    if key not in d:
        d[key] = value
    else:
        n = 2
        while f"{key}_{n}" in d:
            n += 1
        d[f"{key}_{n}"] = value


def _parse_scenario_vars(lines: list[str], start: int, block_end: int) -> tuple[dict[str, str], int]:
    """Parse 场景变量 field — single inline or multi-line key:value items."""
    result: dict[str, str] = {}
    i = start
    while i < block_end:
        stripped = lines[i].strip()
        if not stripped.startswith("- ") or stripped.startswith("- **"):
            break
        item = stripped[2:]
        parts = _COLON.split(item, 1)
        if len(parts) == 2:
            _add_var(result, parts[0].strip(), parts[1].strip())
        else:
            _add_var(result, f"_unnamed", item)
        i += 1
    return result, i


def _find_case_end(lines: list[str], start: int) -> int:
    """Find where the current TC block ends (next ### or ## or EOF)."""
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("### ") or stripped.startswith("## "):
            return i
    return len(lines)


def _parse_cases(lines: list[str], config_end: int) -> list[TestCase]:
    cases: list[TestCase] = []
    current_section = ""

    i = config_end
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("## 覆盖变更"):
            break

        section_m = _SECTION_HEADER.match(stripped)
        if section_m:
            current_section = section_m.group(1)
            i += 1
            continue

        tc_m = _TC_HEADER.match(stripped)
        if not tc_m:
            i += 1
            continue

        tc = TestCase(id=tc_m.group(1), title=tc_m.group(2).strip(), section=current_section)
        case_end = _find_case_end(lines, i)
        j = i + 1

        while j < case_end:
            field_m = _FIELD_LINE.match(lines[j].strip())
            if not field_m:
                j += 1
                continue

            fname = field_m.group(1).strip()
            fval = field_m.group(2).strip()

            if fname == "优先级":
                tc.priority = fval

            elif fname == "场景变量":
                if fval:
                    parts = _COLON.split(fval, 1)
                    if len(parts) == 2:
                        _add_var(tc.scenario_vars, parts[0].strip(), parts[1].strip())
                    else:
                        _add_var(tc.scenario_vars, "_inline", fval)
                j += 1
                sub_vars, j = _parse_scenario_vars(lines, j, case_end)
                for k, v in sub_vars.items():
                    _add_var(tc.scenario_vars, k, v)
                continue

            elif fname == "断言":
                tc.assertions = _split_assertions(fval)

            elif fname == "标记":
                tc.markers = [m.strip() for m in re.split(r"[、,]", fval) if m.strip()]

            j += 1

        cases.append(tc)
        i = case_end

    return cases


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_case_file(path: str | Path) -> ParseResult:
    """Parse a single Markdown case file into structured data."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    module = path.parent.name
    shared_config, config_end = _parse_shared_config(lines)
    cases = _parse_cases(lines, config_end)

    return ParseResult(
        module=module,
        source_file=str(path),
        shared_config=shared_config,
        cases=cases,
    )


# ---------------------------------------------------------------------------
# CLI entry for standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m aitest_kit.codegen.parser <path_to_md>")
        sys.exit(1)

    result = parse_case_file(sys.argv[1])
    print(f"Module: {result.module}")
    print(f"Source: {result.source_file}")
    print(f"\n=== Shared Config ===")
    cfg = result.shared_config
    print(f"  Interfaces: {cfg.interfaces}")
    print(f"  HTTP body keys: {list(cfg.base_request_http.keys()) if cfg.base_request_http else 'None'}")
    print(f"  gRPC body: {'yes' if cfg.base_request_grpc else 'no'}")
    print(f"  Preconditions: {len(cfg.preconditions)}")
    print(f"  Common assertions: {cfg.common_assertions}")
    print(f"  Variables: {cfg.variables}")

    print(f"\n=== Cases ({len(result.cases)}) ===")
    for tc in result.cases:
        print(f"\n  {tc.id}: {tc.title}")
        print(f"    Priority: {tc.priority}")
        print(f"    Section: {tc.section}")
        print(f"    Scenario vars: {tc.scenario_vars}")
        print(f"    Assertions: {tc.assertions}")
        if tc.markers:
            print(f"    Markers: {tc.markers}")
