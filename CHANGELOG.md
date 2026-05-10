# Changelog

## 0.1.1 - 2026-05-10

### Added

- Added PyPI-ready package metadata, including README long description, MIT SPDX license, license file, classifiers, keywords, and project links.
- Added a full `discount_system` external-project migration acceptance record, covering init, knowledge build, test design, codegen, real pytest execution, and emitter-build smoke analysis.
- Added PyPI/TestPyPI release commands and irreversible-upload notes to the v0.1 release spec.

### Changed

- Updated install documentation to use the PyPI package path while keeping local wheel installation instructions for release validation.
- Clarified the `test-codegen` skill workflow so first-pass AI exploration must be回灌 into fixture/profile/case_flow before final delivery.

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
