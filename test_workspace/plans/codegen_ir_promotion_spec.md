# Codegen Case IR 与 case_body 晋升机制 Spec

## 背景

当前 codegen 已经形成三条生成路线：

- 默认模板：Markdown 共享配置 + `request_overrides` + 通用断言规则生成标准推荐接口测试。
- 规则模板：`assertion_rules`、`builtin_assertion_rules`、`named_templates` 生成稳定断言代码。
- `case_bodies`：对多端点、多请求、副作用、日志、隔离服务等复杂场景复制已验证的 pytest 函数体。

这三条路线符合项目哲学：AI 先探索未知，跑通后把稳定模式沉淀为代码和规则。但目前生成策略判断分散在 emitter 中，`case_bodies` 也缺少系统化晋升机制，导致两个问题：

- 单条用例为什么走 HTTP、gRPC、case_body、manual 或 skip，缺少可观察的中间解释。
- 大量已验证的 `case_bodies` 中存在重复结构，但缺少统一方式判断应晋升为断言规则、默认模板、helper 还是 structured `case_flow`。

本 spec 设计轻量 Case IR 和 `case_bodies` 晋升机制，目标是增强可观测性和沉淀能力，不把系统改造成重型测试 DSL。

## 当前实现状态

截至本轮实现，已经落地：

- Case IR dataclass 与 planner：`aitest_kit/codegen/ir.py`、`aitest_kit/codegen/planner.py`。
- IR 可观测 CLI：`codegen --dump-ir`、`codegen --explain TC-XXX`。
- emitter 通过 Case IR 渲染 pytest：`emitter.py` 负责装载、诊断和落盘，`ir_renderer.py` 负责渲染。
- `case_bodies` 晋升候选只读分析：`codegen --analyze-promotion`。
- `case_flows` v1 底座：profile loader、轻量校验、planner strategy、IR 结构和 renderer，支持 `call` / `assign` / `assert` / `comment` 四类 step。
- 真实迁移试点：`validation_ratelimit` 剩余可执行 `case_bodies` 已全部晋升为 `case_flows`；`rough_ranking` 23 条稳定 recommend flow 已全部晋升；`issuance` 晋升 17 条并保留 1 条并发 `case_body`；`ab_service` 晋升 26 条运行中 API flow，并保留 14 条文件、subprocess、Remote SDK 生命周期和 mock 相关 `case_body`。
- 防呆校验：同一 case_id 不允许同时出现在 `case_bodies` 和 `case_flows`；`case_flow` 的 `assert` step 必须写成可执行 Python `assert ...`，否则 codegen 直接报错。
- promotion analyzer 方法检测已从固定对象名扩展为“profile 中的 fixture / `case_flow.object` / `case_flow.call` 对象名 + 默认对象名”，便于新项目使用 `api`、`service`、`order` 等对象名。
- promotion report 落盘：支持将晋升分析写入 `test_workspace/reports/codegen/latest/`，包含人读 Markdown 和工具读 JSON。
- promotion patch 草案落盘：支持生成 review-only 的 patch Markdown 和 diff 草案，默认不修改 profile。
- profile 生成前体检：`codegen --validate-profile` 校验 profile 结构、case_id 引用、`case_flow` 格式和 module_type，并可落盘审计报告。

尚未落地：

- 自动从已验证 pytest 反向提取 `case_flows`。
- 从 promotion report 生成可直接应用的 `case_flows` profile patch。

## 当前用例分布

基于现有 `test_workspace/cases/` 和 `codegen_profile`，模块可粗分为两类：

