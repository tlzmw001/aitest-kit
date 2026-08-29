# AITest Getting Started

本文面向第一次把 `aitest-kit` 接入新项目的用户，同时也作为长期协作的参考手册。

核心原则：

```text
AI 负责探索未知，代码负责稳定重复。
```

AI 读文档、理解系统、设计用例、解释失败、沉淀规则；`aitest-kit` 负责 Markdown 解析、profile 校验、Case IR 规划、pytest 生成、freshness check、执行和报告。

## 一、快速上手

### 安装

```bash
python3 -m pip install -U aitest-kit
```

找不到 `aitest` 命令时用模块入口：

```bash
python3 -m aitest_kit.cli --help
```

### 初始化 workspace

```bash
cd /path/to/your_project
aitest init --target ./aitest_workspace
cd ./aitest_workspace
```

初始化后的目录：

```text
docs/                  # 放公开 API 文档、设计文档、OpenAPI/proto 等
aitest_config/          # 项目配置、codegen 配置、schema、refs
test_workspace/         # 知识库、用例、Module Harness、profile、generated、报告
skills/                 # agent-neutral AI skills，按需复制到 .codex/.claude/.agents
AGENTS.md / CLAUDE.md   # AI 协作说明
```

从 workspace 外执行 CLI 时加 `--workspace`：

```bash
aitest doctor --workspace /path/to/aitest_workspace
```

### 体检

```bash
aitest doctor
```

刚初始化时没有模块是正常的。下一步把文档放入 `docs/`，然后让 AI 按 skills 走完整流程：

```text
doc-review -> knowledge-build -> test-design -> test-scaffold -> test-codegen -> aitest run
```

建议第一轮只选一个小模块或一条主链路，不要一开始覆盖整个系统。

### 使用本地 Console

Console MVP 是现有确定性 CLI 的本地控制面，不复制 registry、Profile Gate、codegen 或报告
逻辑。正式 wheel 内置编译后的 Vue 前端；安装用户不需要 Node.js，也不需要进入 AITest 源码目录：

```bash
python3 -m pip install "aitest-kit[server]"
AITEST_CONSOLE_PORT=<本地端口> aitest console --workspace /path/to/aitest_workspace
```

源码开发者使用 Node.js 22.18+；修改 Vue 后运行 `npm --prefix console_web run build`；构建结果写入
`aitest_kit/console/web/`，随后进入 wheel。`--workspace` 可以是任意已初始化目录。界面选择
未初始化目录时，打开操作只返回状态，不写文件；用户明确点击“初始化并打开”后才调用既有
`aitest init` 模板逻辑，而且不使用 force。模板冲突或部分初始化结构会停止并要求人工检查。
省略 `--workspace` 时，Console 会先进入空态，用户可直接在工作台选择或初始化目录。

`aitest console` 只允许 loopback IP。每次启动生成临时 Console session token，浏览器通过该
token 调用本地 API。打开 workspace 只读取结构和文件，不执行项目 Python 代码；validate、
codegen 和 run 必须由用户显式发起。

环境页可以由用户显式创建或编辑 workspace `.env`、当前 `AITEST_ENV_FILE` 和 task
`env_files`。敏感值默认隐藏，外部 env 文件需要逐文件授权。Console 不把 env 值写入
localStorage；任务输出会对 Console 已知的敏感值做脱敏，测试资产仍不得主动打印凭证。
Console 也不会自动修改 `.gitignore`。

源码 checkout 安装 Pi Worker 依赖后，可从主导航“Agent”创建本地 session。approval 模式下，
write/edit、Shell 和外部目录请求由页面内审批卡处理；write/edit 可以查看 Monaco Diff。
full_trust 会继承 Console 进程的本地权限，读取内容可能进入模型上下文，因此每次创建都必须
针对当前 workspace 明确确认。页面刷新会使用 `after_seq` 恢复当前 Console 进程内保存的事件；
Console 或 Pi Worker 进程重启后的 session 恢复尚未提供。

## 二、迁移原则

### 首轮按黑盒边界执行

新项目首轮只使用公开设计文档、API 定义、配置 schema、示例请求/响应和可执行 API 行为作为规则来源。不从目标系统源码推断业务规则。源码可在后续灰盒补文档阶段使用，但必须记录边界切换。

