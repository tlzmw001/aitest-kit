# aitest-kit

> Turn development docs, API contracts, and AI-designed test ideas into reviewable, reproducible, runnable automated test assets.

[中文 README](README.md)

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

AITest Kit is an AI-assisted automated testing toolchain for bringing new backend services, API gateways, business systems, and existing test projects into a maintainable test workflow.

Core principle:

```text
AI explores unknowns. Code stabilizes repeatable work.
```

AI reads docs, understands a new system, drafts test cases, explains failures, and identifies reusable patterns. `aitest-kit` handles deterministic Markdown parsing, profile validation, Case IR planning, pytest generation, freshness checks, test execution, and structured reports.

## 3-Minute Start

### 1. Install

```bash
python3 -m pip install -U aitest-kit
```

If the `aitest` script is not on `PATH`, use the module entrypoint:

```bash
python3 -m aitest_kit.cli --help
```

### 2. Initialize a Workspace

The recommended layout is an independent AITest workspace under the target project:

```bash
cd /path/to/your_project
aitest init --target ./aitest_workspace
cd ./aitest_workspace
```

The workspace contains:

```text
docs/                 # public API docs, design docs, OpenAPI/proto files
aitest_config/         # project config, codegen config, schemas, refs
test_workspace/        # knowledge base, cases, fixtures, profiles, generated pytest, reports
.codex/.claude/.agents # AI skills
AGENTS.md / CLAUDE.md  # AI collaboration guidance
```

### 3. Health Check

```bash
aitest doctor
```

An empty workspace has no modules yet. Put public API/design docs under `docs/`, then use the bundled AI skills:

```text
doc-review -> knowledge-build -> test-design -> test-scaffold -> test-codegen -> aitest run
```

If Markdown cases and profiles already exist:

```bash
aitest codegen --all --validate-profile
aitest codegen --all
aitest codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

## What It Is For

AITest Kit is useful when:

- You have docs or API contracts but little or no automated testing.
- You want AI help with test design without permanently depending on one-shot generated pytest.
- You want test design, generated code, runtime reports, and confirmed SUT bugs separated.
- You need failure triage across docs, cases, fixture/profile, environment, codegen, and SUT behavior.
- You want the project to become more deterministic over time as repeated patterns are promoted into code/config.

It is not meant for:

- One-off throwaway pytest generation.
- Systems without executable interfaces or observable results.
- Automatically creating production accounts, real tokens, paid API keys, or high-risk test resources.

## Workflow

```text
Public docs / API contracts
  -> L0/L1/L2 test knowledge base
  -> Markdown test cases
  -> fixture + codegen profile
  -> Case IR
  -> generated pytest
  -> aitest run / report
  -> fixes and rule promotion
```

### Docs and Knowledge

Put public behavior sources under `docs/`:

```text
docs/public_api.md
docs/openapi.yaml
docs/protos/
docs/config_schema.md
```

Use AI skills:

```text
doc-review       find documentation gaps
doc-gen          generate test-facing docs from source when needed
knowledge-build  build L0 system index, L1 module contract, L2 change docs
```

Unknown behavior should be marked as `[?]` instead of guessed.

### Markdown Cases

Module-level cases:

```text
test_workspace/cases/{module}/business.md
test_workspace/cases/{module}/boundary.md
```

Optional suite-level cases:

```text
test_workspace/casesuites/{suite}/aitest_suite.yaml
test_workspace/casesuites/{suite}/business.md
test_workspace/casesuites/{suite}/codegen_profile_{suite}_suite.md
```

Markdown cases are the reviewable source of test design.

### Fixtures and Profiles

```text
test_workspace/tests/fixtures/{module}.py
test_workspace/tests/fixtures/codegen_profile_{module}.md
```

Fixtures are action libraries: clients, public API calls, setup, cleanup, and reusable test actions.

Profiles configure deterministic generation: `module_type`, `variables`, `request_overrides`, `assertion_rules`, `case_flows`, and `case_bodies`.

### Codegen

```bash
aitest codegen --all --validate-profile
aitest codegen --all --dump-ir
aitest codegen --all
aitest codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

