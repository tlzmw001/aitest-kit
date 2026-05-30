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
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

Common registry-backed scopes:

```bash
aitest codegen --target <target> --module <module> --check
aitest run --target <target> --module <module>
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --case-id TC-XXX-001
aitest run --target <target>
aitest run --all
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

Target-aware suite cases:

```text
test_workspace/suites/{target}/{suite}/suite.yaml
test_workspace/suites/{target}/{suite}/business.md
test_workspace/suites/{target}/{suite}/profile_{suite}_suite.md
```

Markdown cases are the reviewable source of test design.

### Fixtures and Profiles

```text
test_workspace/targets/{target}/target.yaml
test_workspace/targets/{target}/modules/{module}.yaml
test_workspace/targets/{target}/fixtures/{module}.py
test_workspace/targets/{target}/helpers/
test_workspace/targets/{target}/profiles/profile_{module}.md
```

Fixtures are action libraries: clients, public API calls, setup, cleanup, and reusable test actions.

Profiles configure deterministic generation: `module_type`, `variables`, `request_overrides`, `assertion_rules`, `case_flows`, and `case_bodies`.

### Codegen

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

Codegen modes:

| Command | Requires profile gate | Writes generated pytest | Purpose |
|---|---:|---:|---|
| `--dry-run` | No | No | Parse Markdown only; useful before scaffold/profile is complete |
| `--validate-profile` | It is the gate | No | Validate profile JSON Schema, case id alignment, and case_flow/case_body semantics |
| `--check` | Yes | No | Regenerate into a tmpdir and diff against existing generated pytest |
| `--dump-ir` | Yes | No | Print suite Case IR JSON for strategy, fixture, request, and assertion tracing |
| `--explain <TC-ID>` | Yes | No | Print IR details for one case |
| `--health-report` | Yes | No, unless `--write-report` is used | Report codegen health, maturity, and stabilization signals |
| `--analyze-promotion` | Yes | No, unless `--write-report` is used | Analyze current suite profile case_bodies promotion candidates |
| no mode flag | Yes | Yes | Generate pytest |

Diagnostic modes have different scopes. `--dump-ir` and `--explain` operate on one `--suite-file` for precise suite/case debugging. `--health-report` and `--analyze-promotion` support `--suite-file`, `--target <target> --module <module>`, and `--target <target>` for module/target aggregation. `--suggest-promotion-patch` remains suite-only to avoid producing broad patch drafts that are hard to review safely.

From outside the workspace:

```bash
aitest codegen --workspace /path/to/aitest_workspace --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
```

### Run and Report

```bash
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest report --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

Reports are written to:

```text
test_workspace/reports/<target>/<module>/suites/<suite>/latest/
test_workspace/reports/<target>/<module>/cases/<case_id>/latest/
test_workspace/reports/<target>/<module>/module/latest/
test_workspace/reports/<target>/target/latest/
test_workspace/reports/tasks/<task_name>/latest/
```

Every report bucket keeps historical `runs/{run_id}/` entries and a `latest/` copy. Aggregate runs such as task, target, and module store suite-unit details under the same run id in `units/`, so one command does not create multiple unrelated top-level run ids.

`aitest run` checks generated freshness before executing pytest. If Markdown/profile changed but generated pytest was not refreshed, it writes a `BLOCKED_RUN` report and stops.

## CLI Cheat Sheet

| Command | Purpose |
|---|---|
| `aitest init --target <dir>` | Initialize a clean workspace |
| `aitest upgrade --workspace <dir> --check` | Check whether copied workspace assets need updates |
| `aitest upgrade --workspace <dir> --apply` | Apply safe template upgrades |
| `aitest doctor` | Check layout, profiles, generated freshness, collect, and env hints |
| `aitest registry register-suite --target <target> --module <module> --suite-file <suite.yaml>` | Register a suite into a module aggregate entry |
| `aitest task create --name <task> --suite-file <suite.yaml>...` | Create a task manifest from explicit suite files |
| `aitest codegen --suite-file <suite.yaml>` | Generate pytest for one target-aware suite |
| `aitest codegen --task-file <task.yaml>` | Generate or check suites listed by a task |
| `aitest codegen --target <target> [--module <module>]` | Generate or check registry suites for one target or module |
| `aitest codegen --all` | Iterate all active suites in the registry |
| `aitest run --suite-file <suite.yaml>` | Run one suite and write structured reports |
| `aitest run --suite-file <suite.yaml> --case-id <TC-ID>` | Run one case from a suite |
| `aitest run --task-file <task.yaml>` | Run a task and write an aggregate task report |
| `aitest run --target <target> [--module <module>]` | Run active suites for one target or module |
| `aitest run --all` | Run all active suites in the registry |
| `aitest report --suite-file/--task-file/--target/--all ...` | Re-render report for that scope |

For real API tests, provide service URLs, accounts, tokens, and API keys through a local env file:

```bash
AITEST_ENV_FILE=/tmp/your-system-test.env aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

`aitest run` injects that env file into the pytest subprocess. Reports record environment variable names only, never values. Real shell environment variables take precedence over the env file.

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
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --check
python3 -m aitest_kit.cli codegen --target coupon_system --module calibration --check
python3 -m aitest_kit.cli run --target coupon_system --module calibration -- --collect-only -q
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
