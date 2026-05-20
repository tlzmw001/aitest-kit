---
name: aitest-run-tests
description: Run generated AITest pytest through aitest run, read the structured report, and classify failures without automatically blaming the system under test.
---

# AITest Run Tests

Use this skill when the user wants to execute generated tests, produce a report, or
understand failures from an AITest run.

## Role

You run or guide `aitest run`, then interpret the generated report. Treat failure
classification as a testing workflow task, not as automatic product-bug judgment.

## Boundaries

- Do not skip failing tests to manufacture success.
- Do not relax assertions to make tests pass.
- Do not modify generated pytest by hand.
- Do not automatically edit target-system source code.
- Do not treat assertion failure as a system bug without evidence.

## Workflow

1. Locate the workspace.
2. Identify the target module or use `--all` only when the user asks for all modules.
3. Run or recommend freshness-safe execution:

```bash
aitest run <module>
```

4. Read report outputs:
   - `test_workspace/reports/latest/result.json`
   - `test_workspace/reports/latest/report.md`
5. Summarize:
   - pass/fail/error/skip/manual counts
   - report path
   - freshness blocked status, if any
6. For failures, classify into:
   - documentation issue
   - Markdown case issue
   - fixture/profile issue
   - codegen issue
   - test environment issue
   - likely system-under-test bug
7. Provide the smallest next action.

## Output

Lead with the result:

- Run status
- Report path
- Failure classification
- Evidence
- Next command or edit target

## Example User Prompts

- "Run AITest for this module."
- "Read the latest AITest report and explain failures."
- "Tell me whether this is a test issue or product bug."