| 模块 | 主要生成形态 | 说明 |
|------|--------------|------|
| `ab_experiment` | `request_overrides` + `assertion_rules` | 标准推荐接口，含 HTTP/gRPC 与实验断言 |
| `calibration` | `assertion_rules` + `named_templates` | 分段/线性校准，复杂点在断言公式 |
| `e2e` | `request_overrides` + `assertion_rules` | 标准链路组合验证 |
| `feature_scoring` | `request_overrides` + 少量规则 | 特征打分结果断言 |
| `scene_routing` | `request_overrides` + `assertion_rules` | 路由、兜底与 gRPC 场景 |
| `ab_service` | `case_flows` + `case_bodies` | 运行中 API CRUD 已结构化；文件、Remote SDK、mock 生命周期保留 body |
| `issuance` | `case_flows` + 1 条 `case_body` | 推荐触发发放、库存和查询观察已结构化；并发库存用例保留 body |
| `logging` | `case_bodies` | 隔离进程、日志捕获 |
| `rough_ranking` | `case_flows` | 隔离服务 + scoring proxy 仍由 fixture 负责，测试体已结构化为 recommend flow |
| `validation_ratelimit` | `case_flows` | 参数校验、schema 422、gRPC missing、限流均已结构化；不可行用例仍按 skip 处理 |

这说明第一版 IR 必须覆盖现有路线，但晋升机制应优先从重复度高、风险较低的模块试点，而不是一次性重写所有 `case_bodies`。

## 设计目标

1. 把 Markdown parse、生成策略规划、pytest 渲染拆成清晰边界：
   - parser 回答“Markdown 写了什么”。
   - Case IR 回答“这条用例准备怎么生成，为什么”。
   - emitter 回答“如何把生成计划渲染为 pytest”。
2. Case IR 第一版只镜像现有 emitter 决策，不改变生成结果。
3. 所有策略决策必须可解释，至少能追踪到 Markdown、project_config 或 codegen_profile 的来源。
4. `case_bodies` 晋升机制第一版只做候选分析，不自动改 profile。
5. structured `case_flow` 是 `case_bodies` 的一种晋升目标，只覆盖重复、稳定、低控制流的多步骤测试。
6. 保留 `case_body` 作为复杂场景逃生通道，不追求 100% 结构化。
7. 新项目迁移时优先改 `project_config`、profile、fixture/helper，不大改 skill 和 codegen engine。

## 非目标

- 不让 parser 读取 profile 或 project_config。
- 不让 Case IR 做业务语义推理，例如判断某优惠券为什么业务上应该命中。
- 不在第一版支持任意 Python 控制流形式的 `case_flow`。
- 不引入新依赖来做 JSON Schema 校验；第一版使用轻量 Python 校验函数。
- 不修改 `coupon_system/` 或 `ab_experiment_sdk/`。
- 不直接手写修改 generated pytest 作为长期源文件。

## 格式选择

采用组合方案，而不是 YAML 与 JSON 二选一：

| 场景 | 格式 | 理由 |
|------|------|------|
| `codegen_profile_{module}.md` 编写 | YAML | 人和 AI 都更容易维护多行模板、case_body、case_flow |
| profile/case_flow 结构契约 | JSON Schema 风格 | 明确字段、类型和禁用未知字段，便于后续校验 |
| 运行时 IR | Python dataclass | 便于类型化传递和单元测试 |
| `--dump-ir` 机器输出 | JSON | 稳定 diff、便于 CI/工具消费 |
| `--explain TC-XXX` 人类输出 | YAML 风格文本 | 便于调试阅读 |

第一版不新增 `jsonschema` 依赖，先实现 `validate_case_flow_profile()` 这类轻量校验函数。若后续校验复杂度明显上升，再单独评估依赖引入。

## 数据流

目标数据流：

```text
Markdown business.md / boundary.md
  -> parser.parse_case_file()
  -> ParseResult
      - SharedConfig
      - TestCase[]
      - errors[]
  -> planner.build_case_ir()
      输入 ParseResult + ProjectConfig + codegen_profile
  -> CaseIR[]
  -> emitter.render_case_ir()
  -> generated pytest
  -> pytest collect/run
  -> emitter-build / promotion analyze
  -> assertion_rules / request_overrides / case_flow / case_body
```

当前 emitter 已经消费 Case IR 渲染 pytest；`--dump-ir` / `--explain` 仍作为调试入口保留。

