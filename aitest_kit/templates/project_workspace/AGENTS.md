# AITest Workspace 协作指南

本文件适用于当前目录及其所有子目录。这里是一个由 `aitest init` 初始化的新项目测试工作区，用于围绕目标系统建设 AI 驱动的自动化测试流程。

## 项目定位

当前目录是目标系统的独立测试工作区。默认工作流是：

`开发文档 -> 测试知识库 -> Markdown suite -> target fixture/profile -> codegen -> pytest 执行 -> 修正与沉淀`

AI 的默认角色是测试工程师。除非用户明确要求，不要为了让测试通过而修改目标系统业务代码；如果现有接口无法支撑测试条件，记录为测试基础设施需求或待测系统 bug。

## 目录结构

- `aitest_config/`
  项目级配置目录，包含路径、codegen 项目配置、schema 和共享格式参考。

- `test_workspace/knowledge/`
  测试知识库目录，包含 L0/L1/L2 和 `TEST_SPEC.md`。

- `test_workspace/targets/`
  按目标系统组织 target/module registry、模块 fixture、helper 和 module profile。

- `test_workspace/suites/`
  按目标系统组织独立 suite；suite 通过 `suite.yaml` 绑定到 target/module。

- `test_workspace/generated/`
  按目标系统保存 codegen 生成的 pytest 文件，视为编译产物。

- `test_workspace/cases/`
  legacy 兼容路径：按模块组织 Markdown 用例。

- `test_workspace/tests/fixtures/`
  兼容旧布局：模块级 fixture 与 `profile_{module}.md`。

- `test_workspace/tests/generated/`
  兼容旧布局：codegen 生成的 pytest 文件，视为编译产物。

- `test_workspace/reports/`
  测试执行报告目录。

- `test_workspace/results/`
  已确认的待测系统 bug、测试发现和复现记录。

- `.codex/skills/`
  Codex 本地 skill 定义。

- `.claude/skills/`
  Claude Code skill 定义。

- `.agents/skills/`
  agents 工作流 skill 定义。

## 常用命令

在当前 workspace 根目录内执行：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest report
```

如果从 workspace 外部执行，给命令追加：

```bash
--workspace /path/to/this/workspace
```

## 测试飞轮

1. 文档审查：确认公开文档、接口定义、配置和错误行为是否足够支撑测试。
2. 知识构建：把文档沉淀为 L0/L1/L2 测试知识库。
3. 用例设计：在 `test_workspace/suites/{target}/{suite}/` 编写 L2/迭代批次用例。
4. profile/fixture：在 target 目录维护模块 fixture/helper/module profile；suite 用例在用例目录旁维护 `_suite` profile。
5. codegen：通过 profile gate、dump IR、check，再正式生成 pytest。
6. 执行与报告：用 `aitest run` 生成结构化报告。
7. 失败分流：区分文档问题、用例问题、fixture/codegen 问题、环境问题和待测系统 bug。
8. 规则沉淀：稳定模式沉淀到 profile、project_config、fixture/helper 或 emitter 规则。

## 信息边界

新项目迁移首轮按黑盒测试方式推进：只使用公开设计文档、接口定义、配置 schema、示例请求响应和可执行 API 行为作为规则来源。

不要读取目标系统源码、已有测试或内部实现文档来推断业务规则，除非用户明确切换到灰盒补文档阶段，并说明哪些文件可以读、读它们是为了补全文档还是为了修复测试基础设施。

## 关键约定

- 测试知识库是测试设计主输入，不要长期绕过知识层直接写 pytest。
- Markdown 用例是源数据；generated pytest 是编译产物。
- `profile_{module}.md` 位于 `test_workspace/targets/{target}/profiles/`；`profile_{suite}_suite.md` 跟随具体用例 suite。旧命名 `codegen_profile_*` 仍兼容。
- 生成代码不手改为长期资产；优先改 Markdown、profile、fixture、helper 或配置后重新生成。
- 配置、端口、URL、凭证都走环境变量或配置文件，不硬编码。
- 不放宽断言、不 skip 失败用例、不伪造成功响应。
- 确认是待测系统 bug 时，记录到 `test_workspace/results/`。
- 运行产物放到 `test_workspace/reports/`，不要和 bug 记录混用。

## Skill 使用

当用户明确指定本地 skill，或任务明显匹配某个 skill 时，按本地 SOP 执行：

1. Codex 协作优先读取 `.codex/skills/{skill}/SKILL.md`。
2. Claude Code 协作优先读取 `.claude/skills/{skill}/SKILL.md`。
3. agents 工作流优先读取 `.agents/skills/{skill}/SKILL.md`。
4. 修改或迁移 skill 时，保持三处语义一致。

核心 skill：

- `doc-review`：审查开发文档完整性。
- `doc-gen`：从源码和现有文档补全测试设计输入。
- `knowledge-build`：构建或更新测试知识库。
- `test-design`：生成 Markdown 测试用例。
- `test-scaffold`：构建 target/module fixture + codegen profile。
- `test-codegen`：从 Markdown/profile 生成 pytest。
- `test-fix`：修正用例问题并沉淀经验。
- `emitter-build`：从已验证 pytest 提取确定性模板。

## 验证要求

声称完成前，至少给出并运行相关验证命令。常规 codegen 修改应覆盖：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

如服务环境已就绪，再运行对应模块的真实 pytest。
