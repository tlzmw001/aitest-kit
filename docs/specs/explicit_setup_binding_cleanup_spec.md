# Explicit Setup Binding Cleanup Spec

## Status

IMPLEMENTED

## Background

Codegen currently has two setup mechanisms with different ownership models:

```text
default_http:
  parser -> planner
    -> CaseIR.setup_call = setup_{module}(case_id="{case_id}")
    -> renderer emits the call before the HTTP request

case_flow:
  profile default_case_setup / case_flows
    -> ResolvedProfile applies the default setup step
    -> CaseFlowIR renders explicit flow steps
```

The `case_flow` path is explicit and profile-owned. The generated setup step
has a declared call, arguments, and optional `save_as` value that later flow
steps can consume.

The `default_http` path is implicit and planner-owned. A case that only asks for
the default HTTP strategy still gets a generated `setup_{module}(case_id=...)`
call. The return value is not used by the default HTTP renderer, so the call can
only work through side effects such as data setup, cache setup, or hidden
per-case branching inside a fixture.

That implicit behavior makes migrated projects harder to reason about:

- Users may provide a fixture/client/helper that does not accept `case_id`.
- Generated default HTTP tests call setup code that the profile did not declare.
- Runtime case context already covers capture/log attribution, so passing
  `case_id` through implicit setup is no longer needed for observability.
- Real per-case data setup belongs in explicit `case_flow` steps.

## Goal

Make setup ownership explicit:

- `default_http` is a simple single-request strategy.
- `default_http` does not generate `setup_{module}(case_id=...)`.
- `default_http` does not inject `setup_{module}` into the pytest function
  signature.
- `case_flow` remains the strategy for per-case setup, factory calls, state
  preparation, multi-step calls, SDK/gRPC/custom clients, and actions whose
  result is consumed by later steps.
- `default_case_setup` remains profile-owned and only applies to `case_flow`.
- Runtime case context remains capture/log attribution only.

This is a breaking cleanup. There is no compatibility migration layer and no
new `default_http_setup` field.

## Non-Goals

- Do not add `default_http_setup`.
- Do not make `case_flow` auto-capture.
- Do not change strategy priority.
- Do not change request binding, profile variables, or assertion resolution.
- Do not remove `default_case_setup`.
- Do not extend runtime case context to pytest fixture setup/teardown.

## Target Behavior

### default_http

Before:

```python
def test_tc_demo_001(self, http_base_url, setup_demo):
    __tc_meta__ = {...}
    __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
    try:
        setup_demo(case_id="TC-DEMO-001")
        __aitest_request = _req(...)
        resp = http_helper.post(http_base_url, "/...", json=__aitest_request)
        ...
    finally:
        reset_case_context(__aitest_ctx_token)
```

After:

```python
def test_tc_demo_001(self, http_base_url):
    __tc_meta__ = {...}
    __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
    try:
        __aitest_request = _req(...)
        resp = http_helper.post(http_base_url, "/...", json=__aitest_request)
        ...
    finally:
        reset_case_context(__aitest_ctx_token)
```

After the cleanup is complete, `default_http` only needs `http_base_url` in the
pytest function signature. Module fixtures are still available to explicit
`case_flow`, `case_body`, and profile-declared custom paths.

### case_flow

`default_case_setup` keeps the current explicit behavior:

```yaml
default_fixture: setup_demo
default_object: client_factory
default_case_setup:
  call: client_factory
  kwargs:
    case_id: "{case_id}"
  save_as: case
case_flows:
  TC-DEMO-001:
    steps:
      - call: case.get
        args: ["/health"]
        save_as: resp
```

It resolves to an explicit first flow step:

```python
case = client_factory(case_id="TC-DEMO-001")
resp = case.get("/health")
```

## Code Changes

### Affected Production Files

- `aitest_kit/codegen/ir.py`
  - Remove `SetupCallIR`.
  - Remove `CaseIR.setup_call`.
- `aitest_kit/codegen/planner.py`
  - Stop importing `SetupCallIR`.
  - Stop assigning implicit `setup_call` for `default_http`.
  - Stop adding `setup_{module}` to default HTTP fixture lists.
- `aitest_kit/codegen/ir_renderer.py`
  - Remove `_render_setup_call()`.
  - Stop rendering setup calls in `_render_default_body()`.
  - Emit missing `setup_{module}` TODO comments only when a rendered case
    actually declares that fixture.

### Affected Tests

- `tests/test_codegen_planner.py`
  - Replace `case_ir.setup_call is None` assertions with behavior checks that
    default HTTP IR has request/call data and no setup field in serialized IR.
  - Assert default HTTP fixtures contain `http_base_url` only.
- `tests/test_codegen_ir.py`
  - Add or update default HTTP rendering coverage to assert generated code does
    not contain `setup_demo(case_id=...)`.
  - Assert default HTTP generated function signatures do not contain
    `setup_demo`.
  - Keep existing `default_case_setup` case_flow tests unchanged except for any
    import or IR shape cleanup.

### Affected Documentation

- `docs/usebook/codegen_profile_guide.md`
- `docs/usebook/codegen_troubleshooting.md`
- `aitest_config/refs/config-files.md`
- `aitest_kit/templates/project_workspace/aitest_config/refs/config-files.md`
- `.codex/skills/test-codegen/refs/emitter_rules.md`
- `.claude/skills/test-codegen/refs/emitter_rules.md`
- `.agents/skills/test-codegen/refs/emitter_rules.md`
- `aitest_kit/templates/project_workspace/skills/test-codegen/refs/emitter_rules.md`
- `.codex/skills/test-scaffold/refs/constraints.md`
- `.claude/skills/test-scaffold/refs/constraints.md`
- `.agents/skills/test-scaffold/refs/constraints.md`
- `aitest_kit/templates/project_workspace/skills/test-scaffold/refs/constraints.md`

Documentation should state:

- `default_http` does not auto-run per-case setup.
- `default_http` does not require `setup_{module}` in the generated pytest
  function signature.
- Request differences belong in `requests` and `variables`.
- Per-case setup, factory calls, state preparation, SDK/gRPC/custom clients, and
  multi-step logic belong in `case_flow` or `case_body`.
- `default_case_setup` only applies to `case_flow`.
- Runtime case context is only for capture/log attribution.

## Completion Criteria

- No production code references `SetupCallIR` or `CaseIR.setup_call`.
- No default HTTP generated test contains an implicit
  `setup_{module}(case_id=...)` call.
- No default HTTP generated test requires `setup_{module}` in the pytest
  function signature.
- No default HTTP-only generated file emits a missing `setup_{module}` TODO.
- `case_flow` `default_case_setup` still expands and renders as an explicit
  first step.
- Generated suites remain fresh.
- Profile validation remains green.
- The final verification commands pass.

## Verification

Run:

```bash
python3 -m pytest tests/test_codegen_planner.py tests/test_codegen_ir.py -q
python3 -m pytest tests -q
python3 -m compileall aitest_kit
python3 -m aitest_kit.cli codegen --all
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli run --all -- --collect-only -q
git diff --check
```

Also run structural checks:

```bash
rg -n "SetupCallIR|setup_call|_render_setup_call" aitest_kit
rg -n "^\s+setup_[A-Za-z0-9_]+\(case_id=" test_workspace/generated
```

The first command should find no production references. The second command
should find no unassigned implicit default HTTP setup calls. Assigned
`case = setup_xxx(case_id=...)` calls from explicit `case_flow`
`default_case_setup` are allowed.
