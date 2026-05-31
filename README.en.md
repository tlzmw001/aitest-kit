# aitest-kit

> Turn development docs, API contracts, and AI-designed test ideas into reviewable, reproducible, runnable automated test assets.

[中文 README](README.md)

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

```text
AI explores unknowns. Code stabilizes repeatable work.
```

## Why aitest-kit

- **Test design separated from test code** — Markdown cases are the reviewable design source; pytest is a build artifact, deterministically generated from Markdown + profile. No manual maintenance needed.
- **Failure triage, not just pass/fail** — Every failure is classified: docs gap, case issue, fixture/profile issue, environment problem, codegen bug, or SUT bug. No guesswork.
- **Gets more deterministic over time** — AI explores the system and drafts cases early on; validated patterns are promoted into profiles and assertion_rules, gradually reducing AI involvement and increasing repeatability.
- **9 AI skills across the full workflow** — From doc review, knowledge base, test design to fixture scaffolding, codegen, failure fixing, and rule promotion. Skills constrain AI behavior; human review gates quality.

Not meant for: one-off pytest, systems without executable interfaces, or auto-creating production accounts and paid resources.

## 3-Minute Start

### 1. Install

```bash
python3 -m pip install -U aitest-kit
```

If `aitest` is not on `PATH`, use `python3 -m aitest_kit.cli --help`.

### 2. Initialize a Workspace

```bash
cd /path/to/your_project
aitest init --target ./aitest_workspace
cd ./aitest_workspace
```

This creates:

```text
docs/                  # public API docs, design docs, OpenAPI/proto
aitest_config/          # project config, codegen config, schemas, refs
test_workspace/         # knowledge base, cases, fixtures, profiles, generated pytest, reports
skills/                 # agent-neutral AI skills, copy to .codex/.claude/.agents as needed
AGENTS.md / CLAUDE.md   # AI collaboration guidance
```

For configuration file formats, see `aitest_config/refs/config-files.md`.

### 3. Health Check

```bash
aitest doctor
```

An empty workspace has no modules yet. Put docs under `docs/`, then use the bundled AI skills:

```text
doc-review → knowledge-build → test-design → test-scaffold → test-codegen → aitest run
```

If you already have Markdown cases and profiles:

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

For detailed migration steps and long-term maintenance, see [Getting Started](docs/usebook/aitest_getting_started.md).

## Workflow

```text
Public docs / API contracts
  → L0/L1/L2 test knowledge base
  → Markdown test cases
  → fixture + codegen profile
  → Case IR → generated pytest
  → aitest run / report
  → fixes and rule promotion
```

| Phase | What | Tools |
|---|---|---|
| Docs & knowledge | Put public docs in `docs/`, build testable contracts | `/doc-review` `/knowledge-build` |
| Case design | Generate Markdown cases from knowledge base, human review | `/test-design` |
| Scaffolding | Add fixtures, helpers, profiles for new modules | `/test-scaffold` |
| Codegen | Markdown + profile → pytest | `aitest codegen` |
| Run & report | Freshness check → pytest → structured reports | `aitest run` |
| Promotion | Extract repeated patterns into rules and templates | `/emitter-build` |

## CLI Cheat Sheet

```bash
aitest init --target <dir>                                   # initialize workspace
aitest doctor                                                # health check
aitest codegen --suite-file <suite.yaml> --validate-profile  # profile gate
aitest codegen --suite-file <suite.yaml>                     # generate pytest
aitest codegen --suite-file <suite.yaml> --check             # check generated freshness
aitest run --suite-file <suite.yaml>                         # run one suite
aitest run --target <target> [--module <module>]             # run by target/module
aitest run --all                                             # run all active suites
aitest report --suite-file/--target/--all ...                # re-render reports
```

For real API tests, provide credentials via env file:

```bash
AITEST_ENV_FILE=/tmp/test.env aitest run --suite-file <suite.yaml>
```

Reports record variable names only, never values. Full options: `aitest --help`.

## AI Skills

The workspace includes an agent-neutral `skills/` directory. Copy to your agent:

```bash
mkdir -p .claude/skills && cp -R skills/. .claude/skills/   # Claude Code
mkdir -p .codex/skills && cp -R skills/. .codex/skills/     # Codex
```

| Skill | When to use |
|---|---|
| `doc-review` | Check whether docs are sufficient for test generation |
| `doc-gen` | Generate test-facing docs from source or existing docs |
| `knowledge-build` | Build/update the L0/L1/L2 test knowledge base |
| `test-design` | Generate Markdown cases from the knowledge base |
| `test-scaffold` | Add fixtures/profiles for new modules or suites |
| `test-codegen` | Generate pytest from Markdown/profile |
| `test-fix` | Fix bad cases and record lessons |
| `test-maintain` | Diagnose workspace state, route to the right skill |
| `emitter-build` | Extract validated patterns into reusable rules |

## Codegen Paths

| Path | Profile Config | Best For |
|---|---|---|
| Default HTTP/gRPC | `request_overrides` | Single endpoint, stable request shape |
| Assertion rules | `assertion_rules` | Standard calls, reusable assertion templates |
| Structured flow | `case_flows` | Linear multi-step workflows |
| Custom body | `case_bodies` | Concurrency, subprocesses, mocks, file lifecycle |

Recommended evolution: `case_bodies → case_flows → assertion_rules / default templates`. See [Profile Guide](docs/usebook/codegen_profile_guide.md).

## Workspace Layout

```text
aitest_workspace/
├── docs/                         # public doc input
├── aitest_config/
│   ├── aitest.yaml               # workspace config + codegen defaults
│   ├── schemas/                  # profile JSON Schema
│   └── refs/                     # case format, config file reference
├── test_workspace/
│   ├── knowledge/                # L0/L1/L2 + TEST_SPEC
│   ├── suites/                   # Markdown cases + suite profiles
│   ├── targets/                  # fixtures, helpers, module profiles
│   ├── generated/                # generated pytest (build artifact)
│   ├── reports/                  # run reports
│   └── results/                  # confirmed SUT bug records
├── skills/                       # agent-neutral AI skills
├── AGENTS.md
└── CLAUDE.md
```

## Security

- Do not commit `.env`, tokens, passwords, or production accounts.
- Profile `variables.env` stores variable names only, not values; reports may contain request/response details — review before sharing.
- Does not auto-create accounts, top up balances, or call paid resources.

## Stable Scope

v0.2.x stable: `aitest init/codegen/run/report/doctor/upgrade`, workspace layout, Markdown case format, profile schema, Case IR → pytest path, freshness check, structured reports.

Still evolving: health/promotion report wording, `case_flows` step vocabulary, internal Python APIs, frontend and contract-test directions.

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

This repository includes `coupon_system` as a realistic regression asset. See [Coupon System Full Example](docs/usebook/coupon_system_full_example.md).

## Documentation

- [中文 README](README.md)
- [Getting Started](docs/usebook/aitest_getting_started.md) — Install, initialize, migrate, and maintain
- [Profile Guide](docs/usebook/codegen_profile_guide.md)
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md)
- [Contributing](CONTRIBUTING.md)
- [CHANGELOG](CHANGELOG.md)

## License

[MIT](LICENSE)
