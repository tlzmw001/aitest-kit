# Codex Skills

新项目工作区可以把稳定的 AITest skills 放在这里，但不要把项目业务规则写进 skill。

推荐分工：

- skill：描述通用流程，例如 knowledge-build、test-design、test-codegen、test-fix、emitter-build。
- `aitest_config/project_config.yaml`：描述项目级 codegen 配置。
- `test_workspace/knowledge/TEST_SPEC.md`：描述项目级测试规则和踩坑记录。
- `codegen_profile_{module}.md`：描述模块级生成规则。
- fixture/helper：描述项目级测试能力和环境编排。

如果当前项目直接使用 AIAutoTest 仓库中的 skills，可以从 `.codex/skills/` 同步一份到这里，并在 review 时保持语义一致。