### 框架层不随项目迁移改动

迁移新项目时，优先改 workspace 配置：`aitest.yaml`、`target.yaml`、canonical module package、suite profile 和 suite。不要为适配单个项目修改 parser、planner、renderer 或 emitter engine。

### workspace 模板只有一个来源

`aitest init` 的模板源是 `aitest_kit/templates/project_workspace/`。不要新建镜像模板。

## 三、完整迁移步骤

### 1. 准备文档

把公开文档放入 `docs/`，至少覆盖：

- 服务用途和主要模块
- HTTP/gRPC 入口和请求/响应字段
- 错误码和错误响应
- 业务规则和优先级
- 可观测状态：查询接口、日志、指标、存储 key 等
- 测试环境如何访问服务：base URL、端口、环境变量

文档缺失的信息在知识库标 `[?]`，不猜。

### 2. 构建测试知识库

使用 `knowledge-build` 从 `docs/` 构建知识库：

- L0：系统架构和模块索引
- L1：模块当前完整行为
- L2：需求变更和测试重点
- `TEST_SPEC.md`：跨模块测试准则和历史陷阱

知识库是测试设计的主输入，不要绕过知识库直接写 pytest。

### 3. 设计 Markdown 用例

推荐按 suite 组织用例：

```text
test_workspace/suites/{target}/{suite}/suite.yaml
test_workspace/suites/{target}/{suite}/business.md
test_workspace/suites/{target}/{suite}/profile_{suite}_suite.md
```

`suite.yaml` 绑定 target/module 和 case_files。Markdown 用例由 `/test-design` 生成或修订，人工 review 后进入 codegen。

格式要求：

- `json` 代码块必须是严格合法 JSON，禁止 `{{var}}` 占位符
- 基础请求体必须是可执行默认值
- case 级差异写在 profile 的 `requests`、`variables` 或 `case_flows` 中

### 4. 补充项目配置

`aitest_config/aitest.yaml` 是 workspace 适配入口，决定默认 API 路径、调用函数、断言映射、module_type 和内置断言规则。

分层：

```text
框架层：parser / planner / renderer / CLI
项目配置层：aitest.yaml
target/module/suite 层：target.yaml / canonical module package / target helper / suite profile / suite
```

迁移时先通过项目配置层和模块配置层适配。

### 5. 建立 canonical Module Harness

每个模块至少准备：

```text
test_workspace/targets/{target}/modules/{module}/
├── module.yaml
├── profile.md
├── fixture.py
└── harness.py
```

`harness.py` 定义 `{Module}Harness`，封装该模块的公开 API、状态准备、查询、清理和复杂控制逻辑。`fixture.py` 只负责 pytest 生命周期与依赖装配，公开 fixture 固定为 `setup_{module}`，直接返回或 yield `{Module}Harness`。必需环境变量缺失时应明确失败，不静默回退。

module profile `profile.md` 放 L1 稳定的变量默认值和断言规则；`module_type` 只写在 `module.yaml`。suite profile 放 TC-ID 绑定的 `variables`、`requests`、`structured_assertions`、`case_flows`、`case_bodies`。codegen 自动把 `setup_{module}` 注入 generated pytest，并固定绑定为 `harness`；flow 不再配置 fixture/object。

单模块能力留在 module package。只有同一 target 内至少两个 module 已经实际复用的纯技术适配才放到 `test_workspace/targets/{target}/helpers/`；不建立 `test_workspace/helpers/`。

详细字段说明见 [Profile Guide](./codegen_profile_guide.md)。

### 6. codegen 门禁

按固定顺序验证：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

- `--validate-profile` 是硬门禁，ERROR 必须先修。
- `--dump-ir` 观察每条 case 的 strategy、Harness 绑定和断言来源。
- `--check` 确认 generated 与 Markdown/profile 同步。
- collect 只验证可导入和可收集，不代表真实测试通过。

完成 suite 注册后可用更大范围验证：

```bash
aitest codegen --target <target> --module <module> --check
aitest run --target <target> --module <module> -- --collect-only -q
```

### 7. 运行测试和报告

