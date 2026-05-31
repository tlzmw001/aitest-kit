# AIAutoTest

AI 驱动的自动化测试工具，围绕"文档 → 知识库 → 用例 → codegen → pytest → 报告 → 沉淀"构建可复用测试流程。

## 项目结构

```
coupon_system/          # 内置示例/验证目标：智能优惠券推荐策略服务（FastAPI + gRPC + Redis）
ab_experiment_sdk/      # 内置示例/依赖服务：AB 实验服务与 SDK
docs/                   # 开发文档输入目录（skill 的输入源）
test_workspace/         # 本仓自用测试资产工作区
  knowledge/            #   测试知识库（L0/L1/L2 + TEST_SPEC）
  suites/               #   suite 用例（Markdown + suite.yaml + suite profile）
  targets/              #   target/module registry、fixture、helper、module profile
  generated/            #   codegen 生成的 pytest 文件（编译产物）
  reports/              #   测试执行报告（运行产物，不入库）
  results/              #   待测系统 bug 记录
  plans/                #   方案文档
aitest_kit/             # Python 测试工具库
  templates/            #   包内唯一 project_workspace 模板；模板只维护 agent-neutral skills/ 一份源目录
  codegen/              #   codegen 引擎
aitest_config/          # 项目级配置
  aitest.yaml           #   workspace 路径 + codegen 默认规则
  schemas/              #   JSON Schema
tests/                  # aitest-kit 自身测试
examples/               # 面向用户的示例项目或示例 workspace
plugins/                # Codex plugin 方向的实验和产品化资产
.claude/skills/         # 本仓开发时实际使用的 Claude Code skill，不是 init 模板副本
.codex/skills/          # 本仓开发时实际使用的 Codex skill，不是 init 模板副本
.agents/skills/         # 本仓开发时实际使用的 agents workflow skill，不是 init 模板副本
```

新链路优先使用 `test_workspace/targets/`、`test_workspace/suites/`、`test_workspace/generated/`、`test_workspace/reports/`；历史兼容目录可能仍存在，例如 `test_workspace/cases/`、`test_workspace/tests/`、`test_workspace/backups/`。

## 常用命令

```bash
# 安装依赖
pip install -e ".[dev,server]"

# 启动待测系统
python -m coupon_system.main

# 运行单测
pytest tests/

# 执行 generated 测试并生成结构化报告
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --case-id TC-XXX-001
python3 -m aitest_kit.cli report --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli registry register-suite --target <target> --module <module> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli task create --name <task_name> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli run --target <target> --module <module>
python3 -m aitest_kit.cli report --target <target> --module <module>
python3 -m aitest_kit.cli run --target <target>
python3 -m aitest_kit.cli report --target <target>
python3 -m aitest_kit.cli run --all
python3 -m aitest_kit.cli report --all

# 初始化并操作独立新项目 workspace
python3 -m aitest_kit.cli init --target /path/to/aitest_workspace
python3 -m aitest_kit.cli doctor --workspace /path/to/aitest_workspace
python3 -m aitest_kit.cli codegen --workspace /path/to/aitest_workspace --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
python3 -m aitest_kit.cli run --workspace /path/to/aitest_workspace --target <target>
python3 -m aitest_kit.cli upgrade --check --workspace /path/to/aitest_workspace
python3 -m aitest_kit.cli upgrade --apply --workspace /path/to/aitest_workspace
```

完整 codegen/run/report 选项见 `aitest <subcommand> --help`。

## 技术栈

- Python 3.9+
- FastAPI + gRPC（待测系统）
- httpx + grpcio（测试客户端）
- Redis（数据层）

## 测试飞轮工作流

九个核心 skill 构成一条闭环流水线。仓库本地可能还有 `project-learning` 等辅助 skill，但它们不属于默认测试飞轮：

