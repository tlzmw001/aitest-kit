---
name: fix-failures
description: Triage failing AITest runs using latest reports, cases, profile, fixture, and generated pytest, then propose or apply the smallest safe fix.
---

# AITest Fix Failures

Use this skill when generated tests fail, `aitest run` reports failures, or the
user asks whether a failure is a docs, case, fixture/profile, codegen, environment,
or system-under-test issue.

## Role

You perform failure triage before editing. The goal is the smallest correct fix,
not making tests green by weakening them.

## Boundaries

- Do not skip tests to manufacture success.
- Do not relax assertions without evidence that the case was wrong.
- Do not hand-edit generated pytest.
- Do not automatically modify target-system source code.
- Do not label a system-under-test bug without evidence.

## Required Inputs

- Latest run report, or permission to run `aitest run`.
- Module name when possible.
- Workspace path, if not running from the workspace root.

## Workflow

1. Reproduce or read the failure:
   - `test_workspace/reports/latest/result.json`
   - `test_workspace/reports/latest/report.md`
   - pytest output if provided
2. Identify affected case IDs.
3. Read the source assets for those cases:
   - Markdown case file
   - `codegen_profile_<module>.md`
   - module fixture
   - generated pytest only as compiled output
4. Classify each failure:
   - documentation issue
   - Markdown case issue
   - fixture/profile issue
   - codegen issue
   - test environment issue
   - likely system-under-test bug
5. If editing is requested, modify source assets only:
   - docs/knowledge/cases
   - fixture/profile
   - codegen implementation, only when the generated output proves a framework bug
6. Regenerate and verify with the standard sequence:

```bash
aitest codegen <module> --validate-profile
aitest codegen <module> --check
aitest codegen <module>
aitest run <module>
```

## Output

Lead with:

- Failure classification
- Evidence
- Files that should change
- Commands to verify
- Any system-under-test bug record needed under `test_workspace/results/`

## Example User Prompts

- "These AITest cases failed; classify the root cause."
- "Fix the latest AITest run failure."
- "Is this a test problem or a product bug?"
