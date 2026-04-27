# rough_ranking 边界测试用例

> 生成方式：手动试跑（test-design 第二轮，读代码补充）
> 关联知识库：L1/rough_ranking
> 生成日期：2026-04-25

---

## 一、截断参数边界

### TC-RANK-011：truncate_count 小于等于 0 时直接返回空列表
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"A","value":100},{"item_id":"B","value":80}], strategy_params={"truncate_count":0,"truncate_rule":"top_value"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回值等于 `[]`。
- **预期结果**：`truncate_count <= 0` 时直接返回空列表，不继续过滤、排序或打散。

### TC-RANK-012：truncate_count 为非数字时默认按候选总数处理
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"A","value":10},{"item_id":"B","value":50},{"item_id":"C","value":30}], strategy_params={"truncate_count":"bad-number","truncate_rule":"top_value"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回列表长度为 3。
  4. 断言返回 item_id 顺序仍为 `["A", "B", "C"]`。
- **预期结果**：`truncate_count` 非数字时回退为候选总数；在未启用其他新能力且无需截断时，返回全部候选券。

## 二、规则降级

### TC-RANK-013：未知 truncate_rule 时 warning 后回退到 top_value
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`；使用 `caplog.set_level("WARNING")` 捕获日志。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"A","value":10},{"item_id":"B","value":80},{"item_id":"C","value":50}], strategy_params={"truncate_count":2,"truncate_rule":"top_score"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`，并打开 WARNING 级别日志采集。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回 item_id 顺序为 `["B", "C"]`。
  4. 在 `caplog.records` 中查找包含 `未知粗排规则` 的 warning 日志。
- **预期结果**：未知 `truncate_rule` 不抛异常；记录 warning，并按 `top_value` 回退，返回 `["B", "C"]`。

### TC-RANK-014：未知 prior_rule 时 warning 后回退到 top_value
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`；使用 `caplog.set_level("WARNING")` 捕获日志。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"P_low","isPrior":True,"value":10},{"item_id":"P_high","isPrior":True,"value":90},{"item_id":"N1","isPrior":False,"value":100}], strategy_params={"truncate_count":2,"prior_count":1,"prior_rule":"manual_pick","truncate_rule":"top_value"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`，并打开 WARNING 级别日志采集。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回 item_id 顺序为 `["P_high", "N1"]`。
  4. 在 `caplog.records` 中查找包含 `未知 prior_rule` 的 warning 日志。
- **预期结果**：未知 `prior_rule` 不抛异常；记录 warning，并按 `top_value` 从优先券中选择 `P_high`，剩余名额由普通券 `N1` 补满。

### TC-RANK-015：prior_count 大于 truncate_count 时被截断到 truncate_count
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`；使用 `caplog.set_level("WARNING")` 捕获日志。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"P1","isPrior":True,"value":100},{"item_id":"P2","isPrior":True,"value":90},{"item_id":"P3","isPrior":True,"value":80},{"item_id":"N1","isPrior":False,"value":70}], strategy_params={"truncate_count":2,"prior_count":5,"prior_rule":"top_value","truncate_rule":"top_value"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`，并打开 WARNING 级别日志采集。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回 item_id 顺序为 `["P1", "P2"]`。
  4. 在 `caplog.records` 中查找包含 `prior_count=5 大于 truncate_count=2` 的 warning 日志。
- **预期结果**：`prior_count` 超出总截断数时会被裁剪到 `truncate_count`；最终只返回前 2 张保送券 `P1`、`P2`。

## 三、随机与排序边界

### TC-RANK-016：truncate_rule=random 时按打乱后的顺序截断
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`；使用 `patch("coupon_system.services.coarse_ranker.random.shuffle", side_effect=lambda seq: seq.reverse())` 固定随机打乱结果。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"A","value":10},{"item_id":"B","value":20},{"item_id":"C","value":30},{"item_id":"D","value":40}], strategy_params={"truncate_count":2,"truncate_rule":"random"})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 使用 `patch(...random.shuffle, side_effect=lambda seq: seq.reverse())` 固定随机行为。
  3. 调用输入中的 `coarse_ranker.rank(...)`。
  4. 断言返回 item_id 顺序为 `["D", "C"]`。
- **预期结果**：`truncate_rule="random"` 时，先按打乱后的顺序排列候选券，再取前 2 个；在本用例的固定随机条件下结果为 `["D", "C"]`。

### TC-RANK-017：sort_keys 含非法元素时跳过非法 key，非数字权重按 0.0 处理
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"A","value":30,"min_spend":100},{"item_id":"B","value":20,"min_spend":200},{"item_id":"C","value":10,"min_spend":300}], strategy_params={"truncate_count":2,"sort_keys":[{"field":"value","weight":"bad-weight"},{"field":123,"weight":1.0},"not-a-dict"]})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回列表长度为 2。
  4. 断言返回 item_id 顺序为 `["A", "B"]`。
- **预期结果**：`field` 非字符串的 key 被跳过，非 dict 元素被跳过，`weight="bad-weight"` 按 `0.0` 处理；所有候选券综合得分相同，最终保持原顺序并截取前 2 个，即 `["A", "B"]`。

## 四、打散降级

### TC-RANK-018：diversity.max_per_group 非数字时跳过打散直接截断
- **关联**：L1/rough_ranking
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `coarse_ranker` fixture 的构造方式初始化 `CoarseRanker`。
- **输入**：调用 `coarse_ranker.rank(items=[{"item_id":"A","coupon_type":"cash","value":100},{"item_id":"B","coupon_type":"cash","value":90},{"item_id":"C","coupon_type":"discount","value":80}], strategy_params={"truncate_count":2,"truncate_rule":"top_value","diversity":{"enabled":True,"group_field":"coupon_type","max_per_group":"bad-number"}})`
- **测试步骤**：
  1. 初始化 `coarse_ranker`。
  2. 调用输入中的 `coarse_ranker.rank(...)`。
  3. 断言返回 item_id 顺序为 `["A", "B"]`。
- **预期结果**：`max_per_group` 非数字时，打散阶段整体跳过，直接按已排序结果截断，返回 `["A", "B"]`。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/rough_ranking | `truncate_count<=0` 返回空、`truncate_count` 非数字默认总数、未知 `truncate_rule/prior_rule` 回退、`prior_count>truncate_count` 裁剪、`truncate_rule=random`、`sort_keys` 非法元素降级、`diversity.max_per_group` 非法时跳过打散 | `filters` 非 dict 的可观测 warning 行为、`diversity` 配置整体非 dict 时的降级 |
| L2/0404 | 粗排增强能力的随机/降级容错分支 | 增强能力不配置时的向后兼容 |
