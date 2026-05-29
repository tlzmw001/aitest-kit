# AITest 新项目迁移指南

本文面向已经安装 `aitest-kit`，并准备把 AITest 工作流接入一个新待测系统的用户。

AITest 的迁移目标不是一次性让 AI 直接生成大量 pytest，而是建立一条可审查、可重复、可逐步沉淀规则的测试飞轮：

```text
公开文档 -> 测试知识库 -> Markdown 用例 -> profile/fixture -> generated pytest -> run/report -> 修正与沉淀
```

## 一、迁移原则

### 1. 首轮按黑盒边界执行

新项目首轮迁移只使用以下信息作为规则来源：

- 公开设计文档
- API 定义：OpenAPI、Swagger、proto 等
- 配置 schema
- 示例请求/响应
- 可执行 API 行为

不要读取目标系统源码、已有测试或内部实现文档来推断业务规则。源码可以在后续灰盒补文档阶段使用，但必须明确记录边界切换：读了哪些文件、为了补全文档还是为了修复测试基础设施。

### 2. 框架层不随项目迁移改动

AITest 当前不拆分 `aitest_kit` 与 workspace 协议仓库。框架代码、schema、模板和回归资产同仓维护；真实用户项目通过独立 workspace 隔离。

迁移新项目时，优先改：

- `aitest_config/config.yaml`
- `aitest_config/project_config.yaml`
- `test_workspace/tests/fixtures/{module}.py`
- `test_workspace/tests/fixtures/codegen_profile_{module}.md`
- `test_workspace/cases/{module}/`

不要为了适配单个项目直接修改 parser、planner、renderer 或 emitter engine。只有当多个项目反复出现同一稳定模式时，才考虑进入框架层沉淀。

### 3. workspace 模板只有一个来源

`aitest init` 使用的唯一模板源是：

```text
aitest_kit/templates/project_workspace/
```

不要新增或维护顶层 `templates/project_workspace/` 镜像。这样源码运行和安装后运行都读取同一份模板，避免双模板同步问题。

## 二、初始化 workspace

推荐把 AITest workspace 放在目标项目下的独立目录：

```bash
cd /path/to/your_project
aitest init --target ./aitest_workspace
cd ./aitest_workspace
```

初始化后，目标目录中会出现：

```text
AGENTS.md
CLAUDE.md
.agents/
.claude/
.codex/
docs/
aitest_config/
test_workspace/
```

这些文件都属于 AITest workspace 的初始化资产：

- `AGENTS.md` / `CLAUDE.md`：AI 协作入口和项目规则。
- `.agents/`、`.claude/`、`.codex/`：不同 AI 环境使用的本地 skills。
- `docs/`：放公开设计文档、API 文档和迁移输入。
- `aitest_config/`：项目配置和 codegen schema。
- `test_workspace/`：知识库、Markdown 用例、fixture、profile、generated pytest、报告和结果记录。

如果不在 workspace 目录内执行命令，统一使用 `--workspace`：

```bash
aitest codegen --workspace /path/to/your_project/aitest_workspace --all --validate-profile
aitest codegen --workspace /path/to/your_project/aitest_workspace --all
aitest run --workspace /path/to/your_project/aitest_workspace <module>
aitest report --workspace /path/to/your_project/aitest_workspace
```

## 三、升级已有 workspace

`aitest-kit` 升级后，先升级 Python 包：

```bash
python3 -m pip install -U aitest-kit
```

这一步只更新 CLI、codegen、doctor、run/report 等程序代码，不会自动覆盖已经复制进项目的 workspace 文件。要同步新版模板资产，使用：

```bash
aitest upgrade --workspace /path/to/your_project/aitest_workspace --check
aitest upgrade --workspace /path/to/your_project/aitest_workspace --apply
```

`upgrade` 会检查 `.aitest/workspace.json` 中记录的模板哈希：

- 当前文件仍等于旧模板 → 可以安全升级。
- 当前文件已经被用户修改 → 默认跳过，提示人工 review。
- 目标文件缺失 → 如果属于安全模板资产，自动补齐。
- 项目专属配置、fixture、profile、用例、generated pytest 和测试结果 → 默认不自动覆盖。

不要用 `aitest init --force` 升级已有 workspace，它会直接覆盖模板管理文件，容易丢失项目适配。

## 四、准备迁移输入

把公开文档放入 workspace 的 `docs/` 目录，例如：

```text
docs/public_api.md
docs/openapi.yaml
docs/protos/
docs/config_schema.md
```

文档最少应覆盖：