Single module:

```bash
aitest codegen <module> --validate-profile
aitest codegen <module> --dump-ir
aitest codegen <module> --explain TC-XXX-001
aitest codegen <module>
aitest codegen <module> --check
```

From outside the workspace:

```bash
aitest codegen --workspace /path/to/aitest_workspace --all --validate-profile
```

### Run and Report

```bash
aitest run <module>
aitest report
```

Reports are written to:

```text
test_workspace/reports/latest/
test_workspace/reports/runs/{run_id}/
```

`aitest run` checks generated freshness before executing pytest. If Markdown/profile changed but generated pytest was not refreshed, it writes a `BLOCKED_RUN` report and stops.

## CLI Cheat Sheet

| Command | Purpose |
|---|---|
| `aitest init --target <dir>` | Initialize a clean workspace |
| `aitest upgrade --workspace <dir> --check` | Check whether copied workspace assets need updates |
| `aitest upgrade --workspace <dir> --apply` | Apply safe template upgrades |
| `aitest doctor` | Check layout, profiles, generated freshness, collect, and env hints |
| `aitest codegen <module>` | Generate pytest for one module |
| `aitest codegen --all` | Generate pytest for all modules |
| `aitest codegen --cases <suite_dir>` | Generate pytest for a case suite |
| `aitest codegen --all --check` | Check generated freshness |
| `aitest run <module>` | Run generated pytest and write structured reports |
| `aitest report` | Re-render report from an existing `result.json` |

## AI Skills

The workspace includes `.codex`, `.claude`, and `.agents` skills:

| Skill | Use Case |
|---|---|
| `doc-review` | Review whether docs are testable |
| `doc-gen` | Generate test-facing docs from source or existing docs |
| `knowledge-build` | Build/update the L0/L1/L2 test knowledge base |
| `test-design` | Generate Markdown cases from the knowledge base |
| `test-scaffold` | Build module fixtures and profiles or suite profiles |
| `test-codegen` | Generate pytest and verify the codegen path |
| `test-fix` | Fix bad cases and record lessons |
| `emitter-build` | Promote stable repeated patterns |

## Codegen Paths

| Path | Profile Config | Best For |
|---|---|---|
| Default HTTP/gRPC | `request_overrides` | Single endpoint with stable request shape |
| Assertion rules | `assertion_rules` | Standard calls with reusable assertion templates |
| Structured flow | `case_flows` | Linear multi-step workflows |
| Custom body | `case_bodies` | Concurrency, subprocesses, mocks, file lifecycle |

Recommended evolution:

```text
case_bodies -> case_flows -> assertion_rules / default templates
```

## Security

- Do not commit `.env`, tokens, passwords, production accounts, or real user data.
- `variables.env` stores environment variable names only, not values.
- Reports may contain request/response/error details and should be reviewed before sharing.
- AITest Kit does not automatically create accounts, top up balances, create real API keys, or call high-risk paid resources.

## Stable Scope

Stable in v0.1.x:

- `aitest init/codegen/run/report/doctor/upgrade`
- workspace layout
- Markdown case format
- module/suite profile schema
- Case IR to pytest generation path
- freshness check
- structured report format

Still evolving:

- health/promotion report wording
- `case_flows` step vocabulary
- internal Python APIs
- future frontend, contract-test, and additional emitter types

## Development

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
python3 -m pip install -e ".[dev,server]"

python3 -m pytest tests -q
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli doctor
```

This repository includes `coupon_system` as a realistic regression asset for validating codegen, reporting, fixtures/profiles, and migration behavior.

## Documentation

- [中文 README](README.md)
- [Quickstart](docs/usebook/aitest_quickstart.md)
- [Migration Guide](docs/usebook/aitest_migration_guide.md)
- [Profile Guide](docs/usebook/codegen_profile_guide.md)
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md)
- [Coupon System Full Example](docs/usebook/coupon_system_full_example.md)
- [Roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [CHANGELOG](CHANGELOG.md)

## License

[MIT](LICENSE)
