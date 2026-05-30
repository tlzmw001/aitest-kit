# AITest 工作流与 Skill 协作指南

本文是一份长期协作手册，面向已经知道 AITest Kit 基本用途、准备在真实项目中持续维护测试资产的用户和 AI 协作者。

它不是 quickstart，不是迁移 checklist，也不是源码阅读指南。它回答的问题是：

- 用户、AI、CLI、Markdown、profile、fixture、generated pytest 和 report 分别负责什么。
- 新增模块、新增用例、测试失败、generated stale、fixture 缺动作时应该从哪一层进入。
- 如何避免把一次性 AI 生成变成不可维护的 pytest 堆。

## 1. 核心原则

AITest 的核心原则是：

```text
AI 负责探索未知，代码负责稳定重复。
```

AI 适合做：

- 阅读公开文档和 API 契约。
- 理解新系统和业务规则。
- 设计初版 Markdown 用例。
- 判断某类 pytest 是否值得沉淀。
- 解释失败原因。
- 补充 fixture/profile 中暂时无法由代码推断的适配逻辑。

代码必须做：

- 解析 Markdown。
- 校验 profile 格式和语义。
- 检查 case_id 对齐。
- 选择生成策略。
- 生成 Case IR。
- 渲染 pytest。
- 执行 freshness check。
- 收集 pytest 结果。
- 生成结构化报告。

AITest 不是要去掉 AI，而是让 AI 在明确边界内工作：未知部分由 AI 探索，稳定部分由代码门禁保证。

## 2. 资产分层

AITest 的测试资产按层组织：

```text
公开文档 / API 契约
  -> 测试知识库 L0/L1/L2
  -> Markdown 用例
  -> fixture + codegen profile
  -> Case IR
  -> generated pytest
  -> aitest run / report
  -> 失败修正与规则沉淀
```

每一层都有不同职责：

| 层级 | 主要文件 | 职责 |
|---|---|---|
| 公开文档 / API 契约 | `docs/` | 描述系统公开行为、接口、字段、错误码、业务规则 |
| 测试知识库 | `test_workspace/knowledge/` | 把原始文档转成可测试契约 |
| Markdown 用例 | `test_workspace/suites/{target}/{suite}/` | 人类可 review 的测试设计源文件 |
| fixture/helper | `test_workspace/targets/{target}/fixtures/`、`helpers/` | 提供测试动作库、读取运行变量、管理 setup/cleanup |
| profile | `test_workspace/targets/{target}/profiles/profile_{module}.md`、`profile_{suite}_suite.md` | 指导 codegen 如何把用例接到 fixture |
| Case IR | `aitest codegen --dump-ir` | parser 和 renderer 之间的可检查中间表示 |
| generated pytest | `test_workspace/generated/{target}/` | 编译产物，由 codegen 生成 |
| report | `test_workspace/reports/` | 测试执行结果和失败分流 |
| results | `test_workspace/results/` | 已确认的待测系统问题记录 |

## 3. 不要直接修改 generated pytest

`test_workspace/generated/{target}/` 下的 pytest 是编译产物，不是长期维护源文件。

如果生成结果不对，应回到对应源头修改：

| 问题 | 应修改的位置 |
|---|---|
| 用例表达错 | Markdown case |
| 执行步骤错 | module profile 或 suite profile |
| 动作能力缺失 | fixture/client/helper |
| 默认生成规则错 | `aitest_config/aitest.yaml` 或 codegen |
| profile 校验规则不足 | profile schema / profile validator |
| 报告分类错 | report collector / classifier |

直接修改 generated pytest 会在下一次 codegen 时被覆盖，也会绕过 profile gate、Case IR 和 freshness check。

## 4. Skill 职责总览

AITest workspace 内置多套 skills，适配不同 AI 编程环境。它们是 AI 的工作 SOP，不是 CLI 的替代品。

