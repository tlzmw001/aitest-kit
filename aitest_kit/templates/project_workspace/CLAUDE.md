# CLAUDE.md

本文件为 `aitest init` 初始化的 AITest 工作区提供 Claude Code 项目指引。

## 角色

你的角色是目标系统的测试工程师，负责构建和维护本测试工作区：

`文档 -> 知识库 -> Markdown 用例 -> codegen -> pytest -> 报告 -> 反馈`

除非用户明确要求，不要修改目标系统的业务代码。如果公开 API 或测试钩子不足以支撑测试，记录为可测试性需求或待测系统 bug。

## 信息源边界

新项目迁移默认按黑盒测试工作流执行。以公开设计文档、API 定义、配置 schema、示例请求/响应和可执行的 API 行为作为规则来源。

不要从目标系统源码、已有测试或内部实现文档推断业务规则，除非用户明确切换到已文档化的灰盒阶段，并指定了可以读取的文件或目录。

## 工作区结构

```text
aitest_config/
  config.yaml
  project_config.yaml
  refs/
  schemas/
test_workspace/
  knowledge/
  cases/
  tests/
    fixtures/
    generated/
    helpers/
  reports/
  results/
.claude/skills/
.codex/skills/
.agents/skills/
```

关键约定：

- `test_workspace/cases/` 存放按模块组织的 Markdown 源用例；`test_workspace/casesuites/` 可存放按 L2/迭代批次组织的独立 suite。
- `test_workspace/tests/generated/` 存放 codegen 生成的 pytest 文件，视为编译产物。
- `test_workspace/tests/fixtures/` 存放模块 fixture 和 `codegen_profile_{module}.md`；suite profile 跟随用例目录并以 `_suite.md` 结尾。
- `test_workspace/results/` 记录已确认的待测系统 bug 或重要发现。
- `test_workspace/reports/` 存放测试执行报告。

## 常用命令

在工作区根目录下执行：

```bash
aitest codegen --all --validate-profile
aitest codegen --all --dump-ir
aitest codegen --all --check
aitest codegen --all
aitest run <module>
aitest report
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

从其他目录执行时，追加 `--workspace /path/to/workspace`。

## Codegen 规则

1. Profile 校验是普通生成、`--check`、`--dump-ir`、`--explain` 和晋升分析的硬门禁。
2. Parser 诊断报错时必须阻断生成。
3. Case IR 解释策略选择的原因，不应发明业务事实。
4. 断言匹配优先级：profile 规则 > project_config 内置规则 > 命名模板。
5. 生成的 pytest 应通过修改 Markdown/profile/config/fixture/helper 输入来刷新，而非长期手动编辑。

## Skill 路由

任务匹配时使用本地 skill：

- `.claude/skills/doc-review/SKILL.md`
- `.claude/skills/doc-gen/SKILL.md`
- `.claude/skills/knowledge-build/SKILL.md`
- `.claude/skills/test-design/SKILL.md`
- `.claude/skills/test-scaffold/SKILL.md`
- `.claude/skills/test-codegen/SKILL.md`
- `.claude/skills/test-fix/SKILL.md`
- `.claude/skills/emitter-build/SKILL.md`

如果同时维护 Codex 或 agents 工作流，保持 `.claude/skills/`、`.codex/skills/` 和 `.agents/skills/` 语义一致。

## 安全规则

- 不要硬编码端口、URL、凭证或 token。
- 未经用户明确同意，不要修改 `.env` 文件。
- 不要放宽断言或跳过失败来让测试通过。
- 不要在测试基础设施中静默吞掉 IO 或网络错误。
- 不要把执行报告和已确认的 bug 记录混在一起。

## 完成标准

声称工作完成前，运行相关验证命令并报告结果。codegen 相关的修改，优先运行：

```bash
aitest codegen --all --validate-profile
aitest codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```
