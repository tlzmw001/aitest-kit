---
name: promote-rules
description: Analyze verified AITest generated pytest, profile, fixture, and Markdown cases for repeatable patterns worth promoting without automatically applying patches.
---

# AITest Promote Rules

Use this skill after tests are passing and the user wants to reduce repeated
case_flow, case_body, assertion, or fixture patterns.

## Role

You produce a promotion review report. Promotion is an abstraction decision, so
AI can analyze and recommend, but humans review before profile, fixture, or
emitter changes are applied.

## Boundaries

- Do not automatically apply promotion patches.
- Do not automatically convert `case_body` to `case_flow`.
- Do not treat every repeated shape as worth promoting.
- Do not modify `project_config.yaml`, profile, fixture, or emitter unless the
  user explicitly asks after reviewing the report.
- Do not read target-system source unless explicitly allowed.

## Required Inputs

- Module name.
- Passing generated pytest, or the command/result proving it passed.
- Workspace path, if not running from the workspace root.

## Workflow

1. Verify the module is stable enough to review:

```bash
aitest codegen <module> --validate-profile
aitest codegen <module> --check
python -m pytest test_workspace/tests/generated -q
```

2. Read only test assets:
   - `test_workspace/tests/generated/`
   - `test_workspace/tests/fixtures/codegen_profile_<module>.md`
   - `test_workspace/tests/fixtures/<module>.py`
   - `test_workspace/cases/<module>/`
   - relevant `test_workspace/knowledge/`
3. Identify repeated patterns:
   - raw assertion groups
   - repeated `case_flow` step sequences
   - repeated `case_body` structures
   - fixture methods that encode stable public API actions
4. Recommend a target layer:
   - keep as-is
   - helper method
   - `case_flow`
   - named assertion/template
   - project config rule
   - emitter change
5. Include risks and verification commands.

## Output

Promotion candidate report:

- Candidate name
- Evidence case IDs
- Repeated structure
- Recommended layer
- Why this layer is better than alternatives
- Risks
- Verification commands

## Example User Prompts

- "These tests pass; what patterns should we promote?"
- "Analyze this module for case_flow simplification."
- "Should any case_bodies become stable rules?"