```bash
AITEST_ENV_FILE=/tmp/your-project-test.env aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

`aitest run` 会先做 freshness check，Markdown/profile 变了但 generated 没更新会生成 `BLOCKED_RUN` 并停止。env 文件变量注入 pytest 子进程；报告只记录变量名，不记录变量值。

需要把运行时请求/响应留给人工排查时，加 `--capture`：

```bash
AITEST_ENV_FILE=/tmp/your-project-test.env \
  aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --capture
```

capture 写入当前 run 目录下的 `capture.jsonl`；task、module、target 和 `--all` 聚合运行写入聚合 run 目录。框架只自动捕获默认 HTTP 用例，`case_flow`、`case_body`、gRPC、SDK 或特殊 Harness capability 不自动捕获，用户可在 Harness 或 target helper 中调用 `aitest_kit.helpers.capture.capture_io()`。在 generated 测试函数体内调用时，`capture_io()` 可自动归因到当前 case；显式传入 `case_id` 仍然有效。pytest fixture setup/teardown 阶段不在该 context 内。capture 不自动脱敏，敏感字段应在 Harness 中处理后再写入。

## 四、失败分流

失败后先分流，不直接改 generated pytest。

| 类型 | 判断方式 | 处理方式 |
|---|---|---|
| 文档问题 | 公开文档未说明、字段不明确 | 补知识库 `[?]` 或找产品确认 |
| 用例问题 | 断言不可观测、场景不稳定 | 修 Markdown，必要时记录 mismatch |
| profile 问题 | profile gate 报错、case_id 不匹配 | 修 profile |
| Harness 问题 | 前置状态没准备好、环境变量缺失、capability 实现错误 | 修 module package 或 target helper |
| codegen 问题 | IR/renderer 生成错误 | 修 codegen 并补测试 |
| 环境问题 | 服务没启动、端口不通 | 修启动命令或环境配置 |
| 待测系统 bug | 请求和断言合理，系统行为不符合契约 | 记录到 `test_workspace/results/` |

禁止为了通过测试而放宽断言、skip 失败用例、伪造响应或手改 generated pytest。

详细错误码和排查步骤见 [Troubleshooting](./codegen_troubleshooting.md)。

## 五、迁移完成标准

一个模块迁移完成至少满足：

- `--validate-profile` errors = 0
- `--check` generated up to date
- `--collect-only` 可收集
- `UNPARSED ASSERTION` 为 0，或已记录无法自动化原因
- `case_bodies` 有保留理由
- 待测系统 bug 已记录到 `test_workspace/results/`
- 重要经验已沉淀到 `TEST_SPEC.md`、profile 或相关文档

## 六、长期维护

### 资产分层

| 层级 | 主要文件 | 职责 |
|---|---|---|
| 公开文档 | `docs/` | 系统公开行为、接口、字段、错误码 |
| 测试知识库 | `test_workspace/knowledge/` | 可测试契约 |
| Markdown 用例 | `test_workspace/suites/` | 人类可 review 的测试设计源文件 |
| Module Harness | `test_workspace/targets/{target}/modules/{module}/` | 模块能力、pytest 装配、setup/cleanup、模块规则 |
| target helper | `test_workspace/targets/{target}/helpers/` | 已证实跨 module 复用的纯技术适配 |
| profile | module package 的 `profile.md` + `profile_*_suite.md` | 稳定规则与 suite 编排配置 |
| generated pytest | `test_workspace/generated/` | 编译产物 |
| report | `test_workspace/reports/` | 测试执行结果 |
| results | `test_workspace/results/` | 已确认的待测系统问题 |

generated pytest 是编译产物。生成结果不对时，应回到对应源头（Markdown、profile、Module Harness、target helper、aitest.yaml）修改，不直接改 generated。

### Skill 路由

| 场景 | 推荐入口 |
|---|---|
| 新系统第一次接入 | `doc-review -> knowledge-build -> test-design -> test-scaffold -> test-codegen` |
| 文档不完整 | `doc-gen` |
| 新模块没有 Module Harness/profile | `test-scaffold` |
| 现有模块新增用例，Harness capability 够用 | `test-codegen` |
| 新增用例但 Harness 缺能力 | `test-scaffold` 增量补，再 `test-codegen` |
| 用例写错或断言不可观测 | `test-fix` |
| 测试失败不知归因 | `aitest run` 看报告，再路由 |
| 重复 case_flow / case_body 太多 | `emitter-build` |
| 不确定走哪个入口 | `test-maintain` |

### Harness / fixture / helper / profile 边界

| 概念 | 职责 | 示例 |
|---|---|---|
| Harness | 面向模块的测试能力 | `harness.login()`、`harness.call_api()`、状态准备和复杂控制流 |
| fixture | pytest 注入和生命周期 | 读取 env、装配 Harness、注册 cleanup |
| target helper | 同一 target 内已证实跨 module 复用的纯技术适配 | HTTP 传输、gRPC 调用、等待轮询 |
| profile | codegen 编排配置 | `variables`、`case_flows`、`case_bodies` |

调用关系：`case_flow -> harness -> target helper（可选） -> target API`。`setup_{module}` 只装配 Harness 和生命周期；case_flow 从固定根对象 `harness` 编排当前用例。不要让 fixture 按 case_id 隐藏用例逻辑，也不要创建 `test_workspace/helpers/`。

### 生成路线选择

| 场景 | 推荐路线 |
|---|---|
| 单接口、固定 HTTP endpoint、只改请求字段 | `default_http` |
| gRPC、SDK、多端点或模块动作库 | Harness capability + `case_flows` |
| 多端点但流程线性、需要保存中间变量 | `case_flows` |
| if/else、for、try/finally 控制流 | 优先封装为 Harness capability；测试函数仍需复杂编排时用 `case_bodies` |
| 进程、mock、临时文件生命周期 | 优先封装为 Harness capability；仍需测试函数编排时用 `case_bodies` |
| 只适合人工观察 | `manual` |
| 可行性存疑 | `skipped` |

推荐演进方向：`case_bodies -> Harness capability + case_flows -> assertion_rules / 默认模板`。大量用例需要 `case_bodies` 时，先检查 Harness 能力边界是否合理。

### 人工 review 清单

AI 生成初稿后，以下判断必须由人 review：

- 知识库是否正确理解业务
- 断言是否可观测
- 用例是否来自明确契约
- Harness 是否按 capability 组织，而不是按 case_id 隐藏逐条用例逻辑
- case_flow 是否保持线性清晰
- case_body 是否有保留理由
- env/resource 是否安全、可脱敏
- report 中的待测系统 bug 是否真的成立

### 反模式

- 直接修改 generated pytest
- 绕过知识库直接从零散文档写 pytest
- fixture 或 Harness 里按 case_id 写死每条用例逻辑和断言
- profile 变成大量 Python 表达式拼接
- 缺 env 或缺测试数据时误判为待测系统 bug
- 为了通过测试而放宽断言、skip 失败或伪造响应
- 用例没有人工 review 就跑真实环境

## 七、升级已有 workspace

```bash
python3 -m pip install -U aitest-kit
aitest upgrade --workspace /path/to/aitest_workspace --check
aitest upgrade --workspace /path/to/aitest_workspace --apply
```

`upgrade` 检查模板哈希：仍等于旧模板的文件安全升级，本地改过的跳过并提示人工 review。不要用 `aitest init --force` 升级已有 workspace。

## 八、常见问题

### 找不到 `aitest`

使用模块入口 `python3 -m aitest_kit.cli --help`，或把 Python 用户脚本目录加入 `PATH`。

### `doctor` 提示没有模块

刚初始化时正常。创建 target/module registry 和 suite 后再跑。

### profile 校验失败

先修 profile。profile gate 是硬门禁，ERROR 时不进入 Case IR 和 emitter。

### generated 过期

重新生成后用 `--check` 确认 up to date。

### 环境变量缺失

Module Harness 装配阶段会报缺少的变量名。通过 shell、CI secret 或 `AITEST_ENV_FILE` 提供，不要放宽断言或 skip。

### pytest collect 找不到 test_workspace

推荐通过 `aitest run --suite-file <suite.yaml> -- --collect-only -q` 执行。直接用 `python -m pytest` 时需要在 workspace 根目录运行，或设置 `PYTHONPATH`。

## 相关文档

- [Profile Guide](./codegen_profile_guide.md) — module/suite profile 编写细节
- [Troubleshooting](./codegen_troubleshooting.md) — codegen 常见问题和排查
