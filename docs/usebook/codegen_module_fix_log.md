# codegen 模块修复根因记录

本文档记录 Markdown 用例编译为 pytest 集成测试过程中，每个模块修复后的根因、修复方式和后续预防建议。

目标不是替代单个 bug 的详细复现文档，而是把跨模块反复出现的问题沉淀成可回顾、可预防的模式。后续每完成一个模块，就在本文追加一节。

## 记录格式

每个模块按以下信息记录：

- **修复状态**：已通过、部分通过、待测系统 bug 保留失败等。
- **初始失败现象**：pytest 或 codegen 暴露出的直接错误。
- **根因分类**：Markdown 用例、codegen emitter、codegen profile、fixture、环境、待测系统 bug。
- **具体根因**：导致失败的直接原因。
- **修复方式**：实际修改了哪些测试侧资产。
- **验证结果**：codegen、编译、pytest 的最终结果。
- **预防建议**：后续生成同类模块时应提前检查的规则。

## 总览

| 模块 | 修复状态 | 主要根因分类 | 当前验证结果 | 备注 |
|------|----------|--------------|--------------|------|
| `ab_experiment` | 已通过（已知缺陷用例不生成） | Markdown 用例、codegen emitter、fixture、待测系统 bug | `10 passed` | `TC-AB-005/010` 已记录为 `scene_experiments.json` 热更新能力缺失 |
| `ab_service` | 已通过 | Markdown 用例、codegen profile、fixture、codegen emitter 能力缺口 | `40 passed` | 非推荐接口模块，不能走默认 `/api/v1/recommend` 模板 |
| `feature_scoring` | 已通过 | Markdown 用例、codegen profile、fixture、codegen emitter 路径解析、环境可构造性 | `13 passed` | 5 条不可执行边界场景已标记可行性存疑 |

## ab_experiment

### 修复状态

已通过。测试侧 codegen/fixture 问题已修复，`TC-AB-005` 和 `TC-AB-010` 已按用户要求标记为待测系统 bug，不再作为当前 generated 可执行通过项生成。

最终模块结果：

```text
10 collected
10 passed
```

已知缺陷用例：

- `TC-AB-005`
- `TC-AB-010`

详细系统 bug 记录见：

- `test_workspace/results/ab_experiment_scene_experiments_hot_reload_bug.md`

### 初始失败现象

首次运行 `ab_experiment` 生成测试时，主要失败表现为：

- 多条 business 用例报 `NameError: name '_req' is not defined`
- `TC-AB-010` 断言缺少 `ab_boundary_left`
- 部分 case 级输入没有按场景变量传入，例如 `external=1`、`scene_name="ad"`、指定 `user_id/reqId`

### 根因分类

- Markdown 用例格式问题
- codegen emitter 能力缺口
- fixture 数据准备不一致
- 待测系统 bug

### 具体根因

1. Markdown 基础请求体不是合法 JSON。

   `business.md` 中基础请求体包含未加引号的模板变量：

   ```json
   "external": {{external}}
   ```

   parser 使用 `json.loads` 解析 Markdown 中的 ```json 代码块。该写法不是合法 JSON，导致 `base_request_http=None`，emitter 没有生成 `BASE_REQUEST` 和 `_req(...)` helper，最终所有调用 `_req(...)` 的测试报 `NameError`。

2. codegen 不支持 case 级请求覆盖。

   用例场景变量要求不同 case 使用不同的请求字段，例如：

   - `external=1`
   - `scene_name="ad"`
   - `device="pc"`
   - 指定 `user_id`
   - 指定 `reqId` / `req_id`

   旧 emitter 只生成默认 `u_ab_###` 和 `req_ab_###`，没有把 case 级覆盖注入到 `_req(...)`，导致部分用例没有真正执行其设计场景。

3. fixture 白名单用户和生成请求用户不一致。

   白名单 setup 使用的用户 ID 与 codegen 生成请求中的用户 ID 不一致，导致白名单前置条件没有命中。

4. `scene_experiments.json` 热更新能力缺失。

   `TC-AB-005` 和 `TC-AB-010` 依赖运行时修改场景到实验映射。当前主服务只在启动时加载一次 `coupon_system/config/scene_experiments.json` 到内存，没有 reload、watch、版本检查或管理接口。

   因此运行中修改配置不会影响后续请求。这个问题不是测试侧应通过放宽断言或伪造响应解决的问题，应保留为待测系统 bug；当前 generated 测试先不生成这两条可执行通过项。

