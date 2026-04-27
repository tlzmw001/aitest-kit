# issuance 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/issuance
> 生成日期：2026-04-25

---

## 一、库存不足处理

### TC-ISSUE-009：所有推荐候选券都库存不足时返回成功但 coupon 为空
- **关联**：L1/issuance
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "A", 0)` 和 `setup_stock(redis_store, "B", 0)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="A", score=0.9), ItemScore(item_id="B", score=0.8)]`。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_issue_all_empty", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-issue-009", score_threshold=0.5, max_claim_per_request=2, context={}, items=[{"item_id":"A","coupon_type":"discount","value":10,"min_spend":0,"expire_days":3},{"item_id":"B","coupon_type":"discount","value":8,"min_spend":0,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`。
  2. 将候选券 `A`、`B` 的库存都初始化为 `0`。
  3. 调用输入中的 `biz.recommend_and_claim(...)`。
  4. 断言 `result["code"] == 0`，`result["coupon"] is None`。
  5. 断言 `result["results"]` 仍包含 `A` 和 `B` 两条打分结果，且二者 `recommended` 都为 `True`。
- **预期结果**：当所有推荐候选券都库存不足时，请求仍返回成功响应 `code=0`，但 `coupon=None`，不会抛出 `STOCK_EMPTY` 错误。

## 二、发放记录持久化

### TC-ISSUE-010：发放成功后领取记录可被查询接口读取
- **关联**：L1/issuance
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`。
- **输入**：先调用 `biz.recommend_and_claim(user_id="u_issue_persist", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-issue-010", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`，再调用 `biz.query_user_coupons("u_issue_persist")`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`。
  2. 调用发放接口，保存返回的 `coupon.instance_id` 为 `instance_id`。
  3. 调用 `biz.query_user_coupons("u_issue_persist")`。
  4. 断言查询结果 `code == 0`、`total == 1`。
  5. 断言 `coupons[0]["instance_id"] == instance_id`，且 `coupons[0]["item_id"] == "COUPON_ACT_001"`、`coupons[0]["user_id"] == "u_issue_persist"`、`coupons[0]["status"] == "claimed"`。
- **预期结果**：发放成功后，领取记录会被持久化，并可通过用户券查询接口完整读出。

## 三、过期时间计算

### TC-ISSUE-011：coupon 过期时间按 claim_time 加 expire_days 天数计算
- **关联**：L1/issuance
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`；使用 `patch("coupon_system.services.coupon_service.time.time", return_value=1700000000)` 固定发放时间。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_issue_expire", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-issue-011", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`。
  2. 使用 `patch("coupon_system.services.coupon_service.time.time", return_value=1700000000)` 固定当前时间。
  3. 调用输入中的 `biz.recommend_and_claim(...)`。
  4. 断言 `result["coupon"]["claim_time"] == 1700000000`。
  5. 断言 `result["coupon"]["expire_time"] == 1700259200`。
- **预期结果**：发放成功时，`claim_time` 为当前时间戳，`expire_time` 等于 `claim_time + expire_days * 86400`；在本用例中应为 `1700259200`。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/issuance | 所有候选券都库存不足时 `coupon=None`、发放记录持久化验证、`expire_time` 计算 | 库存并发扣减的原子性与回滚 |
| L2/0402 | 无新增覆盖（请求级 `score_threshold` / `max_claim_per_request` 已有历史覆盖） | 无 |
