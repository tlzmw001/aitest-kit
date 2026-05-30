# AIAutoTest 协作指南

本文件适用于当前目录及其所有子目录。

它的目标有两层：

1. 说明这个仓库是什么、主要目录做什么、推荐按什么工作流协作
2. 约束 AI 在本仓库中的编码、调试、验证和安全行为

## 项目定位

`AIAutoTest` 是一个 AI 驱动的自动化测试项目，围绕一条稳定的测试飞轮展开：

`开发文档 -> 测试知识库 -> Markdown 用例 -> codegen -> pytest 执行 -> 修正与沉淀`

仓库中同时包含：

- `aitest-kit` 工具代码
- workspace 初始化模板
- AI skills 与协作规则
- 内置示例/验证目标：`coupon_system/`、`ab_experiment_sdk/`
- 本仓自用的测试资产工作区 `test_workspace/`

在这个仓库里协作时，优先遵守这条飞轮，而不是绕过文档、知识库和 Markdown 用例，直接产出零散 pytest。

## 仓库结构

- `coupon_system/`
  待测系统：智能优惠券推荐策略服务，包含 FastAPI、gRPC、Redis 与相关数据层逻辑。

- `ab_experiment_sdk/`
  AB 实验服务与 SDK。默认视为待测/依赖服务，不为测试便利随意修改。

- `docs/`
  开发文档输入目录，通常是文档审查、知识构建、测试设计的起点。

- `test_workspace/`
  AI 生成测试资产的工作目录。新链路优先使用 `targets/`、`suites/`、`generated/`、`reports/`；历史兼容目录可能仍存在，例如 `cases/`、`tests/`、`backups/`。

- `test_workspace/knowledge/`
  测试知识库目录，包含 L0/L1/L2 以及 `TEST_SPEC` 等内容。

- `test_workspace/targets/`
  按目标系统组织 target/module registry、模块 fixture、helper 和 module profile。

- `test_workspace/suites/`
  按目标系统组织独立 suite；suite 通过 `suite.yaml` 绑定 target/module。

- `test_workspace/generated/`
  按目标系统保存 codegen 生成的 pytest 文件，视为编译产物。

- `test_workspace/reports/`
  测试执行报告目录，包含 `result.json`、`report.md` 和 JUnit XML。该目录是运行产物，不入库。

- `test_workspace/results/`
  待测系统 bug、测试发现和执行结果记录。

- `test_workspace/plans/`
  测试方案、规划、spec 与阶段性设计文档目录。

- `aitest_kit/`
  Python 测试工具库，包含 parser、emitter、CLI、HTTP/gRPC 客户端与断言能力。

- `aitest_kit/templates/project_workspace/`
  新项目 workspace 的包内唯一模板源。包含干净 `aitest_config/`、`test_workspace/`、`AGENTS.md`、`CLAUDE.md` 和 agent-neutral `skills/`。模板内只维护 `skills/` 一份源目录，不维护 `.codex/.claude/.agents` 三份副本；不要再新增顶层 `templates/project_workspace/` 镜像。

- `tests/`
  `aitest-kit` 自身的单元测试与集成测试。

- `examples/`
  面向用户的示例项目或示例 workspace。

- `plugins/`
  Codex plugin 方向的实验和产品化资产。

- `aitest_config/`
  项目级配置目录。

- `aitest_config/aitest.yaml`
  统一配置入口，包含 workspace 路径和 codegen 默认规则。

- `.claude/skills/`
  Claude Code Skill 定义。本仓开发时实际使用的 agent skill 目录之一，不是 `aitest init` 模板的三份副本。

- `.codex/skills/`
  Codex 原生本地 skill 定义。Codex 协作时优先使用这里的同名 skill。本仓开发时实际使用的 agent skill 目录之一，不是 `aitest init` 模板的三份副本。

