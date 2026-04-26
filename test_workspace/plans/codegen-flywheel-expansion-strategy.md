# Codegen 与测试飞轮扩展策略

> 背景：基于现有 skill、`business.md` 示例用例和 `test-execution-strategy.md` 的补充思路。目标不是只服务当前优惠券项目，而是抽象出更适合企业级通用测试流程和高可用测试能力的扩展方案。

## 一、核心判断

`codegen` 不应被设计成“AI 读取 Markdown 后自由编写 pytest”的工具。

更稳妥的定位是：

> `test-codegen` 是一个把已通过格式校验的 Markdown 可执行规格，确定性编译成 pytest 资产的生成器。AI 的职责是维护规范、迁移旧用例、解释失败和沉淀规则，而不是在每条测试代码里自由发挥。

这意味着：

1. Markdown 仍是唯一人工维护源。
2. codegen 可以有内部 IR，但 IR 不是人工维护的第二份用例。
3. pytest 文件是编译产物，可以提交仓库、CI 可跑，但不手工编辑。
4. 企业级规模下，codegen 的稳定性优先于短期灵活性。

## 二、当前主要矛盾

`TEST_SPEC` 已经定义了正确的黑盒接口测试方向：

- 测试以外部客户端调 HTTP / gRPC 接口执行。
- 待测服务作为独立进程运行。
- 禁止在测试中 import 服务内部模块。
- 禁止 mock 内部方法。
- arrange 通过 Redis、配置文件、管理 API、实验 API 等外部方式构造。

但当前部分 `business.md` 示例仍是旧式内部测试描述，例如：

- 引用 `tests/test_coupon_service.py` 中的 `biz` fixture。
- 直接调用 `biz.recommend_and_claim(...)`。
- 使用 `patch("coupon_system.services.xxx.time.time")`。
- 设置 `mock_scoring_client.score.return_value`。

这些用例适合组件级或白盒单元测试，但不适合作为企业级黑盒 codegen 的直接输入。

因此，codegen 之前必须先解决测试层级定义问题，不能让生成器在旧格式自由文本中猜测执行方式。

## 三、Markdown 的两层含义

Markdown 可以继续作为唯一人工维护源，但同一份 Markdown 里需要区分两类信息：

1. 人类可读的测试设计信息：
   - 为什么测。
   - 覆盖哪个业务规则。
   - 风险点是什么。
   - 与知识库或需求的关系是什么。

2. 机器可解析的执行规格：
   - setup。
   - request。
   - assert。
   - teardown。
   - execution level。
   - test layer。
   - interface。
   - env profile。

codegen 只读取机器可解析部分。自由文本可以保留给人 review，但不能作为生成 pytest 的推理来源。

建议链路：

```text
知识库
  ↓
Markdown 测试设计
  ↓
Markdown 可执行规格
  ↓
case-lint
  ↓
IR
  ↓
pytest
```

IR 可以是 codegen 内部的 dict / JSON AST，也可以输出到 `tests/generated/.cache/` 用于调试。它不是人工编辑层，因此不违背“Markdown 是唯一数据源”的原则。

## 四、codegen 的推荐阶段

### 1. Case Normalize

读取 `business.md` / `boundary.md`，将用例转为统一结构。

旧格式用例如果不可解析，不猜测、不补脑，输出为不可 codegen 的问题项。

### 2. Case Lint

检查用例是否满足可执行条件：

- 是否有 `执行级别`：`L-Auto` / `L-Semi` / `L-Manual`。
- 是否有 `测试层级`：`API` / `Contract` / `Component` / `E2E` / `Chaos` / `Perf` / `Security` / `Observability`。
- HTTP 是否有 method、path、完整 JSON body。
- gRPC 是否有 service、method、完整 message。
- setup 是否只使用已注册的外部能力，如 `[redis]`、`[http]`、`[file]`、`[experiment]`。
- assert 是否是受支持表达式。
- teardown 是否能清理 setup 产生的数据。
- 用例 ID 是否唯一。
- 是否出现禁止内容：内部 fixture、内部 import、内部 patch、mock 内部 client。

Markdown 不通过 lint 时，禁止 codegen。

### 3. Lower To IR

将 Markdown 降级为统一中间结构，例如：

