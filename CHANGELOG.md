# Changelog

## 0.1.6 - 2026-05-28

### Added

- Added the `test-maintain` skill as a maintenance router for test asset updates, including Codex, Claude, agents, and initialized workspace template copies.

### Changed

- Ignored local agent settings and local test backup directories so personal machine state does not pollute release diffs.

## 0.1.5 - 2026-05-28

### Added

- Added unique report run IDs with microsecond precision and a random suffix to prevent parallel `aitest run` executions from writing to the same report directory.
- Added `AITEST_ENV_FILE` loading for `aitest run`, injecting configured env-file values into the pytest subprocess while recording only variable names in reports.
- Added `require_env()` and `require_envs()` helpers so fixtures can report missing runtime inputs as `PRECONDITION_MISSING` instead of generic fixture failures.

### Changed

- Updated report output for env-file blocked runs and env-file metadata.
- Updated scaffold skills and workspace templates to generate fixture env checks through `require_env()`.

## 0.1.4 - 2026-05-27

### Changed

- Reworked the Chinese README into a 3-minute onboarding entry that covers installation, workspace initialization, core workflow, CLI commands, AI skills, codegen paths, and safety boundaries.
- Updated the English README to match the current workspace, suite profile, doctor, upgrade, and reporting workflows.
- Rewrote the packaged workspace README so newly initialized projects get clearer next steps for docs, knowledge, cases, fixture/profile, codegen, and reports.
- Refined the quickstart and migration guide to emphasize the real new-project workflow and clarify that `business.md`/`boundary.md` are organization conventions, not mandatory file names.

## 0.1.3 - 2026-05-26

### Added

- Added case-suite profile support so generated pytest can be organized by Markdown case files instead of only module-level profiles.
- Added workspace upgrade support through `.aitest/workspace.json` manifests and the `aitest upgrade` command.
- Added upgrade-aware workspace template metadata, including packaged skill reference files and case-suite directories.

### Changed

- Refactored codegen execution into module and suite runners to reduce CLI orchestration complexity.
- Strengthened profile validation, doctor checks, and scaffold/codegen skill guidance for new-project migrations.
- Split long skill files into focused `refs/` documents across Codex, Claude, agents, and workspace templates.

## 0.1.2 - 2026-05-20

### Added

- Added `aitest doctor` for lightweight workspace diagnostics, including profile validation and generated pytest freshness checks.
- Added open-source onboarding assets: issue templates, pull request template, contributing guide, English README, roadmap, and full `coupon_system` example guide.
- Added a formal migration guide and project code-reading guide, replacing older informal codegen teaching notes.
- Added project-learning skill notes and a P2 codegen target extension spec for future API/UI/E2E/Contract boundaries.

### Changed

- Renamed public project branding from `openTester` to `aitest-kit` across package metadata and documentation.
- Reworked README positioning and quickstart content for PyPI-first installation and new-project workspace usage.
- Updated CI generated-test collection dependencies to include server extras.

## 0.1.1 - 2026-05-10

### Added

- Added PyPI-ready package metadata, including README long description, MIT SPDX license, license file, classifiers, keywords, and project links.
- Added a full `discount_system` external-project migration acceptance record, covering init, knowledge build, test design, codegen, real pytest execution, and emitter-build smoke analysis.
- Added PyPI/TestPyPI release commands and irreversible-upload notes to the v0.1 release spec.

### Changed

- Updated install documentation to use the PyPI package path while keeping local wheel installation instructions for release validation.
- Clarified the `test-codegen` skill workflow so first-pass AI exploration must be fed back into fixture/profile/case_flow before final delivery.

## 0.1.0 - 2026-05-08

### Added

- Added the `aitest` CLI with `init`, `codegen`, `run`, and `report` commands.
- Added a single packaged project workspace template under `aitest_kit/templates/project_workspace/`.
- Added `aitest init --target <dir>` for creating a clean workspace for one target system.
- Added `--workspace <dir>` support so codegen, run, and report can operate outside the source repository.
- Added profile JSON Schema and semantic validation as a hard gate for normal codegen, `--check`, `--dump-ir`, `--explain`, and promotion analysis.
- Added Case IR dump/explain/check flows for understanding generated pytest output.
- Added structured execution reports through `aitest run` and `aitest report`.
- Added Quickstart, profile guide, troubleshooting guide, and new-project migration playbook.

### Supported In 0.1

- Local, file-based test workspaces.
- Markdown test cases as the source of generated pytest.
- Module-level `codegen_profile_{module}.md` files for request overrides, assertion rules, `case_flows`, and `case_bodies`.
- Generated pytest freshness checks before structured test execution.
- Local AI collaboration assets through `AGENTS.md`, `CLAUDE.md`, and `.codex/.claude/.agents` skills.

### Not Supported In 0.1

- Web UI.
- Fully automatic migration of a new target system.
- Automatic extraction of `case_flows` from verified pytest.
- Automatic application of promotion patches.
- Automatic modification of target-system business code.
- Guaranteed zero-configuration support for every language, protocol, or framework.

### Experimental

- Codegen health and promotion reports are intended for review and migration planning.
- `case_flows` are stable enough for generated tests, but their step vocabulary may still grow in later minor versions.
- Internal Python module APIs under `aitest_kit.codegen` may change; the public surface is the CLI, workspace layout, Markdown case format, and profile schema.

### Security And Privacy

- Do not commit `.env` files, service credentials, access tokens, or production data inside an AITest workspace.
- Generated reports may contain request IDs, response bodies, assertion messages, and service error details; treat `test_workspace/reports/` as test evidence that may require review before sharing.
- Keep secrets in environment variables or local secret managers. Fixtures should fail clearly when a required environment variable is missing.
- `aitest-kit` does not sanitize target-system responses automatically in v0.1.