```
── 设计阶段 ──

docs/（开发文档）
  ↓
doc-review  ── 审查文档完整性，输出缺口清单
  ↓
doc-gen     ── 从源码补全缺失的设计文档（可选，文档不足时用）
  ↓
knowledge-build ── 从文档构建/更新测试知识库（L0/L1/L2）
  ↓
test-design ── 基于知识库 + TEST_SPEC 生成测试用例（Markdown）
  ↓
人工评审用例
  ├─ 通过：进入 test-scaffold / test-codegen
  └─ 有问题：test-fix 修正用例，沉淀经验到 TEST_SPEC 和相关 skill

── 脚手架阶段 ──

test-scaffold ── 构建或增量修正 target/module fixture、helper、module profile
  ↓
基于具体 suite 用例补 suite profile
  ↓
验证：validate-profile / dump-ir / codegen --check / collect

── 代码生成阶段 ──

test-codegen ── Markdown 用例 → pytest 代码
  ↓
validate-profile / dump-ir / check
  ↓
生成 generated pytest
  ↓
collect 验证

── 执行报告阶段 ──

aitest run
  ↓
freshness check
  ↓
pytest 执行
  ↓
result.json + report.md
  ↓
失败时分流：
  ├─ 用例问题 → test-fix → 重新 codegen
  ├─ fixture/codegen 问题 → test-scaffold 或更新 fixture/profile/emitter → 重新 codegen
  └─ 待测系统问题 → 记录到 test_workspace/results/

── 维护与沉淀 ──

test-maintain ── 诊断 workspace 状态，判断断裂层，路由到对应 skill 或 CLI
  ↓
测试稳定通过且出现重复模式
  ↓
emitter-build ── 分析是否值得沉淀；人工 review 后再更新 profile / assertion_rules / fixture helper / emitter 规则
```

### test-codegen 行为规则

codegen 链路：suite context 加载 → profile 硬门禁 → parser 解析 Markdown → Case IR planner → emitter 渲染 → 生成后验证。agent 需要遵守的规则：

- 生成策略优先级固定：`skipped` > `custom_case_body` > `structured_case_flow` > `manual` > `default_grpc` > `default_http`
- 断言匹配优先级：profile assertion_rules > `aitest.yaml` builtin_assertion_rules > named_templates
- profile 硬门禁有 ERROR 时不进入 IR/emitter，先修 profile
- UNPARSED 断言应回写到 Markdown/profile/assertion_rules/emitter，不手改 generated
- 测试稳定通过后调用 `/emitter-build`，人工 review 后再沉淀规则

### 使用指引

- **首次接入新项目**：`aitest init --target <aitest_workspace>` → `/doc-review` → `/doc-gen`（按需）→ `/knowledge-build` → `/test-design` → `/test-scaffold` → `/test-codegen`
- **需求迭代**：新文档放入 `docs/` → `/knowledge-build`（增量更新）→ `/test-design`（增量生成）
- **新模块缺 fixture/profile**：`/test-scaffold`（构建 target/module fixture + module profile，再接 suite profile）
- **现有模块新增 suite，且 fixture/helper/module profile 已能支撑用例动作**：`/test-codegen --suite-file <suite.yaml>`；如果需要新增 fixture 方法、环境变量、helper 或 profile 能力，回到 `/test-scaffold`
- **用例出错**：`/test-fix`（修用例 + 记 TEST_SPEC 陷阱 + 更新 skill）
- **生成 pytest**：`/test-codegen --suite-file <suite.yaml>`
- **执行并报告**：`aitest run --suite-file <suite.yaml>`，默认排除 manual；需要时加 `--include-manual`。单 case 调试用 `--case-id <TC-ID>`；模块、target、全量回归用 `--target <target> --module <module>`、`--target <target>` 或 `--all`
- **不确定当前问题属于哪一层**：先用 `/test-maintain` 分诊，再进入对应 skill 或 CLI
- **只想看文档质量**：`/doc-review`

### 关键约定

