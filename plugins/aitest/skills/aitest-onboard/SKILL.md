---
name: aitest-onboard
description: Initialize or inspect an AITest workspace for a target project using aitest-kit CLI commands and explain the next testing workflow step.
---

# AITest Onboard

Use this skill when the user wants to initialize AITest for a project, check whether
a project already has an AITest workspace, or understand the first step for using
AITest Kit.

## Role

You are the workflow entry point. Keep deterministic work in the `aitest` CLI and
use Codex for guidance, explanation, and safe orchestration.

## Boundaries

- Do not modify target-system source code.
- Do not modify `.env` or environment config files.
- Do not install dependencies silently.
- Do not generate tests in this step unless the user explicitly asks to continue.
- Do not copy parser, codegen, runner, or report logic into the plugin.

## Workflow

1. Identify the current project root and intended AITest workspace path.
   - Default workspace path: `./aitest_workspace`.
   - If the user provided a path, use that path.
2. Check whether `aitest` is available.
   - Prefer `aitest --help`.
   - If unavailable, tell the user to install `aitest-kit`:
     - `pip install aitest-kit`
3. If a workspace exists, inspect it instead of overwriting it.
   - Look for `aitest_config/`, `test_workspace/`, `AGENTS.md`, and `CLAUDE.md`.
4. If no workspace exists, initialize it with:
   - `aitest init --target <workspace>`
5. Run or recommend:
   - `aitest doctor --workspace <workspace>`
6. Summarize:
   - created or existing workspace path
   - missing pieces, if any
   - next recommended step

## Output

Keep the final answer action-oriented:

- Workspace path
- Commands run
- Result summary
- Next step, usually one of:
  - put public API docs under `docs/`
  - build the test knowledge base
  - generate Markdown cases
  - generate pytest from existing cases

## Example User Prompts

- "Initialize AITest for this project."
- "Set up AITest in `./aitest_workspace`."
- "Check whether this project is ready for AITest."
