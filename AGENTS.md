# AIAutoTest 协作指南

本文件适用于当前目录及其所有子目录。

它的目标有两层：

1. 说明这个仓库是什么、主要目录做什么、推荐按什么工作流协作
2. 约束 AI 在本仓库中的编码、调试、验证和安全行为

## 项目定位

`AIAutoTest` 是一个 AI 驱动的自动化测试项目，围绕一条稳定的测试飞轮展开：

`开发文档 -> 测试知识库 -> Markdown 用例 -> codegen -> pytest 执行 -> 修正与沉淀`

仓库中同时包含：

- 待测系统
- AB 实验服务
- 测试工具与 codegen 工具
- AI 生成测试资产的工作区

在这个仓库里协作时，优先遵守这条飞轮，而不是绕过文档、知识库和 Markdown 用例，直接产出零散 pytest。

## 仓库结构

- `coupon_system/`
  待测系统：智能优惠券推荐策略服务，包含 FastAPI、gRPC、Redis 与相关数据层逻辑。

- `ab_experiment_sdk/`
  AB 实验服务与 SDK。默认视为待测/依赖服务，不为测试便利随意修改。

- `docs/`
  开发文档输入目录，通常是文档审查、知识构建、测试设计的起点。

- `test_workspace/`
  AI 生成测试资产的工作目录。

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
  新项目 workspace 的包内唯一模板源。包含干净 `aitest_config/`、`test_workspace/`、`AGENTS.md`、`CLAUDE.md` 和 `.codex/.claude/.agents` 三套 skills。不要再新增顶层 `templates/project_workspace/` 镜像。

- `aitest_config/`
  项目级配置目录。

- `aitest_config/aitest.yaml`
  统一配置入口，包含 workspace 路径和 codegen 默认规则。

- `.claude/skills/`
  Claude Code Skill 定义。

- `.codex/skills/`
  Codex 原生本地 skill 定义。Codex 协作时优先使用这里的同名 skill。

- `.agents/skills/`
  agents 工作流的 skill 定义。迁移或同步 skill 时，保持 `.claude/skills/`、`.codex/skills/`、`.agents/skills/` 三处语义一致。

## 常用命令

除非用户明确要求别的方式，否则优先使用项目已有命令。

```bash
pip install -e ".[dev,server]"
python -m coupon_system.main
python3 -m aitest_kit.cli init --target /path/to/your_project
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --health-report --write-report
python3 -m aitest_kit.cli registry register-suite --target <target> --module <module> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli task create --name <task_name> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --case-id TC-XXX-001
python3 -m aitest_kit.cli codegen --target <target> --module <module> --check
python3 -m aitest_kit.cli run --target <target> --module <module>
python3 -m aitest_kit.cli run --target <target>
python3 -m aitest_kit.cli run --all
python3 -m aitest_kit.cli report
python3 -m compileall aitest_kit/codegen
python3 -m pytest test_workspace/generated --collect-only -q
```

## 技术栈

- Python 3.9+
- FastAPI
- gRPC
- Redis
- `httpx`
- `grpcio`
- `pytest`

## 测试飞轮工作流

八个本地 skill 构成一条闭环流水线，分为设计阶段、脚手架阶段和执行阶段：

```text
设计阶段：
docs/
  -> doc-review
  -> doc-gen（按需）
  -> knowledge-build
  -> test-design
  -> 人工评审
  -> test-fix（修正用例并沉淀经验）

脚手架阶段：
test-scaffold
  -> 从用例 + API 文档构建 fixture + codegen profile
  -> 验证：validate-profile / dump-ir / codegen --check / collect

执行阶段：
test-codegen
  -> pytest 执行
  -> result.json + report.md
  -> 失败分流
     -> 用例问题：test-fix -> 重新 codegen
     -> fixture/codegen 问题：更新 fixture/profile/emitter -> 重新 codegen
     -> 待测系统问题：记录到 test_workspace/results/
  -> 测试全部通过
  -> emitter-build 提取确定性模板
```

如果需求发生变化，默认从 `knowledge-build` 重新进入，除非可以明确证明变化非常局部，且不会影响知识层。

## 推荐使用路径

- 首次接入新项目或新模块：
  对新项目先用 `aitest init --target <project_dir>` 创建独立 workspace；从本仓外执行时使用 `--workspace <project_dir>` 运行 `codegen`、`run`、`report`。然后做文档审查，按需补文档，构建知识库，设计 Markdown 测试用例，最后用 `test-scaffold` 构建 fixture 和 profile。

- 新模块缺 fixture/profile：
  使用 `test-scaffold` 构建模块的 fixture + codegen profile，验证通过后再进入 `test-codegen`。