```json
{
  "case_id": "TC-CAL-009",
  "module": "calibration",
  "execution_level": "L-Auto",
  "test_layer": "API",
  "interface": {
    "type": "http",
    "method": "POST",
    "path": "/api/v1/recommend",
    "body": {}
  },
  "setup": [
    {
      "type": "redis",
      "command": "SET",
      "key": "coupon:stock:COUPON_ACT_001",
      "value": "100"
    }
  ],
  "assertions": [
    {
      "type": "response_expr",
      "expr": "response.code == 0"
    },
    {
      "type": "relation_expr",
      "expr": "cal == clamp(1.5 * s + 0.0, 0, 1)"
    }
  ],
  "teardown": []
}
```

### 4. Emit Pytest

用确定性模板生成 pytest：

- 文件名稳定。
- 函数名稳定。
- case id 进入 pytest node id / marker。
- 生成代码不手改。
- 重新生成可覆盖同名文件。
- 文件 header 写明来源 Markdown、生成器版本和生成时间。

## 五、不建议兼容过多旧格式

旧格式如：

```markdown
- **前置条件**：按 tests/test_coupon_service.py 中 biz fixture 的构造方式初始化...
- **输入**：调用 biz.recommend_and_claim(...)
- **预期结果**：返回 {...}
```

不应由 codegen 直接兼容。

原因：

- 会迫使 codegen 做自然语言理解。
- 会诱导 AI 猜测 fixture、mock、内部调用方式。
- 同类用例生成风格会不一致。
- CI 失败时难以区分业务错误、用例错误还是生成器理解错误。
- 换项目后很难复用。

建议：

1. `test-codegen` 只支持新规范。
2. 旧格式由 `case-migrate` 或 `test-fix` 迁移。
3. 不可迁移的旧用例标为 `L-Manual` 或 `Component`，不要混入黑盒 API codegen。

## 六、执行级别与测试层级分离

现有执行策略中的执行级别：

- `L-Auto`
- `L-Semi`
- `L-Manual`

建议继续保留，但补充独立的测试层级字段：

```markdown
- **执行级别**：L-Auto / L-Semi / L-Manual
- **测试层级**：API / Contract / Component / E2E / Chaos / Perf / Security / Observability
```

两者解决的问题不同：

| 字段 | 解决的问题 |
|------|------------|
| 执行级别 | 这条用例能否自动执行 |
| 测试层级 | 这条用例测试的系统边界是什么 |

示例：

| 场景 | 执行级别 | 测试层级 | codegen 处理 |
|------|----------|----------|--------------|
| 参数校验 HTTP 请求 | L-Auto | API | 生成 pytest |
| HTTP/gRPC 响应一致性 | L-Auto | Contract | 生成 pytest |
| 日志包含 trace_id | L-Semi | Observability | 请求自动化，日志检查注释或辅助断言 |
| Redis 故障恢复 | L-Auto / L-Semi | Chaos | 依赖环境能力，支持则生成 |
| 内部函数 patch time | L-Auto | Component | 走组件测试 codegen，不混入黑盒 API 测试 |
| UI 视觉检查 | L-Manual | E2E/UI | 不生成 pytest 或生成 manual marker |

## 七、test-codegen skill 职责边界

### 负责

- 读取 `aitest_config/config.yaml`。
- 读取 `TEST_SPEC`。
- 读取 `case-format.md`。
- 读取目标模块 Markdown cases。
- 校验用例是否可执行。
- 生成 `tests/generated/test_{module}.py`。
- 生成或更新 `tests/generated/manifest.json`。
- 输出不可生成用例列表和原因。
- 运行格式检查、编译检查、pytest 收集检查。

### 不负责

- 修改业务源码。
- 修改 `.env`。
- 推断未写明的 setup。
- 从自然语言里猜 HTTP body。
- 给不确定断言脑补期望值。
- 为了通过测试放宽断言。
- 手写一次性 pytest 逻辑绕过规范。
- 把内部单元测试伪装成黑盒测试。

## 八、建议扩展的 skill 链路

现有飞轮：

```text
doc-review
  ↓
doc-gen
  ↓
knowledge-build
  ↓
test-design
  ↓
test-fix
```

建议扩展为：

```text
doc-review
  ↓
doc-gen
  ↓
knowledge-build
  ↓
test-design
  ↓
case-review / case-lint
  ↓
case-migrate / case-fix
  ↓
test-codegen
  ↓
test-execute
  ↓
test-triage
  ↓
test-fix
  ↓
knowledge-update / spec-update
```

