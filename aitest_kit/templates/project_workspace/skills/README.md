# AITest Skills

本目录是 agent-neutral 的 AITest skill 源目录。它不直接绑定 Codex、Claude Code 或其他 agent；使用哪个 agent，就把这一份 `skills/` 复制到对应的隐藏目录。

## 安装到当前 agent

Codex：

```bash
mkdir -p .codex/skills
cp -R skills/. .codex/skills/
```

Claude Code：

```bash
mkdir -p .claude/skills
cp -R skills/. .claude/skills/
```

agents workflow：

```bash
mkdir -p .agents/skills
cp -R skills/. .agents/skills/
```

## 可用 skill

- `doc-review`：审查开发文档是否足够支撑测试。
- `doc-gen`：从源码和现有文档补全测试设计输入。
- `knowledge-build`：构建或更新测试知识库。
- `test-design`：生成 Markdown 测试用例。
- `test-scaffold`：构建 fixture、helper、module profile 和 suite profile。
- `test-codegen`：从 Markdown/profile 生成 pytest。
- `test-fix`：修正用例问题并沉淀经验。
- `test-maintain`：诊断测试资产状态并路由到正确流程。
- `emitter-build`：从已验证 pytest 提取确定性模板。

## 维护规则

- `skills/` 是模板内唯一 skill 源，不要同时维护 `.codex/.claude/.agents` 三份模板副本。
- 项目业务规则不要写进 skill，应放到 `test_workspace/knowledge/`、`TEST_SPEC.md`、profile、fixture 或 helper。
- 修改本目录后，如当前 agent 已复制过一份隐藏目录，需要重新复制或手动同步。
