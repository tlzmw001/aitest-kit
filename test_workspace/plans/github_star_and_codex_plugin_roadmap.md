# GitHub 高 Star 与 Codex 插件路线图

## 目标

短中期目标不是先做重型商业化平台，而是把 `aitest-kit` 打磨成一个容易理解、容易试用、容易贡献、适合传播的高质量 GitHub 项目。

核心定位：

```text
AITest Kit 把开发/API 文档转成可评审的测试知识库、Markdown 用例、generated pytest 和结构化测试报告。
AI 负责探索未知，代码负责沉淀稳定、可重复、可验证的测试资产。
```

Codex 插件作为中期探索目标：它不替代 CLI 和 workspace，而是作为 Codex 用户的工作流入口，帮助用户更顺畅地运行 AITest Kit 测试飞轮。

## 当前判断

- 当前项目已有可用内核：CLI、workspace template、profile gate、Case IR、case_flow、pytest codegen、run/report、promotion report。
- 距离高 star 主要缺：开箱体验、英文入口、社区基础设施、examples、doctor/lint、扩展机制说明。
- 距离商业化还缺团队协作、权限审计、dashboard、历史趋势、CI/Issue 集成、私有部署方案。商业化先不作为当前主目标。

## 优先级路线

### P0：补齐开源项目基础设施

目标：让陌生开发者知道怎么试、怎么提问题、怎么贡献。

要做：

- 新增 `CONTRIBUTING.md`：开发环境、验证命令、generated 文件规则、PR 要求。
- 新增 GitHub issue templates：
  - Bug report
  - Feature request
  - New project migration issue
- 新增 Pull Request template：变更范围、验证命令、是否改 schema/template/skills/generated。
- 补英文文档入口：
  - `README.en.md` 或将英文设为主 README、中文迁移到 `README.zh-CN.md`
  - English Quickstart
- 补 Roadmap/Status：说明当前官方支持 API testing，unit/frontend/contract 是未来方向。

### P1：强化开箱体验和传播案例

目标：让用户 5 到 10 分钟看到完整价值。

要做：

- 整理官方 examples：
  - minimal REST API
  - discount_policy 多端点状态流
  - gRPC / mixed protocol 示例可后置
- 每个 example 需要包含：
  - public API doc
  - aitest workspace 或生成步骤
  - codegen/run 命令
  - 预期报告输出
- 设计 `aitest demo` 或至少提供一条清晰 demo 路径。
- README 顶部放清晰流程图和最短成功路径。

### P1：新增自检能力

目标：降低用户迁移新项目时的排查成本。

要做：

- 设计并实现 `aitest doctor`。
- 第一版检查：
  - workspace 结构
  - `aitest_config/config.yaml`
  - `aitest_config/project_config.yaml`
  - profile gate
  - generated freshness
  - pytest collect
  - 常见环境变量缺失
- 后续扩展：
  - Markdown case lint
  - knowledge L0/L1/L2 lint
  - service connectivity check

### P2：设计 emitter 扩展机制

目标：回应“当前主要覆盖 HTTP/gRPC API 测试，场景较窄”的问题，同时避免过早摊大。

要做：

- 写 spec：`emitter registry / custom emitter`。
- 第一阶段只保留当前 `pytest_api` emitter，行为不变。
- 明确扩展方向：
  - `pytest_unit`：源码函数/类单测生成
  - `playwright`：前端/E2E 测试生成
  - `contract`：OpenAPI/proto schema 合同测试
- 暂不立即实现 unit/frontend/contract，只提供清晰扩展边界。

### P2：探索 Codex 插件

目标：把 AITest Kit 变成 Codex 用户可直接使用的测试工作流插件，提升传播和未来商业化入口。

原则：

- 插件是 thin wrapper，不重写核心能力。
- 核心能力仍在 `aitest-kit` CLI、workspace template、schema、report 中。
- 插件负责提供 Codex workflow、命令说明和 skills 分发。

要做：

- 写 Codex plugin spec：
  - 插件定位
  - 插件和 CLI 边界
  - plugin v0 不做什么
  - skills/commands 列表
  - 与 workspace template 的关系
  - 安装和验证方式
- plugin v0 只做 workflow：
  - init
  - doc review
  - knowledge build
  - test design
  - codegen
  - run/report
  - test fix
  - health
- plugin v1 再考虑：
  - codegen health / promotion review report
  - case_body / case_flow 治理辅助
- 暂不做复杂 UI、MCP server、插件内重写 codegen。

### P3：规则沉淀辅助与 codegen 表达层治理

目标：帮助 AI 和人工 review 更快、更稳地判断哪些 pytest、`case_body`、`case_flow` 值得沉淀；不让代码替代业务抽象判断，不自动修改 profile、fixture 或 project_config。

第一性原理判断：

- 规则沉淀本质上是抽象边界判断，不只是语法转换。
- 是否应该沉淀到 fixture、`case_flow`、named template、default strategy 或 project_config，依赖业务语义、可复用性、命名边界和维护成本。
- 这些判断需要 AI 推理和人工 review；纯代码只能可靠完成扫描、分类、统计、候选生成和验证建议。
- 因此 P3 的产品价值不是“自动晋升”，而是“晋升辅助与审计”。

核心判断：

```text
case_body 不是失败；长期无理由的大量 case_body 才是失败。
case_flow 不是万能；把复杂控制流塞进 case_flow 才是失败。
default strategy 不是业务策略；为每个业务模块新增 default 才是失败。
assertion pattern 不是流程理解器；让 regex 猜业务流程才是失败。
```

P3 应做和不应做：

