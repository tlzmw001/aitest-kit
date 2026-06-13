# Codegen Architecture Backlog

## Status

IMPLEMENTED

## Context

Company-project migration and run-capture work exposed several codegen
architecture seams that needed incremental cleanup. P1-P3 have now been
implemented; this file records the decisions and points to the detailed specs.

## P1: Shared Strategy Resolver

Status: IMPLEMENTED in `e3a1bf1`.

Spec: `docs/specs/codegen_strategy_resolution_spec.md`

Resolved problem:

- Planner and profile validator both infer case strategy, but they do not use a
  shared implementation.
- The intended generation priority is:

  ```text
  skipped > custom_case_body > structured_case_flow > manual > default_http
  ```

- Validator sometimes needs to inspect profile intent even when final generation
  would skip a case, so the shared model should distinguish final generation
  strategy from profile-declared executable coverage.

Implemented:

- Define a `StrategyResolution` model.
- Move strategy priority and source/reason tracking into one module.
- Make planner, profile validator, health, and explain consume the shared
  resolver where appropriate.
- Preserve warnings for skipped/manual cases that still have executable profile
  mappings.

## P2: Runtime Profile Resolution View

Status: IMPLEMENTED in `caffcb3`.

Spec: `docs/specs/resolved_profile_a_spec.md`

Resolved problem:

- `RuntimeProfile` currently stores merged raw YAML data.
- Planner, emitter, validator, health, and promotion each reload or reshape
  profile sections independently.
- This spreads default application and field ownership rules across files.

Implemented:

- Add a resolved profile view that exposes typed sections such as requests,
  case flows, case bodies, case fixtures, variables, structured assertions,
  extra imports, module type, and assertion rules.
- Ensure `default_fixture`, `default_object`, and `default_case_setup` are
  applied in one place.
- Keep raw profile data available for diagnostics that need exact source
  ownership.

## P3: Explicit Setup Binding Cleanup

Status: IMPLEMENTED.

Spec: `docs/specs/explicit_setup_binding_cleanup_spec.md`

Resolved problem:

- `default_case_setup` is explicit profile-owned setup for `case_flow`.
- `setup_call` is implicit planner-owned setup for `default_http`.
- Runtime case context now covers capture/log attribution, but some fixtures
  still use case id for real test state setup.

Implemented:

- Separate capture-only case id threading from real per-case setup.
- Remove implicit `setup_call`.
- Remove default HTTP `setup_{module}` fixture injection.
- Keep `default_case_setup` as explicit `case_flow` setup.

## Remaining Discussion Candidates

- `case_flow` rendering can emit redundant aliases when `default_object` and
  `default_case_setup.save_as` use the same name, for example `case = setup_x`
  followed by `case = setup_x(case_id="...")`. This is a readability cleanup,
  not a correctness bug.
- Field-level profile source maps / `ProfileValue` remain out of scope. They
  are the larger方案 B discussion after the lighter ResolvedProfile方案 A.

## Non-Goals For This Backlog

- Do not change `_http` or default JSON naming here.
- Do not make `case_flow` auto-capture.
- Do not extend runtime case context to pytest fixture setup/teardown.
- Do not delete `default_case_setup`; it is still useful for factory fixtures.
