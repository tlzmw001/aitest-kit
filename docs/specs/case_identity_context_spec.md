# Case Identity Runtime Context Spec

## Status

IMPLEMENTED

## Background

Run capture currently requires user-owned fixtures and helpers to pass
`case_id` into `capture_io()` explicitly. This is simple, but company-project
migration exposed an architectural leak: `case_id` is test framework metadata,
while fixture client methods usually model business or protocol operations.

Generated tests already create per-case metadata as `__tc_meta__`, but that
metadata is local to the generated test function. User fixtures and client
methods cannot access it unless `case_id` is threaded through `case_flow`
arguments or `default_case_setup`.

The goal is not to make `case_flow` auto-capture. The goal is to expose the
current generated test case identity as a small runtime context so user-owned
capture/logging code can attribute records without polluting business helper
signatures.

## Current Architecture Snapshot

The codegen pipeline is:

```text
CLI selector
  -> SuiteContext
  -> runtime profile merge
  -> profile gate
  -> Markdown parser
  -> FileIR / CaseIR planner
  -> pytest renderer
  -> aitest run freshness check
  -> pytest subprocess
  -> result/report/capture files
```

Relevant current boundaries:

- `aitest_kit/codegen/suite.py` merges module and suite profile data into a
  `RuntimeProfile`.
- `aitest_kit/codegen/planner.py` chooses strategy and creates `CaseIR`.
- `aitest_kit/codegen/ir_renderer.py` renders generated pytest and currently
  creates `__tc_meta__` inside every generated test function.
- `aitest_kit/helpers/capture.py` writes capture JSONL records and currently
  requires a `case_id` argument.
- `aitest_kit/report/cli.py` and `aitest_kit/report/task_runner.py` only enable
  capture by injecting environment variables into the pytest subprocess.

## Goals

- Add a narrow runtime case identity context for generated pytest execution.
- Let `capture_io()` infer `case_id` from the current context when no explicit
  `case_id` is provided.
- Preserve explicit `capture_io(case_id, ...)` for compatibility and non-codegen
  use.
- Keep `case_flow` and `case_body` capture user-owned: no automatic capture for
  these strategies.
- Reduce mechanical `case_id` threading needed only for capture/log attribution.
- Centralize generated test function metadata setup so future renderer changes
  do not duplicate per-strategy prologue logic.

## Non-Goals

- No automatic `case_flow` capture.
- No request, response, headers, cookies, token, env, base URL, profile variable,
  or business payload storage in context.
- No failure DSL or automatic failure detection.
- No automatic redaction.
- No replacement for `requests.<case_id>.patches`.
- No replacement for `variables.cases`.
- No fixture behavior branching by `case_id`.
- No pytest hook/plugin in the first version.
- No guarantee that module/session fixture setup can read current case context.
- No broad codegen refactor in the first implementation.

## Public Runtime API

Add a small helper module, recommended path:

```python
from aitest_kit.runtime_context import current_case_id
```

Public functions:

```python
def current_case_id() -> str | None:
    """Return the current generated test case id, or None outside a test body."""
```

Internal functions used by generated pytest:

```python
def set_case_context(case_id: str, metadata: dict[str, object] | None = None):
    """Set current generated case identity and return a reset token."""

def reset_case_context(token) -> None:
    """Reset current generated case identity."""
```

Implementation should use `contextvars.ContextVar`, not a plain module global.
This avoids accidental case bleed in async or nested execution paths.

The first version should treat `metadata` as internal. Only `current_case_id()`
is public. Extra metadata can be stored for future diagnostics, but it should
not be exposed until a separate spec approves it.

## Capture API Change

Change `capture_io()` from requiring `case_id` to accepting an optional value:

```python
def capture_io(
    case_id: str | None = None,
    *,
    label: str = "",
    protocol: str = "",
    request: Any = _UNSET,
    response: Any = _UNSET,
    exception: Any = _UNSET,
    metadata: dict[str, Any] | None = None,
) -> None:
    ...
```

Resolution order:

```text
explicit case_id > current runtime case context > no capture record
```

Rules:

- If capture is disabled, `capture_io()` remains a no-op.
- If capture is enabled but no explicit or contextual `case_id` exists,
  `capture_io()` must not write a misleading record such as `case_id="unknown"`.
- Explicit `case_id` keeps existing behavior.
- Positional `capture_io("TC-ITEM-001", ...)` remains valid.

## Generated Pytest Shape

Generated test functions should set case context for the duration of the test
body and always reset it.

Conceptual output:

```python
def test_tc_item_001(self, setup_item):
    """TC-ITEM-001: create item"""
    __tc_meta__ = {
        "tc_id": "TC-ITEM-001",
        "module": "item",
        "category": "item_smoke_business",
        "source": "test_workspace/suites/app/item_smoke/business.md",
        "title": "create item",
        "priority": "P1",
        "markers": [],
    }
    __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
    try:
        ...
    finally:
        reset_case_context(__aitest_ctx_token)
```

This should apply to executable generated test bodies:

- `default_http`
- `structured_case_flow`
- `custom_case_body`
- semi-automated manual cases that still render an executable body

Skipped cases that are not rendered as test functions do not need context.

## Renderer Refactor Boundary

The implementation should avoid adding duplicate set/reset blocks inside every
strategy renderer. Introduce a renderer helper for common test function setup.

