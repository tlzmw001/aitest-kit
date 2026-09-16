# aitest-kit

> Turn development docs, API contracts, and AI-designed test ideas into reviewable, reproducible, runnable automated test assets.

A local-first workbench for test engineers: manage test assets in a browser, use the built-in Pi Agent
to help design and maintain them, and run validation, code generation, tests, and reports through a
deterministic CLI. Files stay in your workspace; you choose the model service and bring your own API key (BYOK).

[中文 README](README.md)

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

```text
AI explores unknowns. Code stabilizes repeatable work.
```

## Why aitest-kit

- **Test design separated from test code** — Markdown cases are the reviewable design source; pytest is a build artifact, deterministically generated from Markdown + profile. No manual maintenance needed.
- **Failure triage, not just pass/fail** — Structured reports distinguish preconditions, environment, scaffolding, codegen, and assertion failures. An assertion failure still needs human review against the contract; it is not automatically a SUT bug.
- **Gets more deterministic over time** — AI explores the system and drafts cases early on; validated patterns are promoted into profiles and assertion_rules, gradually reducing AI involvement and increasing repeatability.
- **9 AI skills across the full workflow** — From doc review, knowledge base, test design to fixture scaffolding, codegen, failure fixing, and rule promotion. Skills constrain AI behavior; human review gates quality.
- **One set of files for the UI and CLI** — Browse directories to open a workspace, edit cases and configuration in Monaco tabs, then validate, generate, run, and inspect structured reports.
- **An Agent with tools and explicit permissions** — Pi can read docs, follow skills to create or modify test assets, and run commands. Choose approval mode or explicitly enable full trust.

Not meant for: one-off pytest, systems without executable interfaces, or auto-creating production accounts and paid resources.

## 3-Minute Start

### 1. Install

To try the Console and Agent described here, install from the current `main` branch. Python 3.9+
is required. The Console and CLI alone do not need Node.js; the Agent additionally needs Node.js 22.19.0+ and npm.

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[server]"
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and use `python` instead of `python3`
if that is your installed command. The repository includes a built frontend; no npm build is needed for ordinary use.
For a released version, use `python3 -m pip install -U "aitest-kit[server]"`; PyPI may lag behind `main`.

Use the same Python environment for subsequent commands. If `aitest` is not on `PATH`, activate the environment
or replace the command prefix with `python3 -m aitest_kit.cli`, for example `python3 -m aitest_kit.cli console --port 8123`.

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

### 3. Open the Console

```bash
aitest doctor
aitest console --workspace . --port 8123
```

