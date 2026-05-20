---
name: design-cases
description: Design AITest Markdown business, boundary, and optional manual cases from L1/L2 knowledge and TEST_SPEC without inventing undocumented assertions.
---

# AITest Design Cases

Use this skill when the user wants Markdown test cases for a module after the
knowledge base exists.

## Role

You design reviewable Markdown cases. The cases are source assets for codegen, so
they must be stable, traceable, and executable when possible.

## Boundaries

- Do not write generated pytest directly.
- Do not invent stable assertions from `[?]` knowledge.
- Do not hide unsupported scenarios; mark them manual or record them as gaps.
- Do not use placeholder JSON in shared HTTP request bodies.
- Do not put project-specific fixture logic into Markdown cases.

## Required Inputs

- Module name.
- Relevant L1/L2 knowledge files.
- `test_workspace/knowledge/TEST_SPEC.md`, if present.
- Workspace path, if not running from the workspace root.

## Workflow

1. Locate module knowledge:
   - `test_workspace/knowledge/L1/<module>.md`
   - related `test_workspace/knowledge/L2/*.md`
2. Read `TEST_SPEC.md` for project-wide case rules.
3. Decide case files:
   - `test_workspace/cases/<module>/business.md`
   - `test_workspace/cases/<module>/boundary.md`
   - optional `mismatch.md` or manual sections only when needed
4. Create or update cases with:
   - shared config
   - executable base request body
   - unique case IDs
   - stable assertions
   - coverage table
   - explicit non-coverage for `[?]` or unstable behavior
5. Run or recommend a parser/codegen dry check when available.
6. Summarize what can proceed to fixture/profile and codegen.

## Output

Report:

- Module
- Case files created/modified
- Case count by category
- Coverage and intentional non-coverage
- Next step, usually fixture/profile preparation then `generate-tests`

## Example User Prompts

- "Design business and boundary cases for discount_policy."
- "Create Markdown cases from this L1/L2 knowledge."
- "Review and improve this module's AITest cases."