### 修复方式

测试侧已完成：

- 将基础请求体改为合法 JSON，给 `external`、`scene_name`、`device` 等字段提供默认值。
- 在 `codegen_profile_ab_experiment.md` 中增加 `request_overrides`，按 case_id 显式声明请求覆盖。
- 扩展 `aitest_kit/codegen/emitter.py`，支持读取 profile 中的 `request_overrides`，并在 `_req(...)` 调用中注入覆盖字段。
- 调整 `test_workspace/tests/fixtures/ab_experiment.py` 中的白名单用户映射，使 setup 用户与生成请求一致。
- 将 `TC-AB-005`、`TC-AB-010` 的剩余失败记录到 `test_workspace/results/ab_experiment_scene_experiments_hot_reload_bug.md`。
- 在 Markdown 中将 `TC-AB-005`、`TC-AB-010` 标记为当前待测系统缺陷，等待主服务支持 `scene_experiments.json` 热更新后再恢复执行。

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_ab_experiment_business.py
  Cases:    7
  Manual:   1
  Skipped:  2
  Unparsed: 0

test_workspace/tests/generated/test_ab_experiment_boundary.py
  Cases:    3
  Manual:   1
  Skipped:  3
  Unparsed: 0
```

pytest：

```text
10 passed in 0.07s
```

相邻回归：

```text
calibration: 25 passed
```

### 预防建议

- Markdown 中标注为 `json` 的基础请求体必须是严格合法 JSON，不能直接写未加引号的模板表达式。
- 需要按用例改变请求字段时，不要只写自然语言场景变量；必须在 codegen profile 中有机器可读的 case 级覆盖规则。
- 白名单、用户 ID、请求 ID 这类前置条件必须与生成请求保持同一个来源，避免 setup 准备了 A 用户，请求却发送 B 用户。
- 依赖运行时修改配置文件的用例，必须先确认待测系统是否支持热更新；不支持时应记录为待测系统 bug，而不是在测试侧模拟成功。

## ab_service

### 修复状态

已通过。

最终模块结果：

```text
40 passed in 0.56s
```

### 初始失败现象

首次运行 `ab_service` 生成测试时，40 条全部失败，统一报：

```text
NameError: name '_req' is not defined
```

同时，检查生成文件发现所有用例都被生成成了对主服务推荐接口的调用：

```python
http_helper.post(http_base_url, "/api/v1/recommend", json=_req(...))
```

这与 `ab_service` 模块真实 API 不匹配。

### 根因分类

- Markdown 用例格式问题
- codegen profile 不完整
- fixture 覆盖不足
- codegen emitter 能力缺口

### 具体根因

1. Markdown 基础请求体不是合法 JSON。

   `business.md` 和 `boundary.md` 中基础请求体包含：

   ```json
   "experiment_names": {{experiment_names}}
   ```

   该写法不是合法 JSON，parser 无法解析基础请求体，导致 emitter 不生成 `_req(...)` helper。

2. `ab_service` 是多端点服务模块，不适合默认推荐接口模板。

   `ab_service` 目标接口包括：

   - `GET /health`
   - `POST /api/v1/ab/evaluate`
   - `GET /api/v1/ab/experiments`
   - `GET /api/v1/ab/experiments/{name}`
   - `POST /api/v1/ab/experiments`
   - `PUT /api/v1/ab/experiments/{name}`
   - `DELETE /api/v1/ab/experiments/{name}`
   - `GET /api/v1/ab/whitelist`
   - `PUT /api/v1/ab/whitelist`
   - `GET /api/v1/ab/whitelist/{user_id}`
   - `PUT /api/v1/ab/whitelist/{user_id}`
   - `DELETE /api/v1/ab/whitelist/{user_id}`
   - Remote SDK 调用

   旧 emitter 默认只知道推荐主服务 `/api/v1/recommend`，旧 `codegen_profile_ab_service.md` 也明确写着“接口路径映射需要后续增强”，因此即使 `_req` 生成成功，也会打错服务和接口。

3. 旧 profile 的断言基本是占位断言。

   多数断言被翻译为：

   ```python
   assert isinstance(resp, dict)
   ```

   这只能让测试“可收集”，不能验证真实业务行为。

4. fixture 没有完整支持实验 CRUD、白名单 CRUD、文件容错、持久化和 Remote SDK。

   `ab_service` 用例需要构造独立实验、白名单、临时 experiments/whitelist 文件、损坏文件、Remote SDK client 等。旧 fixture 只覆盖了少量前置操作。

### 修复方式

测试侧已完成：

- 将 `business.md` 和 `boundary.md` 中基础请求体改为合法 JSON：

  ```json
  "experiment_names": null
  ```

- 扩展 `aitest_kit/codegen/emitter.py`，支持 profile 中声明：

  - `extra_imports`
  - `case_fixtures`
  - `case_bodies`

  该能力是 opt-in。没有声明这些字段的模块仍走原默认生成逻辑。

- 重写 `test_workspace/tests/fixtures/ab_service.py`：

  - 通过 AB 服务公开 HTTP API 准备实验和白名单。
  - 对被覆盖的实验和白名单做 snapshot，并在 teardown 恢复。
  - 使用独立 `TestClient` 和 `tmp_path` 覆盖文件容错、持久化和 Remote SDK 场景。

- 重写 `test_workspace/tests/fixtures/codegen_profile_ab_service.md`：

  - 为 40 条用例声明真实请求路径、请求体和断言。
  - 不再使用默认 `/api/v1/recommend`。
  - 不再使用占位 `isinstance(resp, dict)` 断言。

- 重新生成：

  - `test_workspace/tests/generated/test_ab_service_business.py`
  - `test_workspace/tests/generated/test_ab_service_boundary.py`

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_ab_service_business.py
  Cases:    22
  Manual:   0
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_ab_service_boundary.py
  Cases:    18
  Manual:   1
  Skipped:  0
  Unparsed: 0
```

