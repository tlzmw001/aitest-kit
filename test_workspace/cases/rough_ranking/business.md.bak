# rough_ranking 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/rough_ranking
> 生成日期：2026-04-25

---

## 一、实验控制

### TC-RANK-007：实验关闭时跳过粗排并保持候选顺序进入打分
- **关联**：L1/rough_ranking
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`、`setup_stock(redis_store, "COUPON_MEM_001", 100)`、`setup_stock(redis_store, "COUPON_SHIP_001", 100)`；通过 `biz.experiment_sdk.set_user_whitelist("u_rank_off", {"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_off"})` 强制命中粗排关闭策略；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.80), ItemScore(item_id="COUPON_MEM_001", score=0.60), ItemScore(item_id="COUPON_SHIP_001", score=0.40)]`。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_rank_off", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-rank-007", score_threshold=0.0, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3},{"item_id":"COUPON_MEM_001","coupon_type":"fixed","value":5000,"min_spend":20000,"expire_days":1,"isPrior":True},{"item_id":"COUPON_SHIP_001","coupon_type":"free_shipping","value":0,"min_spend":0,"expire_days":30}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`，并通过白名单将 `coarse_rank_exp_game` 固定到 `cr_off`。
  2. 使用 `patch.object(biz.coarse_ranker, "rank", wraps=biz.coarse_ranker.rank)` 监控粗排调用。
  3. 调用输入中的 `biz.recommend_and_claim(...)`。
  4. 断言 `result["code"] == 0`，`result["experiment_info"]["coarse_rank_exp_game"] == "cr_off"`。
  5. 断言 `mock_rank.assert_not_called()`。
  6. 读取 `mock_scoring_client.score.call_args.kwargs["items"]`，断言 item_id 顺序仍为 `["COUPON_ACT_001", "COUPON_MEM_001", "COUPON_SHIP_001"]`。
- **预期结果**：当粗排实验关闭时，`coarse_ranker.rank` 不被调用；全部候选券按原顺序直接进入打分阶段。

## 二、基础能力

### TC-RANK-008：旧规则 top_min_spend 按门槛高低截断
- **关联**：L1/rough_ranking
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"A","value":80,"min_spend":3000},{"item_id":"B","value":50,"min_spend":8000},{"item_id":"C","value":100,"min_spend":5000},{"item_id":"D","value":20,"min_spend":1000}], strategy_params={"truncate_count":2,"truncate_rule":"top_min_spend"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回列表长度为 2。
  4. 断言返回 item_id 顺序为 `["B", "C"]`。
- **预期结果**：旧规则 `top_min_spend` 生效，返回 `min_spend` 最高的两个候选券，顺序为 `B`、`C`。

### TC-RANK-009：优先券不足时先选完优先券再用普通券补满剩余名额
- **关联**：L1/rough_ranking
- **优先级**：P1
- **类型**：业务
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"P1","isPrior":True,"value":30,"coupon_type":"discount"},{"item_id":"N1","isPrior":False,"value":50,"coupon_type":"cash"},{"item_id":"N2","isPrior":False,"value":80,"coupon_type":"fixed"}], strategy_params={"truncate_count":2,"truncate_rule":"top_value","prior_count":2,"prior_rule":"top_value"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回列表长度为 2。
  4. 断言第 1 个元素 `item_id == "P1"`。
  5. 断言第 2 个元素 `item_id == "N2"`。
- **预期结果**：仅有 1 张优先券时，先保送 `P1`；剩余名额按普通券的 `top_value` 规则补入 `N2`，最终结果为 `["P1", "N2"]`。

## 三、异常场景

### TC-RANK-010：候选券为空时直接返回空列表
- **关联**：L1/rough_ranking
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`。
- **输入**：调用 `coarse_ranker.rank(items=[], strategy_params={"truncate_count":3,"truncate_rule":"top_value"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回值等于 `[]`。
- **预期结果**：候选券为空时，直接返回空列表，不抛异常。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/rough_ranking | 实验关闭时跳过粗排、旧规则 `top_min_spend`、优先券不足时普通券补位、候选券为空返回空列表 | `truncate_count<=0` 返回空、未知 `rule` 降级、随机截断、`sort_keys` 格式异常降级、`diversity` 参数异常跳过打散 |
| L2/0404 | 粗排增强能力在实验关闭时不生效 | 增强能力不配置时的向后兼容 |
