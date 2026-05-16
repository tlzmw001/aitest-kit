# Contributing to aitest-kit

Thank you for contributing to `aitest-kit`. This project is built around one principle:

```text
AI explores unknown systems; code preserves stable, repeatable testing assets.
```

Contributions should keep that boundary clear. Use AI and docs to design tests, but keep parsing, validation, code generation, freshness checks, and reporting deterministic.

## Development Setup

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
pip install -e ".[dev,server]"
```

Python 3.9+ is supported.

## Repository Layout

- `aitest_kit/` — CLI, workspace init, codegen, report, and reusable helpers.
- `aitest_kit/templates/project_workspace/` — the only packaged workspace template used by `aitest init`.
- `docs/usebook/` — user-facing guides.
- `test_workspace/cases/` — Markdown test cases.
- `test_workspace/tests/fixtures/` — module fixtures and `codegen_profile_{module}.md`.
- `test_workspace/tests/generated/` — generated pytest files. Treat these as build outputs.
- `test_workspace/reports/` — local run artifacts. Do not commit generated reports.
- `test_workspace/results/` — confirmed SUT bug records and test findings.

## Generated Pytest Rule

Do not hand-edit files under:

```text
test_workspace/tests/generated/
```

If generated tests are wrong, update one of these sources instead:

- Markdown cases under `test_workspace/cases/`
- module profile under `test_workspace/tests/fixtures/codegen_profile_{module}.md`
- module fixture/helper under `test_workspace/tests/fixtures/` or `test_workspace/tests/helpers/`
- codegen logic under `aitest_kit/codegen/`

Then regenerate and verify:

```bash
python3 -m aitest_kit.cli codegen <module>
python3 -m aitest_kit.cli codegen <module> --check
```

## Codegen Validation

Use this sequence before submitting codegen-related changes:

```bash
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --dump-ir
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli doctor
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

`--dump-ir` is primarily for inspection. Profile validation and `--check` are the blocking gates.

## Test Commands

For general changes:

```bash
python3 -m compileall aitest_kit
python3 -m pytest tests/
```

For generated test collection:

```bash
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

For full generated test execution, start the required local services first. See the usebook documents under `docs/usebook/`.

## Documentation Updates

Update docs when a change affects:

- public CLI behavior
- workspace layout
- codegen profile format
- generated pytest behavior
- run/report output
- workspace template contents
- local skills or migration workflow

Check at least:

- `README.md`
- `README.en.md`
- `docs/usebook/`
- `aitest_kit/templates/project_workspace/README.md`

## Pull Request Expectations

Every PR should include:

- clear summary of the change
- verification commands and results
- whether generated pytest changed
- whether schema/template/skills changed
- any compatibility or migration notes

If a generated file changed, explain which source input caused it and include the codegen command used.

## Release Notes

User-visible changes should update `CHANGELOG.md`. Do not publish or tag releases from a PR unless the release itself is the requested task.