编译：

```text
Compiling 'aitest_kit/codegen/emitter.py'...
Compiling 'test_workspace/tests/fixtures/ab_service.py'...
Compiling 'test_workspace/tests/generated/test_ab_service_business.py'...
Compiling 'test_workspace/tests/generated/test_ab_service_boundary.py'...
```

pytest：

```text
40 passed in 0.56s
```

相邻回归：

```text
calibration: 25 passed
```

### 预防建议

- 非推荐接口模块不能默认套用 `/api/v1/recommend` 模板；codegen profile 必须明确请求入口。
- 多端点模块的 profile 不应只写断言 pattern，还应声明每条 case 的执行体或提供等价的结构化请求映射。
- `assert isinstance(resp, dict)` 只能作为临时占位，进入可执行集成测试阶段前必须替换为业务断言。
- 文件持久化、文件损坏、服务重启、Remote SDK 等场景优先使用隔离 `tmp_path` 和 `TestClient`，避免修改仓库默认配置文件或依赖全局服务状态。
- 通过公共 API 做前置条件，并在 teardown 恢复原状态；不要直接调用待测系统内部实现来“摆状态”。

## feature_scoring

### 修复状态

已通过。当前可执行用例全部通过。

最终模块结果：

```text
13 passed in 0.18s
```

codegen 结果：

```text
test_workspace/tests/generated/test_feature_scoring_business.py
  Cases:    8
  Manual:   6
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_feature_scoring_boundary.py
  Cases:    5
  Manual:   4
  Skipped:  5
  Unparsed: 0
```

### 初始失败现象

首次运行 `feature_scoring` 生成测试时，16 条用例中 12 条失败：

- business 文件 8 条全部报 `NameError: name '_req' is not defined`
- boundary 中 `TC-FEAT-009`、`TC-SCORE-006`、`TC-SCORE-007`、`TC-SCORE-009` 报 `KeyError: 'results[0]'`

### 根因分类

- Markdown 用例格式问题
- codegen emitter 路径解析问题
- codegen profile 请求覆盖缺失
- fixture 前置条件错位
- 环境可构造性不足

### 具体根因

1. business 基础请求体不是合法 JSON。

   `business.md` 中基础请求体包含：

   ```json
   "external": {{external}}
   ```

   parser 无法用 `json.loads` 解析该代码块，因此 `base_request_http=None`，emitter 不生成 `BASE_REQUEST` 和 `_req(...)`，最终所有 business 用例在运行时报 `NameError`。

2. emitter 把数组下标路径当成普通字典 key。

   断言：

   ```text
   response.body.results[0].item_id == "COUPON_FEAT_NOT_IN_TSV"
   ```

   被生成成：

   ```python
   assert resp["results[0]"]["item_id"] == "COUPON_FEAT_NOT_IN_TSV"
   ```

   实际响应结构是 `resp["results"][0]["item_id"]`，所以运行时报 `KeyError: 'results[0]'`。

