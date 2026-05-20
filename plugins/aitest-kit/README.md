# AITest Kit Codex Plugin Prototype

This directory contains the repository-local prototype for the AITest Kit Codex plugin.

The plugin is intentionally a thin workflow layer. It does not copy or reimplement
`aitest-kit` parser, codegen, runner, or report logic. Deterministic execution
stays in the Python package and CLI.

## Scope

Prototype v0 includes three entry skills:

- `onboard` — initialize or inspect an AITest workspace.
- `generate-tests` — run the codegen gate sequence and generate pytest.
- `run-tests` — run generated tests, read reports, and triage failures.

Out of scope for this prototype:

- Public plugin marketplace publishing.
- PyPI package changes.
- Workspace template changes.
- MCP server or web dashboard.
- Automatic promotion patch application.
- Duplicating workspace `.codex/.claude/.agents` skills.

## Relationship To AITest Kit

```text
aitest-kit Python package
  -> deterministic CLI: init / doctor / codegen / run / report

workspace template
  -> project structure: aitest_config / test_workspace / local skills

Codex plugin
  -> user-facing workflow entry and explanation layer
```

The plugin should call or guide the user to call `aitest` commands. It should not
make silent environment changes, modify `.env`, or edit generated pytest by hand.

## Prototype Verification

For this repository-local prototype, verification is structural:

```bash
python3 -m json.tool plugins/aitest-kit/.codex-plugin/plugin.json >/dev/null
find plugins/aitest-kit/skills -name SKILL.md | sort
```

End-to-end installation into Codex is a later milestone.

## Local Codex Discovery

This repository includes a local marketplace descriptor:

```text
.agents/plugins/marketplace.json
```

It points Codex to:

```text
./plugins/aitest-kit
```

To test local discovery, add a marketplace entry to your Codex config manually or
through Codex plugin installation UI when available:

```toml
[marketplaces.aitest-kit-local]
source_type = "local"
source = "/Users/zmw/AIAutoTest"

[plugins."aitest-kit@aitest-kit-local"]
enabled = true
```

Do not add this automatically from the plugin prototype. Updating user-level
Codex config is an installation step and should be explicit.