新增能力建议：

| Skill | 作用 |
|-------|------|
| `case-lint` | 只检查 Markdown 是否符合可执行规范，不生成代码 |
| `case-migrate` | 把旧格式用例迁移到新格式，保留业务意图 |
| `test-codegen` | 从已通过 lint 的用例生成 pytest |
| `test-execute` | 启动或连接测试环境，执行 pytest，收集报告 |
| `test-triage` | 对失败结果分类：环境失败、用例错误、产品 bug、生成器 bug |
| `test-report` | 汇总覆盖、通过率、失败原因、关联需求 |
| `fixture-gen` / `harness-gen` | 为项目生成 `tests/conftest.py` 和 `tests/helpers/` 适配层 |

## 九、企业级通用性的关键：Adapter

不要把当前优惠券系统的领域知识写进通用 codegen。

通用 codegen 只认识通用动作：

```text
[http]
[grpc]
[redis]
[file]
[db]
[kafka]
[queue]
[env]
[clock]
[log]
[metric]
[browser]
[command]
```

具体项目动作通过 adapter 提供：

```text
tests/helpers/
  http.py
  grpc.py
  redis_ops.py
  assertions.py
  adapters/
    coupon.py
    ab_experiment.py
```

Markdown 中可以写领域动作：

```markdown
- [domain:coupon.stock] COUPON_ACT_001 = 100
- [domain:user_features] u001 = {"gender":"female"}
- [domain:ab_whitelist] u001 = {"calibration_exp_game":"cal_on"}
```

codegen 不直接理解“库存”“用户特征”“AB 白名单”，只生成对项目 adapter 的调用：

```python
coupon.set_stock("COUPON_ACT_001", 100)
coupon.set_user_features("u001", {"gender": "female"})
ab.set_whitelist("u001", {"calibration_exp_game": "cal_on"})
```

这样迁移到其他企业项目时，通用 codegen 不变，只替换 adapter。

## 十、高可用测试能力的扩展位置

高可用能力不能只靠 codegen，应进入知识库、用例格式、执行环境和 triage 闭环。

建议在 L1 模块知识库中补充：

```markdown
## 可靠性契约
- 依赖 Redis 不可用时行为
- 下游 HTTP/gRPC 超时时行为
- 重试次数与退避策略
- 幂等键
- 超时预算
- 降级响应格式
- 熔断/限流行为
- 数据一致性要求
- 可观测信号：日志、metric、trace、告警
```

用例层面支持：

```markdown
- **测试层级**：Chaos
- **fault**：
  - [dependency] redis unavailable
- **assert**：
  - response.code == 0
  - response.results.length == 0
  - [metric] coupon_dependency_error_total{dep="redis"} increased_by 1
  - [manual] 告警在 5 分钟内触发
```

执行层根据环境 profile 决定如何实现故障注入：

| 环境 | 可能实现 |
|------|----------|
| local | docker compose + toxiproxy |
| CI | testcontainers + toxiproxy |
| K8s | Chaos Mesh / Litmus |
| 服务网格 | Envoy fault injection |
| 可观测 | Prometheus / Loki / OpenTelemetry |

codegen 只生成对 fault adapter 的调用，不直接绑定某个基础设施。

## 十一、执行环境 Profile

企业级执行需要 profile，避免测试代码硬编码端口、URL、凭据。

示例：

```yaml
profiles:
  local:
    http_base_url: http://localhost:8000
    grpc_target: localhost:50051
    redis_url: redis://localhost:6379/0
    fault_injection: disabled

  ci:
    http_base_url: ${HTTP_BASE_URL}
    grpc_target: ${GRPC_TARGET}
    redis_url: ${REDIS_URL}
    fault_injection: toxiproxy

  staging:
    http_base_url: ${STAGING_HTTP_BASE_URL}
    grpc_target: ${STAGING_GRPC_TARGET}
    redis_url: disabled
    fault_injection: mesh
```

生成出来的 pytest 不应写死端口、URL，应从配置或环境变量读取。

## 十二、generated 目录提交策略

建议企业级主干提交 `tests/generated/`。

同时在 CI 增加：

```text
test-codegen --check
```