| Skill | 什么时候用 | 主要产物 |
|---|---|---|
| `doc-review` | 检查开发文档是否足够支撑测试设计 | 文档缺口和待确认项 |
| `doc-gen` | 文档不足且允许从源码或接口定义补测试设计输入 | 面向测试的补充设计文档 |
| `knowledge-build` | 从文档构建或更新 L0/L1/L2 | 测试知识库 |
| `test-design` | 为模块或需求 suite 设计 Markdown 用例 | `business.md`、`boundary.md` 或 suite case 文件 |
| `test-scaffold` | 构建 fixture、module profile 或 suite profile | fixture、profile、suite 接线 |
| `test-codegen` | 从 Markdown/profile 生成 pytest 并验证 | generated pytest 和 codegen 验证结果 |
| `test-fix` | 修正错误用例并沉淀经验 | 修订后的 Markdown、TEST_SPEC、profile 说明 |
| `test-maintain` | 用户不知道该走哪个入口时做影响面分析和路由 | 路由建议，不直接改文件 |
| `emitter-build` | 从已验证测试中提取可沉淀模式 | 规则沉淀建议 |

CLI 做确定性事情：

```text
aitest init
aitest upgrade
aitest doctor
aitest codegen
aitest run
aitest report
```

skill 做 AI 工作流：

```text
读文档
判断缺口
生成知识库
设计用例
构建 fixture/profile
修正用例
分析是否沉淀规则
```

正确搭配是：skill 产出或修改源资产，CLI 验证源资产能否稳定执行。

## 5. 常见用户意图路由

| 用户意图 | 推荐入口 |
|---|---|
| 第一次把新系统接入 AITest | `doc-review -> knowledge-build -> test-design -> test-scaffold -> test-codegen` |
| 文档不完整，需要先补测试设计输入 | `doc-gen` |
| 需要从公开文档建立测试知识库 | `knowledge-build` |
| 需要新增一批 Markdown 用例 | `test-design` |
| 新模块没有 fixture/profile | `test-scaffold` |
| 现有模块新增用例，fixture 动作已经足够 | `test-codegen` |
| 现有模块新增用例，但 fixture 缺动作 | `test-scaffold` 增量补 fixture/profile，再 `test-codegen` |
| `aitest codegen --check` stale | `test-codegen` |
| 某条用例写错或断言不可观测 | `test-fix` |
| 测试失败但不知道归因 | 先 `aitest run` 看 report，再路由 |
| 重复 case_flow 或 case_body 太多 | `emitter-build` |
| 不确定应该使用哪个 skill | `test-maintain` |

`test-maintain` 只负责影响面分析和路由，不应该绕过底层 skill 直接改文件。

## 6. 新项目第一次接入

推荐从一个小模块或一条主链路开始，而不是一次覆盖整个系统。

```text
1. aitest init
   创建独立 workspace。

2. 放入公开文档
   docs/public_api.md
   docs/openapi.yaml
   docs/config_schema.md

3. doc-review
   检查文档是否足够设计测试。

4. knowledge-build
   生成 L0/L1/L2。

5. test-design
   为 target/module 下的需求 suite 生成 Markdown 用例。

6. 人工 review
   确认用例是否测了真实语义，断言是否可观测，前置条件是否可复现。

7. test-scaffold
   生成 target/module registry、fixture/client/helper、module profile 和 suite profile。

8. test-codegen
   运行 validate-profile、dump-ir、codegen、check、collect-only。

9. aitest run
   运行真实测试并生成 report。

10. 失败分流
    区分文档、用例、fixture/profile、环境、codegen 和待测系统问题。

11. emitter-build
    测试稳定后再沉淀重复模式。
```

不要从初始化直接跳到手写 pytest。允许 AI 在初期探索，但最终应回到：

```text
Markdown suite -> target fixture/profile -> Case IR -> generated pytest
```

## 7. 现有模块新增用例

如果已有 target/module，现在新增一批 suite 用例，需要先判断 fixture 动作是否够用。

