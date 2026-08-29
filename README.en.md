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
test_workspace/         # knowledge, suites, Module Harness packages, generated pytest, reports
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
| Scaffolding | Build a Module Harness and profiles | `/test-scaffold` |
| Codegen | Markdown + profile → pytest | `aitest codegen` |
| Run & report | Freshness check → pytest → structured reports | `aitest run` |
| Promotion | Extract repeated patterns into rules and templates | `/emitter-build` |

## CLI Cheat Sheet

```bash
aitest init --target <dir>                                   # initialize workspace
aitest doctor                                                # health check
aitest agent doctor                                          # check the local Pi Runtime
aitest codegen --suite-file <suite.yaml> --validate-profile  # profile gate
aitest codegen --suite-file <suite.yaml>                     # generate pytest
aitest codegen --suite-file <suite.yaml> --check             # check generated freshness
aitest run --suite-file <suite.yaml>                         # run one suite
aitest run --suite-file <suite.yaml> --capture               # run and write capture.jsonl
aitest run --target <target> [--module <module>]             # run by target/module
aitest run --all                                             # run all active suites
aitest report --suite-file/--target/--all ...                # re-render reports
```

### Local Console

The local Console uses Vue 3 and the AITest FastAPI backend and only binds to a loopback
address. Release wheels include the compiled frontend, so installed users do not need Node.js
or an AITest source checkout:

```bash
python3 -m pip install "aitest-kit[server]"
AITEST_CONSOLE_PORT=<local-port> aitest console --workspace /path/to/aitest_workspace
```

Frontend contributors use Node.js 22.18+ and run `npm --prefix console_web run build` after Vue changes. The build is
written to `aitest_kit/console/web/` and shipped in the wheel. `--workspace` may point to any
initialized workspace. Opening an uninitialized directory never writes files automatically;
the existing non-force initializer runs only after the user explicitly selects “Initialize and
open”, and template conflicts preserve the existing files.
Omit `--workspace` to open the empty Console first and choose or initialize a directory in the UI.

The Console browses and edits Markdown, profiles, YAML, and Harness/helper source; runs
profile validation, codegen, generated synchronization checks, and tests; and reads
`result.json` / `report.md` history. Generated files and reports remain read-only. Users can
explicitly edit authorized `.env`, `AITEST_ENV_FILE`, and task `env_files`; env values never
enter the ordinary file API. Job output redacts values known to the Console, while test assets
must still never print credentials deliberately.

Under **Settings → Model connection**, users provide a connection name, API type, Base URL,
model name, and API key without looking up a Pi provider. The connection test sends one real,
tool-free request through the Pi Worker. Non-sensitive settings are written to the workspace;
the API key remains only in the current Console process memory and must be entered again after
restarting the Console or switching workspaces.

From a source checkout with the Pi Worker dependencies installed, the **Agent** navigation item
can create either an approval or full-trust local session. A resumable SSE stream presents the
conversation, tool timeline, and inline approval cards. Write/edit requests can open Monaco Diff,
and backend-validated workspace paths and AITest run/report events link to the editor or reports.
Approval mode supports allow once, allow for session, and deny. Every full-trust session requires
an explicit confirmation for the current workspace. Browser refresh can replay events retained by
the current Console process; session recovery after a Console or Pi Worker process restart remains
out of scope.

For real API tests, provide credentials via env file:

```bash
AITEST_ENV_FILE=/tmp/test.env aitest run --suite-file <suite.yaml>
```

Reports record variable names only, never values. Full options: `aitest --help`.

For failure debugging, add `--capture`; the run directory will contain one `capture.jsonl`.
The framework auto-captures default HTTP cases only. Custom fixtures, gRPC, or SDK calls can
call `aitest_kit.helpers.capture.capture_io()` manually. When called inside a generated test
function body, `capture_io()` can infer the current case; explicit `case_id` still works and
wins. Pytest fixture setup/teardown runs outside this context. Capture does not redact; redact
in your fixture before writing sensitive data.

