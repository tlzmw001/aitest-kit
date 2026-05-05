# issuance 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `setup_issuance` | `fixtures/issuance.py` | 初始化库存、关闭粗排/校准实验、清理用户领取状态，并返回 issuance 测试操作对象 |

## 请求模板

issuance 用例通过推荐接口触发发放，再通过库存、用户券查询或 gRPC 查询接口观察副作用。
稳定的多请求、库存和查询流程通过 `case_flows` 结构化生成；并发库存用例保留 `case_bodies`。

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
case_flows:
  TC-ISSUE-001:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-001
        save_as: issue
      - call: issue.request
        args:
          - u_issue_http_ok
          - req_issue_001
        kwargs:
          score_threshold: 0.0
          max_claim_per_request: 1
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: 'assert resp[''coupon''][''item_id''] == max(resp[''results''], key=lambda r: r[''score''])[''item_id'']'
      - assert: assert resp['coupon']['user_id'] == 'u_issue_http_ok'
      - assert: assert resp['coupon']['status'] == 'claimed'
  TC-ISSUE-002:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-002
        save_as: issue
      - call: issue.request
        args:
          - u_issue_grpc_ok
          - req_issue_002
        kwargs:
          score_threshold: 0.0
          max_claim_per_request: 1
        save_as: body
      - call: issue.grpc_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: 'assert resp[''coupon''][''item_id''] == max(resp[''results''], key=lambda r: r[''score''])[''item_id'']'
      - assert: assert resp['coupon']['user_id'] == 'u_issue_grpc_ok'
      - assert: assert resp['coupon']['status'] == 'claimed'
  TC-ISSUE-003:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-003
        save_as: issue
      - call: issue.request
        args:
          - u_issue_high_threshold
          - req_issue_003
        kwargs:
          score_threshold: 1.0
          max_claim_per_request: 1
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is None
      - assert: assert all((not r['recommended'] for r in resp['results']))
  TC-ISSUE-004:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-004
        save_as: issue
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_A
          - 2
      - call: issue.stock
        args:
          - COUPON_ISSUE_A
        save_as: before
      - call: issue.request
        args:
          - u_issue_stock_decr
          - req_issue_004
        kwargs:
          items:
            expr: issue_items('COUPON_ISSUE_A')
          score_threshold: 0.0
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - call: issue.stock
        args:
          - COUPON_ISSUE_A
        save_as: after
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_A'
      - assert: assert before == 2
      - assert: assert after == 1
  TC-ISSUE-005:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-005
        save_as: issue
      - call: issue.request
        args:
          - u_issue_query
          - req_issue_005
        kwargs:
          items:
            expr: issue_items('COUPON_ISSUE_A')
          score_threshold: 0.0
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - call: issue.query_coupons
        args:
          - u_issue_query
        save_as: query
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: assert query['code'] == 0
      - assert: assert query['total'] >= 1
      - assert: assert 'COUPON_ISSUE_A' in {c['item_id'] for c in query['coupons']}
  TC-ISSUE-006:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-006
        save_as: issue
      - call: issue.request
        args:
          - u_issue_expire_3
          - req_issue_006
        kwargs:
          items:
            expr: '[issue_item(''COUPON_ISSUE_A'', expire_days=3)]'
          score_threshold: 0.0
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: assert resp['coupon']['expire_time'] - resp['coupon']['claim_time'] == 3 * 86400
  TC-ISSUE-007:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-007
        save_as: issue
      - call: issue.post_recommend
        args:
          - expr: issue.request('u_issue_threshold_control', 'req_issue_007a', items=issue_items('COUPON_ISSUE_A'), score_threshold=1.0)
        save_as: first
      - call: issue.post_recommend
        args:
          - expr: issue.request('u_issue_threshold_control', 'req_issue_007b', items=issue_items('COUPON_ISSUE_A'), score_threshold=0.0)
        save_as: second
      - assert: assert first['code'] == 0
      - assert: assert first['coupon'] is None
      - assert: assert second['code'] == 0
      - assert: assert second['coupon'] is not None
      - assert: assert second['coupon']['item_id'] == 'COUPON_ISSUE_A'
  TC-ISSUE-008:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-008
        save_as: issue
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_A
          - 0
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_B
          - 100
      - call: issue.post_recommend
        args:
          - expr: issue.request('u_issue_max_claim', 'req_issue_008a', items=issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B'),
              score_threshold=0.0, max_claim_per_request=1, policy_id='policy_fallback_001')
        save_as: first
      - call: issue.post_recommend
        args:
          - expr: issue.request('u_issue_max_claim', 'req_issue_008b', items=issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B'),
              score_threshold=0.0, max_claim_per_request=2, policy_id='policy_fallback_001')
        save_as: second
      - assert: assert first['code'] == 0
      - assert: assert first['coupon'] is None
      - assert: assert second['code'] == 0
      - assert: assert second['coupon'] is not None
      - assert: assert second['coupon']['item_id'] == 'COUPON_ISSUE_B'
  TC-ISSUE-009:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-009
        save_as: issue
      - call: issue.cleanup_user
        args:
          - user_no_coupons
      - call: issue.query_coupons
        args:
          - user_no_coupons
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupons'] == []
      - assert: assert resp['total'] == 0
  TC-ISSUE-010:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-010
        save_as: issue
      - call: issue.grpc_query_coupons
        args:
          - ''
        save_as: resp
      - assert: assert resp['code'] == 1001
      - assert: assert resp['message'] == 'user_id不能为空'
      - assert: assert resp['coupons'] == []
      - assert: assert resp['total'] == 0
  TC-ISSUE-011:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-011
        save_as: issue
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_A
          - 0
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_B
          - 100
      - call: issue.request
        args:
          - u_issue_stock_next
          - req_issue_011
        kwargs:
          items:
            expr: issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B')
          score_threshold: 0.0
          max_claim_per_request: 2
          policy_id: policy_fallback_001
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
      - assert: assert issue.stock('COUPON_ISSUE_A') == 0
  TC-ISSUE-012:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-012
        save_as: issue
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_A
          - 0
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_B
          - 0
      - call: issue.request
        args:
          - u_issue_all_empty
          - req_issue_012
        kwargs:
          score_threshold: 0.0
          max_claim_per_request: 2
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is None
      - assert: assert resp['code'] != 1006
  TC-ISSUE-016:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-016
        save_as: issue
      - call: issue.request
        args:
          - u_issue_default_expire
          - req_issue_016
        kwargs:
          items:
            expr: '[issue_item(''COUPON_ISSUE_A'', expire_days=None)]'
          score_threshold: 0.0
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: assert resp['coupon']['expire_time'] - resp['coupon']['claim_time'] == 7 * 86400
  TC-ISSUE-017:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-017
        save_as: issue
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_A
          - 0
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_B
          - 100
      - call: issue.request
        args:
          - u_issue_max_gt_count
          - req_issue_017
        kwargs:
          items:
            expr: issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B')
          score_threshold: 0.0
          max_claim_per_request: 10
          policy_id: policy_fallback_001
        save_as: body
      - call: issue.post_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
  TC-ISSUE-018:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-018
        save_as: issue
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_A
          - 0
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_B
          - 100
      - call: issue.request
        args:
          - u_issue_grpc_stock_next
          - req_issue_018
        kwargs:
          items:
            expr: issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B')
          score_threshold: 0.0
          max_claim_per_request: 2
          policy_id: policy_fallback_001
        save_as: body
      - call: issue.grpc_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is not None
      - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
      - assert: assert issue.stock('COUPON_ISSUE_A') == 0
  TC-ISSUE-019:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-019
        save_as: issue
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_A
          - 0
      - call: issue.set_stock
        args:
          - COUPON_ISSUE_B
          - 0
      - call: issue.request
        args:
          - u_issue_grpc_all_empty
          - req_issue_019
        kwargs:
          score_threshold: 0.0
          max_claim_per_request: 2
        save_as: body
      - call: issue.grpc_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is None
      - assert: assert resp['code'] != 1006
  TC-ISSUE-020:
    fixture: setup_issuance
    steps:
      - call: setup_issuance
        kwargs:
          case_id: TC-ISSUE-020
        save_as: issue
      - call: issue.request
        args:
          - u_issue_grpc_max_gt_count
          - req_issue_020
        kwargs:
          score_threshold: 0.0
          max_claim_per_request: 10
        save_as: body
      - call: issue.grpc_recommend
        args:
          - expr: body
        save_as: resp
      - assert: assert resp['code'] == 0
      - assert: assert resp['coupon'] is None or resp['coupon']['item_id'] in {r['item_id'] for r in resp['results']}
```
