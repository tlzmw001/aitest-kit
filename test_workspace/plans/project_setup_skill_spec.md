# project-setup skill 设计方案

## 问题

现有 skill 覆盖了"设计 → 生成 → 执行 → 沉淀"的闭环，但缺少一个环节：**项目/模块的基础设施搭建**。

具体表现：

| 场景 | 需要做什么 | 现状 |
|------|-----------|------|
| 新项目接入 | 写 config.yaml、project_config.yaml | AI 没有引导，容易漏字段或猜错 |
| 新模块接入 | 写 fixture、codegen_profile | AI 参考已有模块模仿，但不知道该问什么 |
| 切换部署环境 | 改服务地址、环境变量 | 散落在各文件中，没有统一入口 |

这些步骤的共同特征：**AI 写得出代码，但正确性依赖于人提供的上下文（部署拓扑、隔离策略、可用 API）**。没有引导式对话，AI 会跳过问答直接猜，review 成本反而更高。

## 目标

一个 `project-setup` skill，覆盖两个子流程：

1. **新项目初始化** — 从零创建配置文件
2. **新模块接入** — 为已有项目添加模块的 fixture 和 profile

## 设计原则

- 问清楚再动手，不猜
- 生成的产物必须能被后续 skill（test-codegen、emitter-build）直接消费
- 不做编排，不替代其他 skill，只管基础设施

## 子流程一：新项目初始化

### 触发条件

`aitest_config/config.yaml` 不存在，或 `project_config.yaml` 不存在。

### AI 需要向用户确认的问题

**第一组：被测系统基本信息**

| # | 问题 | 用途 | 示例回答 |
|---|------|------|---------|
| 1 | 被测系统的技术栈？（语言、框架） | config.yaml service 段 | Python/FastAPI + gRPC |
| 2 | 服务入口地址？（HTTP/gRPC 分别） | config.yaml service.endpoints | HTTP localhost:8000, gRPC localhost:50051 |
| 3 | API 路径模式？（RESTful 前缀） | project_config.yaml api_path | /api/v1/ |
| 4 | 有哪些协议？只有 HTTP 还是也有 gRPC？ | config.yaml protocols | HTTP + gRPC |

**第二组：测试基础设施**

| # | 问题 | 用途 | 示例回答 |
|---|------|------|---------|
| 5 | 有没有外部依赖？（Redis、MySQL、MQ 等） | config.yaml data 段 | Redis localhost:6379 |
| 6 | 测试数据怎么隔离？（独立数据库/唯一 ID/teardown） | fixture 设计参考 | 每条用例用唯一 user_id，teardown 清 Redis key |
| 7 | 有没有管理/调试接口可用于 setup？ | fixture 设计参考 | 有白名单 CRUD 接口 |
| 8 | 已知的系统限制？（限流、缓存延迟、异步处理） | config.yaml known_limitations | 限流 100 QPS，Redis 缓存 5s 延迟 |

**第三组：项目结构映射**

| # | 问题 | 用途 | 示例回答 |
|---|------|------|---------|
| 9 | 有几个主要模块？大致的功能划分？ | project_config.yaml modules | calibration、scoring、routing 三个模块 |
| 10 | 每个模块的测试复杂度预期？（简单接口 / 多步骤 / 需隔离进程） | module_type 预判 | calibration 简单接口，logging 需要隔离进程 |

### 产出

```
aitest_config/
  config.yaml           ← 新建
  project_config.yaml   ← 新建
```

产出后建议用户执行 `aitest codegen --all --validate-profile` 验证。

## 子流程二：新模块接入

### 触发条件

用户要求为某模块生成测试，但以下文件不存在：
- `test_workspace/tests/fixtures/{module}.py`
- `test_workspace/tests/fixtures/codegen_profile_{module}.md`

### AI 需要向用户确认的问题

**前置**：先读已有模块的 fixture 和 profile 了解项目模式，减少重复提问。

| # | 问题 | 用途 | 示例回答 |
|---|------|------|---------|
| 1 | 这个模块的 API 端点？（可能有多个） | fixture + profile | POST /api/v1/recommend |
| 2 | 调用方式和已有模块（如 calibration）一样吗？还是有特殊的？ | module_type 判断 | 一样，标准 HTTP |
| 3 | setup 需要做什么？（初始化数据、配置实验、注册白名单等） | fixture setup 逻辑 | 需要先通过管理接口创建实验配置 |
| 4 | teardown 需要恢复什么？ | fixture teardown 逻辑 | 删除创建的实验配置 + 清 Redis 缓存 |
| 5 | 不同用例之间的差异主要在哪？（请求字段不同？前置条件不同？） | _CASE_CONFIGS 设计 | 每条用例的实验配置不同 |
| 6 | 有没有用例需要特殊处理？（多步骤、并发、进程隔离） | case_body/case_flow 预判 | TC-XXX-005 需要并发测试 |

### 产出

```
test_workspace/tests/fixtures/{module}.py              ← 新建
test_workspace/tests/fixtures/codegen_profile_{module}.md  ← 新建（初始版本，module_type + 空规则）
conftest.py                                            ← 追加 pytest_plugins 注册
```

### 产出后的衔接

fixture 和 profile 创建完成后，提示用户：

```
基础设施已就绪，建议执行：
1. aitest codegen {module} --validate-profile   ← 检查 profile 格式
2. /test-codegen {module}                       ← 生成 pytest 并补写 UNPARSED
```

## 与现有 skill 的关系

```
/project-setup（本 skill）
  ↓ 产出 config + fixture + 初始 profile
/test-codegen
  ↓ 消费 config + fixture + profile，生成 pytest
/emitter-build
  ↓ 从已验证 pytest 反向提取规则，更新 profile
/project-setup（维护场景）
  ↓ 新增模块时再次调用
```

project-setup 不编排其他 skill，只管"让基础设施就绪"。后续流程由用户自行触发或按 CLAUDE.md 的工作流引导。

## 不做什么

- 不做跨 skill 编排（已有 CLAUDE.md 工作流）
- 不做 fixture 逻辑调试（调试归 test-fix）
- 不做断言规则提取（归 emitter-build）
- 不替代 test-codegen 的首次使用检查（那个检查只是提醒，不是引导式对话）

## 实现优先级

1. **先做子流程二（新模块接入）** — 频率更高，价值更明确
2. 子流程一（新项目初始化）等有第二个项目实际接入时再验证和完善

## 待验证

- 问题列表是否完备？需要在第二个项目实际接入时根据遗漏补充
- fixture 的模板化程度：标准推荐接口的 fixture 结构高度相似，是否值得提供 fixture 模板？
- 和 test-codegen 的边界：test-codegen 发现 fixture 不存在时，应该提示"先跑 /project-setup"还是自动衔接？