3. profile 没有把场景变量中的请求覆盖落到 `_req(...)`。

   用例要求不同 case 使用不同的 `user_id`、`external`、`reqId/req_id` 和 `item_id`，旧 profile 只写了说明，没有机器可读的 `request_overrides`。生成代码仍使用默认 `u_feat_###` 和默认 item，占位 `{{item_id}}` 也会进入真实请求。

4. fixture 准备的用户和请求用户不一致。

   旧 fixture 使用 `u_score_{tc_num}` 写用户特征，但生成请求使用 `u_feat_###` 或用例要求的业务用户 ID，导致用户特征、AB 白名单和真实请求没有命中同一个用户。

5. 打分故障兜底边界场景当前不可在集成环境按 case 构造。

   `TC-SCORE-006`、`TC-SCORE-007`、`TC-SCORE-009` 分别要求内部 gRPC 打分服务超时、不可用和抛出 `RuntimeError`。源码中的 mock scorer 有内部开关，但当前以独立进程运行的 gRPC mock 服务没有公开 HTTP/gRPC 控制接口，pytest fixture 不能按单条用例切换故障状态。

   这些场景在旧单元测试里通过 mock `scoring_client.score.side_effect` 覆盖，但当前集成测试约定不能直接调用或替换待测系统内部对象。因此这几条已标记为可行性存疑，等待测试环境提供可控 mock 服务能力后再恢复执行。

### 修复方式

测试侧已完成：

- 将 `feature_scoring/business.md` 中的 `external` 默认值改为合法 JSON 值 `0`。
- 在 `codegen_profile_feature_scoring.md` 中补充 `request_overrides`，覆盖每条可执行用例的 `user_id`、`external`、`reqId/req_id` 和 `items`。
- 在 `codegen_profile_feature_scoring.md` 中补充 boundary 通用断言规则，消除 `除明确异常外，response.code == 0` 的不可解析项。
- 扩展 `aitest_kit/codegen/emitter.py` 的通用路径渲染，支持 `results[0].field` 生成 `resp["results"][0]["field"]`。
- 调整 `test_workspace/tests/fixtures/feature_scoring.py`：
  - 通过主服务 admin API 初始化库存和用户特征。
  - 通过 AB 服务白名单强制关闭粗排和校准，避免其他模块实验影响打分断言。
  - 让 fixture 的用户 ID 与 profile 生成请求保持一致。
  - teardown 清理本模块写入的 AB 白名单。
- 将 `TC-SCORE-006`、`TC-SCORE-007`、`TC-SCORE-009` 标记为可行性存疑；加上原有 `TC-FEAT-005`、`TC-SCORE-008`，boundary 当前共跳过 5 条不可执行用例。

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_feature_scoring_business.py
  Cases:    8
  Manual:   6
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_feature_scoring_boundary.py
  Cases:    5
  Manual:   4
  Skipped:  5
  Unparsed: 0