### Local Pi Agent Runtime (source-checkout PoC)

Phase 1 supports the Agent Runtime from an AITest source checkout only. It does not depend on a
global `pi` command, and the Node Worker is not yet bundled in PyPI wheels. Node.js must satisfy
`>=22.19.0`:

```bash
npm ci --prefix agent_runtime/pi_worker
aitest agent doctor --workspace /path/to/aitest_workspace
```

Store only model references and environment variable names in
`aitest_config/aitest.yaml`, never the key value:

```yaml
agent:
  runtime: pi
  connection_name: Anthropic
  model:
    protocol: anthropic_messages
    provider: anthropic
    name: claude-sonnet-4-5
    api_key_env: ANTHROPIC_API_KEY
    base_url: null
    base_url_env: null
```

Provide the key through the current shell. Approval mode is the default. Full trust requires an
explicit confirmation for every session and gives the native read/write/edit/grep/find/ls/bash
tools the current local user's host permissions. It is not a sandbox:

```bash
export ANTHROPIC_API_KEY=<your-key>
aitest agent run --workspace /path/to/aitest_workspace \
  --skill-path /path/to/skill \
  --prompt "Inspect the test assets and run profile validation"

aitest agent run --workspace /path/to/aitest_workspace \
  --mode full_trust \
  --prompt "Perform the approved test-maintenance task"
```

The protocol and logs carry the environment variable name, not the key. In approval mode,
workspace reads and searches are allowed by default; write/edit/bash/external-directory access
asks for approval, while `.env` and private-key paths are denied by default.

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
| `case-migrate` | Optional; convert external/historical cases into AITest Markdown cases |
| `test-design` | Generate Markdown cases from the knowledge base |
| `test-scaffold` | Build a Harness for a module or add a suite profile |
| `test-codegen` | Generate pytest from Markdown/profile |
| `test-fix` | Fix bad cases and record lessons |
| `test-maintain` | Diagnose workspace state, route to the right skill |
| `emitter-build` | Extract validated patterns into reusable rules |

## Codegen Paths

| Path | Profile Config | Best For |
|---|---|---|
| Default HTTP/gRPC | `requests` | Single endpoint, stable request shape |
| Assertion rules | `assertion_rules` | Standard calls, reusable assertion templates |
| Structured flow | `case_flows` | Linear multi-step workflows |
| Custom body | `case_bodies` | Concurrency, subprocesses, mocks, file lifecycle |

`case_flows` only orchestrate steps from the fixed `harness` root. Temporary files, log capture, mocks, loops, conditions, and cleanup belong in Module Harness capabilities. See [Profile Guide](docs/usebook/codegen_profile_guide.md).

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
│   ├── targets/                  # target registry + modules/{module}/{module.yaml,profile.md,fixture.py,harness.py}
│   ├── generated/                # generated pytest (build artifact)
│   ├── reports/                  # run reports
│   └── results/                  # confirmed SUT bug records
├── skills/                       # agent-neutral AI skills
├── AGENTS.md
└── CLAUDE.md
```

Each module has one public runtime shape: the `setup_{module}` fixture directly returns a `{Module}Harness`, exposed to generated pytest as `harness`. Module-specific capabilities stay in the module package. Only proven technical adapters shared by multiple modules in one target belong in `targets/{target}/helpers/`; there is no workspace-level helpers directory.

## Security

- Do not commit `.env`, tokens, passwords, or production accounts.
- Profile `variables.env` stores variable names only, not values; reports may contain request/response details — review before sharing.
- Does not auto-create accounts, top up balances, or call paid resources.

## Stable Scope

v0.3.x stable: `aitest init/codegen/run/report/doctor/upgrade`, workspace layout, Markdown case format, profile schema, request bindings, structured assertions, Case IR → pytest path, freshness check, structured reports.

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