用于验证 Markdown 和 generated 代码一致。

理由：

- CI 不应依赖 AI 临时生成。
- 提交生成物能让 pytest collection、IDE、覆盖率、测试分片稳定。
- 人主要 review Markdown diff。
- generated diff 作为编译产物，必要时可抽查。
- `--check` 可以防止 Markdown 改了但忘记重新生成。

建议目录：

```text
tests/
  conftest.py
  helpers/
  generated/
    test_calibration.py
    test_validation_ratelimit.py
    manifest.json
    README.md
```

`manifest.json` 示例：

```json
{
  "source": "test_workspace/cases/calibration/business.md",
  "case_ids": ["TC-CAL-005", "TC-CAL-006"],
  "generator_version": "0.1.0",
  "generated_at": "2026-04-26T00:00:00Z"
}
```

## 十三、对现有执行策略的补充建议

建议在 `test-execution-strategy.md` 后续版本中补充以下决策：

1. 增加 `case-lint` 阶段。
2. 增加 IR 概念，作为机器内部中间结构。
3. 明确 legacy 用例不直接 codegen。
4. 区分执行级别和测试层级。
5. 引入 project adapter。
6. 新增 `test-execute` / `test-triage` 闭环。
7. 明确 generated 目录是否提交，以及 `codegen --check` 策略。
8. 明确高可用测试依赖执行环境能力，不由 codegen 单独承担。

## 十四、当前项目的建议落地顺序

### 阶段 1：规范冻结

选择一个模块做样板，建议优先 `calibration`。

原因：

- `calibration/business.md` 已经接近共享配置 + 精简用例格式。
- 相比 `validation_ratelimit`，它更少依赖内部 fixture 和 mock 描述。

需要补齐：

- `执行级别`。
- `测试层级`。
- 标准化 `setup/request/assert/teardown` 标签。
- 消除不可执行的自然语言 setup。

### 阶段 2：case-lint

先把 lint 规则写入 `TEST_SPEC` 和 `case-format.md`。

可以先人工执行，再实现脚本。

### 阶段 3：测试工具层

建立：

```text
tests/
  conftest.py
  helpers/
    http.py
    redis_ops.py
    assertions.py
    config.py
```

第一阶段只支持 HTTP、Redis、基础断言。

### 阶段 4：最小 codegen

只支持：

- `[http]`
- `[redis]`
- response 结构断言
- 简单关系断言
- `[manual]` 注释

先生成 3 到 5 条 pytest，跑通完整链路。

### 阶段 5：协议和可靠性扩展

再扩展：

- gRPC。
- 日志断言。
- metrics 断言。
- fault injection。
- contract 对齐测试。
- test-triage。

## 十五、最终目标飞轮

建议最终飞轮形态：

```text
需求/设计文档
  ↓ doc-review
文档质量审查报告
  ↓ doc-gen
面向测试的设计文档
  ↓ knowledge-build
L0/L1/L2 测试知识库
  ↓ test-design
Markdown 测试用例
  ↓ case-lint
可执行性校验报告
  ↓ case-migrate / test-fix
规范化 Markdown 用例
  ↓ test-codegen
pytest generated tests
  ↓ test-execute
执行报告、覆盖报告、失败日志
  ↓ test-triage
失败归因：产品 bug / 用例错误 / 环境问题 / 生成器问题 / 文档缺口
  ↓ test-fix / knowledge-build / doc-review
沉淀回 TEST_SPEC、知识库、用例和 skill
```

这个飞轮的重点不是“能生成测试代码”，而是能够持续完成：

- 规范化。
- 可执行化。
- 自动执行。
- 失败归因。
- 知识回写。
- 规则沉淀。

企业级测试系统的长期价值主要来自后四项。

## 十六、待进一步讨论的问题

1. 是否接受 `IR` 作为机器内部中间产物，但不作为人工维护源。
2. `Component` 层测试是否纳入同一个 codegen，还是拆成独立 skill。
3. 旧格式用例是批量迁移，还是按模块逐步迁移。
4. `generated/` 是否提交 git。
5. 首个样板模块选 `calibration` 还是 `validation_ratelimit`。
6. 高可用测试第一阶段支持到什么程度：日志、metric、fault injection 是否都纳入首版。
7. project adapter 的规范是否先在当前项目里试点，再抽象为通用约定。