- `.agents/skills/`
  agents 工作流的 skill 定义。本仓开发时实际使用的 agent skill 目录之一，不是 `aitest init` 模板的三份副本。迁移或同步本仓 skill 时，保持 `.claude/skills/`、`.codex/skills/`、`.agents/skills/` 三处语义一致。

## 常用命令

除非用户明确要求别的方式，否则优先使用项目已有命令。

```bash
pip install -e ".[dev,server]"
python -m coupon_system.main
python3 -m aitest_kit.cli init --target /path/to/aitest_workspace
python3 -m aitest_kit.cli doctor --workspace /path/to/aitest_workspace
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --health-report --write-report
python3 -m aitest_kit.cli registry register-suite --target <target> --module <module> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli task create --name <task_name> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --case-id TC-XXX-001
python3 -m aitest_kit.cli report --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli codegen --target <target> --module <module> --check
python3 -m aitest_kit.cli run --target <target> --module <module>
python3 -m aitest_kit.cli report --target <target> --module <module>
python3 -m aitest_kit.cli run --target <target>
python3 -m aitest_kit.cli report --target <target>
python3 -m aitest_kit.cli run --all
python3 -m aitest_kit.cli report --all
python3 -m aitest_kit.cli upgrade --check --workspace /path/to/aitest_workspace
python3 -m aitest_kit.cli upgrade --apply --workspace /path/to/aitest_workspace
python3 -m compileall aitest_kit/codegen
python3 -m pytest test_workspace/generated --collect-only -q
```

完整 codegen/run/report 选项见 `aitest <subcommand> --help`。

## 技术栈

- Python 3.9+
- FastAPI
- gRPC
- Redis
- `httpx`
- `grpcio`
- `pytest`

## 测试飞轮工作流

九个核心 skill 构成一条闭环流水线。仓库本地可能还有 `project-learning` 等辅助 skill，但它们不属于默认测试飞轮。

```text
设计阶段：
docs/
  -> doc-review
  -> doc-gen（按需）
  -> knowledge-build
  -> test-design
  -> 人工评审
     -> 通过：进入 test-scaffold / test-codegen
     -> 有问题：test-fix 修正用例并沉淀经验

脚手架阶段：
test-scaffold
  -> 构建或增量修正 target/module fixture、helper、module profile
  -> 基于具体 suite 用例补 suite profile
  -> 验证：validate-profile / dump-ir / codegen --check / collect

代码生成阶段：
test-codegen
  -> validate-profile / dump-ir / check
  -> 生成 generated pytest
  -> collect 验证

执行报告阶段：
aitest run
  -> freshness check
  -> pytest 执行
  -> result.json + report.md
  -> 失败分流
     -> 用例问题：test-fix -> 重新 codegen
     -> fixture/codegen 问题：test-scaffold 或更新 fixture/profile/emitter -> 重新 codegen
     -> 待测系统问题：记录到 test_workspace/results/

维护与沉淀：
test-maintain
  -> 诊断当前 workspace 状态
  -> 判断是文档、知识库、用例、scaffold、codegen、run/report 哪一层断裂
  -> 路由到对应 skill 或 CLI
测试稳定通过且出现重复模式
  -> emitter-build 分析是否值得沉淀
  -> 人工 review 后再更新 profile / assertion_rules / fixture helper / emitter 规则
```

如果需求发生变化，默认从 `knowledge-build` 重新进入，除非可以明确证明变化非常局部，且不会影响知识层。如果只是 suite profile、fixture、环境变量或生成链路问题，不应重建知识库，应由 `test-maintain` 分诊后进入 `test-scaffold`、`test-codegen` 或 `test-fix`。

## 推荐使用路径

- 首次接入新项目或新模块：
  对新项目先用 `aitest init --target <aitest_workspace>` 创建独立 workspace；从本仓外执行时使用 `--workspace <aitest_workspace>` 运行 `codegen`、`run`、`report`。然后做文档审查，按需补文档，构建知识库，设计 Markdown 测试用例，最后用 `test-scaffold` 构建 fixture、helper、module profile 和 suite profile。

