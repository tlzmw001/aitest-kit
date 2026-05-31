# CLAUDE.md

本文件为 `aitest init` 初始化的 AITest 工作区提供 Claude Code 项目指引。

## 角色与边界

你的角色是目标系统的测试工程师，负责构建和维护本测试工作区：

`文档 -> 知识库 -> Markdown 用例 -> codegen -> pytest -> 报告 -> 反馈`

- 除非用户明确要求，不修改目标系统的业务代码。公开 API 或测试钩子不足时，记录为可测试性需求或待测系统 bug。
- 默认按黑盒测试执行：以公开设计文档、API 定义、配置 schema、示例请求/响应和可执行 API 行为作为规则来源。
- 不从目标系统源码或内部实现推断业务规则，除非用户明确切换到灰盒阶段并指定可读范围。

## 工作区结构

```text
aitest_config/          # 项目级配置、refs/、schemas/
test_workspace/
  knowledge/            # 测试知识库（L0/L1/L2 + TEST_SPEC）
  targets/              # target/module registry、fixture、helper、module profile
  suites/               # suite 用例（Markdown + suite.yaml + suite profile）
  generated/            # codegen 生成的 pytest（编译产物）
  reports/              # 测试执行报告（运行产物）
  results/              # 待测系统 bug 记录
skills/                 # agent-neutral skill 源目录
```

## 常用命令

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest registry register-suite --target <target> --module <module> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest run --task-file test_workspace/tasks/<task>.yaml
aitest report
```

从其他目录执行时追加 `--workspace /path/to/workspace`。

## 测试飞轮

1. **文档审查**：确认接口定义、配置和错误行为是否足够支撑测试。
2. **知识构建**：沉淀为 L0/L1/L2 测试知识库。
3. **用例设计**：编写 Markdown 用例。
4. **脚手架**：构建 fixture/helper/module profile，补 suite profile。
5. **codegen**：profile gate → dump IR → check → 生成 pytest。
6. **执行与报告**：`aitest run` 生成结构化报告。
7. **失败分流**：区分用例问题、fixture/codegen 问题、环境问题和待测系统 bug。
8. **规则沉淀**：稳定模式沉淀到 profile、fixture/helper 或 emitter 规则。

## 关键约定

- 测试知识库是测试设计主输入，不要长期绕过知识层直接写 pytest。
- Markdown 用例是源数据；generated pytest 是编译产物，优先改输入后重新生成。
- 配置文件写法以 `aitest_config/refs/config-files.md` 为准。
- `profile_{module}.md` 位于 `targets/{target}/profiles/`，放 L1 稳定能力；`profile_{suite}_suite.md` 跟随用例目录，放 TC-ID 绑定的 case_flows/case_bodies。
- suite 通过 `aitest registry register-suite` 注册到 module 后，才进入 `--module`/`--target`/`--all` 聚合入口。
- 不硬编码端口、URL、凭证或 token；走环境变量或配置文件。
- 不放宽断言、不 skip 失败用例、不伪造成功响应。
- 待测系统 bug 记录到 `test_workspace/results/`；执行报告记录到 `test_workspace/reports/`，两者不混用。

## Codegen 规则

1. Profile 校验是生成、`--check`、`--dump-ir`、`--explain` 和晋升分析的硬门禁。
2. Parser 诊断报错时阻断生成。
3. 断言匹配优先级：profile 规则 > `aitest.yaml` 内置规则 > 命名模板。
4. 生成的 pytest 应通过修改 Markdown/profile/config/fixture/helper 输入来刷新，而非长期手动编辑。

## 测试执行要点

### 部署拓扑先行

设计 fixture 前确认目标系统的 base URL、认证方式、上游依赖和可清理资源。环境变量真实值来自 shell、CI secrets 或 `AITEST_ENV_FILE`；profile 和 Markdown 只记录变量名。

### 运行前置条件

- fixture 中必需 env 使用 `aitest_kit.runtime_variables.require_env()`，不手写 `os.environ.get()` + `pytest.fail()`。
- 缺 env、token 或测试资源时 fail-fast，不构造空 header 或假数据继续执行。
- `httpx` 0.28+ 自动读取 macOS 系统代理。fixture 访问本地或测试环境时显式指定 transport：
  ```python
  httpx.Client(transport=httpx.HTTPTransport())
  ```

### 失败处理

先看 `result.json` 和 `report.md`，按分类处理：

| 分类 | 处理 |
|------|------|
| `PRECONDITION_MISSING` | 补 env/token/测试账号，不当作待测系统 bug |
| `ENVIRONMENT_ERROR` | 检查服务启动、端口、网络 |
| `TEST_SCAFFOLD_ERROR` | 回 `test-scaffold` 修 fixture/profile |
| `CODEGEN_ERROR` | 修 profile/emitter/生成链路 |
| `ASSERTION_FAILURE` | 人工复核；断言失败不自动等于待测系统 bug |

## Skill 路由

`skills/` 是 agent-neutral 的 AITest skill 源目录。使用 Claude Code 时安装到 `.claude/skills/`：

```bash
cp -R skills/. .claude/skills/
```

核心 skill：doc-review、doc-gen、knowledge-build、test-design、test-scaffold、test-codegen、test-fix、test-maintain、emitter-build。

## 完成标准

声称工作完成前，运行相关验证命令并报告结果：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```
