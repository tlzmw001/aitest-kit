# Codegen Target Extension Spec

## 背景

`aitest-kit` 当前已经稳定支持 API 测试生成链路：

```text
Markdown API cases
  -> parser
  -> profile / project_config
  -> planner
  -> Case IR
  -> pytest API renderer
  -> generated pytest
```

这条链路证明了项目核心方法论是可行的：

```text
AI 负责探索未知测试空间；
框架负责定义边界、校验格式、稳定生成和持续执行；
重复出现并经过验证的模式，逐步从 AI 手写沉淀为结构化规则。
```

P2 的目标不是马上把 `aitest-kit` 扩成前端、单测、合同测试全能工具，而是先定义未来不同测试目标如何接入 codegen 架构，避免把所有能力都堆进当前 API IR 或 `ir_renderer.py`。

本 spec 以 `test_workspace/plans/github_star_and_codex_plugin_roadmap.md` 为当前路线依据。旧 release spec 中关于自动反向提取 `case_flow`、自动应用 promotion patch 的描述视为历史阶段判断，不作为本阶段执行范围。

## 核心原则

1. 项目哲学不变：AI 先探索，框架后约束，稳定模式逐步沉淀。
2. 测试目标可以不同：API、UI、E2E、Contract 的 case format、IR、fixture、emitter 可以不同。
3. 公共飞轮必须一致：文档 -> 知识库 -> Markdown 用例 -> IR -> generated tests -> run/report -> 失败反哺 -> 规则沉淀。
4. 不强迫所有测试目标复用当前 API Case IR：当前 Case IR 更接近 `ApiCaseIR`，未来需要 `BaseCaseIR + TypedCaseIR`。
5. 不把 `case_flow` 做成通用编程语言：复杂控制流下沉到 fixture/helper，flow 只表达可审查的线性步骤。
6. 不用 AI 每次重写稳定规则：规则一旦重复、验证、review，就沉淀进 schema、profile、helper、emitter 或 template。

## 统一飞轮

不同测试目标共享同一条测试资产沉淀飞轮：

```text
需求 / 开发文档
  -> 测试知识库
  -> Markdown 用例
  -> Typed Case IR
  -> Target Emitter
  -> Generated Tests
  -> Run / Report
  -> Failure Triage
  -> Rule Promotion
       -> profile / schema / helper / emitter / skill
```

共享的是方法论和治理链路，不是所有字段结构。

共享：

- `case_id`
- title
- priority
- module / category
- source trace
- diagnostics
- profile gate
- schema validation
- freshness check
- run/report
- promotion review

不强行共享：

- API request body
- HTTP/gRPC endpoint
- UI locator
- browser context
- OpenAPI operation
- mock setup
- cleanup lifecycle
- assertion detail grammar

## 为什么不能只扩展 emitter

如果未来支持前端测试，只替换最后的 renderer 不够。

API 测试的核心语义是：

```text
endpoint
method
request body
request overrides
response assertion
HTTP/gRPC helper
```

UI 测试的核心语义是：

```text
page
locator
action
navigation
wait
visual assertion
browser context
storage state
```

Contract 测试的核心语义是：

```text
schema source
operation id
request/response example
compatibility rule
schema assertion
```

如果把这些都塞进当前 API Case IR，会导致两个问题：

1. IR 语义污染：API 测试不需要的字段会进入公共结构。
2. `case_flow` 变成小型编程语言：不断增加 `click`、`fill`、`wait`、`loop`、`if`、`try/finally` 等控制结构后，profile 会变得不可审查。

因此未来扩展不能只发生在 emitter 层，而应当允许 case format、normalizer/planner、typed IR 和 emitter 按测试目标分化。

## 目标架构

```text
                 ┌────────────────────┐
                 │   Markdown cases    │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │ Common Case Parser  │
                 │ case_id/title/etc.  │
                 └─────────┬──────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌────────────┐ ┌───────────┐ ┌────────────┐
       │ API Planner│ │ UI Planner│ │ Contract   │
       │/Normalizer │ │/Normalizer│ │ Normalizer │
       └─────┬──────┘ └─────┬─────┘ └─────┬──────┘
             ▼              ▼             ▼
       ┌───────────┐ ┌──────────┐ ┌──────────────┐
       │ ApiCaseIR │ │ UiCaseIR │ │ContractCaseIR│
       └─────┬─────┘ └────┬─────┘ └──────┬───────┘
             ▼            ▼              ▼
       ┌──────────┐ ┌──────────────┐ ┌──────────────┐
       │pytest_api│ │playwright_ui │ │contract      │
       │emitter   │ │emitter       │ │emitter       │
       └──────────┘ └──────────────┘ └──────────────┘
```

## 分层职责

### Common Case Parser

负责解析所有测试目标共享的 Markdown 外壳：

- `case_id`
- title
- module / category
- source file
- priority
- markers
- section
- shared config 原文
- scene variables 原文
- assertion 原文
- diagnostics

Common parser 不负责理解所有测试领域细节。

### Target Normalizer / Planner

负责把通用解析结果转换成目标专属 IR。

API normalizer / planner：

- endpoint / method
- request body
- request overrides
- protocol
- fixture
- API assertion
- API case_flow / case_body

UI normalizer / planner：

- page URL
- browser context
- user action
- locator
- wait condition
- UI assertion
- visual assertion

E2E normalizer / planner：

- cross-system lifecycle
- setup / action / verify / cleanup
- environment dependency
- multi-service state flow

Contract normalizer / planner：

- OpenAPI / proto source
- operation id
- schema path
- example selection
- compatibility check

### Typed Case IR