- 新模块缺 fixture/profile：
  使用 `test-scaffold` 构建模块的 fixture、helper、module profile 和必要的 suite profile，验证通过后再进入 `test-codegen`。

- 现有模块新增 suite，且 fixture/helper/module profile 已能支撑用例动作：
  使用 `test-codegen` 生成或刷新 pytest。如果 `test-codegen` 发现需要新增 fixture 方法、环境变量、helper 或 profile 能力，应回到 `test-scaffold`。

- 需求迭代：
  将新文档放入 `docs/`，先增量更新知识库，再增量生成或修订 Markdown 用例。

- 用例出错或质量不稳定：
  优先使用 `test-fix` 修正用例，并把教训沉淀到 `TEST_SPEC`、profile 或相关 workflow 说明里。

- 生成 pytest：
  使用 `test-codegen`，从 Markdown suite 和 profile 生成 `test_workspace/generated/{target}/` 下的 pytest。

- 执行并生成报告：
  使用 `aitest run --suite-file <suite.yaml>`，默认排除 manual 用例；需要执行 manual 时加 `--include-manual`。单 case 调试使用 `--case-id <TC-ID>`。模块、目标系统或全量回归使用 `--target <target> --module <module>`、`--target <target>` 或 `--all`。报告写入 `test_workspace/reports/`，失败反哺清单用于后续 `test-fix` 或 fixture/profile 修正。

- 不确定当前问题属于哪一层：
  先使用 `test-maintain` 做分诊，再进入 `test-design`、`test-scaffold`、`test-codegen`、`test-fix` 或 `emitter-build`。

- 测试全部通过后：
  如果出现重复且稳定的生成模式，使用 `emitter-build` 分析是否值得沉淀；人工 review 后再更新 profile、assertion_rules、fixture helper 或 emitter 规则。

- 只检查文档质量：
  只做 `doc-review`，不强制进入后续流程。

## 项目级关键约定

- 测试知识库是测试设计的主输入。
  除非用户明确要求，否则不要绕过知识层，直接从零散文档写测试用例。

- Markdown 用例是核心设计产物。
  如果后续存在 codegen 或 pytest 生成环节，应把 Markdown 视为源数据。

- `TEST_SPEC` 是共享行为准则。
  重复踩到的坑、边界条件和经验，应统一沉淀到这里，而不是每次重新摸索。

- workspace 模板只有一个来源。
  `aitest_kit/templates/project_workspace/` 是 `aitest init` 使用的唯一模板源；不要维护第二份顶层模板副本。模板 skill 只维护 `aitest_kit/templates/project_workspace/skills/` 一份源，不维护 `.codex/.claude/.agents` 三份副本。

- 配置文件写法以 `aitest_config/refs/config-files.md` 为准。
  新建或修改 `aitest.yaml`、`target.yaml`、`module.yaml`、`suite.yaml`、module profile、suite profile、task 或 env 配置前，先按该手册确认字段归属。

- 测试用例按 suite 组织。
  L2/迭代批次放到任意 suite 目录，并用 `suite.yaml` 声明 `target`、`module`、`suite` 和 `case_files`。suite profile 固定使用 `{suite_dir}/profile_{suite}_suite.md`，不要在 `suite.yaml` 里配置路径。

- suite 注册是聚合执行入口。
  单个 suite 可直接用 `--suite-file` 执行；只有通过 `aitest registry register-suite` 写入 `module.yaml.registered_suites` 的 active suite，才会进入 `--module`、`--target` 和 `--all`。手写 `registered_suites` 时推荐直接写 suite manifest 路径字符串；需要 `status` 时再写 `{suite, manifest, status}` mapping。

- 模块 fixture 按 target/module 拆分。
  模块逻辑放到 `test_workspace/targets/{target}/fixtures/{module}.py`，由 `modules/{module}.yaml` 注册。