## parser 与 Case IR 边界

parser 只负责 Markdown 结构提取：

- 共享配置：接口、基础请求体、标准前置、通用断言、变量定义。
- 用例：ID、标题、优先级、场景变量、断言、标记、section。
- Markdown/JSON 结构诊断，例如 `E001`。

parser 不负责：

- 判断 HTTP/gRPC。
- 判断是否使用 `case_bodies`。
- 匹配断言规则。
- 选择 fixture。
- 合并 request_overrides。
- 读取 project_config 或 codegen_profile。

Case IR planner 负责结合 parser 输出、project_config 和 profile 做生成计划：

- 决定 `strategy`。
- 决定 `protocol`。
- 解析 fixture 列表。
- 规划 setup、request、call、assertion、custom body。
- 记录 source_trace 和 diagnostics。

## Case IR v1

第一版 `CaseIR` 保留三类信息：用例元数据（case_id/title/module/source/section/priority/markers）、生成计划（strategy/protocol/fixtures/setup/request/call/assertions/custom_body/case_flow）和可观测信息（diagnostics/source_trace）。

### Strategy

第一版只支持现有路线：

| strategy | 适用场景 |
|----------|----------|
| `default_http` | 标准 HTTP 推荐接口 |
| `default_grpc` | 场景变量标注 gRPC 的标准推荐接口 |
| `custom_case_body` | profile 中存在对应 `case_bodies[case_id]` |
| `manual` | marker 包含 manual |
| `skipped` | marker 包含可行性存疑 |

| strategy | 适用场景 |
|----------|----------|
| `structured_case_flow` | profile 中存在对应 `case_flows[case_id]` |

优先级：

```text
skipped > custom_case_body > structured_case_flow > manual > default_grpc > default_http
```

说明：

- `skipped` 最高优先级，避免不可行用例生成执行体。
- `custom_case_body` 暂时优先于 `case_flow`，防止未完成迁移时改变现有输出。
- 后续某条用例正式从 `case_body` 晋升到 `case_flow` 时，必须删除旧 `case_body`。同一 case_id 同时存在于两处会被 profile 校验拒绝，避免 `case_body` 遮蔽 `case_flow`。

### Protocol

第一版保持现有规则：只从 `TestCase.scenario_vars` 的值中识别 `gRPC`。

IR 需要记录 source trace：

```yaml
protocol:
  value: grpc
  source: scenario_vars.协议
  raw_value: gRPC
```

如果 strategy 为 `custom_case_body`，protocol 可以记录为 `custom`，因为实际调用由 body 决定。

### AssertionIR

断言规划记录 `source`、`kind`、`code_lines`、`resolved_by` 和 `variables`。`kind` 第一版包括 `builtin_rule`、`profile_rule`、`named_template`、`manual_comment`、`unparsed`；`resolved_by` 示例为 `project_config.builtin_assertion_rules.status_code`、`profile.assertion_rules.piecewise_cascade`、`named_templates.skip` 或 `UNPARSED`。

### Source Trace

每个关键决策都应可追踪：

```yaml
strategy:
  value: custom_case_body
  source: profile.case_bodies.TC-ABS-001
protocol:
  value: grpc
  source: scenario_vars.协议
fixtures:
  value: [setup_ab_service, tmp_path]
  source: profile.case_fixtures.TC-ABS-012
assertions[0]:
  source: "`response.code == 0`"
  resolved_by: project_config.builtin_assertion_rules.status_code
```

## 诊断分层

新增 IR 后，错误应按层归属：

