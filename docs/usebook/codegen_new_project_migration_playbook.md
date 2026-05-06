# 新项目 codegen 迁移 Playbook

本文档用于把当前 AI 自动化测试飞轮迁移到一个新的待测系统。它不是 codegen 架构说明，而是迁移操作手册：新项目第一次接入时，先允许 AI 探索未知；稳定后逐步把规则沉淀到配置、profile、fixture、helper 和 `case_flows`，最终让同类用例主要靠确定性 codegen 生成。

目标链路：

```text
开发文档
  -> 测试知识库
  -> Markdown 用例
  -> project_config / codegen_profile / fixture
  -> parser -> Case IR -> emitter
  -> generated pytest
  -> pytest 执行
  -> 修正、报告、规则晋升
```

## 一、迁移原则

新项目迁移时，先守住几条边界：

| 原则 | 说明 |
|---|---|
| Markdown 是测试设计源文件 | 不把 generated pytest 当长期手写源 |
| profile 是模块生成规则 | 模块差异优先沉淀到 `codegen_profile_{module}.md` |
| fixture/helper 是测试能力边界 | 环境编排、数据准备、查询副作用放在 fixture/helper |
| Case IR 是可观测中间层 | 用 `--dump-ir` / `--explain` 排查生成策略，不让 emitter 变黑盒 |
| AI 处理未知，代码处理稳定模式 | 初期可以有 UNPARSED / case_body，稳定后逐步规则化 |
| 不追求 100% case_flow | 并发、进程、文件生命周期、mock、复杂控制流继续保留 `case_body` |

迁移成功的标志不是所有模块都达到 L3/L4，而是：

- profile 硬门禁 0 ERROR。
- generated pytest 能 collect。
- 关键用例有真实业务断言，不靠弱断言凑自动化。
- 新增同类用例时，主要改 Markdown/profile，而不是反复手写 pytest。

## 二、迁移阶段

### Phase 0：确定迁移边界

先明确这次迁移的范围，避免一开始就把系统做重：

- 新项目名称、模块列表、第一批试点模块。
- 可读输入：开发文档、接口定义、配置样例、错误码、数据格式。
- 不可触碰范围：待测系统源码、生产配置、`.env`、外部依赖服务。
- 测试入口：HTTP、gRPC、SDK、CLI，或混合入口。
- 可控测试条件：请求参数、测试配置、Redis/DB 数据、管理 API、mock 服务。
- 可观测结果：响应体、状态码、日志、指标、存储副作用、外部调用记录。

第一批不要选最大模块，优先选“接口稳定、规则典型、断言可观测”的模块。

### Phase 1：构建知识库和 Markdown 用例

推荐顺序：

```text
docs/
  -> doc-review
  -> doc-gen（按需）
  -> knowledge-build
  -> test-design
  -> 人工 review
```

Markdown 用例需要满足 codegen 的基本输入要求：

- `## 共享配置` 使用统一 section 名。
- HTTP 基础请求体是合法 JSON，不出现 `{{var}}` 占位符。
- gRPC 用例在场景变量中明确写 `协议：gRPC` 或等价 protocol 字段。
- 可控输入写在请求覆盖、前置条件或 profile overrides 中。
- 系统中间产物不要写成前置条件。
- 断言只写真正要检查的业务契约；说明性文字放到说明里。

这一阶段允许出现无法自动化的用例，但要明确标注：

| 标记 | 使用场景 |
|---|---|
| `[manual]` | 需要人工观察日志、指标或外部平台 |
| `[!可行性存疑: ...]` | 当前测试基础设施无法稳定构造或观测 |
| mismatch / results 记录 | 用例暴露的是系统能力缺口或 bug |

### Phase 2：建立项目配置层

新项目至少需要检查或重建：

| 文件 | 作用 |
|---|---|
| `aitest_config/config.yaml` | 测试资产路径、服务地址、协议偏好、已知限制 |
| `aitest_config/project_config.yaml` | helper import、API path、变量映射、模块缩写、内置断言规则、module_type |
| `aitest_config/schemas/codegen_profile.schema.json` | profile/case_flow 结构契约，通常不随项目改 |