```

编译：

```text
Compiling 'aitest_kit/codegen/emitter.py'...
Compiling 'test_workspace/tests/fixtures/feature_scoring.py'...
Compiling 'test_workspace/tests/generated/test_feature_scoring_business.py'...
Compiling 'test_workspace/tests/generated/test_feature_scoring_boundary.py'...
```

pytest：

```text
13 passed in 0.18s
```

相邻回归：

```text
calibration: 25 passed
```

### 预防建议

- feature/scoring 这类模块的用例既依赖请求字段，又依赖外部服务路由；必须在 profile 中用结构化 `request_overrides` 固化 case 输入。
- 断言里出现 `results[0].field`、`items[0].field` 这类路径时，codegen 必须按数组访问生成，不能把 `results[0]` 当作字段名。
- fixture 的用户 ID、AB 白名单、Redis 用户特征和请求体必须来自同一份 case 映射。
- 如果边界场景要求外部依赖按用例故障注入，先确认 mock 服务是否有公开控制接口；没有时应标记不可执行，并推动测试环境补齐控制能力。

## issuance

### 初始失败

```text
18 collected, 18 failed
NameError: name '_req' is not defined
```

### 根因

1. `business.md` 和 `boundary.md` 的基础请求体不是合法 JSON，包含 `{{score_threshold}}`、`{{max_claim_per_request}}`、`{{items}}` 占位符，parser 输出 `HTTP body keys: None`，emitter 因此没有生成 `BASE_REQUEST` 和 `_req`。
2. 多条 issuance 用例不是单次推荐请求：
   - `TC-ISSUE-004/005/009/010` 需要额外调用库存、HTTP 查询或 gRPC 查询接口。
   - `TC-ISSUE-007/008` 需要同一业务场景下发起两次请求并比较结果。
   - `TC-ISSUE-013` 需要并发请求。
   默认单请求模板会生成可收集但无效的占位断言。
3. `TC-ISSUE-003/007` 使用 `score_threshold=1.01` 表示“高于分数上界不发放”，但服务实现 `_resolve_claim_controls` 明确要求阈值在 `[0.0, 1.0]` 内，`1.01` 是非法参数，会返回 `1001`，不属于“合法请求成功但 coupon 为空”场景。
4. `TC-ISSUE-010` 覆盖 gRPC 查询接口，但测试 helper 只有 `Recommend`，没有 `QueryUserCoupons`。
5. “最高分库存不足后尝试下一张”这类场景如果依赖真实 mock scoring，由于 mock 分数含随机噪声，探测请求得到的 top/second 不能保证下一次请求仍然一致；这会让测试不稳定。

### 修复方式

- 将 `issuance` 的基础 HTTP 请求体改成严格合法 JSON，给 `score_threshold`、`max_claim_per_request` 和默认 `items` 提供可执行默认值。
- 将 `TC-ISSUE-003/007` 的高阈值请求从 `1.01` 修正为合法边界值 `1.0`，保留“合法请求不发放”的测试意图。
- 重写 `test_workspace/tests/fixtures/issuance.py`：
  - 统一构造 issuance 请求体和 coupon item。
  - 通过主服务 admin API 初始化库存。
  - 通过 AB 服务白名单关闭粗排和校准，避免跨模块实验影响发放断言。
  - 通过 Redis tracker 清理用户领取集合、实例集合和对应 instance key，保证重复运行隔离。
  - 提供 HTTP/gRPC recommend、HTTP 查询、gRPC 查询、库存查询等操作方法。
- 扩展测试 helper：
  - `redis_ops.RedisTracker.smembers()` 用于清理用户实例集合。
  - `grpc_ops.query_user_coupons()` 用于覆盖 `CouponService/QueryUserCoupons`。
- 将 `codegen_profile_issuance.md` 改为 `case_bodies` 驱动，为多请求、查询、并发和库存副作用用例生成真实 pytest 代码。
- 对库存兜底尝试下一张的用例，使用服务已有 `policy_fallback_001` 固定同分结果，避免依赖随机打分排序，同时不指定打分服务返回值。

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_issuance_business.py
  Cases:    10
  Manual:   0
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_issuance_boundary.py
  Cases:    8
  Manual:   0
  Skipped:  2
  Unparsed: 0
```

编译：

```text
Compiling 'test_workspace/tests/helpers/redis_ops.py'...
Compiling 'test_workspace/tests/helpers/grpc_ops.py'...
Compiling 'test_workspace/tests/fixtures/issuance.py'...
Compiling 'test_workspace/tests/generated/test_issuance_business.py'...
Compiling 'test_workspace/tests/generated/test_issuance_boundary.py'...
```

pytest：

```text
18 passed in 0.18s
```

相邻回归：

```text
calibration: 25 passed
```

### 预防建议

- 只要用例需要库存查询、用户券查询、并发或多次请求，就不要依赖默认单请求模板，应直接使用模块 profile 的 `case_bodies`。
- 请求级参数的边界必须先对照服务端校验规则；非法参数用例和合法无发放用例要分开设计。
- 不能通过“先探测一次随机打分”来稳定下一次请求的 top/second；若测试目标是发放逻辑，应使用服务已有确定性路径或可控测试环境能力。
- gRPC 覆盖不只包括 `Recommend`，模块涉及查询 RPC 时 helper 也要补齐对应 RPC 客户端。

## logging

### 初始失败

```text
9 collected, 8 failed, 1 passed
NameError: name '_req' is not defined
```

### 根因

1. `business.md` 基础 HTTP 请求体中仍包含 `{{external}}`，不是合法 JSON，parser 输出 `HTTP body keys: None`，emitter 因此没有生成 `BASE_REQUEST` 和 `_req`。
2. 原 `codegen_profile_logging.md` 将日志断言翻译成 `assert isinstance(resp, dict)`，只能证明接口有响应，不能验证 `recommend request:` 日志字段，属于占位断言。
3. 日志用例的真实断言依赖 stdout/stderr 采集；当前全局集成测试只连接已启动的主服务进程，pytest 无法直接读取该进程日志。

### 修复方式

