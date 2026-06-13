# Codegen Strategy Resolution Spec

## Status

IMPLEMENTED

## Background

Codegen currently decides a case's execution strategy in more than one place.
The planner uses `aitest_kit/codegen/planner.py::_strategy_for()` to choose the
final generated `CaseIR.strategy`, while the profile validator uses
`aitest_kit/codegen/profile_validator.py::_strategy_name_for_case()` for
structured assertion target validation.

Those two implementations are close, but not identical. The planner priority
is:

```text
skipped > custom_case_body > structured_case_flow > manual > default_http
```

The validator previously checked `case_bodies` and `case_flows` before skipped
markers. That let profile-provided executable mappings affect validation for a
case that the planner would still skip. The result is an architectural mismatch:
validation can approve profile sections that generation will never render.

## Goals

- Define one shared resolver for codegen strategy selection.
- Preserve the planner's existing final strategy priority.
- Keep profile-declared executable intent visible even when final generation is
  skipped or manual.
- Use the same final strategy in planner and profile validation.
- Keep source and reason tracking stable for `CaseIR.source_trace["strategy"]`.
- Preserve existing warnings for skipped cases that still have executable
  profile mappings.

## Non-Goals

- Do not change `_http` naming or introduce default JSON naming.
- Do not change generated pytest rendering behavior beyond using the shared
  strategy result.
- Do not make `case_flow`, `case_body`, manual, or skipped cases auto-capture.
- Do not add a resolved runtime profile view in this change.
- Do not remove or redesign `default_case_setup` or `setup_call`.
- Do not change the public profile schema.

## Strategy Model

Add `aitest_kit/codegen/strategy.py` with a small primitive-input resolver. It
must not depend on `TestCase`, `CaseIR`, or `ProfileValidationReport`; callers
pass the `case_id`, Markdown markers, `case_bodies`, and `case_flows`.

The resolver returns:

```python
@dataclass(frozen=True)
class StrategyResolution:
    case_id: str
    final_strategy: str
    final_source: str
    final_reason: str
    profile_intent: str
    profile_source: str
    manual: bool
    skipped: bool
    skip_reason: str | None
```

`final_strategy` drives generation and validations that must match generated
output. It follows the planner priority:

```text
skipped > custom_case_body > structured_case_flow > manual > default_http
```

`profile_intent` records what the profile attempted to provide:

```text
custom_case_body | structured_case_flow | none
```

This preserves validator diagnostics such as "skipped case has executable
profile mapping" without letting that mapping override final generation.

## Caller Behavior

### Planner

`build_file_ir()` uses `resolve_case_strategy()` once per case.

- `CaseIR.strategy` uses `resolution.final_strategy`.
- `CaseIR.skip_reason` uses `resolution.skip_reason`.
- `source_trace["strategy"]` uses `final_strategy`, `final_source`, and
  `final_reason`.
- Existing protocol, fixture, request binding, assertion, and case_flow logic
  continue to branch on the final strategy.

### Profile Validator

Structured assertion target validation uses `resolution.final_strategy`, because
structured assertions only matter if generation will render them.

Warnings that reason about profile coverage use `resolution.profile_intent`.
For example, a `[!可行性存疑]` case with `case_flows.<case_id>` should still warn
with W503 even though final generation remains skipped.

Manual/comment-only flow validation can keep using marker checks, but marker
matching should come from the shared helper to avoid separate case-insensitive
logic.

### Health and Explain

No direct change is required in this spec. Both modules consume `CaseIR` after
planning, so they already observe the final strategy once the planner uses the
resolver.

## Impacted Files

- `aitest_kit/codegen/strategy.py`
  - new shared strategy constants, `StrategyResolution`, marker helpers, and
    `resolve_case_strategy()`.
- `aitest_kit/codegen/planner.py`
  - replace local marker/strategy helpers with the shared resolver.
- `aitest_kit/codegen/profile_validator.py`
  - replace local strategy and marker logic with the shared resolver/helper.
- `tests/test_codegen_strategy.py`
  - cover resolver priority and profile intent separation.
- `tests/test_codegen_profile_validator.py`
  - ensure skipped cases with profile mappings still warn and structured
    assertions are validated against final skipped behavior.

Existing planner priority and source trace coverage in
`tests/test_codegen_planner.py` remains part of the regression surface, but the
file does not need new cases for this implementation.

## Compatibility Notes

- Existing generated strategy priority is preserved.
- Existing source trace strings for planner strategies are preserved.
- Existing `case_bodies` vs `case_flows` conflict validation remains in
  `profile.py`.
- The only intentional validator behavior change is that a skipped case with a
  `structured_assertions` entry is now rejected as skipped, even if a profile
  `case_flow` also exists. That matches the generated output, because the
  planner will not render the flow or the structured assertion for skipped
  cases.

## Verification Plan

Run focused tests:

```bash
python3 -m pytest tests/test_codegen_strategy.py tests/test_codegen_planner.py tests/test_codegen_profile_validator.py -q
```

Run full regression:

```bash
python3 -m pytest tests -q
```

Run build/codegen checks:

```bash
python3 -m compileall aitest_kit
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli run --all -- --collect-only -q
```
