# logging 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/logging
> 生成日期：2026-04-25

---

## 一、内部路由日志

### TC-LOG-004：external=0 时请求日志包含 route=1 和关键字段
- **关联**：L1/logging
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`；使用 `caplog.set_level("INFO")` 捕获日志。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_log_internal", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-log-004", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`，并打开 INFO 日志采集。
  2. 调用输入中的 `biz.recommend_and_claim(...)`。
  3. 在 `caplog.records` 中筛选包含 `recommend request:` 的日志行。
  4. 断言存在且仅存在 1 条匹配日志。
  5. 断言该日志包含 `reqId=req-log-004`、`user_id=u_log_internal`、`item_ids=COUPON_ACT_001`、`route=1`、`scene_id=1001`。
- **预期结果**：内部打分请求会打印一条 INFO 日志，且日志字段完整，`route=1` 表示内部打分服务。

### TC-LOG-005：reqId 为空字符串时自动生成 UUID 并写入日志
- **关联**：L2/0402
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`；使用 `caplog.set_level("INFO")` 捕获日志。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_log_uuid", scene_name="game", device="mobile", policy_id="", external=0, req_id="", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`，并打开 INFO 日志采集。
  2. 调用输入中的 `biz.recommend_and_claim(...)`，显式传入 `req_id=""`。
  3. 读取 `mock_scoring_client.score.call_args.kwargs["request_id"]`，保存为 `generated_req_id`。
  4. 在 `caplog.records` 中筛选包含 `recommend request:` 的日志行，并读取最新一条。
  5. 断言 `generated_req_id` 匹配 UUID 正则 `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`。
  6. 断言日志中包含 `reqId={generated_req_id}`，且 `mock_scoring_client.score.call_args.kwargs` 中不存在 `route` 键。
- **预期结果**：当 `req_id` 为空字符串时，系统会自动生成 UUID，并把同一个 UUID 同时写入请求日志和打分请求参数；`route` 字段只用于日志，不下发给打分服务。

## 二、请求分支一致性

### TC-LOG-006：兜底请求在跳过打分前仍打印一条请求日志
- **关联**：L1/logging
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；使用 `caplog.set_level("INFO")` 捕获日志。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_log_fallback", scene_name="game", device="mobile", policy_id="policy_fallback_001", external=0, req_id="req-log-006", score_threshold=0.0, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、库存，并打开 INFO 日志采集。
  2. 调用输入中的 `biz.recommend_and_claim(...)`，让请求命中兜底分支。
  3. 断言 `biz.scoring_client.score.assert_not_called()`。
  4. 在 `caplog.records` 中筛选包含 `recommend request:` 的日志行。
  5. 断言存在且仅存在 1 条匹配日志，并且日志包含 `reqId=req-log-006`、`route=1`、`scene_id=3001`。
- **预期结果**：即使请求命中兜底策略并跳过打分，也会在进入兜底前记录一条完整的请求日志。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/logging | 内部打分 `route=1` 的日志验证、兜底分支仍打印请求日志 | logging 未配置导致 INFO 日志不落地的风险、日志写入失败不影响业务 |
| L2/0402 | `reqId` 为空时自动生成 UUID 并写入日志、`route` 字段不下发给打分服务 | 无 |