- 测试知识库是测试设计的主输入，不要长期绕过知识层直接写 pytest
- Markdown 用例是核心设计产物；如果后续存在 codegen 或 pytest 生成环节，应把 Markdown 视为源数据
- TEST_SPEC 是所有 skill 的行为准则，经验教训统一沉淀在此
- workspace 模板只有一个来源：`aitest_kit/templates/project_workspace/`；模板 skill 只维护 `aitest_kit/templates/project_workspace/skills/` 一份源，不维护 `.codex/.claude/.agents` 三份副本
- 配置文件写法以 `aitest_config/refs/config-files.md` 为准；新建或修改 target/module/suite/profile/task/env 配置前先确认字段归属
- 用例存放在 suite 目录，用 `suite.yaml` 绑定 target/module
- 单 suite 可直接通过 `--suite-file` 执行；进入 `--module`、`--target`、`--all` 聚合前，必须用 `aitest registry register-suite` 注册到对应 module；手写 `registered_suites` 时推荐直接写 suite manifest 路径字符串，需要 `status` 时再写 `{suite, manifest, status}` mapping
- 模块 fixture 按 target/module 拆分到 `test_workspace/targets/{target}/fixtures/{module}.py`
- module profile 存放在 `test_workspace/targets/{target}/profiles/profile_{module}.md`，只放 L1 稳定能力；suite profile 跟随用例目录，命名为 `profile_{suite}_suite.md`，具体 TC-ID 绑定的 `case_flows`、`case_bodies`、`request_overrides`、`case_fixtures` 应优先放 suite profile
- generated pytest 是编译产物；如果需要手修，先判断应回写到 suite profile、module profile、fixture/helper 还是 emitter
- 测试执行报告写入 `test_workspace/reports/`，属于运行产物，不提交；待测系统 bug 仍记录到 `test_workspace/results/`
- 项目结构或流程发生变更时，检查是否需要同步更新 `CLAUDE.md` 和 `README.md`，并询问用户是否需要更新 `docs/usebook/` 下的文档

### test-report 行为规则

- `aitest run` 先做 env file 加载和 generated freshness check，不通过则 `BLOCKED_RUN`，pytest 不执行
- 默认追加 `-m "not manual"`；`--include-manual` 才执行 manual 用例
- `result.json` 是结构化事实源，`report.md` 是阅读版；`aitest report` 只重渲染不重新执行
- 失败分类包括 `PRECONDITION_MISSING`、`ENVIRONMENT_ERROR`、`TEST_SCAFFOLD_ERROR`、`CODEGEN_ERROR`、`ASSERTION_FAILURE`、`TEARDOWN_ERROR`、`UNKNOWN`；断言失败不自动等于待测系统 bug

## 测试执行注意事项

### 部署拓扑先行

设计 fixture 前必须确认服务的实际部署模式：
- 确认 target 的 base URL、认证方式、管理 API、上游依赖、数据存储和可清理资源
- 确认服务间调用边界，例如本地 SDK、远程 HTTP/gRPC 服务、数据库、缓存、消息队列或第三方上游
- 环境变量真实值来自 shell、CI secrets、当前工作目录 `.env` 或 `AITEST_ENV_FILE`；profile、Markdown 和报告说明只记录变量名，不记录变量值
- 优先用运行时 API 或管理 API 准备测试状态；高风险资源创建、付费资源、真实账号和不可逆数据变更必须先让用户确认

### 运行前置条件

- fixture 中必需 env 使用 `aitest_kit.runtime_variables.require_env()`，不要手写 `os.environ.get(...)` + `pytest.fail(...)`，这样报告才能稳定归类为 `PRECONDITION_MISSING`
- case-scoped 变量优先写到 suite profile 的 `variables.cases`；模块级默认变量写到 module profile 或 suite profile 的 `variables.defaults`
- 缺少 env、token、测试账号或测试资源时，不要构造空 header、空 token 或假数据继续执行；应 fail-fast，让报告暴露缺失的前置条件

### HTTP fixture 注意事项

httpx 0.28+ 会自动读取 macOS 系统代理，`proxy=None` 无效。fixture/helper 使用 `httpx` 访问本地或测试环境 HTTP 服务时，默认显式指定 transport：
```python
httpx.Client(transport=httpx.HTTPTransport())
```

如果测试确实需要代理，必须显式配置并在 fixture/profile 中说明，不能依赖系统代理的隐式行为。

### 失败处理

- 先看 `result.json` 和 `report.md`，不要只看终端红色失败
- `PRECONDITION_MISSING`：补 env、token、测试账号或运行前置；不要把它当作待测系统 bug
- `ENVIRONMENT_ERROR`：检查服务启动、端口、上游依赖、网络和超时
- `TEST_SCAFFOLD_ERROR`：回到 `test-scaffold` 修 fixture/helper/profile
- `CODEGEN_ERROR`：修 `aitest_kit`、emitter、profile 渲染或生成链路，并补回归测试
- `ASSERTION_FAILURE`：人工复核契约、用例、fixture 状态和实际响应；断言失败不自动等于待测系统 bug
- 人工确认是用例问题后，使用 `test-fix` 修 Markdown 或 mismatch
- 人工确认是待测系统 bug 后，记录到 `test_workspace/results/`，保留复现命令、实际结果和期望结果
- 不为通过测试而放宽断言、skip 失败用例或伪造响应
- 偶发失败先补可观测性，再修逻辑