- 需求迭代：
  将新文档放入 `docs/`，先增量更新知识库，再增量生成或修订 Markdown 用例。

- 用例出错或质量不稳定：
  优先使用 `test-fix` 修正用例，并把教训沉淀到 `TEST_SPEC`、profile 或相关 workflow 说明里。

- 生成 pytest：
  使用 `test-codegen`，从 Markdown suite 和 profile 生成 `test_workspace/generated/{target}/` 下的 pytest。

- 执行并生成报告：
  使用 `aitest run --suite-file <suite.yaml>`，默认排除 manual 用例；需要执行 manual 时加 `--include-manual`。单 case 调试使用 `--case-id <TC-ID>`。模块、目标系统或全量回归使用 `--target <target> --module <module>`、`--target <target>` 或 `--all`。报告写入 `test_workspace/reports/`，失败反哺清单用于后续 `test-fix` 或 fixture/profile 修正。

- 测试全部通过后：
  使用 `emitter-build` 从已验证的 pytest 提取确定性模板，减少后续 AI 补写比例。

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
  `aitest_kit/templates/project_workspace/` 是 `aitest init` 使用的唯一模板源；不要维护第二份顶层模板副本。

- 配置文件写法以 `aitest_config/refs/config-files.md` 为准。
  新建或修改 `aitest.yaml`、`target.yaml`、`module.yaml`、`suite.yaml`、module profile、suite profile、task 或 env 配置前，先按该手册确认字段归属。

- 测试用例按 suite 组织。
  L2/迭代批次放到任意 suite 目录，并用 `suite.yaml` 声明 `target`、`module`、`suite`、`case_files` 和 suite profile。

- suite 注册是聚合执行入口。
  单个 suite 可直接用 `--suite-file` 执行；只有通过 `aitest registry register-suite` 写入 `module.yaml.registered_suites` 的 active suite，才会进入 `--module`、`--target` 和 `--all`。手写 `registered_suites` 时推荐直接写 suite manifest 路径字符串；需要 `status` 时再写 `{suite, manifest, status}` mapping。

- 模块 fixture 按 target/module 拆分。
  模块逻辑放到 `test_workspace/targets/{target}/fixtures/{module}.py`，由 `modules/{module}.yaml` 注册。

- module profile 与 fixture 同目录，suite profile 跟随用例目录。
  `test_workspace/targets/{target}/profiles/profile_{module}.md` 放 L1 稳定能力；`profile_{suite}_suite.md` 放该批用例的 `case_flows/case_bodies/request_overrides`。

- 生成的 pytest 是编译产物。
  优先修改 Markdown 用例、profile、fixture、emitter 或 `aitest.yaml`，再重新生成；不要把生成文件当作长期手写源文件。

- 待测系统 bug 记录到 `test_workspace/results/`。
  不跳过、不放宽断言、不伪造成功响应。等待系统修复后重新执行验证。

- 例行执行报告记录到 `test_workspace/reports/`。
  `results/` 放待测系统 bug 记录，`reports/` 放运行产物，两者不要混用。

## 测试角色边界

AI 的角色是测试工程师，不是被测系统的开发者。

- 默认不修改 `coupon_system/`。
- 默认不修改 `ab_experiment_sdk/`。
- 只改测试资产、测试工具和协作流程：`test_workspace/`、`aitest_kit/`、`aitest_config/`、`.codex/skills/`、`.claude/skills/`、`.agents/skills/`、文档。
- 通过被测系统已有 API、环境变量、磁盘数据文件来构造测试条件。
- 现有接口无法满足测试需求时，记录为“测试基础设施需求”，交给用户决定是否修改被测系统。
- 不操作 git commit，除非用户明确要求。

## codegen 流程细节

`test-codegen` 采用 Case IR + emitter 优先、AI 补写 UNPARSED 的模式：

1. profile 硬门禁。
   普通 codegen、`--check`、`--dump-ir`、`--explain` 和 promotion 分析必须先通过 profile gate；JSON Schema 或语义校验有 ERROR 时不进入 IR/emitter。`--dry-run` 只跑 parser，不要求 profile 通过。

2. parser 解析 Markdown 用例。
   使用 `aitest_kit/codegen/parser.py` 确定性提取结构。JSON 块解析失败时输出诊断信息，例如 E001，不静默返回 `None`。

3. 诊断门控。
   parser 输出有 errors 时，codegen 终止并打印诊断与修复建议，不生成残缺 pytest。

4. 读取项目配置。
   `aitest_config/aitest.yaml` 是统一配置入口；`aitest_kit/workspace_config.py` 和 `aitest_kit/codegen/project_config.py` 是 loader，不是项目配置编辑入口。