- 将 `test_workspace/cases/logging/business.md` 的基础请求体改成合法 JSON，`external` 使用默认值 `0`。
- 重写 `test_workspace/tests/fixtures/logging.py`：
  - 每个日志用例按需启动一个独立主服务子进程。
  - 使用随机 HTTP/gRPC 端口，避免与已运行服务冲突。
  - 子进程入口先调用 `logging.basicConfig(level=logging.INFO)`，再启动 `coupon_system.main.main()`。
  - 通过子进程 admin API 初始化库存。
  - 请求完成后停止进程并收集 stdout/stderr，供测试断言真实日志内容。
- 重写 `codegen_profile_logging.md`，用 `case_bodies` 生成真实日志断言：
  - `TC-LOG-001/003/006/010` 覆盖 HTTP 日志。
  - `TC-LOG-002/004` 覆盖 gRPC 日志。
  - `TC-LOG-005` 覆盖空 reqId 自动 UUID。
  - `TC-LOG-007/008` 保留 manual 的 route 下发隔离人工核验，但仍校验业务请求成功。

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_logging_business.py
  Cases:    8
  Manual:   2
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_logging_boundary.py
  Cases:    1
  Manual:   0
  Skipped:  3
  Unparsed: 0
```

编译：

```text
Compiling 'test_workspace/tests/fixtures/logging.py'...
Compiling 'test_workspace/tests/generated/test_logging_business.py'...
Compiling 'test_workspace/tests/generated/test_logging_boundary.py'...
```

pytest：

```text
9 passed in 6.06s
```

### 预防建议

- 日志类用例不能用响应结构占位代替日志断言；如果断言对象是 stdout/stderr，就必须提供可采集的进程或日志 handler。
- 已运行服务进程的日志不可被 pytest 直接读取时，应在 fixture 中启动隔离子进程并使用随机端口。
- Markdown 的基础请求体仍必须是合法 JSON；case 差异放到 profile 的 case body 或 request override 中。

## rough_ranking

### 初始失败

```text
23 collected, 23 failed
NameError: name '_req' is not defined
```

### 根因

1. `business.md` 和 `boundary.md` 的基础 HTTP 请求体使用 `items: {{items}}`，不是合法 JSON，parser 输出 `HTTP body keys: None`，emitter 没有生成 `_req`。
2. 旧 profile 将 `rank_input_items` 近似成 `resp["results"]` 的集合或首元素断言。两者语义不同：
   - `rank_input_items` 是主服务发给打分服务的候选顺序，验证粗排核心逻辑。
   - `response.results` 是打分后的响应结果，可能受打分返回顺序、分数和后续处理影响。
3. 粗排策略参数需要按 case 动态变化，但原 fixture 只在少量 case 上设置白名单，无法把每条用例的策略参数注入 AB 服务。
4. 要观测“打分服务实际收到的 item 顺序”，已运行主服务无法在测试进程内替换 scoring target，需要隔离启动主服务并改写 `COUPON_CONFIG_PATH`。

### 修复方式

- 将 rough_ranking 的 business/boundary 基础请求体改成合法 JSON，提供默认 `A/B/C` item 列表。
- 重写 `test_workspace/tests/fixtures/rough_ranking.py`：
  - 为每个 case 更新 AB 服务中的 `coarse_rank_exp_game.cr_v2_full.params`，teardown 恢复原实验配置。
  - 为用例用户设置白名单命中 `cr_v2_full` 或 `cr_off`，并关闭校准实验。
  - 启动记录型 gRPC scoring proxy，记录 `ScoringService/Score` 请求中的 `items[*].item_id`。
  - 复制 `settings.yaml` 到临时路径，改写 scoring 端口后用 `COUPON_CONFIG_PATH` 启动隔离主服务。
  - 通过隔离主服务 admin API 初始化库存。
- 重写 `codegen_profile_rough_ranking.md`，所有 case 使用 `case_bodies`，断言 `case.rank_input_items`，不再用响应集合替代粗排顺序。

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_rough_ranking_business.py
  Cases:    12
  Manual:   0
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_rough_ranking_boundary.py
  Cases:    11
  Manual:   5
  Skipped:  0
  Unparsed: 0
```

编译：

```text
Compiling 'test_workspace/tests/fixtures/rough_ranking.py'...
Compiling 'test_workspace/tests/generated/test_rough_ranking_business.py'...
Compiling 'test_workspace/tests/generated/test_rough_ranking_boundary.py'...
```

pytest：

```text
23 passed in 15.22s
```

### 预防建议