| 代码 | 层 | 含义 |
|------|----|------|
| `E001` | parser | Markdown JSON 解析失败 |
| `E101` | parser/raw | 必需 Markdown 字段缺失或结构异常 |
| `E201` | planner | 无法决定 strategy/protocol |
| `E202` | planner | strategy 需要的请求体、fixture 或 profile 字段缺失 |
| `E203` | planner | assertion 无法解析，生成 UNPARSED |
| `E301` | emitter | emitter 不支持某个 IR strategy/kind |
| `E401` | validation | 生成文件 AST/collect 校验失败 |
| `E501` | profile validation | profile YAML 或基础结构非法 |
| `E502` | profile validation | 同一 case_id 同时定义在 `case_bodies` 和 `case_flows` |
| `E503` | profile validation | `case_flow` step/字段格式非法 |
| `E504` | profile validation | module_type 未知或缺少必需 profile 字段 |
| `E505` | profile validation | profile 引用的 case_id 不存在于 Markdown |
| `E510/E511` | profile validation | 模块用例目录或 Markdown 源文件缺失 |

已有 diagnostics 保持兼容，新增诊断不应静默吞掉 parser errors。

## profile 生成前校验

`--validate-profile` 是生成前体检，不生成 pytest、不修改 profile。它解决的问题是：在迁移新项目或晋升 `case_flow` 时，把 profile 格式错误提前暴露，而不是等到 codegen 或 pytest 阶段才发现。

第一版校验范围：

- profile 必须包含合法 YAML mapping；未知顶层字段报错。
- `assertion_rules`、`request_overrides`、`case_fixtures`、`case_bodies`、`case_flows`、`extra_imports` 的基础类型必须正确。
- `case_bodies` / `case_flows` / `case_fixtures` / `request_overrides` 的 case_id 必须能在同模块 Markdown 用例中找到。
- 同一 case_id 不允许同时存在于 `case_bodies` 和 `case_flows`。
- `case_flow` 复用现有轻量结构校验；`assert` step 必须显式写成 `assert ...`。
- module_type 来自 profile 的 `module_type` 或 `project_config.modules.{module}.module_type`；若类型要求 `case_bodies`，`case_bodies` 或 `case_flows` 任一存在即可满足。

第一版命令：

```bash
python3 -m aitest_kit.cli codegen ab_service --validate-profile
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --validate-profile --write-report
```

`--all` 只扫描包含 `business.md` 或 `boundary.md` 的真实模块目录，避免归档目录干扰校验。

校验报告复用 codegen 报告目录，输出 `{module}_profile_validation.md/json`，用于迁移审计和排查；只读报告不代表自动修复。

## `case_bodies` 晋升机制

晋升机制由 `emitter-build` 或独立 promotion analyzer 执行。第一版只读分析，不自动修改 profile。

### 报告与 patch 产物

promotion analyzer 的运行产物不放在 `plans/`，统一写入 codegen 报告目录：

```text
test_workspace/reports/codegen/latest/
  {module}_promotion_report.md
  {module}_promotion_report.json
  {module}_promotion_patch.md
  {module}_promotion_patch.diff
```

约定：

- `promotion_report.md` 给人 review，解释候选、保留理由、检测到的 object/method/flag。
- `promotion_report.json` 给工具和后续 AI 消费，字段应保持稳定。
- `promotion_patch.md` 是人工 review 草案，说明哪些 case 可考虑晋升，以及同一 profile edit 中需要删除哪些旧 `case_bodies`。
- `promotion_patch.diff` 只作为保守 diff 草案，不自动应用，不保证能直接替换 profile。
- 当前默认写 `latest/`；如果后续需要历史追踪，再扩展 `runs/{timestamp}/`。

第一版命令：

```bash
python3 -m aitest_kit.cli codegen ab_service --analyze-promotion --write-report
python3 -m aitest_kit.cli codegen ab_service --suggest-promotion-patch
```

### 晋升分类

每条 `case_body` 先按目标分类：

| 分类 | 说明 |
|------|------|
| `promote_to_default_template` | 可退回默认请求模板，只需补 request_overrides/assertion_rules |
| `promote_to_assertion_rule` | 请求流程标准，只有断言可模板化 |
| `promote_to_named_template` | 复杂断言需要 if/elif/else 或参数化代码生成 |
| `promote_to_case_flow` | 多步骤流程稳定，差异主要是参数、保存变量和期望值 |
| `promote_to_helper` | 多个 body 重复 Python 逻辑，应下沉 fixture/helper |
| `keep_case_body` | 少见、复杂、并发、进程、mock、文件生命周期等暂不晋升 |