迁移时只改项目配置层，不改 codegen engine，除非能证明是框架通用能力缺失。

`project_config.yaml` 中优先沉淀跨模块稳定规则：

- 默认 HTTP/gRPC 调用方式。
- 通用 API path。
- 变量名映射。
- 模块缩写。
- 多模块共用的断言规则。
- `module_type` 及其必需字段。

### Phase 3：为首个模块建立 profile 和 fixture

每个模块固定有两类文件：

| 文件 | 作用 |
|---|---|
| `test_workspace/tests/fixtures/{module}.py` | 模块测试能力：构造条件、调用 helper、查询副作用、teardown |
| `test_workspace/tests/fixtures/codegen_profile_{module}.md` | 模块生成规则：overrides、assertion_rules、case_bodies、case_flows |

首版 profile 不要追求完美。建议按这个顺序补：

1. `module_type`：让 profile gate 知道模块类型。
2. `request_overrides`：把 case 级请求差异从 Markdown 自然语言转成结构化覆盖。
3. `assertion_rules`：把高频断言沉淀为规则。
4. `case_bodies`：先承接复杂、多步骤、生命周期类用例。
5. `case_flows`：等 case_body 跑通且结构稳定后再晋升。

不要为了消除 UNPARSED 写弱断言，例如 `assert isinstance(resp, dict)`。这类断言只能证明有响应，不能证明业务契约。

### Phase 4：执行 codegen 门禁

迁移期间每轮都按固定顺序收口：

```bash
python3 -m aitest_kit.cli codegen {module} --validate-profile
python3 -m aitest_kit.cli codegen {module} --dump-ir
python3 -m aitest_kit.cli codegen {module} --check
python3 -m aitest_kit.cli codegen {module}
python3 -m pytest test_workspace/tests/generated/test_{module}_*.py --collect-only -q
```

全量收口：