如果动作已经足够，例如已有：

```text
client.login()
client.create_resource()
client.query_resource()
client.call_api()
```

可以走：

```text
test-design -> test-codegen
```

如果新增用例需要新动作，例如：

```text
上传文件
流式响应
二次认证
创建特殊状态数据
查询异步任务结果
清理跨接口副作用
```

应该回到：

```text
test-scaffold incremental -> test-codegen
```

不要让 `test-codegen` 强行手写 generated pytest，也不要把每条用例的专有逻辑藏进 fixture。

## 8. 失败分流

测试失败后先分流，不要直接修改 generated pytest。

| 类型 | 典型表现 | 处理方式 |
|---|---|---|
| `PRECONDITION_MISSING` | 缺少必需环境变量、token、测试账号、运行前置条件 | 补运行输入或标记不可执行前置 |
| `ENVIRONMENT_ERROR` | 服务未启动、端口不通、依赖不可用、超时 | 修测试环境或启动方式 |
| `TEST_SCAFFOLD_ERROR` | fixture/client/helper 准备状态错误、调用封装错误、cleanup 错误 | 修 fixture/helper/profile |
| `TEST_CASE_ERROR` | Markdown 用例预期错、场景不可观测、前置不稳定 | 修 Markdown 或记录 mismatch |
| `CODEGEN_ERROR` | IR、renderer、profile merge、生成代码有框架问题 | 修 `aitest_kit` 并补回归测试 |
| `SUT_BUG` | 请求和断言都合理，系统行为不符合公开契约 | 记录到 `test_workspace/results/` |
| `UNKNOWN` | 信息不足，无法可靠分类 | 补日志、补报告上下文或人工确认 |

report 是规则化初判，不自动宣判待测系统 bug。尤其是断言失败，需要人工确认：

- 用例是否来自明确契约。
- fixture 是否准备了正确测试状态。
- 运行变量是否满足前置条件。
- 断言是否覆盖真实业务语义。

## 9. fixture / client / helper / profile 边界

这四个概念容易混，需要保持职责清楚。

| 概念 | 职责 | 示例 |
|---|---|---|
| helper | 通用技术工具 | HTTP 请求、gRPC 调用、Redis 操作、等待轮询、脱敏 |
| fixture | pytest 注入和生命周期入口 | 读取 env、创建 client、注册 cleanup、返回 factory |
| client/action object | 面向模块的测试动作库 | `client.login()`、`client.call_api()`、`client.query_state()` |
| profile | codegen 编排配置 | `variables`、`case_flows`、`case_bodies`、`request_overrides` |

典型调用关系：

```text
case_flow
  -> client/action object
  -> helper
  -> target_service public API
```

fixture 可以直接返回 client，也可以返回工厂函数。

直接返回 client：

```text
setup_target_module -> TargetModuleClient
```

返回工厂函数：

```text
setup_target_module -> client_factory
client_factory(case_id="TC-MOD-001") -> TargetModuleClient
```

工厂函数适合真实项目，因为不同用例可能需要不同 case_id、变量、资源 alias 或 cleanup 上下文。

不要把 fixture 写成隐藏 pytest。fixture 提供动作和生命周期，case_flow 表达当前用例的流程和断言。

## 10. default / case_flow / case_body 怎么选

AITest 当前有三条主要生成路线：

| 路线 | 含义 | 适用场景 |
|---|---|---|
| `default_http/default_grpc` | 框架自动拼请求、自动调用默认接口、自动解析断言 | 单接口、请求结构稳定、每条用例只覆盖少量字段 |
| `structured_case_flow` | profile 明确写线性步骤，codegen 稳定渲染 pytest | 多端点但流程线性，需要保存中间变量或调用 client 动作 |
| `custom_case_body` | profile 直接给 pytest 函数体片段 | 分支、循环、try/finally、mock、进程、文件生命周期等复杂场景 |

选择规则：