### 候选门槛

建议晋升必须满足：

- 至少 3 条已验证通过的 `case_body` 结构相似。
- 差异主要是参数、期望值、case_id。
- 使用 fixture/helper 的公开测试能力。
- 不依赖复杂循环、分支、线程、进程生命周期或 monkeypatch。
- 晋升后生成代码更可解释，而不是把 Python 藏进 YAML 字符串。

不满足时保留 `case_body`，并在报告中说明原因。

### 当前模块试点结果

已完成结构化试点：

- `validation_ratelimit`：单次 HTTP/gRPC 参数校验、schema 缺字段、限流多次请求均已晋升为 `case_flows`。
- `rough_ranking`：recommend_http/recommend_grpc 流程已晋升为 `case_flows`；隔离服务和 scoring proxy 生命周期仍下沉在 fixture 中。
- `issuance`：库存、查询、HTTP/gRPC 推荐副作用流程已晋升为 `case_flows`；并发库存用例保留 `case_body`。
- `ab_service`：运行中 API CRUD/schema flow 已晋升为 `case_flows`；文件持久化、subprocess、Remote SDK 生命周期和 mock 用例保留 `case_body`。

暂缓：

- `logging`：隔离进程和日志捕获是测试主体，继续保留 `case_body`。

## structured `case_flow` v1

`case_flow` 是 `case_bodies` 的一种晋升目标，用于表达稳定多步骤测试。它不是通用编程语言。

### YAML 形态

```yaml
case_flows:
  TC-VAL-001:
    fixture: setup_validation_ratelimit
    steps:
      - call: setup_validation_ratelimit
        kwargs:
          case_id: "TC-VAL-001"
        save_as: case
      - call: case.http
        args: ["", "req-val-001"]
        kwargs:
          external: 0
          score_threshold: 0.5
          max_claim_per_request: 1
        save_as: resp
      - assert: "assert resp == ERR"
```

### 支持能力

第一版仅支持：

- `call`: 调用 fixture/helper 对象方法。
- `args` / `kwargs`: 字面量参数、`ref` 引用、显式 `expr`。
- `save_as`: 保存中间结果到局部变量。
- `assign`: 用显式 `expr` 派生局部变量，例如从 raw response 中提取 `locs`。
- `assert`: 复用现有 assertion resolver 或受控 raw assertion。
- `comment`: 渲染受控注释，例如 manual check 说明。

第一版不支持：

- 任意 `for` / `while` / `if` 控制流。
- 动态 import。
- 隐式 eval。
- 线程/进程生命周期。
- monkeypatch 或复杂 fixture 生命周期。

涉及这些能力时继续保留 `case_body`。

### 结构校验

`case_flows` 校验规则：

- 顶层必须是 dict。
- case_id 必须匹配 `^TC-[A-Z0-9]+-\d+$`。
- `fixture` 必须是非空字符串。
- `steps` 必须是非空 list。
- 每个 step 必须且只能是 `call`、`assign`、`assert` 或 `comment` 之一。
- `save_as` 必须是合法 Python 标识符。
- `assign` 目标必须是合法 Python 标识符，且必须提供非空 `expr`。
- `comment` 必须是非空字符串。
- `ref` 必须引用前面已经 `save_as` 的变量。
- `expr` 必须显式声明，emitter 原样渲染，不做求值。
- `assert` 必须是字符串，去掉可选反引号后必须以 `assert ` 开头；裸表达式如 `` `resp == ERR` `` 会直接报错。
- 同一 case_id 不允许同时存在于 `case_bodies` 和 `case_flows`。
- 未知字段默认报错。

## 文件影响计划

### Phase 0: Spec 与 skill

