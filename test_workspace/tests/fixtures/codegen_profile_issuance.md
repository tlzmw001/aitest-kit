# issuance 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `setup_issuance` | `fixtures/issuance.py` | 初始化库存、关闭粗排/校准实验、清理用户领取状态，并返回 issuance 测试操作对象 |

## 请求模板

issuance 用例通过推荐接口触发发放，再通过库存、用户券查询或 gRPC 查询接口观察副作用。
多请求、并发、查询接口用例不能使用默认单次 `/api/v1/recommend` 模板，统一通过 `case_bodies` 显式生成。

## 关键约束

- 不指定打分服务返回值；断言最高分券时只使用响应里的 `results[*].score`。
- 需要稳定验证“第一张库存不足后尝试下一张”的用例，使用服务已有兜底策略 `policy_fallback_001` 固定同分结果，并依赖 Python 稳定排序保留请求顺序，不改待测服务。
- 每个用户进入测试前清理 `coupon:user:{user}:instances`、`coupon:user:{user}:claimed` 和对应实例 key，避免重复运行污染。

## emitter 规则

```yaml
extra_imports:
  - from concurrent.futures import ThreadPoolExecutor
  - from test_workspace.tests.fixtures.issuance import issue_item, issue_items

case_bodies:
  TC-ISSUE-001: |
    issue = setup_issuance(case_id="TC-ISSUE-001")
    body = issue.request(
        "u_issue_http_ok",
        "req_issue_001",
        score_threshold=0.0,
        max_claim_per_request=1,
    )
    resp = issue.post_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["item_id"] == max(resp["results"], key=lambda r: r["score"])["item_id"]
    assert resp["coupon"]["user_id"] == "u_issue_http_ok"
    assert resp["coupon"]["status"] == "claimed"

  TC-ISSUE-002: |
    issue = setup_issuance(case_id="TC-ISSUE-002")
    body = issue.request(
        "u_issue_grpc_ok",
        "req_issue_002",
        score_threshold=0.0,
        max_claim_per_request=1,
    )
    resp = issue.grpc_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["item_id"] == max(resp["results"], key=lambda r: r["score"])["item_id"]
    assert resp["coupon"]["user_id"] == "u_issue_grpc_ok"
    assert resp["coupon"]["status"] == "claimed"

  TC-ISSUE-003: |
    issue = setup_issuance(case_id="TC-ISSUE-003")
    body = issue.request(
        "u_issue_high_threshold",
        "req_issue_003",
        score_threshold=1.0,
        max_claim_per_request=1,
    )
    resp = issue.post_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is None
    assert all(not r["recommended"] for r in resp["results"])

  TC-ISSUE-004: |
    issue = setup_issuance(case_id="TC-ISSUE-004")
    issue.set_stock("COUPON_ISSUE_A", 2)
    before = issue.stock("COUPON_ISSUE_A")
    body = issue.request(
        "u_issue_stock_decr",
        "req_issue_004",
        items=issue_items("COUPON_ISSUE_A"),
        score_threshold=0.0,
    )
    resp = issue.post_recommend(body)
    after = issue.stock("COUPON_ISSUE_A")
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["item_id"] == "COUPON_ISSUE_A"
    assert before == 2
    assert after == 1

  TC-ISSUE-005: |
    issue = setup_issuance(case_id="TC-ISSUE-005")
    body = issue.request(
        "u_issue_query",
        "req_issue_005",
        items=issue_items("COUPON_ISSUE_A"),
        score_threshold=0.0,
    )
    resp = issue.post_recommend(body)
    query = issue.query_coupons("u_issue_query")
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert query["code"] == 0
    assert query["total"] >= 1
    assert "COUPON_ISSUE_A" in {c["item_id"] for c in query["coupons"]}

  TC-ISSUE-006: |
    issue = setup_issuance(case_id="TC-ISSUE-006")
    body = issue.request(
        "u_issue_expire_3",
        "req_issue_006",
        items=[issue_item("COUPON_ISSUE_A", expire_days=3)],
        score_threshold=0.0,
    )
    resp = issue.post_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["expire_time"] - resp["coupon"]["claim_time"] == 3 * 86400

  TC-ISSUE-007: |
    issue = setup_issuance(case_id="TC-ISSUE-007")
    first = issue.post_recommend(issue.request(
        "u_issue_threshold_control",
        "req_issue_007a",
        items=issue_items("COUPON_ISSUE_A"),
        score_threshold=1.0,
    ))
    second = issue.post_recommend(issue.request(
        "u_issue_threshold_control",
        "req_issue_007b",
        items=issue_items("COUPON_ISSUE_A"),
        score_threshold=0.0,
    ))
    assert first["code"] == 0
    assert first["coupon"] is None
    assert second["code"] == 0
    assert second["coupon"] is not None
    assert second["coupon"]["item_id"] == "COUPON_ISSUE_A"

  TC-ISSUE-008: |
    issue = setup_issuance(case_id="TC-ISSUE-008")
    issue.set_stock("COUPON_ISSUE_A", 0)
    issue.set_stock("COUPON_ISSUE_B", 100)
    first = issue.post_recommend(issue.request(
        "u_issue_max_claim",
        "req_issue_008a",
        items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
        score_threshold=0.0,
        max_claim_per_request=1,
        policy_id="policy_fallback_001",
    ))
    second = issue.post_recommend(issue.request(
        "u_issue_max_claim",
        "req_issue_008b",
        items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
        score_threshold=0.0,
        max_claim_per_request=2,
        policy_id="policy_fallback_001",
    ))
    assert first["code"] == 0
    assert first["coupon"] is None
    assert second["code"] == 0
    assert second["coupon"] is not None
    assert second["coupon"]["item_id"] == "COUPON_ISSUE_B"

  TC-ISSUE-009: |
    issue = setup_issuance(case_id="TC-ISSUE-009")
    issue.cleanup_user("user_no_coupons")
    resp = issue.query_coupons("user_no_coupons")
    assert resp["code"] == 0
    assert resp["coupons"] == []
    assert resp["total"] == 0

  TC-ISSUE-010: |
    issue = setup_issuance(case_id="TC-ISSUE-010")
    resp = issue.grpc_query_coupons("")
    assert resp["code"] == 1001
    assert resp["message"] == "user_id不能为空"
    assert resp["coupons"] == []
    assert resp["total"] == 0

  TC-ISSUE-011: |
    issue = setup_issuance(case_id="TC-ISSUE-011")
    issue.set_stock("COUPON_ISSUE_A", 0)
    issue.set_stock("COUPON_ISSUE_B", 100)
    body = issue.request(
        "u_issue_stock_next",
        "req_issue_011",
        items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
        score_threshold=0.0,
        max_claim_per_request=2,
        policy_id="policy_fallback_001",
    )
    resp = issue.post_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["item_id"] == "COUPON_ISSUE_B"
    assert issue.stock("COUPON_ISSUE_A") == 0

  TC-ISSUE-012: |
    issue = setup_issuance(case_id="TC-ISSUE-012")
    issue.set_stock("COUPON_ISSUE_A", 0)
    issue.set_stock("COUPON_ISSUE_B", 0)
    body = issue.request(
        "u_issue_all_empty",
        "req_issue_012",
        score_threshold=0.0,
        max_claim_per_request=2,
    )
    resp = issue.post_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is None
    assert resp["code"] != 1006

  TC-ISSUE-013: |
    issue = setup_issuance(case_id="TC-ISSUE-013")
    issue.set_stock("COUPON_ISSUE_CONCURRENT", 1)
    body_a = issue.request(
        "u_issue_concurrent_a",
        "req_issue_013a",
        items=issue_items("COUPON_ISSUE_CONCURRENT"),
        score_threshold=0.0,
    )
    body_b = issue.request(
        "u_issue_concurrent_b",
        "req_issue_013b",
        items=issue_items("COUPON_ISSUE_CONCURRENT"),
        score_threshold=0.0,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(issue.post_recommend, [body_a, body_b]))
    successes = [
        r for r in responses
        if r["coupon"] is not None and r["coupon"]["item_id"] == "COUPON_ISSUE_CONCURRENT"
    ]
    empty = [r for r in responses if r["coupon"] is None]
    assert all(r["code"] == 0 for r in responses)
    assert len(successes) == 1
    assert len(empty) == 1
    assert issue.stock("COUPON_ISSUE_CONCURRENT") == 0

  TC-ISSUE-016: |
    issue = setup_issuance(case_id="TC-ISSUE-016")
    body = issue.request(
        "u_issue_default_expire",
        "req_issue_016",
        items=[issue_item("COUPON_ISSUE_A", expire_days=None)],
        score_threshold=0.0,
    )
    resp = issue.post_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["expire_time"] - resp["coupon"]["claim_time"] == 7 * 86400

  TC-ISSUE-017: |
    issue = setup_issuance(case_id="TC-ISSUE-017")
    issue.set_stock("COUPON_ISSUE_A", 0)
    issue.set_stock("COUPON_ISSUE_B", 100)
    body = issue.request(
        "u_issue_max_gt_count",
        "req_issue_017",
        items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
        score_threshold=0.0,
        max_claim_per_request=10,
        policy_id="policy_fallback_001",
    )
    resp = issue.post_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["item_id"] == "COUPON_ISSUE_B"

  TC-ISSUE-018: |
    issue = setup_issuance(case_id="TC-ISSUE-018")
    issue.set_stock("COUPON_ISSUE_A", 0)
    issue.set_stock("COUPON_ISSUE_B", 100)
    body = issue.request(
        "u_issue_grpc_stock_next",
        "req_issue_018",
        items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
        score_threshold=0.0,
        max_claim_per_request=2,
        policy_id="policy_fallback_001",
    )
    resp = issue.grpc_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is not None
    assert resp["coupon"]["item_id"] == "COUPON_ISSUE_B"
    assert issue.stock("COUPON_ISSUE_A") == 0

  TC-ISSUE-019: |
    issue = setup_issuance(case_id="TC-ISSUE-019")
    issue.set_stock("COUPON_ISSUE_A", 0)
    issue.set_stock("COUPON_ISSUE_B", 0)
    body = issue.request(
        "u_issue_grpc_all_empty",
        "req_issue_019",
        score_threshold=0.0,
        max_claim_per_request=2,
    )
    resp = issue.grpc_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is None
    assert resp["code"] != 1006

  TC-ISSUE-020: |
    issue = setup_issuance(case_id="TC-ISSUE-020")
    body = issue.request(
        "u_issue_grpc_max_gt_count",
        "req_issue_020",
        score_threshold=0.0,
        max_claim_per_request=10,
    )
    resp = issue.grpc_recommend(body)
    assert resp["code"] == 0
    assert resp["coupon"] is None or resp["coupon"]["item_id"] in {r["item_id"] for r in resp["results"]}
```