```bash
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli codegen --all --health-report --write-report
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

各命令的用途：

| 命令 | 关注点 |
|---|---|
| `--validate-profile` | JSON Schema、case_id、case_flow、module_type 是否正确 |
| `--dump-ir` | 每条用例的 strategy、protocol、fixture、assertion 来源 |
| `--explain TC-XXX` | 单条用例为什么走 HTTP/gRPC/case_body/case_flow/manual/skip |
| `--check` | generated 是否与当前 Markdown/profile 同步 |
| `--health-report --write-report` | 模块成熟度、UNPARSED、case_body/case_flow、断言命中统计 |

profile 有 ERROR 时不要绕过门禁继续生成；先修 profile 或 Markdown。

### Phase 5：运行 pytest 并分流失败

测试失败先分类，不急着改生成器：

| 失败类型 | 判断方式 | 处理 |
|---|---|---|
| Markdown 用例问题 | 断言不可观测、前置条件不是可控输入、用例和系统能力不一致 | 修改 Markdown 或转 mismatch/results |
| profile/codegen 问题 | IR strategy 错、overrides 错、assertion rule 误匹配 | 修 profile、project_config 或 codegen 通用逻辑 |
| fixture/helper 问题 | 前置没生效、teardown 缺失、副作用查询不准 | 修 fixture/helper |
| 测试环境问题 | 服务未启动、依赖不可达、隔离不足 | 修执行指南或测试基础设施 |
| 待测系统 bug | 用例合理且可复现，实际行为不符合契约 | 记录到 `test_workspace/results/` |

不要通过放宽断言、skip 失败用例、伪造响应来让测试变绿。

### Phase 6：沉淀和晋升

跑通后再做规则沉淀：

| 现象 | 晋升方向 |
|---|---|
| 多条用例只是请求字段不同 | `request_overrides` |
| 多条用例共享响应断言模式 | `assertion_rules` 或 project builtin rule |
| 断言需要参数化代码块 | named template |
| 多步骤流程稳定重复 | `case_flows` |
| Python 逻辑重复但流程复杂 | fixture/helper |
| 并发、进程、文件、mock 生命周期 | 保留 `case_body` |

晋升前先跑：

```bash
python3 -m aitest_kit.cli codegen {module} --analyze-promotion --write-report
python3 -m aitest_kit.cli codegen {module} --suggest-promotion-patch
```

promotion patch 只是 review 草案，不自动应用 profile。正式迁移时，删除旧 `case_bodies[case_id]`，新增 `case_flows[case_id]`，再跑 profile gate 和 collect。

## 三、生成路线决策表

| 场景 | 推荐路线 | 说明 |
|---|---|---|
| 标准单接口请求 + 响应字段断言 | 默认模板 + `request_overrides` + `assertion_rules` | 首选路线 |
| HTTP/gRPC 同结构对比 | 默认模板或 `case_flow` | 只有需要双调用/副作用查询时才上 `case_flow` |
| 多端点 CRUD | `case_flow` | 调 helper、保存结果、查询状态、断言 |
| 需要查询 Redis/DB 副作用 | `case_flow` 或 fixture helper | 查询能力放 helper，测试体保持结构化 |
| 需要隔离进程、日志捕获 | `case_body` | 不强行结构化 |
| 并发库存、竞态测试 | `case_body` | 控制流复杂，保留 Python 更清楚 |
| 文件持久化、mock 生命周期 | `case_body` | 生命周期比步骤表达更重要 |
| 当前无法稳定观测 | manual / skipped / results | 不做假自动化 |

## 四、真实参照一：logging 为什么保留 case_body

`logging` 是“不要强行 case_flow”的典型参照。

它的测试主体不是一次普通接口调用，而是：

- 启动隔离服务进程。
- 构造日志触发条件。
- 捕获 stdout/stderr 或日志文件。
- 等待服务生命周期和输出刷新。
- 断言日志内容。
- 清理进程和临时资源。

这些动作包含进程生命周期、时序等待、日志捕获和资源清理。把它们硬塞进 `case_flow` 会让 YAML 变成另一种 Python，而且不容易校验。正确做法是：

- 复杂生命周期继续放 `case_body`。
- 可复用的启动、等待、捕获、清理逻辑下沉到 fixture/helper。
- Markdown 只描述测试意图和可观测契约。
- health report 中看到 `case_body` 不一定是坏事，关键看它是否合理、是否重复、是否已有真实断言。

判断一个新项目里的日志类模块是否应保留 `case_body`，可以问：

1. 测试是否需要控制进程或线程生命周期？
2. 是否需要等待异步日志刷新？
3. 是否需要 monkeypatch、mock 或临时文件系统？
4. 如果改成 `case_flow`，是否只是把 Python 藏进 `expr` 字符串？

如果多数答案是“是”，保留 `case_body`。

## 五、真实参照二：feature_scoring 下一步更像测试环境增强

`feature_scoring` 是另一个参照：它不一定缺 codegen 架构，更多是测试环境能力要增强。

这类模块通常有这些特点：

- 输入可以通过推荐请求控制一部分。
- 中间特征、打分、外部服务响应并不总是黑盒可观测。
- 故障注入、慢响应、异常路径需要 mock 或可配置依赖。
- 有些断言不能只靠最终推荐响应稳定证明。

因此，`feature_scoring` 的下一步不一定是继续加 `case_flow`，而是先补测试能力：

- scoring mock 支持按 case_id 返回特征/分数/错误。
- fixture 能查询或记录外部打分请求。
- 对不可观测中间状态建立稳定观测点。
- 只有当“调用 -> 记录请求 -> 返回响应 -> 查询记录 -> 断言”稳定重复时，才晋升为 `case_flow`。

迁移到新项目时，如果遇到类似模块，不要急着把每个边界都写成 generated pytest。先判断测试入口是否足够可控，观测点是否足够稳定。否则应该记录为测试基础设施需求，而不是制造弱断言。
