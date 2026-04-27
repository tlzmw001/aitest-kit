# validation_ratelimit 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/validation_ratelimit
> 生成日期：2026-04-25

---

## 一、限流后端异常

### TC-RATE-004：Redis 限流检查抛异常时请求直接失败
- **关联**：L1/validation_ratelimit
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；设置 `config.rate_limit.enabled=True`、`config.rate_limit.max_qps=10`、`config.rate_limit.per_user_qps=10`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；使用 `patch.object(biz.redis, "check_rate_limit", side_effect=ConnectionError("redis down"))` 模拟 Redis 限流检查异常。
- **输入**：调用 `biz.recommend_and_claim(...)`，参数为 `user_id="u_rate_redis_error"`、`scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`、`req_id="req-rate-004"`、`score_threshold=0.5`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz` 并启用限流。
  2. 用 `patch.object(biz.redis, "check_rate_limit", side_effect=ConnectionError("redis down"))` 替换限流检查。
  3. 在 `pytest.raises(ConnectionError, match="redis down")` 作用域中调用 `biz.recommend_and_claim(...)`。
  4. 断言不会返回 `{"code": 1010}` 或 `{"code": 1001}` 业务错误体。
- **预期结果**：调用直接抛出 `ConnectionError("redis down")`；请求不会进入 `scene_router.route(...)`，也不会返回业务层错误码。

## 二、限流精度

### TC-RATE-005：同一时间戳的 3 次请求仍应按 3 次计数
- **关联**：L1/validation_ratelimit
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；设置 `config.rate_limit.enabled=True`、`config.rate_limit.max_qps=2`、`config.rate_limit.per_user_qps=10`、`config.rate_limit.window_seconds=1`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`；使用 `patch("coupon_system.services.redis_store.time.time", return_value=1000.0)` 固定所有限流检查时间戳为同一个值。[!可行性存疑: 当前实现使用 `str(now)` 作为 Redis ZSET member，同一时间戳下可能发生 member 覆盖，导致第 3 次请求未被限流；详见 `mismatch.md`]
- **输入**：连续调用 3 次 `biz.recommend_and_claim(...)`；三次参数仅 `user_id` 不同，依次为 `u_rate_same_ts_1`、`u_rate_same_ts_2`、`u_rate_same_ts_3`；其余参数均为 `scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`、`req_id="req-rate-same-ts-{n}"`、`score_threshold=0.5`、`max_claim_per_request=1`、`context={}`、`items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]`
- **测试步骤**：
  1. 初始化 `biz` 并启用全局限流，设置 `max_qps=2`、`per_user_qps=10`。
  2. 使用 `patch("coupon_system.services.redis_store.time.time", return_value=1000.0)`，让三次调用的限流检查都使用同一个时间戳。
  3. 连续调用三次 `biz.recommend_and_claim(...)`，每次换一个 `user_id`，避免触发用户级限流。
  4. 记录三次返回的 `code`。
  5. 断言全局限流仍按“请求次数”而不是“唯一时间戳数”计数。
- **预期结果**：前 2 次返回 `code=0`；第 3 次返回 `code=1010`。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/validation_ratelimit | 限流 Redis 异常时行为、并发/同时间戳请求下的限流精度 | 无 |
