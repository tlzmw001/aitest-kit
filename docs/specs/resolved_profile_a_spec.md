# Resolved Profile A-Phase Spec

## Status

IMPLEMENTED

## Background

`RuntimeProfile` currently stores merged module/suite profile YAML as a raw
`dict`. Planner, profile validator, emitter, and promotion then each reshape
that dict through `load_profile_*()` helpers or local `_mapping()` calls.

This is workable today, but it spreads the runtime interpretation of profile
sections across multiple modules. Recent strategy-resolution work clarified a
similar problem: final generation behavior should have one shared source of
truth. Profile runtime sections need the same treatment.

## Goal

Complete方案 A: introduce a read-only `ResolvedProfile` runtime view and move
codegen runtime consumers to it incrementally.

The end state for A is:

```text
RuntimeProfile.data
  -> resolve_profile(...)
      -> ResolvedProfile
          -> planner runtime inputs
          -> validator runtime-behavior inputs
          -> emitter runtime inputs
          -> promotion runtime inputs
```

## Non-Goals

- Do not implement方案 B.
- Do not add field-level source maps or `ProfileValue`.
- Do not change profile YAML schema.
- Do not change merge semantics in `profile_merge.py`.
- Do not change codegen strategy priority.
- Do not change generated pytest output except where an existing bug is proven
  by tests.
- Do not remove raw module/suite profile data from validator diagnostics.

## Architectural Boundary

`ResolvedProfile` answers: "what final runtime profile sections should codegen
consume?"

Raw module/suite data still answers:

- Did the user write a field in the wrong layer?
- Did the YAML violate schema or top-level shape rules?
- Did module and suite profile definitions conflict?
- Which case-scoped keys were declared in a specific source file?

This means validator remains split:

```text
raw module/suite data:
  schema, ownership, source-shape diagnostics

ResolvedProfile:
  runtime behavior checks that must match planner/emitter
```

## A1: Add Read-Only ResolvedProfile

### Scope

Add `aitest_kit/codegen/resolved_profile.py`.

Define:

```python
@dataclass(frozen=True)
class ResolvedProfile:
    raw: dict[str, Any]
    rules: list[AssertionRule]
    requests: dict[str, dict[str, Any]]
    structured_assertions: dict[str, list[dict[str, Any]]]
    extra_imports: list[str]
    case_fixtures: dict[str, list[str]]
    case_bodies: dict[str, list[str]]
    case_flows: dict[str, dict[str, Any]]
    variables: dict[str, Any]
    module_type: str | None
    case_flow_defaults: CaseFlowDefaults
```

Define:

```python
def resolve_profile(profile: ProfileSource) -> ResolvedProfile:
    ...
```

The first implementation may compose existing loader helpers. A1 is not allowed
to change planner, validator, emitter, promotion, or generated output.

Read-only in方案 A means immutable top-level `ResolvedProfile` field bindings
and a consumer contract that codegen stages do not mutate resolved sections.
It does not convert nested dict/list containers into immutable proxy objects,
because方案 A must preserve existing loader return types for incremental
migration.

### Completion Standard

- `ResolvedProfile` returns exactly the same values as the existing
  `load_profile_*()` helpers for paths and `RuntimeProfile`.
- `None` input returns empty/default sections.
- `default_fixture`, `default_object`, and `default_case_setup` are applied to
  `case_flows` exactly as `load_profile_case_flows()` applies them today.
- No production consumer is migrated yet.

### Tests

Add `tests/test_codegen_resolved_profile.py`.

Required cases:

- `resolve_profile(None)` returns empty sections/defaults.
- Path-based profile resolves requests, structured assertions, extra imports,
  case fixtures, case bodies, case flows, variables, module type, and assertion
  rules.
- RuntimeProfile-based resolution preserves merged data and applies case_flow
  defaults.
- Equivalence assertions compare resolved fields with the existing
  `load_profile_*()` helper outputs.

### Review Gate

After A1 tests pass, run a read-only subagent review focused on:

- Does `ResolvedProfile` stay read-only and behavior-preserving?
- Is the new module boundary clearer than expanding `profile.py`?
- Are tests sufficient to prove equivalence?

## A2: Migrate Planner Runtime Inputs