- 粗排、召回、过滤这类“中间阶段顺序”不能用最终响应顺序近似；需要在真实边界上加可观测代理或测试 hook。
- profile 中的断言映射不能把核心断言降级成集合包含或 `isinstance`，否则会丢失测试意图。
- 需要动态策略参数的模块应在 fixture 中保存原配置、按 case 更新、teardown 恢复，避免污染后续模块。

## scene_routing

### 初始失败

```text
15 collected, 13 failed, 2 passed
NameError: name '_req' is not defined
TC-ROUTE-010/017: assert 0.5 == 0.6
TC-ROUTE-013/018: assert 3001 == 1001
```

### 根因

1. `business.md` 基础请求体中 `scene_name`、`device`、`policy_id`、`external` 使用模板占位符，`external: {{external}}` 不是合法 JSON，导致 business generated 文件没有 `_req`。
2. `boundary.md` 虽然是合法 JSON，但默认值是字符串 `"{{scene_name}}"`、`"{{device}}"`、`"{{policy_id}}"`；没有 case 级请求覆盖时，实际请求命中未知场景，返回兜底 `scene_id=3001`，导致 `policy_id=""` 用例错误失败。
3. 原 fixture 只初始化库存，没有按用例设置 Redis 兜底分 key，三级兜底分用例依赖外部残留状态。
4. `TC-ROUTE-010/017` 暴露待测系统缺陷：场景级兜底分存在但非数字时，服务直接回配置默认值 `0.5`，没有继续读取全局 Redis 兜底分 `0.6`。

### 修复方式

- 将 `scene_routing` business/boundary 基础请求体改成合法且可执行的默认值：`scene_name=game`、`device=mobile`、`policy_id=""`、`external=0`。
- 在 `codegen_profile_scene_routing.md` 增加 `request_overrides`，把每条用例的 `scene_name`、`device`、`policy_id`、`external`、特殊 user_id 固化到 `_req(...)`。
- 扩展 `setup_scene_routing`：
  - 按 case 初始化 `COUPON_ROUTE_*` 库存。
  - 按 case 清理并设置 `coupon:fallback:score:3001`、`coupon:fallback:score:default`。
- 将 `TC-ROUTE-010/017` 记录为待测系统 bug：`test_workspace/results/scene_routing_fallback_invalid_scene_score_bug.md`，并在 Markdown 中标记为当前不可作为通过项生成。

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_scene_routing_business.py
  Cases:    9
  Manual:   0
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_scene_routing_boundary.py
  Cases:    4
  Manual:   0
  Skipped:  6
  Unparsed: 0
```

编译：

```text
Compiling 'test_workspace/tests/fixtures/scene_routing.py'...
Compiling 'test_workspace/tests/generated/test_scene_routing_business.py'...
Compiling 'test_workspace/tests/generated/test_scene_routing_boundary.py'...
```

pytest：

```text
13 passed in 0.08s
```

### 预防建议

- 合法 JSON 中的 `"{{field}}"` 仍然可能是错误默认值；只要 case 需要覆盖请求字段，就必须在 profile 中写机器可读 `request_overrides`。
- Redis 前置不能依赖运行环境残留，必须由 fixture 每条 case 清理后重建。
- 遇到可复现的待测系统规格不一致时，记录到 `test_workspace/results/`，不要用测试侧改断言掩盖。

## validation_ratelimit

### 初始失败

```text
27 collected, 25 failed, 2 passed
NameError: name '_req' is not defined
```

### 根因

1. `business.md` 基础请求体包含 `{{external}}`、`{{score_threshold}}`、`{{max_claim_per_request}}`，不是合法 JSON，parser 输出 `HTTP body keys: None`，generated 文件缺少 `_req`。
2. 原 profile 将 `response == err/limited`、schema loc、限流多请求断言都翻译成 `assert isinstance(resp, dict)`，没有验证错误体、422 loc 或限流行为。
3. HTTP helper 只有 `post()`，会对 422 调用 `raise_for_status()`，不适合 schema 校验用例。
4. 限流用例要求低 QPS 配置，但已运行主服务使用默认 `max_qps=1000/per_user_qps=10`，无法触发用例描述中的第 2 或第 3 次限流。
5. 原 fixture 清理的 key 是 `coupon:rl:*`，实际服务使用 `coupon:rate:global` 和 `coupon:rate:user:{user_id}`。

### 修复方式

- 将 `validation_ratelimit/business.md` 基础请求体改成合法 JSON，给控制字段设置默认值。
- 扩展 `test_workspace/tests/helpers/http.py`，新增 `post_response()`，用于保留 HTTP 422 response。
- 重写 `test_workspace/tests/fixtures/validation_ratelimit.py`：
  - 提供 `ERR`、`LIMITED` 标准响应体。
  - 统一构造 HTTP/gRPC 请求体。
  - 支持 gRPC optional 字段缺失请求。
  - 清理真实限流 key：`coupon:rate:global`、`coupon:rate:user:{user_id}`。
  - 对限流用例复制 `settings.yaml` 到临时文件，改写低 QPS 配置后用随机端口启动隔离主服务。
  - 对窗口恢复用例轮询 Redis key 消失，不依赖固定短 sleep。
- 重写 `codegen_profile_validation_ratelimit.md`，用 `case_bodies` 生成真实断言：
  - 参数校验断言完整 `ERR`。
  - schema 校验断言 422 和 `detail[*].loc`。
  - gRPC 缺字段断言业务错误体。
  - 限流用例显式发送 2/3 次请求并断言 `LIMITED`。

### 验证结果

codegen：

```text
test_workspace/tests/generated/test_validation_ratelimit_business.py
  Cases:    25
  Manual:   2
  Skipped:  0
  Unparsed: 0