- module profile 与 fixture 同目录，suite profile 跟随用例目录。
  `test_workspace/targets/{target}/profiles/profile_{module}.md` 放 L1 稳定能力；`profile_{suite}_suite.md` 放该批用例的 `case_flows/case_bodies/request_overrides`。具体 TC-ID 绑定的 `case_flows`、`case_bodies`、`request_overrides`、`case_fixtures` 应优先放 suite profile，不要塞回 module profile。

- 生成的 pytest 是编译产物。
  优先修改 Markdown 用例、profile、fixture、emitter 或 `aitest.yaml`，再重新生成；不要把生成文件当作长期手写源文件。如果 generated pytest 需要手修，先判断应回写到 suite profile、module profile、fixture/helper 还是 emitter。

- 待测系统 bug 记录到 `test_workspace/results/`。
  不跳过、不放宽断言、不伪造成功响应。等待系统修复后重新执行验证。

- 例行执行报告记录到 `test_workspace/reports/`。
  `results/` 放待测系统 bug 记录，`reports/` 放运行产物，两者不要混用。

## 测试角色边界

AI 的角色是测试工程师，不是被测系统的开发者。

- 默认不修改 `coupon_system/` 和 `ab_experiment_sdk/`；只有用户明确要求修示例目标或验证目标时，才进入对应源码。
- 对外部真实项目同样默认只维护 AITest workspace，不修改业务仓库源码；如果必须改业务代码、测试钩子或部署配置，先记录为可测试性需求，由用户确认后再做。
- 只改测试资产、测试工具和协作流程：`test_workspace/`、`aitest_kit/`、`aitest_config/`、`aitest_kit/templates/project_workspace/skills/`、`.codex/skills/`、`.claude/skills/`、`.agents/skills/`、文档。
- 未经用户明确同意，不修改 `.env`、local env 文件、凭证文件或真实部署配置。
- 不把 token、密码、API key、真实账号、生产数据写入代码、profile、Markdown 用例或报告说明；profile 和 runtime variables 只记录环境变量名，不记录值。
- 通过被测系统已有 API、管理 API、测试环境配置、环境变量、临时文件、磁盘数据文件或可控测试数据来构造测试条件。
- 不自动创建高风险资源，例如真实付费 API key、充值、生产账号、不可逆数据变更，除非用户明确授权。
- 现有接口无法满足测试需求时，不用 `case_body` 或 fixture 伪造系统行为；记录为“测试基础设施需求”或待测系统 bug，交给用户决定是否修改被测系统。
- 不操作 git commit，除非用户明确要求。

## codegen 行为规则

codegen 链路：suite context 加载 → profile 硬门禁 → parser 解析 Markdown → Case IR planner → emitter 渲染 → 生成后验证。agent 需要遵守的规则：

- 生成策略优先级固定：`skipped` > `custom_case_body` > `structured_case_flow` > `manual` > `default_grpc` > `default_http`
- 断言匹配优先级：profile assertion_rules > `aitest.yaml` builtin_assertion_rules > named_templates
- profile 硬门禁有 ERROR 时不进入 IR/emitter，先修 profile
- UNPARSED 断言应回写到 Markdown/profile/assertion_rules/emitter，不手改 generated
- 测试稳定通过后调用 `/emitter-build`，人工 review 后再沉淀规则

## 测试报告行为规则

- `aitest run` 先做 env file 加载和 generated freshness check，不通过则 `BLOCKED_RUN`，pytest 不执行
- 默认追加 `-m "not manual"`；`--include-manual` 才执行 manual 用例
- `result.json` 是结构化事实源，`report.md` 是阅读版；`aitest report` 只重渲染不重新执行
- 失败分类包括 `PRECONDITION_MISSING`、`ENVIRONMENT_ERROR`、`TEST_SCAFFOLD_ERROR`、`CODEGEN_ERROR`、`ASSERTION_FAILURE`、`TEARDOWN_ERROR`、`UNKNOWN`；断言失败不自动等于待测系统 bug