## codegen 可移植架构

codegen 的可移植性来自分层归属。迁移新项目时，优先改 workspace/target/module/suite/task 配置；只有确认框架能力缺失时才改 `aitest_kit`。

```
┌─────────────────────────────────────────────────────┐
│  框架层（发布包内，迁移项目不改）                        │
│  - codegen: parser / Case IR / planner / emitter    │
│  - report: run / collector / classifier / renderer  │
│  - registry: target/module/suite/task loader        │
│  - templates/project_workspace: init 模板和 skills   │
│  - profile validator (profile_validator.py)         │
│  - JSON Schema (codegen_profile.schema.json)        │
├─────────────────────────────────────────────────────┤
│  workspace 默认配置层（少量全局默认）                   │
│  - aitest_config/aitest.yaml                        │
│  - aitest_config/refs/                              │
│  - paths / module_type / default_request / rules    │
├─────────────────────────────────────────────────────┤
│  target registry 层（一个待测系统一份）                 │
│  - targets/{target}/target.yaml                     │
│  - source_root / docs / knowledge_refs / defaults   │
├─────────────────────────────────────────────────────┤
│  module 能力层（一个业务模块一份）                      │
│  - modules/{module}.yaml                            │
│  - fixtures/{module}.py / helpers/                  │
│  - profiles/profile_{module}.md                     │
├─────────────────────────────────────────────────────┤
│  suite 用例层（一个需求批次/用例集一份）                 │
│  - suites/{target}/{suite}/suite.yaml               │
│  - Markdown case files                              │
│  - profile_{suite}_suite.md                         │
├─────────────────────────────────────────────────────┤
│  task / selector 执行层                              │
│  - tasks/{task}.yaml                                │
│  - registered_suites                                │
│  - --suite-file / --task-file / --target / --all    │
├─────────────────────────────────────────────────────┤
│  运行输入层                                           │
│  - shell env / CI secrets / AITEST_ENV_FILE          │
│  - profile variables 只声明 env 名，不保存值          │
└─────────────────────────────────────────────────────┘
```

### 首次接入新项目的 codegen 配置

1. 先执行 `aitest init --target <aitest_workspace>` 创建独立 workspace，不直接复用本仓 `test_workspace/`
2. 建立 `test_workspace/targets/{target}/target.yaml`，配置 target 默认目录和知识库引用
3. 建立 `modules/{module}.yaml`，注册 fixture 文件、默认 fixture、module profile 和 module_type
4. 建立 `fixtures/{module}.py`、必要的 `helpers/` 和 `profiles/profile_{module}.md`，沉淀模块级稳定动作与断言能力
5. 准备一份 smoke suite：`suite.yaml` + Markdown 用例 + `profile_{suite}_suite.md`
6. 依次验证：`--validate-profile` → `--dump-ir` → 生成 → `--check` → `aitest run -- --collect-only -q`

workspace 模板只有一个来源：`aitest_kit/templates/project_workspace/`。模板同时初始化 `AGENTS.md`、`CLAUDE.md` 和 agent-neutral `skills/`；不要维护顶层 `templates/project_workspace/` 镜像。

### module_type 分类

`module_type` 是模块能力契约，在 `modules/{module}.yaml` 中声明。名称来自 `aitest_config/aitest.yaml.codegen.module_types`。选择建议：

- 默认 HTTP/gRPC 路线足够时用 `standard_http` 或 `standard_recommend`
- 多端点、多步骤、fixture Client 模块用 `multi_endpoint`
- 进程隔离、mock、服务实例管理等用更具体的类型

缺少 `module_type` 产生 W502 warning；类型未定义或 `requires` 不满足产生 E504 error。

### 生成策略与规则层

`assertion_rules`、`request_overrides`、`variables` 是规则层输入，不是独立 strategy。`case_flow` 支持 `call`、`assign`、`assert`、`comment`；复杂 `if/for/try/with` 应封装进 fixture/helper 或用 `case_bodies` 逃生。

晋升方向：`case_bodies` → `case_flows` / fixture helper → assertion_rules / builtin rules。同一 case_id 不允许同时出现在 `case_bodies` 和 `case_flows`。

### 诊断分层