test_workspace/tests/generated/test_validation_ratelimit_boundary.py
  Cases:    2
  Manual:   0
  Skipped:  4
  Unparsed: 0
```

编译：

```text
Compiling 'test_workspace/tests/helpers/http.py'...
Compiling 'test_workspace/tests/fixtures/validation_ratelimit.py'...
Compiling 'test_workspace/tests/generated/test_validation_ratelimit_business.py'...
Compiling 'test_workspace/tests/generated/test_validation_ratelimit_boundary.py'...
```

pytest：

```text
27 passed in 8.51s
```

### 预防建议

- Schema 断言必须保留 raw response，不能复用会自动 raise 的 JSON helper。
- 限流测试不能依赖默认服务配置；需要隔离服务和临时配置文件，且必须清理真实 Redis 限流 key。
- 多请求行为必须在 profile 中展开为多次调用，单请求模板不适合限流、重试、窗口恢复等场景。

## 跨模块已暴露的共性问题

### 1. Markdown JSON 块必须严格可解析

已在 `ab_experiment` 和 `ab_service` 重复出现。

错误模式：

```json
"field": {{value}}
```

正确模式：

```json
"field": null
```

或者给出一个合法默认值，再通过 profile 的请求覆盖在 case 级修改。

预防规则：

- codegen 前先跑 parser，确认 `HTTP body keys` 不是 `None`。
- 对所有 ```json 代码块执行严格 JSON 校验。

### 2. 自然语言场景变量不足以生成可执行测试

用例里写“请求覆盖：external=1”或“接口调用：GET /health”，如果没有结构化 profile 规则，emitter 不能可靠知道如何生成代码。

预防规则：

- 场景变量用于人读。
- codegen profile 用于机器生成。
- 只要请求路径、请求方法、请求体、用户 ID、环境文件、白名单或断言取值需要按 case 变化，就必须在 profile 中补充机器可读映射。

### 3. 默认推荐接口模板只适用于推荐主服务模块

`ab_service` 暴露了一个重要边界：不是所有模块都能映射到 `/api/v1/recommend`。

预防规则：

- 模块开始前先判定接口类型：
  - 推荐主服务模块：可用默认推荐接口模板。
  - 独立服务模块：必须声明模块专属 endpoint 或 case body。
  - SDK/导入/文件副作用模块：通常需要 fixture 或 case body 自定义执行逻辑。

### 4. 前置条件必须与生成请求一致

白名单、实验、用户 ID、请求 ID、临时文件路径如果分别由 fixture 和 emitter 各自猜，很容易错位。

预防规则：

- case_id 到前置条件的映射必须写在 fixture 或 profile 中。
- 用户 ID 和请求 ID 如果有业务含义，必须显式声明，不能依赖默认编号。
- teardown 必须恢复被覆盖的服务状态，尤其是实验配置和白名单。

### 5. 待测系统能力缺失要保留失败信号

`ab_experiment` 的热更新问题说明：测试侧不能为了通过而伪造系统能力。

预防规则：

- 如果用例要求系统支持某能力，但源码和运行行为确认不支持，应记录到 `test_workspace/results/`。
- 不跳过、不放宽断言、不伪造成功响应。
- 等待测系统修复后，再重新执行该模块验证。