Recommended responsibilities:

- render function signature and docstring
- render `__tc_meta__`
- render `set_case_context(...)`
- render profile variable resolution when needed
- render setup comments
- wrap strategy body lines in `try/finally`
- render `reset_case_context(...)`

Keep strategy renderers focused on strategy-specific body lines:

- default HTTP request/call/assertions
- case flow request refs, steps, structured assertions
- custom body lines
- manual comments and skip

## What This Simplifies

### Capture-only case_id threading

Fixtures that only need `case_id` for capture/log attribution can stop accepting
it explicitly:

```python
capture_io(label="POST /items", protocol="http", request=req, response=resp)
```

`case_flow` profiles do not need to pass `case_id` only for this purpose.

### Default HTTP capture

The default HTTP path may keep explicit `capture_io(__tc_meta__["tc_id"], ...)`
in the first implementation. A later cleanup may remove the explicit argument
once context behavior is proven stable.

### Renderer metadata duplication

`__tc_meta__` currently appears in each strategy renderer. Context setup is a
good forcing function to consolidate that common prologue.

## What This Does Not Simplify

### Per-case business setup

Do not remove `default_case_setup` when a factory genuinely needs the case id
to create per-case resources, temporary files, service instances, or cleanup
handles.

Valid use remains:

```yaml
default_case_setup:
  call: client_factory
  kwargs:
    case_id: "{case_id}"
  save_as: client
```

### Request differences

Request differences stay in profile-owned request bindings:

```yaml
requests:
  TC-ITEM-001:
    patches:
      - op: replace
        path: /name
        value: demo
```

Fixtures must not read `current_case_id()` to mutate request payloads.

### Case-scoped variables

Case-specific values stay in:

```yaml
variables:
  cases:
    TC-ITEM-001:
      token:
        env: ITEM_TEST_TOKEN
```

Fixtures must not use context to choose accounts, tokens, base URLs, or other
business data.

## Safety Rules

- Context is for attribution only: capture, logging, and diagnostics.
- Context must not become a general data bag.
- Context absence must be safe and explicit.
- Context reset must happen in a `finally` block.
- Context must not change test pass/fail behavior.
- Capture failures must continue not to fail tests.
- Existing explicit `capture_io(case_id, ...)` calls must remain valid.

## Architecture Debt Recorded For Later

These are related but should not be fixed in the first context implementation.

### Shared strategy resolver

`planner.py` and `profile_validator.py` each resolve case strategy. Their order
and purpose are close but not identical. Introduce a shared strategy resolver
after context lands, then let planner and validator consume it to avoid future
strategy drift.

### NormalizedProfile

Profile data is loaded and normalized repeatedly by `emitter.py`, `planner.py`,
`profile.py`, and validation code. Introduce a `NormalizedProfile` object in a
separate cleanup so profile loading, defaults, variables, requests, case flows,
and diagnostics have one canonical shape.

### setup_call vs default_case_setup

The default HTTP path has `SetupCallIR`, while case flow has
`default_case_setup`. Both can move case identity into fixture/factory code.
After context lands, audit generated suites and decide which uses are
capture-only and which are true per-case setup.

### Renderer file size and strategy body split

`ir_renderer.py` is larger than the project file-size rule target and mixes
header rendering, request helper rendering, strategy rendering, and summary
metadata. Split only after the context helper creates a clear prologue/body
boundary.

### Profile validator size

`profile_validator.py` is also larger than the project file-size rule target and
contains schema checks, semantic checks, case reference checks, warnings, and
module type checks. Split after a shared `NormalizedProfile` exists.

## Implementation Targets

- `aitest_kit/runtime_context.py`
  - add `current_case_id()`
  - add internal set/reset helpers
  - use `contextvars.ContextVar`

- `aitest_kit/helpers/capture.py`
  - make `case_id` optional
  - resolve missing `case_id` from runtime context
  - keep explicit `case_id` precedence
  - do not write a record if capture is enabled but case identity is unavailable

- `aitest_kit/codegen/ir_renderer.py`
  - import runtime context helpers when at least one executable test function is
    rendered
  - add common generated test prologue/reset helper
  - keep no automatic case_flow capture

- Tests
  - context helper set/read/reset
  - `capture_io()` with explicit `case_id`
  - `capture_io()` using current context
  - `capture_io()` with capture enabled but no identity writes nothing
  - generated `case_flow` sets context but does not import/call capture
  - generated `default_http` still captures with correct `case_id`
  - context reset after exception

- Docs and templates
  - update `docs/specs/run_capture_spec.md`
  - update `aitest_config/refs/config-files.md`
  - update template config docs
  - update test-scaffold/test-codegen skill references to forbid context-based
    case branching and to prefer context for capture/log attribution

## Verification

Minimum verification for the first implementation:

```bash
python3 -m compileall aitest_kit
python3 -m pytest tests/test_capture.py tests/test_codegen_ir.py -q
python3 -m pytest tests -q
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli run --all -- --collect-only -q
```

Manual acceptance:

- A `case_flow` fixture can call `capture_io(label=..., request=..., response=...)`
  without receiving `case_id`, and the resulting capture JSONL record contains
  the current TC id.
- A `case_flow` without fixture capture still produces no capture records.
- Existing explicit `capture_io("TC-...", ...)` calls keep working.