未来 IR 应分为共享元数据和目标专属执行计划。

概念草案：

```python
class BaseCaseIR:
    case_id: str
    title: str
    module: str
    category: str
    priority: str
    source_file: str
    diagnostics: list[Diagnostic]
    target: str


class ApiCaseIR(BaseCaseIR):
    protocol: str
    request: ApiRequestPlan | None
    call: ApiCallPlan | None
    assertions: list[AssertionIR]
    case_flow: ApiCaseFlow | None


class UiCaseIR(BaseCaseIR):
    browser: BrowserPlan
    page_flow: list[UiStep]
    assertions: list[UiAssertionIR]


class ContractCaseIR(BaseCaseIR):
    schema_source: str
    operation_id: str
    examples: list[ContractExample]
    checks: list[ContractCheck]
```

这是架构草案，不是 P2 代码实现要求。

### Target Emitter

emitter 只消费对应的 Typed Case IR，做确定性渲染。

emitter 不做：

- 不读业务文档。
- 不猜用例意图。
- 不自动修改 profile。
- 不自动补 fixture。
- 不执行 AI 推理。

概念接口：

```python
class TargetEmitter:
    name: str
    target: str

    def supports(self, module_plan: object) -> bool:
        ...

    def render(self, module_plan: object, context: object) -> object:
        ...
```

## 测试目标类型

### `api + pytest_api`

当前唯一正式支持的目标。

用途：

- HTTP API 测试
- gRPC API 测试
- 多端点状态流 API 测试

当前实现继续使用现有 parser、planner、Case IR 和 pytest renderer。

### `ui + playwright_ui`

未来目标。

用途：

- 页面交互测试
- 表单输入
- locator / role 断言
- navigation / wait
- 可选视觉断言

不在 P2 实现。

### `e2e + pytest_e2e / playwright_e2e`

未来目标。

用途：

- 跨服务业务链路
- 环境编排
- 状态准备
- 清理策略
- 多系统观测

不在 P2 实现。

### `contract + contract`

未来目标。

用途：

- OpenAPI schema 合同测试
- proto schema 合同测试
- request/response example 验证
- backward compatibility check

不在 P2 实现。

## Profile 配置方式

长期推荐 profile 显式声明测试目标和 emitter：

```yaml
target: api
emitter: pytest_api
module_type: standard_http
```

字段含义：

- `target`：测试语义类型，例如 `api`、`ui`、`e2e`、`contract`。
- `emitter`：输出实现，例如 `pytest_api`、`playwright_ui`、`pytest_e2e`、`contract`。
- `module_type`：当前模块的测试形态和生成约束，例如 `standard_http`、`multi_endpoint`、`isolated_service`。

兼容策略：

```text
旧 profile 没有 target/emitter 时，默认：
  target: api
  emitter: pytest_api
```

不推荐用 `module_type` 推断 emitter。`module_type` 和 `emitter` 是不同概念，混用会导致未来 API target、contract target、E2E target 的边界不清。

## 与 Skill 的关系

skill 负责指导 AI 工作流：

- 读文档
- 构建知识库
- 设计用例
- 写 profile
- 判断某类测试是否适合沉淀
- 解释失败

codegen target 架构负责确定性生成：

- 校验 profile
- 生成 Typed Case IR
- 渲染测试代码
- freshness check
- report 关联

skill 不替代 emitter，emitter 不做 AI 推理。

## 非目标

P2 不做：

- 不实现 UI 测试生成。
- 不实现 E2E 测试生成。
- 不实现 Contract 测试生成。
- 不改变现有 `pytest_api` 输出。
- 不改变现有 codegen CLI 行为。
- 不引入第三方插件系统。
- 不引入 Python `entry_points` 插件发现。
- 不把 `case_flow` 扩展成带 `if`、`loop`、`try/finally` 的通用 DSL。
- 不自动反向提取 `case_flow`。
- 不自动应用 promotion patch。

## 分阶段计划

### Phase 1：Spec only

只完成本 spec。

要求：

- 明确哲学、边界、目标、非目标。
- 明确 API、UI、E2E、Contract 的差异。
- 明确 target / emitter / module_type 的字段职责。
- 不改代码。

### Phase 2：Registry Skeleton

在未来需要时引入最小 registry 骨架。

要求：

- 只注册 `api + pytest_api`。
- 保持现有 generated pytest 输出不变。
- 所有现有 codegen / run / doctor 命令行为不变。

### Phase 3：One New Target Pilot

选择一个新 target 做试点。

候选：

- `contract`：如果项目已有 OpenAPI/proto，可验证 schema 合同测试。
- `ui`：如果有稳定前端样例，可验证 Playwright action/assertion 模型。
- `e2e`：如果有多系统状态流，可验证生命周期和 cleanup 边界。

要求：

- 新 target 必须有独立 case format 草案。
- 新 target 必须有 typed IR。
- 新 target 不污染 API 主链路。

### Phase 4：Promotion / Report Support

在新 target 稳定后再考虑：

- health report 统计不同 target 的覆盖。
- promotion review report 输出不同 target 的沉淀建议。
- report 中区分 API/UI/E2E/Contract 失败类型。

## 验证标准

P2 spec 阶段：

- 文档能解释为什么不能只扩展 emitter。
- 文档能解释为什么共享方法论、不共享全部字段结构。
- 文档能解释 `target`、`emitter`、`module_type` 的区别。
- 文档明确 P2 不改变当前行为。

未来代码阶段：

```bash
python3 -m compileall aitest_kit
python3 -m pytest tests/ -q
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

如果引入 registry skeleton，还必须确认 generated 输出没有无关变化。
