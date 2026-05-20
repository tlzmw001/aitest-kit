# AITest Kit Codex Plugin Prototype

This directory contains the repository-local prototype for the AITest Kit Codex plugin.

The plugin is intentionally a thin workflow layer. It does not copy or reimplement
`aitest-kit` parser, codegen, runner, or report logic. Deterministic execution
stays in the Python package and CLI.

## Scope

Prototype v0 includes nine entry skills:

- `onboard` — initialize or inspect an AITest workspace.
- `review-docs` — review project/API docs for test readiness.
- `build-knowledge` — build or update L0/L1/L2 test knowledge.
- `design-cases` — design Markdown business/boundary cases.
- `generate-tests` — run the codegen gate sequence and generate pytest.
- `run-tests` — run generated tests, read reports, and triage failures.
- `fix-failures` — classify failures and propose the smallest safe fix.
- `promote-rules` — analyze verified tests for rule promotion candidates.
- `learn-project` — teach a project interactively and record lesson notes.

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

For this repository-local prototype, first run structural checks:

```bash
python3 -m json.tool plugins/aitest-kit/.codex-plugin/plugin.json >/dev/null
find plugins/aitest-kit/skills -name SKILL.md | sort
```

Then verify local Codex discovery:

1. Register the local marketplace descriptor in your Codex config.
2. Start a new Codex session in a test repository.
3. Type `@AITest Kit`.
4. Confirm Codex offers to install the local plugin.
5. Install it and verify the plugin skills can be selected.

The expected smoke-test prompts are:

```text
@AITest Kit 使用 onboard 只检查当前项目是否已有 AITest workspace，不要初始化，不要修改文件。
@AITest Kit 使用 review-docs 只说明如何审查 docs/public_api_doc.md 是否足够生成测试，不要修改文件。
@AITest Kit 使用 build-knowledge 只说明如何从 docs 构建 L0/L1/L2，不要修改文件。
@AITest Kit 使用 design-cases 只说明如何从知识库设计 Markdown 用例，不要修改文件。
@AITest Kit 使用 generate-tests 只说明当前 workspace 执行 codegen gate 的命令顺序，不要修改文件。
@AITest Kit 使用 run-tests 只说明如何运行 generated tests 和读取 report，不要执行命令。
@AITest Kit 使用 fix-failures 只说明如何分流 latest report 里的失败，不要修改文件。
@AITest Kit 使用 promote-rules 只说明如何做只读 promotion 分析，不要修改文件。
@AITest Kit 使用 learn-project 只说明如何交互式学习项目并记录 lesson，不要修改文件。
```

Passing this smoke test means plugin discovery, installation, and skill loading
are wired correctly. It does not replace CLI-level validation such as
`aitest codegen --validate-profile` or `aitest run`.

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
through the Codex plugin installation UI:

```toml
[marketplaces.aitest-kit-local]
source_type = "local"
source = "/Users/zmw/AIAutoTest"

[plugins."aitest-kit@aitest-kit-local"]
enabled = true
```

Do not add this automatically from the plugin prototype. Updating user-level
Codex config is an installation step and should be explicit.

## Upgrade Local Plugin

This plugin is loaded from a local repository path. To upgrade an existing local
installation, update the repository first:

```bash
cd /path/to/aitest-kit
git checkout feat/codex-plugin-productization
git pull
python3 -m json.tool plugins/aitest-kit/.codex-plugin/plugin.json >/dev/null
find plugins/aitest-kit/skills -name SKILL.md | sort
```

Then refresh Codex:

1. Open a new Codex session.
2. If the old skill list is still shown, uninstall `AITest Kit` from Codex and
   install it again with `@AITest Kit`.
3. Run one smoke prompt for a newly added skill:

```text
@AITest Kit 使用 review-docs 只说明如何审查 docs/public_api_doc.md 是否足够生成测试，不要修改文件。
```

If Codex selects the expected skill, the local plugin upgrade is complete.

## Share With Other Users

This prototype is not published to a public Codex plugin marketplace. Share it as
a repository-local plugin:

1. Ask users to install the deterministic CLI:

```bash
pip install aitest-kit
```

2. Ask users to clone this repository:

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
git checkout feat/codex-plugin-productization
```

3. Ask users to register the local marketplace in their Codex config:

```toml
[marketplaces.aitest-kit-local]
source_type = "local"
source = "/absolute/path/to/aitest-kit"

[plugins."aitest-kit@aitest-kit-local"]
enabled = true
```

4. In Codex, users can install with:

```text
@AITest Kit
```

The plugin is the workflow and explanation layer. Users still need the
`aitest-kit` Python package for `aitest init`, `aitest doctor`, `aitest codegen`,
`aitest run`, and `aitest report`.