`8123` is an example; choose an available port. The browser opens automatically with a local session credential.
Start in Workbench (工作台), edit in Cases (用例), execute in Run (运行), and inspect Reports (报告).
To have the Agent help create or maintain test assets, continue with [Agent setup and usage](#agent-setup-and-usage).

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
aitest console --workspace <dir> --port <port>                # start the local UI
aitest agent setup                                           # install the current user's Pi Runtime
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

## Local Console: Browse, Edit, Run, and Inspect

The Console uses Vue 3, FastAPI, and Monaco, the editor component used by VS Code.
It binds only to a local loopback address, not a hosted multi-user service. The UI and CLI work on the same workspace files.

| Page | What you can do |
|---|---|
| Workbench (工作台) | Browse directories, open or initialize a workspace; inspect targets, modules, suites, cases, and tasks; create test assets and delete suites |
| Cases (用例) | Edit Markdown, YAML, Python, and profiles in multiple tabs; sanitized Markdown preview, validation, and save-conflict handling; editor themes and tab behavior in Settings |
| Run (运行) | Select a case, suite, module, or task; run profile validation, codegen, freshness checks, and tests |
| Reports (报告) | Review execution history, `result.json`, and `report.md`; read-only JSON viewing |
| Diagnostics (诊断) | Inspect failure categories and open related source files; distinguish configuration, scaffolding, environment, codegen, and assertion problems without automatically blaming the SUT |
| Environment (环境) | Explicitly create or edit authorized env files; sensitive values hidden by default and external env files authorized individually |
| Agent | Chat, inspect tool calls and write diffs, approve actions, continue historical sessions, and inspect request diagnostics |

A suite is the smallest unit for case-asset creation/deletion in the UI. To change or remove an individual case,
edit its Markdown file and save; there is no per-case creation/deletion form. Generated pytest and reports stay read-only.
Harnesses, helpers, and profiles use the code editor rather than complex low-code forms.

### Start from Any Directory

Once installed with the environment activated, you do not need to return to the source checkout.
Specify a workspace, or open the empty Console and browse for one:

```bash
aitest console --workspace /path/to/aitest_workspace --port 8123
# Or choose the workspace in the UI
aitest console --port 8123
```

The port can also be supplied through `AITEST_CONSOLE_PORT`. The browser opens automatically by default.
If it does not, restart with `--no-open` and copy the complete `Session URL` printed in the terminal.
Do not use only the bare address or share the session URL. Restarting the Console invalidates the old credential.

Selecting an uninitialized directory does not write files. Only “Initialize and open” starts the non-force
initializer; template conflicts stop initialization and preserve existing files. Opening a workspace does not run tests.

### A Typical Workflow

1. Open a workspace in Workbench and select or create a target, module, and suite.
2. Edit Markdown cases; maintain module/suite profiles, Harnesses, and helpers as needed.
3. In Run, perform profile validation, codegen, then freshness check. Freshness checks whether generated pytest matches its source cases and configuration; it does not execute tests.
4. Prepare runtime variables in Environment, select the execution scope, and run tests.
5. Read the current and historical Reports; use Diagnostics to locate problems, correct the source, regenerate, and rerun.

Environment supports `.env`, `AITEST_ENV_FILE`, and task `env_files`. Values do not enter the ordinary file API
or localStorage. Job output redacts sensitive values known to the Console, but test assets must still never print credentials deliberately.

## Agent Setup and Usage

The built-in Agent uses the Pi SDK to read docs and test knowledge, follow workspace skills to draft Markdown cases,
maintain Harnesses/profiles, run validation and codegen, and investigate failures. AI makes decisions and edits;
AITest CLI still owns deterministic validation, generation, and execution. The Agent should not bypass the profile gate
or treat generated pytest as hand-maintained source.

### 1. Prepare the Runtime and Model Connection

1. Install Node.js 22.19.0+ and npm, then open Settings → Model connection (设置 → 模型连接).
2. Confirm installation in the Runtime card, or run `aitest agent setup`. It installs locked dependencies under the current user's directory, without modifying the workspace.
3. Enter a connection name, API type, Base URL, model name, and API key; no Pi provider lookup is needed.
   Supported protocols are OpenAI Responses, OpenAI Chat Completions, and Anthropic Messages. For OpenAI-compatible models, auto detection tries Responses first and only falls back to Chat Completions on explicit protocol incompatibility. Claude model names automatically select Anthropic Messages.
4. Test the connection, then save. Testing sends real, tool-free model requests and may incur provider charges; auto-detection fallback can require more than one request.

Use the Base URL and model identifier supplied by your service. Non-sensitive settings are saved in the workspace.
A key entered in the UI stays only in the current Console process memory; enter it again after restarting or switching workspaces.
Alternatively, supply the configured environment variable before starting the Console.
Local-first does not mean offline inference: content read by the Agent may be sent to the configured model service.
Check data-sharing permissions before using external source code or knowledge bases.

### 2. Create a Session and Work with Skills

Open Agent and start with approval mode. The Console supplies `.codex/skills/`, `.agents/skills/`, and `skills/`
from the current workspace. A new workspace's bundled `skills/` works directly; no global Pi configuration is required.
AITest uses an isolated Agent configuration directory and does not automatically load global Pi configuration or third-party extensions.

Example requests, with your own module and paths:

```text
Use test-maintain to inspect this workspace and suggest the next step. Do not modify files yet.
Use test-design and the existing knowledge base to design a suite for the selected module. Stop for my review.
Use test-scaffold to complete the approved suite's Harness and profiles, then test-codegen to validate and generate tests.
Read this run's result.json, distinguish environment, scaffolding, and assertion failures, and propose a fix first.
```

Approval cards show the tool and arguments, with allow once, allow for session, and deny choices.
Write/edit requests support Monaco Diff. External-directory access, recursive grep, writes, and shell commands require approval;
direct reads of sensitive paths are denied by default. **Approval is not a sandbox**: approved grep/shell calls can still access
sensitive data. Full trust uses the local process's permissions and requires confirmation for the current workspace on every
creation or reactivation. Use it only when you trust the task, files, and model.

### 3. Resume History and Diagnose Long Waits

Multiple historical sessions persist, but each Console has only one active Worker; Agent sessions do not run concurrently.
After a restart, review history and explicitly continue. Unfinished turns become `interrupted`; tools are not automatically retried
and old approval grants are not restored. Check whether the last tool already had an effect before continuing.
History is stored in a user-level, workspace-scoped directory, not an additional cross-session semantic memory store.

The composer shows request phases and approval status. Expand request diagnostics to inspect HTTP, first-text, completion,
and automatic-retry timing. For a long wait, enable detailed stream diagnostics for the next message before sending;
detailed SSE statistics currently support only OpenAI Responses. Diagnostics do not record request/response bodies,
reasoning content, headers, or credentials, and do not change permissions or retry policies.

### CLI, Runtime, and Test Credentials

For real API tests, provide credentials via env file:

```bash
AITEST_ENV_FILE=/tmp/test.env aitest run --suite-file <suite.yaml>
```

Environment-source metadata in reports records variable names, not values; request/response details and test output still need care to avoid leaking sensitive data. Full options: `aitest --help`.

For failure debugging, add `--capture`; the run directory will contain one `capture.jsonl`.
The framework auto-captures default HTTP cases only. Custom fixtures, gRPC, or SDK calls can
call `aitest_kit.helpers.capture.capture_io()` manually. When called inside a generated test
function body, `capture_io()` can infer the current case; explicit `case_id` still works and
wins. Pytest fixture setup/teardown runs outside this context. Capture does not redact; redact
in your fixture before writing sensitive data.

### Local Pi Agent Runtime

The Python wheel carries a locked Pi Worker installation seed, not the large expanded
`node_modules`. Install Node.js first (minimum `22.19.0`; Node.js 24 LTS is recommended), then
explicitly install the user-level Runtime:

```bash
aitest agent setup
aitest agent doctor --workspace /path/to/aitest_workspace
```

The default destination is `~/.aitest/runtimes/pi-worker/<bundle-hash>/`; override the root with
`AITEST_RUNTIME_HOME`. Setup uses the exact lockfile shipped in the wheel. It does not install Node,
write to the workspace, modify Python `site-packages`, or read model credentials. Source contributors
can still run `npm ci --prefix agent_runtime/pi_worker`; the resolver prefers a complete source Worker
and otherwise uses the user Runtime matching the current bundle.

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
workspace read/find/ls are allowed by default; grep/write/edit/bash/external-directory access
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
- Do not let the Agent create real accounts, top up balances, or change production resources without confirmation. Connection tests and Agent conversations call your configured model service and may incur charges.

## Stable Scope

Core pipeline: `aitest init/codegen/run/report/doctor/upgrade`, workspace layout, Markdown case format, profile schema, request bindings, structured assertions, Case IR → pytest, freshness checks, and structured reports.

Current `main` also includes the local Console, Monaco editing, Pi Agent approvals and persistent sessions, and request diagnostics. It does not provide a multi-user service, sandbox, or concurrent Agent sessions.
Still evolving: Console/Agent interactions, health/promotion report wording, `case_flows` step vocabulary, internal Python APIs, and contract-test directions.

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

Node.js and a frontend build are needed only when changing the UI source. For source development, use Node.js 22.19.0+
to also satisfy the Worker requirement:

```bash
npm ci --prefix console_web
npm run build --prefix console_web
```

The build writes to `aitest_kit/console/web/`. Restart the Console and use the newly opened session page to see changes;
restarting Python alone does not compile Vue source. See above for source Worker development and user-level Runtime installation.

## Documentation

- [中文 README](README.md)
- [Getting Started](docs/usebook/aitest_getting_started.md) — Install, initialize, migrate, and maintain
- [Profile Guide](docs/usebook/codegen_profile_guide.md)
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md)
- [Contributing](CONTRIBUTING.md)
- [Console / Pi delivery verification](docs/usebook/console_delivery_verification.md) — Cross-platform installation CI, visual baselines, and persistence measurements (Chinese)
- [CHANGELOG](CHANGELOG.md)

## License

[MIT](LICENSE)