5. 读取 profile。
   读取 `suite.yaml`，再临时合并 module profile + suite profile。suite profile 必须以 `_suite.md` 结尾。

6. Case IR planner 生成计划。
   `aitest_kit/codegen/planner.py` 结合 ParseResult、`aitest.yaml` 和 runtime profile 选择 `default_http`、`default_grpc`、`structured_case_flow`、`custom_case_body`、`manual` 或 `skipped`，并记录 source_trace。

7. emitter/IR renderer 生成 pytest。
   `aitest_kit/codegen/emitter.py` 负责装载、诊断和落盘，`aitest_kit/codegen/ir_renderer.py` 负责确定性渲染 `.py`。断言匹配优先级为 `profile assertion_rules > aitest.yaml builtin_assertion_rules > named_templates`。

8. module_type 校验。
   module.yaml/profile 声明的模块类型必须满足 `aitest.yaml` 中该类型的 `requires` 字段；需要 `case_bodies` 的类型可由 `case_bodies` 或 `case_flows` 满足。

9. 生成后验证。
   执行 AST 校验和未定义名检测，避免 `_req` 等关键名缺失。

10. AI 补写 UNPARSED。
   emitter 输出的 `# UNPARSED ASSERTION:` 由 AI 翻译为可执行断言；UNPARSED 为 0 时跳过。

11. 端到端验证。
   运行对应生成测试，必要时运行 `test_workspace/generated/` 的收集检查。

12. 经验沉淀。
    调试经验写入 profile、`TEST_SPEC` 或 skill；测试稳定通过后再使用 `emitter-build` 提取新规则。

日常 codegen 门禁顺序：

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --check
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml>
python3 -m aitest_kit.cli run --suite-file <suite.yaml> -- --collect-only -q
```

常用选择器维度：

```bash
python3 -m aitest_kit.cli codegen --target <target> --module <module> --check
python3 -m aitest_kit.cli run --target <target> --module <module>
python3 -m aitest_kit.cli report --target <target> --module <module>
python3 -m aitest_kit.cli codegen --target <target> --check
python3 -m aitest_kit.cli run --target <target>
python3 -m aitest_kit.cli report --target <target>
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli run --all
python3 -m aitest_kit.cli report --all
```

## 测试报告流程

`aitest run` 是 generated pytest 的结构化执行入口：

1. 默认先执行 generated freshness check，确认 Markdown/profile 与 generated pytest 一致；失败时生成 `BLOCKED_RUN` 报告并停止，不执行过期测试。
2. 默认排除 `@pytest.mark.manual` 用例；报告仍统计 `manual_total`、`manual_executed`、`manual_not_run`。需要执行 manual 时使用 `--include-manual`。
3. collector 用 generated pytest 中的 `__tc_meta__` 与 JUnit XML 结果关联；`__codegen_skipped__` 统计可行性存疑且未生成 pytest 函数的用例。
4. suite 执行输出 `junit.xml`、`result.json`、`report.md` 到 `test_workspace/reports/{target}/{module}/suites/{suite}/` 的 `runs/{run_id}/`，并同步到 `latest/`。case 执行写入 `{target}/{module}/cases/{case_id}/`；module、target、task、all 聚合执行写入对应聚合 bucket，并把 suite unit 明细保存到同一个 run_id 的 `units/` 目录。
5. report 的反哺清单只做规则化初判；断言失败不自动判定为产品 bug，需人工确认后再记录到 `test_workspace/results/`。

## codegen 可移植架构

codegen 管线分三层，换项目时只改配置层，不改框架层：

```text
框架层（换项目不改）
  - parser engine: aitest_kit/codegen/parser.py
  - emitter engine: aitest_kit/codegen/emitter.py
  - CLI: aitest_kit/codegen/cli.py
  - 通用 helpers
  - skill 框架模板

项目配置层（换项目重写，YAML 格式）
  - aitest_config/aitest.yaml
  - target/module registry
  - 项目专属 helper 或 protobuf 封装

模块配置层（每模块一份）
  - test_workspace/targets/{target}/profiles/profile_{module}.md
  - test_workspace/targets/{target}/fixtures/{module}.py

用例批次层（按 L2/迭代批次，可选）
  - suite.yaml
  - profile_{suite}_suite.md
