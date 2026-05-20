---
name: build-knowledge
description: Build or update the AITest L0/L1/L2 testing knowledge base from approved project/API documents while preserving unknowns as [?].
---

# AITest Build Knowledge

Use this skill when the user wants to turn project/API docs into the AITest
knowledge base that later drives Markdown case design.

## Role

You orchestrate knowledge construction. The output is test knowledge, not pytest.
When a workspace has its own `knowledge-build` skill, follow that workspace skill
for project-specific constraints.

## Boundaries

- Do not bypass the knowledge layer and write pytest directly.
- Do not infer undocumented behavior as fact.
- Do not read target-system source unless the user explicitly allows gray-box work.
- Do not overwrite existing knowledge blindly; treat existing L0/L1/L2 as state.
- Do not remove `[?]` markers without evidence.

## Required Inputs

- Document path or directory.
- Workspace path, if not running from the AITest workspace root.
- Optional output knowledge directory; default is `test_workspace/knowledge/`.

## Workflow

1. Locate the AITest workspace:
   - `aitest_config/`
   - `test_workspace/knowledge/`
2. Read the document inputs and existing knowledge files.
3. Determine mode:
   - initialize L0/L1/L2 if no usable knowledge exists
   - incrementally update affected L1/L2 and L0 index if knowledge exists
4. Use the workspace `knowledge-build` SOP if present:
   - `.codex/skills/knowledge-build/SKILL.md`
   - otherwise `.claude/skills/knowledge-build/SKILL.md`
   - otherwise `.agents/skills/knowledge-build/SKILL.md`
5. Write concise knowledge files:
   - L0: system routing/index
   - L1: current module contracts
   - L2: requirement or document deltas
6. Preserve unknowns with typed `[?]` markers.
7. Summarize changed files and next step.

## Output

Report:

- Mode: initialize or incremental update
- Docs used
- Files created/modified
- `[?]` summary
- Next step, usually `design-cases`

## Example User Prompts

- "Build AITest knowledge from docs/public_api_doc.md."
- "Update the knowledge base from this new API spec."
- "Create L0/L1/L2 for this module."