- 服务用途和主要模块。
- HTTP/gRPC 入口。
- 请求/响应字段。
- 错误码和错误响应。
- 业务规则和优先级。
- 可观测状态：查询接口、日志、指标、存储 key 等。
- 测试环境如何访问服务：base URL、端口、环境变量。

文档缺失的信息不要猜测，在知识库里标 `[?]`，后续由产品、开发或灰盒补文档确认。

## 五、构建测试知识库

使用 `knowledge-build` 从 `docs/` 构建或更新测试知识库：

```text
docs/
  -> test_workspace/knowledge/L0_system_architecture.md
  -> test_workspace/knowledge/L1/{module}.md
  -> test_workspace/knowledge/L2/{change}.md
```

知识库的作用是把原始开发文档转成可测试契约：

- L0：系统架构和模块索引。
- L1：模块当前完整行为。
- L2：需求变更和测试重点。
- `TEST_SPEC.md`：跨模块共享测试准则和历史陷阱。

知识库是测试设计的主输入。不要绕过知识库直接从零散文档生成 pytest。

## 六、设计 Markdown 用例

模块级用例默认放在：

```text
test_workspace/cases/{module}/business.md
test_workspace/cases/{module}/boundary.md
```

这两个文件不是强制都要存在。只有 `business.md`、只有 `boundary.md`，或按更细维度拆成多个 Markdown 文件都可以生成 pytest；拆分的目的只是让人类 review 更清晰。

如果用例按需求、迭代或临时批次组织，也可以使用独立 suite：

```text
test_workspace/casesuites/{suite}/aitest_suite.yaml
test_workspace/casesuites/{suite}/{case_file}.md
test_workspace/casesuites/{suite}/codegen_profile_{suite}_suite.md
```

Markdown 用例必须满足：

- `## 共享配置` 使用标准 section 名。
- `json` 代码块必须是严格合法 JSON。
- 基础请求体必须是可执行默认值，不允许 `{{var}}` 占位符。
- case 级差异写在场景变量中，并在 profile、fixture 或 `case_flows` 中落成机器可读配置。
- 不可观测、不可稳定复现、依赖未公开能力的场景，不要伪造成自动化用例。

推荐先让 AI 设计初版，再由人工 review：

- 用例是否真的来自文档和知识库。
- 断言是否可观测。
- 请求体是否完整。
- 是否把产品 bug、文档缺口、测试基础设施需求混进正常回归用例。

## 七、补充项目配置

优先修改：

```text
aitest_config/config.yaml
aitest_config/project_config.yaml
```

其中 `project_config.yaml` 是 codegen 适配的核心。它决定：

- generated pytest 的 helper import。
- 默认 API 路径。
- HTTP/gRPC 调用函数。
- 断言变量映射。
- 模块缩写。
- `default_request.auto_fields`：default_http/default_grpc 自动注入的请求字段。新项目默认应保持为空，只有项目确有稳定唯一字段时才显式配置。
- `module_type`。
- 内置断言规则。

典型分层如下：

```text
框架层：parser / planner / renderer / CLI / helpers
项目配置层：config.yaml / project_config.yaml
模块配置层：fixture / codegen_profile / Markdown cases
```

迁移时先通过项目配置层和模块配置层适配，不要直接改框架层。

## 八、建立模块 fixture 和 profile

每个模块至少准备：

```text
test_workspace/tests/fixtures/{module}.py
test_workspace/tests/fixtures/codegen_profile_{module}.md
```

fixture 负责把“测试能力”封装成可调用对象：

- 读取服务地址和环境变量。
- 调用公开 HTTP/gRPC API。
- 准备和清理测试状态。
- 提供查询副作用的 helper。
- 在必要环境变量缺失时明确失败，不静默回退到其他服务。

profile 负责告诉 codegen 这批 Markdown 用例如何生成：

- `module_type`
- `extra_imports`
- `request_overrides`
- `assertion_rules`
- `case_flows`
- `case_bodies`

生成路线优先级建议：

1. 默认 HTTP/gRPC 模板：适合单请求、规则稳定的模块。
2. `assertion_rules`：适合请求流程标准但断言需要模板化的模块。
3. `case_flows`：适合稳定多步骤流程。
4. `case_bodies`：只保留给并发、进程、mock、文件生命周期等复杂场景。

`case_bodies` 不是失败，但长期无理由的大量 `case_bodies` 需要进入治理。能用线性 `call / assign / assert / comment` 表达的流程，优先沉淀为 `case_flows`。

## 九、执行 codegen 门禁

每轮迁移按固定顺序验证：