## codegen 可移植架构

codegen 的可移植性来自分层归属：迁移新项目时，优先改 workspace/target/module/suite/task 配置；只有确认框架能力缺失时才改 `aitest_kit`。

```text
框架层（发布包内，迁移项目不改）
  - aitest_kit/codegen/：parser、Case IR、planner、emitter、renderer、profile gate
  - aitest_kit/report/：run、collector、failure classifier、report renderer
  - aitest_kit/registry/：target/module/suite/task registry loader
  - aitest_kit/templates/project_workspace/：init 模板和 neutral skills
  - aitest_config/schemas/：profile JSON Schema
  - 通用 CLI：init / doctor / codegen / run / report / registry / task / upgrade

workspace 默认配置层（少量全局默认）
  - aitest_config/aitest.yaml
  - aitest_config/refs/
  - workspace paths、module_type definitions、default_request.auto_fields、builtin_assertion_rules

target registry 层（一个待测系统一份）
  - test_workspace/targets/{target}/target.yaml
  - source_root、docs、knowledge_refs
  - defaults：module_dir / fixture_dir / helper_dir / profile_dir / suite_dir / generated_dir / reports_dir

module 能力层（一个业务模块一份）
  - test_workspace/targets/{target}/modules/{module}.yaml
  - test_workspace/targets/{target}/fixtures/{module}.py
  - test_workspace/targets/{target}/helpers/
  - test_workspace/targets/{target}/profiles/profile_{module}.md
  - 稳定动作库、默认 fixture、module_type、L1 级稳定断言规则

suite 用例层（一个需求批次/用例集一份）
  - test_workspace/suites/{target}/{suite}/suite.yaml
  - Markdown case files
  - test_workspace/suites/{target}/{suite}/profile_{suite}_suite.md
  - TC-ID 绑定的 case_flows / case_bodies / request_overrides / variables.cases

task / selector 执行层（组合运行）
  - test_workspace/tasks/{task}.yaml
  - module.yaml.registered_suites
  - --suite-file / --task-file / --target / --module / --all

运行输入层（不入库或不含密钥值）
  - shell env
  - CI secrets
  - AITEST_ENV_FILE
  - profile variables 只声明 env 名，不保存 env 值
```

## AI 与代码生成边界

本项目的 codegen 哲学是：AI 负责探索未知和做迁移判断，代码负责稳定、可验证、可重复的生成路径。

- AI 可以做：理解新项目业务、生成初版 Markdown 用例、生成或修正 fixture/helper、module profile、suite profile、解释失败原因、判断已验证重复模式是否值得沉淀、对少量 UNPARSED 给出修复并回写到 Markdown/profile/assertion_rules/emitter。
- 代码必须做：suite/target/task 配置解析、Markdown 解析、profile JSON Schema/语义校验、case_id 对齐、IR strategy 选择、Case IR 生成、default request 合并、assertion_rules 解析、case_flow 渲染、generated freshness check、run/report 结构化结果。
- 普通 codegen、`--check`、`--dump-ir`、`--explain` 和 promotion 分析必须先通过 profile gate；格式错误不进入 IR/emitter。
- 稳定模式按归属沉淀：跨项目或跨 target 默认写 `aitest.yaml`；模块级稳定能力写 module profile、fixture 或 helper；具体 TC-ID 绑定内容写 suite profile；复杂逃生用 `case_bodies`，稳定后用 `emitter-build` 评估是否能晋升为 `case_flows`、fixture helper、assertion_rules 或 builtin rules。
- `case_bodies` 是复杂场景逃生通道，不是默认路线；并发、进程、文件生命周期、mock、Remote SDK 生命周期等复杂控制流可以保留。

## module_type 分类

