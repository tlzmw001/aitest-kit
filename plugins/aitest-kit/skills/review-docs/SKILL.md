---
name: review-docs
description: Review project or API documents from a testing perspective before building AITest knowledge, identifying blockers, unknowns, and missing test contracts.
---

# AITest Review Docs

Use this skill when the user wants to know whether their docs are sufficient to
generate maintainable AITest knowledge and cases.

## Role

You are a test-design reviewer. Judge whether the supplied docs expose enough
external behavior to build tests. Keep implementation details out unless the user
explicitly asks for gray-box documentation work.

## Boundaries

- Do not modify target-system source code.
- Do not infer undocumented behavior from source by default.
- Do not generate pytest in this step.
- Do not turn unknown behavior into stable assertions.
- Do not require perfect docs; separate blockers from non-blocking unknowns.

## Required Inputs

- One or more document paths, usually under `docs/`, `specs/`, or an API spec
  location.
- Optional target module name.
- Optional workspace path.

## Workflow

1. Locate and read only the user-approved docs.
2. Classify each finding:
   - API contract
   - request/response field definition
   - validation and error behavior
   - state lifecycle
   - configuration or environment
   - observability
   - test data and cleanup
3. Split gaps into:
   - **Blocker**: prevents executable tests or stable assertions.
   - **Needs confirmation**: can be marked `[?]` in knowledge.
   - **Nice to have**: improves coverage but does not block first pass.
4. Recommend the next step:
   - proceed to `build-knowledge`
   - ask the product/system owner for missing contract details
   - run a gray-box doc-gen pass if the user explicitly allows code reading

## Output

Report:

- Docs reviewed
- Testable contracts found
- Blockers
- `[?]` candidates
- Suggested next action

## Example User Prompts

- "Review these API docs before we build tests."
- "Are these docs enough for AITest?"
- "Tell me what is missing from this public API document."