```

## AI 与代码生成边界

本项目的 codegen 哲学是：AI 负责探索未知和做迁移判断，代码负责稳定、可验证、可重复的生成路径。

- AI 可以做：理解新项目业务、生成初版 Markdown/profile、解释失败原因、判断已验证 body 是否值得晋升、补写少量 UNPARSED。
- 代码必须做：Markdown 解析、profile JSON Schema/语义校验、case_id 对齐、IR strategy 选择、请求体合并、默认断言生成、case_flow 渲染、generated freshness check。
- 普通 codegen、`--check`、`--dump-ir`、`--explain` 和 promotion 分析必须先通过 profile gate；格式错误不进入 IR/emitter。
- 稳定模式优先沉淀到 `aitest.yaml`、profile、fixture/helper 或 `case_flows`，不要长期依赖 AI 重写同类 pytest。
- `case_bodies` 是复杂场景逃生通道，不是默认路线；并发、进程、文件生命周期、mock、Remote SDK 生命周期等复杂控制流可以保留。

## module_type 分类

`codegen_profile` 头部必须声明 `module_type`，emitter 根据类型校验必需字段：

| module_type | 适用场景 | 必需字段 |
|-------------|---------|---------|
| `standard_recommend` | 标准推荐接口模块 | 无额外要求 |
| `multi_endpoint` | 多端点服务模块 | `case_bodies` 或 `case_flows` |
| `subprocess_capture` | 需要隔离进程捕获输出 | `case_bodies` 或 `case_flows` |
| `isolated_service` | 需要隔离服务实例 | `case_bodies` 或 `case_flows` |

## Markdown 用例格式规范

Markdown 用例的共享配置格式是框架标准，所有项目统一使用以下 section 名，不要自定义：

~~~markdown
## 共享配置
**接口**：`POST /api/v1/xxx`
**基础请求体（HTTP）**：
```json
{合法 JSON，不允许 {{var}} 占位符}
```
**基础请求体（gRPC）**：
```text
{protobuf 文本格式}
```
**标准前置**：
- 前置条件列表
**通用断言**：`response.code == 0`
**变量定义**：
- `var_name` = 定义
~~~

关键规则：

- `json` 代码块必须是严格合法 JSON，`json.loads` 必须能解析。
- 变化字段用合法默认值填充，例如 `"external": 0`。
- case 级差异通过 `codegen_profile` 的 `request_overrides` 声明。
- 禁止 `{{var}}` 模板占位符出现在 JSON 块中。
- 区分可控输入与系统中间产物：请求参数、Redis 数据、配置文件、实验参数属于可控输入；打分分数、排序位次、校准后分数等 pipeline 计算结果属于中间产物，不能在前置条件或场景变量中假设其具体值。

## 测试执行注意事项

### 部署拓扑先行

设计 fixture 前必须确认服务的实际部署模式：

- 确认 `AB_SERVICE_URL`、`REDIS_URL`、`HTTP_BASE_URL` 等环境变量的实际值。
- 确认服务间调用关系，例如本地 SDK 与远程服务的边界。
- 优先用运行时 API 操作测试条件，例如 AB 白名单 CRUD，而不是启动时环境变量注入。

### httpx 系统代理

`httpx` 0.28+ 会自动读取 macOS 系统代理，`proxy=None` 无效。测试 helper 中必须用显式 transport：

```python
httpx.Client(transport=httpx.HTTPTransport())
```

### 失败处理

- 测试失败时，先判断是用例问题、fixture/codegen 问题、环境问题，还是待测系统 bug。
- 不为通过测试而放宽断言、skip 失败用例或伪造响应。
- 如果确认是待测系统 bug，记录到 `test_workspace/results/`，保留复现命令和实际/期望差异。
- 偶发失败先补可观测性，再修逻辑。

## 如何使用本地 Skill

当用户明确指定某个本地 skill，或当前任务与其中某个 skill 明显对应时，应按以下方式使用：

1. Codex 协作优先读取 `.codex/skills/{skill}/SKILL.md`。
2. 如果 `.codex/skills/` 不存在对应 skill，再读取 `.claude/skills/` 或 `.agents/skills/` 的同名文件作为 SOP。
3. 执行时保持输出与本仓库测试飞轮一致。
4. 修改或迁移 skill 时，检查 `.claude/skills/`、`.codex/skills/`、`.agents/skills/` 是否需要同步。

当前核心 skill：

- `doc-review`：审查开发文档完整性。
- `doc-gen`：从源码和现有文档补全测试设计输入。
- `knowledge-build`：构建或更新测试知识库。
- `test-design`：生成业务用例、边界用例和 mismatch 记录。
- `test-codegen`：从 Markdown 用例生成 pytest。
- `test-fix`：修正错误用例并沉淀经验。
- `emitter-build`：从已验证 pytest 提取确定性 emitter 模板。

## 文档同步约定

项目结构、流程、codegen 架构或测试执行方式发生变更时，检查是否需要同步更新：

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/usebook/` 下的使用说明

不确定是否要同步用户手册时，先说明影响范围，再由用户决定。