`module_type` 是模块能力契约，在 `modules/{module}.yaml` 中声明。名称来自 `aitest_config/aitest.yaml.codegen.module_types`。选择建议：

- 默认 HTTP/gRPC 路线足够时用 `standard_http` 或 `standard_recommend`
- 多端点、多步骤、fixture Client 模块用 `multi_endpoint`
- 进程隔离、mock、服务实例管理等用更具体的类型

缺少 `module_type` 产生 W502 warning；类型未定义或 `requires` 不满足产生 E504 error。

## 诊断分层

诊断码按前缀定位断裂层：`E001` parser、`E2xx` planner、`E3xx` renderer、`E5xx` profile gate、`E6xx` suite context、`E7xx` registry。完整诊断码表见 `docs/usebook/codegen_troubleshooting.md`。

排查顺序：`aitest doctor` → `--validate-profile` → `--dump-ir` → `--check` → `aitest run`。运行报告里的 `PRECONDITION_MISSING` 等是 failure classification，不是 codegen diagnostic code。

## Markdown 用例格式规范

格式规范和示例见 `aitest_config/refs/case-format.md`。关键规则：

- `json` 代码块必须是严格合法 JSON，禁止 `{{var}}` 占位符
- Markdown 描述场景和断言意图，不负责执行接线；请求差异写 `request_overrides`，多步骤写 `case_flows`
- 不要把 token、密钥、真实账号值写进 Markdown；只写环境变量名

## 测试执行注意事项

### 部署拓扑先行

设计 fixture 前必须确认服务的实际部署模式：

- 确认 target 的 base URL、认证方式、管理 API、上游依赖、数据存储和可清理资源。
- 确认服务间调用边界，例如本地 SDK、远程 HTTP/gRPC 服务、数据库、缓存、消息队列或第三方上游。
- 环境变量真实值来自 shell、CI secrets、当前工作目录 `.env` 或 `AITEST_ENV_FILE`；profile、Markdown 和报告说明只记录变量名，不记录变量值。
- 优先用运行时 API 或管理 API 准备测试状态；高风险资源创建、付费资源、真实账号和不可逆数据变更必须先让用户确认。

### 运行前置条件

- fixture 中必需 env 使用 `aitest_kit.runtime_variables.require_env()`，不要手写 `os.environ.get(...)` + `pytest.fail(...)`，这样报告才能稳定归类为 `PRECONDITION_MISSING`。
- case-scoped 变量优先写到 suite profile 的 `variables.cases`；模块级默认变量写到 module profile 或 suite profile 的 `variables.defaults`。
- 缺少 env、token、测试账号或测试资源时，不要构造空 header、空 token 或假数据继续执行；应 fail-fast，让报告暴露缺失的前置条件。

### HTTP fixture 注意事项

`httpx` 0.28+ 会自动读取 macOS 系统代理，`proxy=None` 无效。fixture/helper 使用 `httpx` 访问本地或测试环境 HTTP 服务时，默认显式指定 transport：

```python
httpx.Client(transport=httpx.HTTPTransport())
```

如果测试确实需要代理，必须显式配置并在 fixture/profile 中说明，不能依赖系统代理的隐式行为。

### 失败处理

- 先看 `result.json` 和 `report.md`，不要只看终端红色失败。
- `PRECONDITION_MISSING`：补 env、token、测试账号或运行前置；不要把它当作待测系统 bug。
- `ENVIRONMENT_ERROR`：检查服务启动、端口、上游依赖、网络和超时。
- `TEST_SCAFFOLD_ERROR`：回到 `test-scaffold` 修 fixture/helper/profile。
- `CODEGEN_ERROR`：修 `aitest_kit`、emitter、profile 渲染或生成链路，并补回归测试。
- `ASSERTION_FAILURE`：人工复核契约、用例、fixture 状态和实际响应；断言失败不自动等于待测系统 bug。
- 人工确认是用例问题后，使用 `test-fix` 修 Markdown 或 mismatch。
- 人工确认是待测系统 bug 后，记录到 `test_workspace/results/`，保留复现命令、实际结果和期望结果。
- 不为通过测试而放宽断言、skip 失败用例或伪造响应。
- 偶发失败先补可观测性，再修逻辑。

