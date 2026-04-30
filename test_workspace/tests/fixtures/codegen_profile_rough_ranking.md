# rough_ranking 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `setup_rough_ranking` | fixtures/rough_ranking.py | 为每条用例设置 AB 粗排策略，启动隔离主服务和记录型打分代理 |

## 请求模板

粗排用例必须验证“进入打分服务的 item 顺序”，不能用 `response.results[*].item_id` 代替。fixture 会启动一个 gRPC scoring proxy，记录主服务调用 `ScoringService/Score` 时传入的 `items[*].item_id`，测试代码统一断言 `case.rank_input_items`。

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| `rank_input_items == [...]` | `assert case.rank_input_items == [...]` |
| `len(rank_input_items) == N` | `assert len(case.rank_input_items) == N` |
| `set(rank_input_items) <= {...}` | `assert set(case.rank_input_items) <= {...}` |
| `response.body.*` / `response.*` | 断言 `resp` 对应字段 |
| 日志类断言 | 保留在 manual 用例注释中，不用响应占位替代 |

## setup 映射

| 场景变量描述 | fixture 行为 |
|-------------|--------------|
| 粗排策略参数 | 更新 AB 服务中 `coarse_rank_exp_game.cr_v2_full.params`，teardown 恢复 |
| 粗排关闭 | 对用例用户设置白名单命中 `cr_off` |
| 校准关闭 | 对用例用户设置白名单命中 `cal_off` |
| 打分代理 | 复制 settings 到临时文件并改写 `scoring_service.port`，用 `COUPON_CONFIG_PATH` 启动隔离主服务 |

## emitter 规则

```yaml
case_bodies:
  TC-RANK-001: |
    case = setup_rough_ranking(case_id="TC-RANK-001")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B", "COUPON_RANK_C"]
  TC-RANK-002: |
    case = setup_rough_ranking(case_id="TC-RANK-002")
    resp = case.recommend_grpc()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B", "COUPON_RANK_C"]
  TC-RANK-003: |
    case = setup_rough_ranking(case_id="TC-RANK-003")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B"]
  TC-RANK-004: |
    case = setup_rough_ranking(case_id="TC-RANK-004")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B"]
  TC-RANK-005: |
    case = setup_rough_ranking(case_id="TC-RANK-005")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert len(case.rank_input_items) == 2
    assert set(case.rank_input_items) <= {"COUPON_RANK_A", "COUPON_RANK_B", "COUPON_RANK_C"}
  TC-RANK-006: |
    case = setup_rough_ranking(case_id="TC-RANK-006")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items[0] == "COUPON_RANK_B"
    assert len(case.rank_input_items) == 2
  TC-RANK-007: |
    case = setup_rough_ranking(case_id="TC-RANK-007")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B"]
  TC-RANK-008: |
    case = setup_rough_ranking(case_id="TC-RANK-008")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items[0] == "COUPON_RANK_B"
  TC-RANK-009: |
    case = setup_rough_ranking(case_id="TC-RANK-009")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert len(case.rank_input_items) == 3
    assert case.rank_input_items[:2] == ["COUPON_RANK_D1", "COUPON_RANK_F1"]
  TC-RANK-010: |
    case = setup_rough_ranking(case_id="TC-RANK-010")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert len(case.rank_input_items) == 1
    assert case.rank_input_items == ["COUPON_RANK_A"]
  TC-RANK-011: |
    case = setup_rough_ranking(case_id="TC-RANK-011")
    resp = case.recommend_grpc()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_B"]
  TC-RANK-012: |
    case = setup_rough_ranking(case_id="TC-RANK-012")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["P1", "P2", "A", "C", "E"]
    assert case.rank_input_items[:2] == ["P1", "P2"]
  TC-RANK-013: |
    case = setup_rough_ranking(case_id="TC-RANK-013")
    resp = case.recommend_http()
    assert resp["code"] == 1001
    assert resp["results"] == []
    assert case.rank_input_items == []
  TC-RANK-014: |
    case = setup_rough_ranking(case_id="TC-RANK-014")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert resp["results"] == []
    assert resp["coupon"] is None
    assert case.rank_input_items == []
  TC-RANK-015: |
    case = setup_rough_ranking(case_id="TC-RANK-015")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert len(case.rank_input_items) == 3
  TC-RANK-016: |
    case = setup_rough_ranking(case_id="TC-RANK-016")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B"]
    # MANUAL CHECK: 应用日志包含 未知粗排规则
  TC-RANK-017: |
    case = setup_rough_ranking(case_id="TC-RANK-017")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert len(case.rank_input_items) == 2
  TC-RANK-018: |
    case = setup_rough_ranking(case_id="TC-RANK-018")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert resp["results"] == []
    assert case.rank_input_items == []
    # MANUAL CHECK: 应用日志包含 未知过滤操作符
  TC-RANK-019: |
    case = setup_rough_ranking(case_id="TC-RANK-019")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B"]
  TC-RANK-020: |
    case = setup_rough_ranking(case_id="TC-RANK-020")
    resp = case.recommend_http()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_B"]
    # MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1
  TC-RANK-021: |
    case = setup_rough_ranking(case_id="TC-RANK-021")
    resp = case.recommend_grpc()
    assert resp["code"] == 0
    assert len(case.rank_input_items) == 3
  TC-RANK-022: |
    case = setup_rough_ranking(case_id="TC-RANK-022")
    resp = case.recommend_grpc()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_A", "COUPON_RANK_B"]
    # MANUAL CHECK: 应用日志包含 未知粗排规则
  TC-RANK-023: |
    case = setup_rough_ranking(case_id="TC-RANK-023")
    resp = case.recommend_grpc()
    assert resp["code"] == 0
    assert case.rank_input_items == ["COUPON_RANK_B"]
    # MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1
```
