# validation_ratelimit 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/validation_ratelimit
> 生成日期：2026-04-25

---

## 一、业务层参数校验

### TC-VAL-006：external 取值为 2 时返回参数无效
- **关联**：L1/validation_ratelimit
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`，并保持 `config.rate_limit.enabled=False`。
- **输入**：调用 `biz.recommend_and_claim(...)`，参数为 `user_id="u_val_external_002"`、`scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=2`、`req_id="req-val-006"`、`score_threshold=0.5`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz`，保持限流关闭，避免被 1010 分支干扰。
  2. 调用 `biz.recommend_and_claim(...)`，其中 `external=2`，其他字段均为合法值。
  3. 断言返回结果中的错误码和错误消息。
- **预期结果**：返回 `{"code": 1001, "message": "参数无效", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`。

### TC-VAL-007：score_threshold 大于 1.0 时返回参数无效
- **关联**：L1/validation_ratelimit
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`，并保持 `config.rate_limit.enabled=False`。
- **输入**：调用 `biz.recommend_and_claim(...)`，参数为 `user_id="u_val_threshold_high"`、`scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`、`req_id="req-val-007"`、`score_threshold=1.01`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz`，保持限流关闭。
  2. 调用 `biz.recommend_and_claim(...)`，其中 `score_threshold=1.01`，其他字段均为合法值。
  3. 断言返回结果中的错误码和错误消息。
- **预期结果**：返回 `{"code": 1001, "message": "参数无效", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`。

### TC-VAL-008：score_threshold 小于 0.0 时返回参数无效
- **关联**：L1/validation_ratelimit
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`，并保持 `config.rate_limit.enabled=False`。
- **输入**：调用 `biz.recommend_and_claim(...)`，参数为 `user_id="u_val_threshold_low"`、`scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`、`req_id="req-val-008"`、`score_threshold=-0.01`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz`，保持限流关闭。
  2. 调用 `biz.recommend_and_claim(...)`，其中 `score_threshold=-0.01`，其他字段均为合法值。
  3. 断言返回结果中的错误码和错误消息。
- **预期结果**：返回 `{"code": 1001, "message": "参数无效", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`。

## 二、请求标识

### TC-VAL-009：reqId 为空字符串时自动生成 UUID 并继续处理请求
- **关联**：L2/0402
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.75)]`；使用 `caplog.set_level("INFO")` 捕获日志。
- **输入**：调用 `biz.recommend_and_claim(...)`，参数为 `user_id="u_reqid_auto"`、`scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`、`req_id=""`、`score_threshold=0.5`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz`、`redis_store`、`mock_scoring_client`，并准备库存。
  2. 使用 `caplog` 打开 INFO 级别日志采集。
  3. 调用 `biz.recommend_and_claim(...)`，显式传入 `req_id=""`。
  4. 读取 `mock_scoring_client.score.call_args.kwargs["request_id"]`。
  5. 在 `caplog.records` 中查找包含 `recommend request:` 的日志行。
  6. 断言生成的 `request_id` 与日志中的 `reqId=` 值一致，且匹配 UUID 正则 `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`。
- **预期结果**：`result["code"] == 0`，`mock_scoring_client.score` 实际收到的 `request_id` 为自动生成的 UUID，日志中存在 `recommend request:` 且 `reqId=` 为同一个 UUID 字符串。

## 三、限流

### TC-RATE-002：全局限流达到上限时第 3 个请求返回 1010
- **关联**：L1/validation_ratelimit
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；设置 `config.rate_limit.enabled=True`、`config.rate_limit.max_qps=2`、`config.rate_limit.per_user_qps=10`、`config.rate_limit.window_seconds=1`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`。
- **输入**：连续调用 3 次 `biz.recommend_and_claim(...)`；三次参数仅 `user_id` 不同，依次为 `u_rate_global_1`、`u_rate_global_2`、`u_rate_global_3`；其余参数均为 `scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`、`req_id="req-rate-global-{n}"`、`score_threshold=0.5`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz`，并将限流参数设置为 `max_qps=2`、`per_user_qps=10`、`window_seconds=1`。
  2. 准备库存与打分 mock，确保业务流程本身可以正常返回 `code=0`。
  3. 在 1 秒窗口内，依次调用三次 `biz.recommend_and_claim(...)`，分别使用三个不同的 `user_id`。
  4. 记录三次调用返回的 `code`。
- **预期结果**：前 2 次返回 `code=0`；第 3 次返回 `{"code": 1010, "message": "请求过于频繁，请稍后重试", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`。

### TC-RATE-003：用户级限流窗口过期后请求恢复成功
- **关联**：L1/validation_ratelimit
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；设置 `config.rate_limit.enabled=True`、`config.rate_limit.max_qps=100`、`config.rate_limit.per_user_qps=1`、`config.rate_limit.window_seconds=1`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`；用 `patch("coupon_system.services.redis_store.time.time", side_effect=[1000.0, 1000.0, 1000.3, 1000.3, 1001.2, 1001.2])` 固定三次请求的全局/用户限流时间点。
- **输入**：对同一个 `user_id="u_rate_window"` 连续调用 3 次 `biz.recommend_and_claim(...)`；其余参数均为 `scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`、`req_id="req-rate-window-{n}"`、`score_threshold=0.5`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz`，并将限流参数设置为 `per_user_qps=1`、`window_seconds=1`。
  2. 使用 `patch("coupon_system.services.redis_store.time.time", side_effect=[1000.0, 1000.0, 1000.3, 1000.3, 1001.2, 1001.2])` 固定三个请求的时间。
  3. 在补丁作用域内，对同一 `user_id` 连续调用三次 `biz.recommend_and_claim(...)`。
  4. 记录三次调用返回的 `code`。
- **预期结果**：第一次返回 `code=0`；第二次返回 `code=1010`；第三次返回 `code=0`，证明 `window_seconds=1` 的限流窗口过期后计数已恢复。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/validation_ratelimit | external 非法值、score_threshold 上下边界非法值、全局限流触发、限流窗口过期后恢复 | 限流 Redis 异常时行为、并发请求下限流精度 |
| L2/0402 | reqId 为空时自动生成 UUID | 无（仅限 validation_ratelimit 范围） |