## 如何使用本地 Skill

当用户明确指定某个本地 skill，或当前任务与其中某个 skill 明显对应时，应按以下方式使用：

1. 当前 agent 已安装本地 skill 时，优先读取当前 agent 对应目录：Codex 用 `.codex/skills/{skill}/SKILL.md`，Claude Code 用 `.claude/skills/{skill}/SKILL.md`，agents workflow 用 `.agents/skills/{skill}/SKILL.md`。
2. 新项目 workspace 默认只提供 agent-neutral 的 `skills/` 源目录；用户应根据实际 agent 复制到 `.codex/skills/`、`.claude/skills/` 或 `.agents/skills/`。
3. 执行时保持输出与本仓库测试飞轮一致。
4. 修改本仓运行中的 skill 时，检查 `.claude/skills/`、`.codex/skills/`、`.agents/skills/` 是否需要同步。
5. 修改 init 模板 skill 时，只更新 `aitest_kit/templates/project_workspace/skills/`；不要在模板里维护 `.codex/.claude/.agents` 三份副本。

当前核心 skill：

- `doc-review`：审查开发文档完整性。
- `doc-gen`：从源码和现有文档补全测试设计输入。
- `knowledge-build`：构建或更新测试知识库。
- `test-design`：生成业务用例、边界用例和 mismatch 记录。
- `test-scaffold`：构建 target/module fixture、helper、module profile 和 suite profile。
- `test-codegen`：从 Markdown 用例生成 pytest。
- `test-fix`：修正错误用例并沉淀经验。
- `test-maintain`：诊断 workspace 状态，定位断裂层并路由到正确 skill 或 CLI。
- `emitter-build`：从已验证 pytest 提取确定性 emitter 模板。

## 文档同步约定

项目结构、流程、CLI、codegen 架构或测试执行方式发生变更时，按影响范围检查文档，不要求无关文档机械同步。

| 变化类型 | 必查文档 |
|---|---|
| 协作规则、仓库结构、AI 工作边界 | `AGENTS.md`、`CLAUDE.md` |
| 安装、发布、CLI 入口、3 分钟上手路径 | `README.md`、`README.en.md`、`docs/usebook/aitest_quickstart.md` |
| 新项目迁移、长期工作流、测试飞轮 | `docs/usebook/aitest_migration_guide.md`、`docs/usebook/aitest_workflow_guide.md` |
| 配置字段、字段归属、target/module/suite/task/env 写法 | `aitest_config/refs/config-files.md`、`aitest_kit/templates/project_workspace/aitest_config/refs/config-files.md` |
| Markdown 用例格式 | `aitest_config/refs/case-format.md`、`aitest_kit/templates/project_workspace/aitest_config/refs/case-format.md` |
| profile、schema、codegen 规则、排障方式 | `docs/usebook/codegen_profile_guide.md`、`docs/usebook/codegen_troubleshooting.md`、`aitest_config/schemas/`、相关 skill |
| run/report 语义、失败分类、报告目录 | `docs/usebook/aitest_workflow_guide.md`、`docs/usebook/aitest_quickstart.md`、`test-maintain` / `test-codegen` skill |
| init 模板内容 | `aitest_kit/templates/project_workspace/README.md`、`AGENTS.md`、`CLAUDE.md`、`skills/README.md` |
| skill 行为 | 本仓 `.codex/skills/`、`.claude/skills/`、`.agents/skills/`；模板 skill 只改 `aitest_kit/templates/project_workspace/skills/` |

`docs/usebook/lessons/` 是交互式学习笔记，不作为发布同步必改项。不确定是否要同步用户手册时，先说明影响范围，再由用户决定。
