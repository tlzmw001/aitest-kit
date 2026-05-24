"""Case IR data structures for codegen planning.

The IR explains how a parsed Markdown case will be generated. It is a
planning artifact, not the Markdown parser and not the pytest renderer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DiagnosticIR:
    code: str
    layer: str
    message: str


@dataclass
class SourceTraceIR:
    value: Any
    source: str
    reason: str = ""


@dataclass
class SetupCallIR:
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestIR:
    source: str
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass
class CallIR:
    helper: str
    target: str
    api_path: str = ""


@dataclass
class VariableIR:
    name: str
    expression: str
    source: str


@dataclass
class AssertionIR:
    source: str
    kind: str
    code_lines: list[str] = field(default_factory=list)
    resolved_by: str = ""
    variables: list[str] = field(default_factory=list)


@dataclass
class CustomBodyIR:
    source: str
    fixtures: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)


@dataclass
class CaseFlowStepIR:
    kind: str
    call: str = ""
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    save_as: str = ""
    target: str = ""
    expr: str = ""
    comment: str = ""
    assertion: AssertionIR | None = None


@dataclass
class CaseFlowIR:
    source: str
    fixture: str
    object_name: str = ""
    steps: list[CaseFlowStepIR] = field(default_factory=list)


@dataclass
class CaseIR:
    case_id: str
    title: str
    module: str
    category: str
    source_file: str
    section: str
    priority: str
    markers: list[str]
    strategy: str
    protocol: str
    skip_reason: str | None = None
    fixtures: list[str] = field(default_factory=list)
    setup_call: SetupCallIR | None = None
    request: RequestIR | None = None
    call: CallIR | None = None
    variables: list[VariableIR] = field(default_factory=list)
    assertions: list[AssertionIR] = field(default_factory=list)
    custom_body: CustomBodyIR | None = None
    case_flow: CaseFlowIR | None = None
    diagnostics: list[DiagnosticIR] = field(default_factory=list)
    source_trace: dict[str, SourceTraceIR] = field(default_factory=dict)


@dataclass
class FileIR:
    module: str
    category: str
    source_file: str
    diagnostics: list[DiagnosticIR] = field(default_factory=list)
    cases: list[CaseIR] = field(default_factory=list)


def ir_to_dict(value: Any) -> Any:
    """Convert dataclass IR objects to plain JSON-serializable structures."""
    return asdict(value)
