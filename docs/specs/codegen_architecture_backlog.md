# Codegen Architecture Backlog

## Status

BACKLOG

## Context

Company-project migration and run-capture work exposed several codegen
architecture seams that should be addressed incrementally. This file records
the order of work only; each item still needs its own spec before
implementation.

## P1: Shared Strategy Resolver

Problem:

- Planner and profile validator both infer case strategy, but they do not use a
  shared implementation.
- The intended generation priority is:

  ```text
  skipped > custom_case_body > structured_case_flow > manual > default_http
  ```

- Validator sometimes needs to inspect profile intent even when final generation
  would skip a case, so the shared model should distinguish final generation
  strategy from profile-declared executable coverage.

Next spec:

- Define a `StrategyResolution` model.
- Move strategy priority and source/reason tracking into one module.
- Make planner, profile validator, health, and explain consume the shared
  resolver where appropriate.
- Preserve warnings for skipped/manual cases that still have executable profile
  mappings.

## P2: Runtime Profile Resolution View

Problem:

- `RuntimeProfile` currently stores merged raw YAML data.
- Planner, emitter, validator, health, and promotion each reload or reshape
  profile sections independently.
- This spreads default application and field ownership rules across files.

Next spec:

- Add a resolved profile view that exposes typed sections such as requests,
  case flows, case bodies, case fixtures, variables, structured assertions,
  extra imports, module type, and assertion rules.
- Ensure `default_fixture`, `default_object`, and `default_case_setup` are
  applied in one place.
- Keep raw profile data available for diagnostics that need exact source
  ownership.

## P3: Explicit Setup Binding Cleanup

Problem:

- `default_case_setup` is explicit profile-owned setup for `case_flow`.
- `setup_call` is implicit planner-owned setup for `default_http`.
- Runtime case context now covers capture/log attribution, but some fixtures
  still use case id for real test state setup.

Next spec:

- Inventory current default HTTP fixtures that rely on implicit `setup_call`.
- Separate capture-only case id threading from real per-case setup.
- Decide whether implicit `setup_call` should be removed, converted to explicit
  profile config, or retained with clearer diagnostics.

## Non-Goals For This Backlog

- Do not change `_http` or default JSON naming here.
- Do not make `case_flow` auto-capture.
- Do not extend runtime case context to pytest fixture setup/teardown.
- Do not delete `default_case_setup`; it is still useful for factory fixtures.
