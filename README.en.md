# aitest-kit

> Turn development and API docs into a reviewable test knowledge base, Markdown test cases, generated pytest code, and structured test reports.

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

`aitest-kit` is an AI-assisted testing toolchain. The CLI and workspace template handle deterministic parsing, validation, code generation, freshness checks, pytest execution, and reports. Local AI skills help with document review, knowledge-base construction, test-case design, failure triage, and rule promotion.

The core idea:

```text
AI explores unknown systems.
Code preserves stable, repeatable testing assets.
```

## Why This Exists

One-shot AI-generated pytest is hard to review and easy to drift. `aitest-kit` keeps the test design as explicit intermediate artifacts:

```text
Docs -> Knowledge Base -> Markdown Cases -> Case IR -> Generated Pytest -> Report
```

That makes the process reviewable, reproducible, and easier to improve over time.

## Install

```bash
pip install aitest-kit
```

To upgrade an existing installation:

```bash
python3 -m pip install -U aitest-kit
```

## Initialize a Workspace

```bash
aitest init --target /path/to/your_project/aitest_workspace
cd /path/to/your_project/aitest_workspace
```

The workspace contains:

- `docs/` for public API and design docs
- `aitest_config/` for project and codegen configuration
- `test_workspace/knowledge/` for L0/L1/L2 knowledge docs
- `test_workspace/cases/` for Markdown test cases
- `test_workspace/casesuites/` for optional L2 or iteration-oriented case suites
- `test_workspace/tests/fixtures/` for module fixtures and profiles
- `test_workspace/tests/generated/` for generated pytest
- `.codex/`, `.claude/`, and `.agents/` skills for AI-assisted workflows (8 skills: doc-review, doc-gen, knowledge-build, test-design, test-scaffold, test-codegen, test-fix, emitter-build)

## Upgrade a Workspace

Package upgrades and workspace template upgrades are separate:

```bash
python3 -m pip install -U aitest-kit
aitest upgrade --workspace /path/to/aitest_workspace --check
aitest upgrade --workspace /path/to/aitest_workspace --apply
```

`pip install -U` updates the CLI and Python code. `aitest upgrade` checks files that were copied into the project by `aitest init`, such as skills, schemas, refs, helpers, and workspace guidance docs.

Do not use `aitest init --force` to upgrade an existing workspace. `upgrade` uses `.aitest/workspace.json` to update only files that still match the previous template; locally modified files are skipped for manual review.

## Codegen Workflow

```bash
aitest codegen --all --validate-profile
aitest codegen --all --dump-ir
aitest codegen --all
aitest codegen --all --check
aitest codegen --cases test_workspace/casesuites/<suite>
aitest doctor
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

From outside the workspace, pass `--workspace`:

```bash
aitest codegen --workspace /path/to/aitest_workspace --all --validate-profile
```

## Run Tests and Reports

```bash
aitest run <module>
aitest report
```

`aitest run` checks generated freshness before running pytest. If generated files are stale, it writes a blocked report instead of executing outdated tests.

Use `aitest doctor` to diagnose workspace layout, profile gate, generated freshness, pytest collection, and fixture environment-variable hints.

Reports are written under:

```text
test_workspace/reports/latest/
test_workspace/reports/runs/{run_id}/
```

## Codegen Paths

| Path | Profile Config | Best For |
|---|---|---|
| default HTTP/gRPC | `request_overrides` | single endpoint, stable request shape |
| assertion rules | `assertion_rules` | standard request flow with reusable assertion logic |
| structured flow | `case_flows` | linear multi-step workflows |
| custom body | `case_bodies` | concurrency, subprocesses, mock transports, file lifecycle |

`case_bodies` are an escape hatch, not the default path. Stable linear workflows should move toward `case_flows`.

## Realistic Example

This repository includes `coupon_system` as a realistic regression target. It demonstrates:

- HTTP and gRPC service testing
- Redis-backed state checks
- AB experiment service integration
- default codegen templates
- assertion rules
- structured `case_flows`
- `case_bodies` for complex lifecycle scenarios
- structured reports

See [Coupon System Full Example](docs/usebook/coupon_system_full_example.md).

## Current Scope

Stable in v0.1:

- workspace initialization
- Markdown case parsing
- profile schema and semantic validation
- Case IR planning
- pytest code generation for API-oriented tests
- generated freshness checks
- structured run reports

In progress:

- `aitest doctor`
- example documentation
- health and promotion review reports
- extension boundaries for future emitters

Future:

- contract testing
- unit-test emitter
- Playwright/E2E emitter
- Codex plugin workflow wrapper

See [ROADMAP.md](ROADMAP.md).

## Documentation

- [中文 README](README.md)
- [AITest Migration Guide](docs/usebook/aitest_migration_guide.md)
- [Quickstart](docs/usebook/aitest_quickstart.md)
- [Profile Guide](docs/usebook/codegen_profile_guide.md)
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE)