```bash
aitest codegen --workspace /path/to/your_project/aitest_workspace --all --validate-profile
aitest codegen --workspace /path/to/your_project/aitest_workspace --all --dump-ir
aitest codegen --workspace /path/to/your_project/aitest_workspace --all
aitest codegen --workspace /path/to/your_project/aitest_workspace --all --check
python3 -m pytest /path/to/your_project/aitest_workspace/test_workspace/tests/generated --collect-only -q
```

说明：

- `--validate-profile` 是硬门禁，profile schema 或语义错误必须先修。
- `--dump-ir` 用来观察每条 case 的 strategy、fixture、断言和来源。
- `--check` 在 generated 文件还没生成或 Markdown/profile 已变化时会提示 stale；生成后再次执行应为 up to date。
- collect 阶段只验证 generated pytest 可导入和可收集，不代表真实业务测试通过。

pytest collect 推荐在 workspace 根目录执行：

```bash
cd /path/to/your_project/aitest_workspace
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

如果必须从其他目录执行，需要显式设置：

```bash
PYTHONPATH=/path/to/your_project/aitest_workspace
```

否则可能出现：

```text
ModuleNotFoundError: No module named 'test_workspace'
```

## 十、运行测试和生成报告

服务启动后执行：

```bash
aitest run --workspace /path/to/your_project/aitest_workspace <module>
```

如果测试需要服务地址、账号、token 或 API key，推荐使用本地不提交的 env 文件：

```bash
AITEST_ENV_FILE=/tmp/your-project-test.env aitest run --workspace /path/to/your_project/aitest_workspace <module>
```

`aitest run` 会把 env 文件中的变量注入 pytest 子进程，fixture 和 profile variables 都能读取；报告只记录变量名，不记录变量值。真实 shell 环境变量优先于 env 文件。

报告默认写入：

```text
test_workspace/reports/latest/
test_workspace/reports/runs/{run_id}/
```

核心产物：

- `junit.xml`
- `result.json`
- `report.md`

`aitest run` 会先做 generated freshness check。如果 Markdown/profile 与 generated pytest 不一致，会生成 `BLOCKED_RUN` 报告并停止，不执行过期测试。

## 十一、失败分流

失败后先分流，不要直接改 generated pytest。

| 类型 | 判断方式 | 处理方式 |
|---|---|---|
| 文档问题 | 公开文档未说明、字段不明确、行为缺失 | 补知识库 `[?]` 或找产品确认 |
| 用例问题 | Markdown 断言不可观测、场景不稳定、请求不合法 | 修 Markdown，必要时记录 mismatch |
| profile 问题 | profile gate 报错、case_id 不匹配、flow 引用错误 | 修 `codegen_profile_{module}.md` |
| fixture 问题 | 前置状态没准备好、环境变量缺失、清理不完整 | 修模块 fixture/helper |
| codegen 问题 | IR/renderer 生成错误、重复模式值得沉淀 | 修 codegen 或增加规则，并补测试 |
| 环境问题 | 服务没启动、端口不通、依赖未安装 | 修启动命令或环境配置 |
| 待测系统 bug | 请求和断言都合理，但系统行为不符合契约 | 记录到 `test_workspace/results/` |

禁止为了通过测试而：

- 手改 generated pytest。
- 放宽断言。
- skip 失败用例。
- 伪造响应。
- 把产品 bug 写成测试侧成功。

## 十二、迁移完成标准

一个模块迁移完成至少满足：

```bash
aitest codegen --workspace /path/to/workspace <module> --validate-profile
aitest codegen --workspace /path/to/workspace <module> --dump-ir
aitest codegen --workspace /path/to/workspace <module>
aitest codegen --workspace /path/to/workspace <module> --check
python3 -m pytest /path/to/workspace/test_workspace/tests/generated --collect-only -q
```

如果测试环境可用，还应执行：

```bash
aitest run --workspace /path/to/workspace <module>
```

完成后检查：

- profile errors = 0。
- generated up to date。
- generated pytest 可 collect。
- `UNPARSED ASSERTION` 为 0，或已明确记录无法自动化原因。
- `case_bodies` 有保留理由。
- 待测系统 bug 已记录到 `test_workspace/results/`。
- 重要经验已沉淀到 `TEST_SPEC.md`、profile 或相关文档。

## 十三、相关文档

- [AITest Quickstart](./aitest_quickstart.md)
- [AITest Workflow Guide](./aitest_workflow_guide.md)
- [Codegen Profile Guide](./codegen_profile_guide.md)
- [Codegen Troubleshooting](./codegen_troubleshooting.md)
