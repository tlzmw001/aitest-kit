---
name: generate-tests
description: Generate pytest from existing AITest Markdown cases and module profile using the standard profile gate, IR dump, freshness check, codegen, and collect sequence.
---

# AITest Generate Tests

Use this skill when the user already has AITest Markdown cases and wants to generate
or refresh pytest files.

## Role

You orchestrate the deterministic codegen gate sequence. The CLI owns parsing,
profile validation, IR planning, rendering, freshness checks, and generated pytest
creation.

## Boundaries

- Do not hand-edit files under `test_workspace/tests/generated/`.
- Do not bypass profile validation.
- Do not relax assertions to make tests pass.
- Do not invent missing fixture behavior without calling it out.
- Do not modify target-system source code.

## Required Inputs

- A module name, or enough context to infer one from `test_workspace/cases/<module>/`.
- A workspace path, if the command is not run from the workspace root.

## Workflow

1. Locate the workspace.
   - Prefer the current directory if it contains `aitest_config/` and `test_workspace/`.
   - Otherwise use the user-provided `--workspace` path.
2. Identify module assets:
   - `test_workspace/cases/<module>/`
   - `test_workspace/tests/fixtures/codegen_profile_<module>.md`
   - `test_workspace/tests/fixtures/<module>.py`
3. If fixture/profile is missing, stop and explain the missing file.
   - Offer to generate an initial fixture/profile only if the user asks.
4. Run the gate sequence:

```bash
aitest codegen <module> --validate-profile
aitest codegen <module> --dump-ir
aitest codegen <module> --check
aitest codegen <module>
python -m pytest test_workspace/tests/generated --collect-only -q
```

5. If `--check` reports stale files, run codegen and then rerun `--check`.
6. Classify failures before proposing edits:
   - Markdown case format issue
   - profile schema or semantic issue
   - fixture/helper issue
   - codegen issue
   - environment issue

## Output

Report:

- Module
- Commands run
- Whether generated pytest is fresh
- Number of collected tests
- Any unresolved diagnostics
- Next step, usually `aitest run <module>`

## Example User Prompts

- "Generate pytest for discount_policy."
- "Refresh generated tests for this module."
- "Run the codegen gates and tell me what failed."
