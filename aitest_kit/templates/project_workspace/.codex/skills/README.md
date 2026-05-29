# Codex Skills

新项目工作区可以把稳定的 AITest skills 放在这里，但不要把项目业务规则写进 skill。

推荐分工：

- skill：描述通用流程，例如 knowledge-build、test-design、test-scaffold、test-codegen、test-fix、emitter-build。
- `aitest_config/aitest.yaml`：描述 workspace 路径、target/module registry 和项目级 codegen 配置。
- `test_workspace/targets/{target}/`：描述被测系统、module fixture/profile/helper 和 target 默认输出目录。
- `test_workspace/knowledge/TEST_SPEC.md`：描述项目级测试规则和踩坑记录。
- `profile_{module}.md` / `profile_{suite}_suite.md`：描述模块级稳定规则和 suite 级生成规则。
- fixture/helper：描述项目级测试能力和环境编排。

如果当前项目直接使用 aitest-kit 仓库中的 skills，可以从 `.codex/skills/` 同步一份到这里，并在 review 时保持语义一致。