诊断码按前缀定位断裂层：`E001` parser、`E2xx` planner、`E3xx` renderer、`E5xx` profile gate、`E6xx` suite context、`E7xx` registry。完整诊断码表见 `docs/usebook/codegen_troubleshooting.md`。

排查顺序：`aitest doctor` → `--validate-profile` → `--dump-ir` → `--check` → `aitest run`。运行报告里的 `PRECONDITION_MISSING` 等是 failure classification，不是 codegen diagnostic code。

### Markdown 用例格式规范

格式规范和示例见 `aitest_config/refs/case-format.md`。关键规则：

- `json` 代码块必须是严格合法 JSON，禁止 `{{var}}` 占位符
- Markdown 描述场景和断言意图，不负责执行接线；请求差异写 `request_overrides`，多步骤写 `case_flows`
- 不要把 token、密钥、真实账号值写进 Markdown；只写环境变量名

### 待测系统 bug 记录

测试发现的待测系统 bug 记录到 `test_workspace/results/`，不跳过、不放宽断言、不伪造成功响应。等待系统修复后重新执行验证。

### 如何使用本地 Skill

当用户明确指定某个本地 skill，或当前任务与其中某个 skill 明显对应时，应按本地 SOP 执行：

1. Claude Code 协作优先读取 `.claude/skills/{skill}/SKILL.md`；Codex 使用 `.codex/skills/{skill}/SKILL.md`，agents workflow 使用 `.agents/skills/{skill}/SKILL.md`。
2. 新项目 workspace 默认只提供 agent-neutral 的 `skills/` 源目录；用户应根据实际 agent 复制到 `.codex/skills/`、`.claude/skills/` 或 `.agents/skills/`。
3. 执行时保持输出与本仓库测试飞轮一致。
4. 修改本仓运行中的 skill 时，检查 `.claude/skills/`、`.codex/skills/`、`.agents/skills/` 是否需要同步。
5. 修改 init 模板 skill 时，只更新 `aitest_kit/templates/project_workspace/skills/`；不要在模板里维护 `.codex/.claude/.agents` 三份副本。

核心 skill：

- `doc-review`：审查开发文档完整性。
- `doc-gen`：从源码和现有文档补全测试设计输入。
- `knowledge-build`：构建或更新测试知识库。
- `test-design`：生成 Markdown 测试用例。
- `test-scaffold`：构建 target/module fixture、helper、module profile 和 suite profile。
- `test-codegen`：从 Markdown/profile 生成 pytest。
- `test-fix`：修正用例问题并沉淀经验。
- `test-maintain`：诊断 workspace 状态，定位断裂层并路由到正确 skill 或 CLI。
- `emitter-build`：从已验证 pytest 提取确定性模板。

### 文档同步约定

项目结构、流程、CLI、codegen 架构或测试执行方式发生变更时，按影响范围检查文档，不要求无关文档机械同步。

| 变化类型 | 必查文档 |
|---|---|
| 协作规则、仓库结构、AI 工作边界 | `AGENTS.md`、`CLAUDE.md` |
| 安装、发布、CLI 入口、迁移、长期工作流 | `README.md`、`README.en.md`、`docs/usebook/aitest_getting_started.md` |
| 配置字段、字段归属、target/module/suite/task/env 写法 | `aitest_config/refs/config-files.md`、`aitest_kit/templates/project_workspace/aitest_config/refs/config-files.md` |
| Markdown 用例格式 | `aitest_config/refs/case-format.md`、`aitest_kit/templates/project_workspace/aitest_config/refs/case-format.md` |
| profile、schema、codegen 规则、排障方式 | `docs/usebook/codegen_profile_guide.md`、`docs/usebook/codegen_troubleshooting.md`、`aitest_config/schemas/`、相关 skill |
| run/report 语义、失败分类、报告目录 | `docs/usebook/aitest_getting_started.md`、`test-maintain` / `test-codegen` skill |
| init 模板内容 | `aitest_kit/templates/project_workspace/README.md`、`AGENTS.md`、`CLAUDE.md`、`skills/README.md` |
| skill 行为 | 本仓 `.codex/skills/`、`.claude/skills/`、`.agents/skills/`；模板 skill 只改 `aitest_kit/templates/project_workspace/skills/` |

`docs/usebook/lessons/` 是交互式学习笔记，不作为发布同步必改项。不确定是否要同步用户手册时，先说明影响范围，再由用户决定。
