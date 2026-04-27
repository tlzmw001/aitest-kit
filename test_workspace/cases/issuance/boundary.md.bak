# issuance 边界测试用例

> 生成方式：手动试跑（test-design 第二轮，读代码补充）
> 关联知识库：L1/issuance
> 生成日期：2026-04-25

---

## 一、库存回滚边界

### TC-ISSUE-012：decr_stock 在库存为 0 时返回 -1 且库存回滚为 0
- **关联**：L1/issuance
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `redis_store` fixture 的构造方式初始化 `RedisStore`；执行 `setup_stock(redis_store, "COUPON_EMPTY", 0)`。
- **输入**：先调用 `redis_store.decr_stock("COUPON_EMPTY")`，再调用 `redis_store.get_stock("COUPON_EMPTY")`
- **测试步骤**：
  1. 初始化 `redis_store` 并将 `COUPON_EMPTY` 库存设为 `0`。
  2. 调用 `redis_store.decr_stock("COUPON_EMPTY")`，保存返回值为 `remaining`。
  3. 调用 `redis_store.get_stock("COUPON_EMPTY")`，保存返回值为 `stock_after`。
  4. 断言 `remaining == -1`。
  5. 断言 `stock_after == 0`。
- **预期结果**：库存为 0 时，`decr_stock()` 返回 `-1`，并通过 `INCR` 回滚使库存保持为 `0`，不会留下负库存。

## 二、发放容错边界

### TC-ISSUE-013：推荐结果中的高分 item 不在原始 items 中时跳过并尝试下一个
- **关联**：L1/issuance
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "B", 100)`。
- **输入**：调用 `biz._do_claim(user_id="u_issue_missing_item", results=[{"item_id":"GHOST","score":0.9,"calibrated_score":0.9,"recommended":True},{"item_id":"B","score":0.8,"calibrated_score":0.8,"recommended":True}], items=[{"item_id":"B","coupon_type":"discount","value":10,"min_spend":0,"expire_days":3}], max_claim_per_request=2)`
- **测试步骤**：
  1. 初始化 `biz` 并为 `B` 准备库存。
  2. 直接调用输入中的 `biz._do_claim(...)`。
  3. 断言返回 `coupon` 不为 `None`。
  4. 断言 `coupon["item_id"] == "B"`。
  5. 断言 `redis_store.get_stock("B") == 99`。
- **预期结果**：当高分推荐项 `GHOST` 不存在于原始 `items` 映射中时，发放逻辑会跳过该项并继续尝试下一个合法候选券 `B`。

### TC-ISSUE-014：item 未提供 expire_days 时默认按 7 天计算过期时间
- **关联**：L1/issuance
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_NO_EXPIRE", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_NO_EXPIRE", score=0.8)]`；使用 `patch("coupon_system.services.coupon_service.time.time", return_value=1700000000)` 固定发放时间。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_issue_default_expire", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-issue-014", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_NO_EXPIRE","coupon_type":"discount","value":10,"min_spend":0}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`。
  2. 使用 `patch("coupon_system.services.coupon_service.time.time", return_value=1700000000)` 固定当前时间。
  3. 调用输入中的 `biz.recommend_and_claim(...)`，其中 item 不提供 `expire_days` 字段。
  4. 断言 `result["coupon"]["claim_time"] == 1700000000`。
  5. 断言 `result["coupon"]["expire_time"] == 1700604800`。
- **预期结果**：当 item 缺少 `expire_days` 时，发放逻辑使用默认值 `7` 天；在本用例中 `expire_time` 应为 `1700000000 + 7 * 86400 = 1700604800`。

## 三、查询顺序边界

### TC-ISSUE-015：query_user_coupons 按 claim_time 倒序返回
- **关联**：L1/issuance
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store` fixture 的构造方式初始化 `CouponBizService`；通过 `redis_store.save_coupon_instance("iid-old", {"instance_id":"iid-old","item_id":"A","user_id":"u_issue_sort","status":"claimed","coupon_type":"discount","value":10,"min_spend":0,"expire_time":2000,"claim_time":1000})` 和 `redis_store.save_coupon_instance("iid-new", {"instance_id":"iid-new","item_id":"B","user_id":"u_issue_sort","status":"claimed","coupon_type":"discount","value":20,"min_spend":0,"expire_time":3000,"claim_time":2000})` 写入两条实例；再执行 `redis_store.add_user_coupon("u_issue_sort", "iid-old")` 与 `redis_store.add_user_coupon("u_issue_sort", "iid-new")`。
- **输入**：调用 `biz.query_user_coupons("u_issue_sort")`
- **测试步骤**：
  1. 初始化 `biz` 与 `redis_store`。
  2. 写入两条属于同一用户的券实例，其中 `iid-new.claim_time = 2000`，`iid-old.claim_time = 1000`。
  3. 将两个实例 ID 关联到用户 `u_issue_sort`。
  4. 调用 `biz.query_user_coupons("u_issue_sort")`。
  5. 断言 `result["code"] == 0`，`result["total"] == 2`。
  6. 断言 `result["coupons"][0]["instance_id"] == "iid-new"`，`result["coupons"][1]["instance_id"] == "iid-old"`。
- **预期结果**：查询结果按 `claim_time` 降序排序，最新领取的券排在前面。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/issuance | `decr_stock` 负库存回滚、发放时 `item` 缺失分支、缺省 `expire_days=7`、查询结果按 `claim_time` 倒序 | 真正并发场景下的 DECR 原子性验证 |
| L2/0402 | 无新增覆盖（请求级参数已被历史用例覆盖） | 无 |