### Scope

Update `aitest_kit/codegen/planner.py` so `build_file_ir()` uses
`resolve_profile()` for runtime profile sections:

- `rules`
- `requests`
- `structured_assertions`
- `case_fixtures`
- `case_bodies`
- `case_flows`
- `variables`

Planner may still import validation helpers such as
`validate_profile_strategy_conflicts()` and `validate_case_flows()`.

### Completion Standard

- `build_file_ir()` no longer directly calls multiple `load_profile_*()`
  helpers.
- Strategy resolution and source trace behavior remain unchanged.
- CaseIR output for existing tests remains unchanged.
- Generated files remain fresh under `codegen --all --check`.

### Tests

Run:

```bash
python3 -m pytest tests/test_codegen_resolved_profile.py tests/test_codegen_planner.py tests/test_codegen_ir.py -q
python3 -m aitest_kit.cli codegen --all --check
```

### Review Gate

After A2 tests pass, run a read-only subagent review focused on:

- Did planner become simpler without changing generated behavior?
- Did any raw-profile diagnostic accidentally move into planner?
- Are strategy and CaseIR behavior still sourced from the same values?

## A3: Migrate Validator Runtime-Behavior Inputs

### Scope

Update `aitest_kit/codegen/profile_validator.py` so runtime behavior checks use
`resolve_profile(context.runtime_profile)`:

- runtime `case_bodies`
- runtime `requests`
- runtime `structured_assertions`
- runtime `case_flows`
- runtime `variables`

Keep raw `module_data` and `suite_data` for schema, top-level, ownership, and
case-reference diagnostics.

### Completion Standard

- Validator runtime behavior sees the same resolved profile view as planner.
- Raw module/suite diagnostics remain raw-source based.
- Existing diagnostics codes/messages remain stable unless covered by an
  explicit test.
- No source-map or ProfileValue logic is introduced.

### Tests

Run:

```bash
python3 -m pytest tests/test_codegen_resolved_profile.py tests/test_codegen_profile_validator.py tests/test_codegen_suite_profile.py -q
python3 -m aitest_kit.cli codegen --all --validate-profile
```

### Review Gate

After A3 tests pass, run a read-only subagent review focused on:

- Did validator preserve raw diagnostics while using resolved runtime sections?
- Are ownership and schema checks still looking at module/suite raw data?
- Do runtime checks now align with planner input?

## A4: Migrate Emitter And Remaining Runtime Consumers

### Scope

Update `aitest_kit/codegen/emitter.py` to consume `ResolvedProfile` for:

- rules
- extra imports
- case fixtures
- case bodies
- case flows
- raw profile data for module type requirements

Update `aitest_kit/codegen/promotion.py` if it reads runtime profile sections
directly. Keep low-level loader helpers in `profile.py` because `ResolvedProfile`
uses them and tests still compare against them.

### Completion Standard

- Emitter no longer directly calls multiple `load_profile_*()` helpers.
- Promotion uses `ResolvedProfile` for runtime section reads if applicable.
- Direct `load_profile_*()` usage is limited to:
  - `profile.py`
  - `resolved_profile.py`
  - suite loading/raw profile parsing
  - tests that assert equivalence or low-level loader behavior
- Existing generated output remains unchanged.

### Tests

Run:

```bash
python3 -m pytest tests/test_codegen_resolved_profile.py tests/test_codegen_ir.py tests/test_codegen_promotion.py -q
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli run --all -- --collect-only -q
```

### Review Gate

After A4 tests pass, run a read-only subagent review focused on:

- Did runtime consumers converge on `ResolvedProfile`?
- Are low-level loaders retained only where they still make architectural sense?
- Is this still方案 A, with no B/source-map expansion?

## Final Verification

After all A phases:

```bash
python3 -m pytest tests -q
python3 -m compileall aitest_kit
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli run --all -- --collect-only -q
git diff --check
```

## Rollback

Each phase is independently revertible:

- A1 only adds `ResolvedProfile` and tests.
- A2 only switches planner consumption.
- A3 only switches validator runtime consumption.
- A4 only switches emitter/promotion runtime consumption.

Because方案 A does not change schema, generated file format, or persisted
runtime data, rollback is code-only.