```text
应该做：
  - 统计各模块 default_http / structured_case_flow / custom_case_body / skipped 占比。
  - 分类 case_body：linear、resource_lifecycle、subprocess、concurrency、mock、unknown。
  - 识别重复 call/assert 结构和重复断言块。
  - 生成 review-only promotion candidate report。
  - 输出候选 YAML 片段、证据、风险点和验证命令。

不应该做：
  - 自动修改 codegen_profile。
  - 自动新增 fixture/helper。
  - 自动重写 project_config。
  - 自动应用 promotion patch。
```

分层模型：

```text
L0  AI handwritten pytest / case_body
    适合新项目探索期和复杂逃生通道。

L1  reviewed case_body
    已人工确认、可运行、可复现，但仍是 Python body。

L2  structured_case_flow
    线性流程：call / assign / assert / comment，可校验、可迁移。

L3  named flow template / domain template
    把重复 case_flow 压缩成业务模板，例如 policy_decision、decision_not_found。

L4  default strategy / builtin assertion rule
    最稳定、最通用、最少配置，适合项目级长期规则。
```

边界规则：

- `case_body` 只用于复杂控制流、复杂资源生命周期、进程/并发/mock/临时文件等 Python 更适合表达的场景。
- 凡是能用线性步骤表达的，不进 `case_body`；凡是必须依赖 Python 控制流表达的，才进 `case_body`。
- `case_flow` 只表达线性业务流程，保持 `call` / `assign` / `assert` / `comment` 四类 step，不引入 `if`、`loop`、`try/finally` 等控制结构。
- 复杂控制流优先下沉到经过 review 的 fixture/helper 方法，再由 `case_flow` 调用 helper，而不是扩展 profile DSL。
- `default_http` / `default_grpc` 只处理技术骨架，例如单接口调用、请求构造、基础响应断言，不按业务模块无限新增 default strategy。
- 默认策略后续应优先配置化硬编码点，例如 endpoint、method、身份字段、request_id 字段、请求值模板，而不是新增多个业务专属 default。
- assertion rules 和 named templates 只处理断言翻译，不负责猜测业务流程。
- 流程由 `case_flow` / `case_body` 显式表达，断言由 assertion rules / named templates 解析生成。

沉淀优先级：

```text
1. 能通过修 Markdown 用例解决的，先修 Markdown。
2. 只是字段差异，优先用 request_overrides / project_config。
3. 只是断言复杂，优先用 assertion_rule / named_template。
4. 是线性多步骤流程，优先用 case_flow。
5. 流程复杂但业务稳定，优先封装 fixture/helper，再由 case_flow 调用。
6. 同类 case_flow 重复 3 次以上，考虑 named flow template。
7. 最后才保留 case_body，并记录保留原因。
```

健康指标建议：

- 探索期：`case_body` 比例可以较高，重点是先跑通真实测试。
- 稳定期：重复 `case_body` 必须进入 promotion review。
- 成熟期：剩余 `case_body` 应该都有明确保留理由。
- 比例用于 health report 和人工 review，不直接作为硬门禁；硬门禁仍聚焦 schema、case_id、parser、IR、freshness 和 renderer 诊断。

后续可做：

- 在 health report 中统计 `default_http`、`structured_case_flow`、`custom_case_body` 占比。
- 对 `case_body` 输出候选分类：可 flow 化、可 helper 化、可模板化、确需保留。
- 在 `codegen_profile` 或报告中记录 `case_body` 保留原因。
- 为重复 `case_flow` 设计 review-only named flow template 候选，不自动改 profile。
- 对候选输出证据链：匹配到的 case_id、重复代码结构、建议沉淀层级、需要人工确认的问题、建议验证命令。
- 如果未来重新评估自动应用 patch，必须先具备稳定候选质量、dry-run、可读 diff、自动验证和回滚机制；在这之前不进入路线图主线。

## 暂不做

- 不马上做重型 SaaS / dashboard。
- 不马上支持单元测试、前端 E2E、合同测试的完整实现。
- 不把 `aitest-kit` 改造成只能在 Codex 中运行的插件。
- 不在插件中复制 codegen/report 核心逻辑。
- 不做自动应用 promotion patch。它不属于当前 P3 目标，除非未来候选质量、dry-run、验证和回滚机制经过多轮人工验证。

## 建议执行顺序

1. 社区基础设施：`CONTRIBUTING`、issue templates、PR template。
2. 英文入口：English README / Quickstart。
3. examples：先整理 minimal REST API 和 discount_policy。
4. `aitest doctor`：先做 workspace/profile/generated/collect 自检。
5. emitter 扩展机制 spec。
6. Codex plugin spec。
7. 最小 Codex plugin v0。
8. codegen 表达层治理：补 health report 指标、case_body 保留原因和重复 flow 模板候选。
9. promotion review report：输出 review-only 候选、证据链、风险点和验证命令。

## 成功标准

- 新用户能在 10 分钟内完成安装、初始化、codegen、run，并看到报告。
- GitHub 首页能清楚说明项目价值、当前能力、未来路线和贡献方式。
- 用户遇到问题时，有结构化 issue 模板和 `aitest doctor` 输出可供排查。
- examples 能展示最小 API 和多端点状态流两个典型场景。
- Codex 用户能通过插件按 AITest Kit 测试飞轮完成一次端到端流程。
- 核心承诺保持不变：AI 做探索，代码做稳定沉淀。
- 生产级项目迁移后，`case_body`、`case_flow`、默认策略和断言模式各有清晰边界；复杂用例可以保留 Python body，但重复模式能被 review 并逐步沉淀。
