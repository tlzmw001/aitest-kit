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
  aitest.yaml
  refs/
  schemas/
test_workspace/
  knowledge/
  targets/
  suites/
  generated/
  reports/
  results/
.claude/skills/
.codex/skills/
.agents/skills/
```

关键约定：

- `test_workspace/suites/{target}/{suite}/` 存放 Markdown 源用例和 suite profile；`suite.yaml` 绑定 target/module。
- `test_workspace/targets/{target}/` 存放 target/module registry、fixture、helper 和 module profile。
- 配置文件写法以 `aitest_config/refs/config-files.md` 为准；新建或修改 target/module/suite/profile/task/env 配置前先确认字段归属。
- suite 可直接通过 `--suite-file` 执行；要进入 module/target/all 聚合入口，使用 `aitest registry register-suite` 注册到 module。手写 `registered_suites` 时推荐直接写 suite manifest 路径字符串；需要 `status` 时再写 `{suite, manifest, status}` mapping。
- `test_workspace/generated/{target}/` 存放 codegen 生成的 pytest 文件，视为编译产物。
- `test_workspace/results/` 记录已确认的待测系统 bug 或重要发现。
- `test_workspace/reports/` 存放测试执行报告。

## 常用命令

在工作区根目录下执行：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest registry register-suite --target <target> --module <module> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest task create --name <task_name> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest report
```

从其他目录执行时，追加 `--workspace /path/to/workspace`。

## Codegen 规则

1. Profile 校验是普通生成、`--check`、`--dump-ir`、`--explain` 和晋升分析的硬门禁。
2. Parser 诊断报错时必须阻断生成。
3. Case IR 解释策略选择的原因，不应发明业务事实。
4. 断言匹配优先级：profile 规则 > `aitest.yaml` 内置规则 > 命名模板。
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
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```