- 新增 `test_workspace/plans/codegen_ir_promotion_spec.md`。
- 仅更新 `.codex/skills/test-codegen/SKILL.md`。
- 仅更新 `.codex/skills/emitter-build/SKILL.md`。
- 不修改 `.claude/skills/`、`.agents/skills/`。
- 状态：已完成。

### Phase 1: IR 数据结构与 planner

- 新增 `aitest_kit/codegen/ir.py`。
- 新增 `aitest_kit/codegen/planner.py`。
- 新增 planner 单元测试。
- emitter 生成结果不变。
- 状态：已完成。

### Phase 2: IR dump/explain

- 修改 `aitest_kit/codegen/cli.py` 或 `aitest_kit/cli.py` 接线。
- 支持 dump 单模块 IR，优先 JSON 输出。
- 支持解释单条 TC 的策略来源。
- 状态：已完成。

### Phase 3: emitter 消费 IR

- 将 `_render_test_function(tc, ctx)` 的策略判断逐步迁移到 IR。
- 输出必须与现有 generated pytest 等价。
- 保持 `emitter.py` 不超过 500 行；必要时拆分渲染模块。
- 状态：已完成，渲染逻辑拆到 `aitest_kit/codegen/ir_renderer.py`。

### Phase 4: promotion analyzer

- 新增 `aitest_kit/codegen/promotion.py`。
- 只读分析 `case_bodies`，输出晋升候选和理由。
- 不自动修改 profile。
- 状态：已完成。

### Phase 5: case_flow v1

- `profile.py` 增加 `load_profile_case_flows()`。
- 新增 `case_flow` 校验和渲染。
- 先试点 `validation_ratelimit` 中最简单的参数校验组，再扩展到 `rough_ranking`、`issuance` 和 `ab_service` 的稳定流程。
- 状态：底座已完成；可结构化试点已完成，剩余 `case_bodies` 均属于并发、服务生命周期、文件、subprocess、Remote SDK 或 mock 场景。

### Phase 6: promotion report artifacts

- `--analyze-promotion --write-report` 写入 Markdown + JSON 报告。
- `--suggest-promotion-patch` 写入 review-only patch Markdown + diff 草案。
- 默认输出到 `test_workspace/reports/codegen/latest/`。
- 状态：已完成第一版，不自动应用 profile patch。

### Phase 7: profile validation

- 新增 `aitest_kit/codegen/profile_validator.py`，独立执行 profile 结构校验。
- `codegen --validate-profile` 支持单模块和 `--all`。
- `ProjectConfig` 读取 `modules` 注册表，供 module_type 校验使用。
- 状态：已完成第一版。

## 验证计划

每个实现阶段至少执行：

```bash
python3 -m compileall aitest_kit/codegen
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

涉及模块迁移时追加：

```bash
python3 -m pytest test_workspace/tests/generated/test_validation_ratelimit_business.py test_workspace/tests/generated/test_validation_ratelimit_boundary.py --collect-only -q
python3 -m pytest test_workspace/tests/generated/test_issuance_business.py test_workspace/tests/generated/test_issuance_boundary.py --collect-only -q
```

如果服务环境就绪，再运行实际模块测试。

## 新项目迁移原则

新项目接入应遵循：

```text
AI bootstrap
  -> 先生成知识库、Markdown、初版 pytest
  -> 允许 UNPARSED 和 case_body 暂时存在

Profile stabilization
  -> 跑通代表用例
  -> 写 project_config、fixture、codegen_profile
  -> 沉淀 request_overrides/assertion_rules/case_bodies

IR observability
  -> dump/explain 生成计划
  -> 排查 parser/profile/emitter/fixture/SUT 边界

Promotion
  -> 高频稳定模式晋升为规则或 case_flow
  -> 复杂少见场景保留 case_body

Stable architecture
  -> 新增同类用例主要改 Markdown/profile
  -> AI 处理未知，代码生成已知
```

skill 只描述稳定流程，不承载项目细节；项目差异进入 `project_config.yaml`、`codegen_profile_{module}.md`、fixture/helper 和知识库。