| 场景 | 推荐路线 |
|---|---|
| 单接口、固定 endpoint、只改请求字段 | `default_http/default_grpc` |
| 多端点但流程线性 | `case_flow` |
| 需要保存中间变量 | `case_flow` |
| 需要用例级变量 | `case_flow` |
| 要删除字段或保留 raw response | `case_flow` |
| HTTP/gRPC/Redis 等动作混合 | `case_flow` + fixture/client |
| 有 if/else、for、try/finally | 封装到 helper/fixture，或使用 `case_body` |
| 多进程、mock、临时文件生命周期 | `case_body` 或 fixture 内封装 |
| 只适合人工观察 | `manual` |
| 可行性存疑 | `skipped` |

`case_flow` 不应被扩展成 YAML 版 Python。它应保持线性、可读、可校验。复杂控制流回到 Python helper、fixture 或 `case_body`。

`case_body` 是必要逃生通道，但不能成为默认路线。如果大量用例都需要 `case_body`，应检查：

- fixture/client 动作库是否太弱。
- 是否有重复流程可以封装成 helper。
- 是否有小能力值得加入 case_flow。
- 用例是否过度特殊化。

## 11. 人工 review 清单

AI 可以生成初稿，但这些判断必须由人 review：

- 知识库是否正确理解业务。
- Markdown 用例是否来自明确契约。
- 断言是否可观测。
- 用例是否测了真实业务语义，而不是只断言状态码或空泛成功。
- fixture 是否把 per-case 逻辑藏太深。
- client 动作是否可复用，还是每条用例一个隐藏实现。
- profile 是否过长、过散或过度依赖 raw expression。
- case_flow 是否保持线性清晰。
- case_body 是否有保留理由。
- env/resource 是否安全、可复现、可脱敏。
- report 中的 `SUT_BUG` 是否真的成立。

人工 review 的目标不是替 AI 重写全部内容，而是确认测试资产没有走偏。

## 12. 反模式

应避免以下做法：

- 直接修改 generated pytest。
- 绕过知识库，直接从零散文档写 pytest。
- fixture 里按 case_id 写死每条用例逻辑和断言。
- profile 变成大量 Python 表达式拼接。
- 把所有复杂场景都塞进 `case_body`。
- 缺 env 或缺测试数据时误判为待测系统 bug。
- 为了通过测试而放宽断言、skip 失败用例或伪造响应。
- 用例没有人工 review 就直接跑真实环境。
- 让 AI 在未明确边界时同时改 Markdown、fixture、profile、generated 和待测系统。

## 13. 推荐工作模式

推荐小步闭环：

```text
1. 先选一个模块或一条主链路。
2. 先生成少量高价值 Markdown 用例。
3. 先完成 target fixture/profile 最小动作库。
4. 先跑通 validate-profile / dump-ir / codegen / check / collect-only。
5. 再连接真实服务执行 aitest run。
6. 根据 report 做失败分流。
7. 修正后重复验证。
8. 稳定通过后再沉淀规则。
```

不要一开始追求覆盖整个系统。AITest 的收益来自长期可维护的测试飞轮，而不是一次性生成大量不可审查的 pytest。

## 14. 与其他文档的关系

| 文档 | 用途 |
|---|---|
| [Quickstart](./aitest_quickstart.md) | 快速安装、初始化和跑通第一轮体检 |
| [Migration Guide](./aitest_migration_guide.md) | 新项目迁移步骤和完成标准 |
| [Profile Guide](./codegen_profile_guide.md) | module/suite profile 编写细节 |
| [Troubleshooting](./codegen_troubleshooting.md) | codegen 常见问题和排查 |
| [Code Reading Guide](./aitest_kit_code_reading_guide.md) | 想通读源码时的阅读路线 |

本文的定位是长期协作手册：当用户、AI 和 AITest CLI 一起维护测试资产时，如何分工、如何路由、如何避免偏离测试飞轮。
