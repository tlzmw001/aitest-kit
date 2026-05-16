# aitest-kit Roadmap

This roadmap describes the current product boundary and near-term direction. It is intentionally conservative: `aitest-kit` should remain easy to install, easy to inspect, and deterministic where it matters.

## Stable in v0.1

- `aitest init` workspace initialization.
- Markdown case parsing.
- codegen profile JSON Schema and semantic validation.
- Case IR planning.
- pytest generation for API-oriented test cases.
- `case_flows` for linear multi-step API workflows.
- `case_bodies` as an explicit escape hatch for complex control flow.
- generated freshness check via `aitest codegen --check`.
- structured test execution reports via `aitest run` and `aitest report`.
- packaged workspace template with `.codex`, `.claude`, and `.agents` skills.

## In Progress

- Better open-source onboarding material.
- English documentation entrypoint.
- `coupon_system` full example walkthrough.
- `aitest doctor` workspace diagnostics.
- Health and promotion reports as review aids.
- Clearer docs for when to use default strategy, assertion rules, `case_flows`, or `case_bodies`.

## Future Directions

- Emitter registry / custom emitter boundaries.
- Contract testing from OpenAPI/proto schemas.
- Unit-test generation support.
- Playwright or frontend/E2E emitter.
- Codex plugin packaging as a workflow wrapper around the existing CLI and workspace.
- Historical report trends and CI-oriented integrations.

## Not Planned for v0.1

- Hosted SaaS dashboard.
- Automatic profile rewriting.
- Automatic fixture generation without review.
- Automatic application of promotion patches.
- Replacing the CLI/workspace model with a plugin-only flow.
- Treating generated pytest as hand-maintained source code.

## Design Boundary

The project should continue to follow this rule:

```text
AI handles exploration and judgment.
Code handles stable parsing, validation, generation, execution, and reporting.
```

When a workflow becomes stable and repeatable, move it into config, profile, fixture/helper code, or deterministic codegen. When a workflow still requires semantic judgment, keep it in the AI-assisted review loop.
