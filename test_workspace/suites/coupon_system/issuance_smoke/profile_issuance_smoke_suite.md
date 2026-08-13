# issuance_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: issuance
suite: issuance_smoke
case_flows:
  TC-ISSUE-001:
    steps:
    - call: harness.request
      args:
      - u_issue_http_ok
      - req_issue_001
      kwargs:
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: 'assert resp[''coupon''][''item_id''] == max(resp[''results''], key=lambda r: r[''score''])[''item_id'']'
    - assert: assert resp['coupon']['user_id'] == 'u_issue_http_ok'
    - assert: assert resp['coupon']['status'] == 'claimed'
  TC-ISSUE-002:
    steps:
    - call: harness.request
      args:
      - u_issue_grpc_ok
      - req_issue_002
      kwargs:
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: body
    - call: harness.grpc_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: 'assert resp[''coupon''][''item_id''] == max(resp[''results''], key=lambda r: r[''score''])[''item_id'']'
    - assert: assert resp['coupon']['user_id'] == 'u_issue_grpc_ok'
    - assert: assert resp['coupon']['status'] == 'claimed'
  TC-ISSUE-003:
    steps:
    - call: harness.request
      args:
      - u_issue_high_threshold
      - req_issue_003
      kwargs:
        score_threshold: 1.0
        max_claim_per_request: 1
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is None
    - assert: assert all((not r['recommended'] for r in resp['results']))
  TC-ISSUE-004:
    steps:
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_A
      - 2
    - call: harness.stock
      args:
      - COUPON_ISSUE_A
      save_as: before
    - call: harness.request
      args:
      - u_issue_stock_decr
      - req_issue_004
      kwargs:
        items:
          expr: harness.issue_items('COUPON_ISSUE_A')
        score_threshold: 0.0
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - call: harness.stock
      args:
      - COUPON_ISSUE_A
      save_as: after
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_A'
    - assert: assert before == 2
    - assert: assert after == 1
  TC-ISSUE-005:
    steps:
    - call: harness.request
      args:
      - u_issue_query
      - req_issue_005
      kwargs:
        items:
          expr: harness.issue_items('COUPON_ISSUE_A')
        score_threshold: 0.0
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - call: harness.query_coupons
      args:
      - u_issue_query
      save_as: query
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: assert query['code'] == 0
    - assert: assert query['total'] >= 1
    - assert: assert 'COUPON_ISSUE_A' in {c['item_id'] for c in query['coupons']}
  TC-ISSUE-006:
    steps:
    - call: harness.request
      args:
      - u_issue_expire_3
      - req_issue_006
      kwargs:
        items:
          expr: '[harness.issue_item(''COUPON_ISSUE_A'', expire_days=3)]'
        score_threshold: 0.0
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: assert resp['coupon']['expire_time'] - resp['coupon']['claim_time'] == 3 * 86400
  TC-ISSUE-007:
    steps:
    - call: harness.post_recommend
      args:
      - expr: harness.request('u_issue_threshold_control', 'req_issue_007a', items=harness.issue_items('COUPON_ISSUE_A'), score_threshold=1.0)
      save_as: first
    - call: harness.post_recommend
      args:
      - expr: harness.request('u_issue_threshold_control', 'req_issue_007b', items=harness.issue_items('COUPON_ISSUE_A'), score_threshold=0.0)
      save_as: second
    - assert: assert first['code'] == 0
    - assert: assert first['coupon'] is None
    - assert: assert second['code'] == 0
    - assert: assert second['coupon'] is not None
    - assert: assert second['coupon']['item_id'] == 'COUPON_ISSUE_A'
  TC-ISSUE-008:
    steps:
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_A
      - 0
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_B
      - 100
    - call: harness.post_recommend
      args:
      - expr: harness.request('u_issue_max_claim', 'req_issue_008a', items=harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B'),
          score_threshold=0.0, max_claim_per_request=1, policy_id='policy_fallback_001')
      save_as: first
    - call: harness.post_recommend
      args:
      - expr: harness.request('u_issue_max_claim', 'req_issue_008b', items=harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B'),
          score_threshold=0.0, max_claim_per_request=2, policy_id='policy_fallback_001')
      save_as: second
    - assert: assert first['code'] == 0
    - assert: assert first['coupon'] is None
    - assert: assert second['code'] == 0
    - assert: assert second['coupon'] is not None
    - assert: assert second['coupon']['item_id'] == 'COUPON_ISSUE_B'
  TC-ISSUE-009:
    steps:
    - call: harness.cleanup_user
      args:
      - user_no_coupons
    - call: harness.query_coupons
      args:
      - user_no_coupons
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupons'] == []
    - assert: assert resp['total'] == 0
  TC-ISSUE-010:
    steps:
    - call: harness.grpc_query_coupons
      args:
      - ''
      save_as: resp
    - assert: assert resp['code'] == 1001
    - assert: assert resp['message'] == 'user_id不能为空'
    - assert: assert resp['coupons'] == []
    - assert: assert resp['total'] == 0
  TC-ISSUE-011:
    steps:
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_A
      - 0
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_B
      - 100
    - call: harness.request
      args:
      - u_issue_stock_next
      - req_issue_011
      kwargs:
        items:
          expr: harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B')
        score_threshold: 0.0
        max_claim_per_request: 2
        policy_id: policy_fallback_001
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
    - assert: assert harness.stock('COUPON_ISSUE_A') == 0
  TC-ISSUE-012:
    steps:
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_A
      - 0
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_B
      - 0
    - call: harness.request
      args:
      - u_issue_all_empty
      - req_issue_012
      kwargs:
        score_threshold: 0.0
        max_claim_per_request: 2
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is None
    - assert: assert resp['code'] != 1006
  TC-ISSUE-013:
    steps:
    - call: harness.concurrent_issue_once
      save_as: result
    - assert: assert all(r['code'] == 0 for r in result['responses'])
    - assert: assert result['success_count'] == 1
    - assert: assert result['empty_count'] == 1
    - assert: assert result['stock'] == 0
  TC-ISSUE-016:
    steps:
    - call: harness.request
      args:
      - u_issue_default_expire
      - req_issue_016
      kwargs:
        items:
          expr: '[harness.issue_item(''COUPON_ISSUE_A'', expire_days=None)]'
        score_threshold: 0.0
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: assert resp['coupon']['expire_time'] - resp['coupon']['claim_time'] == 7 * 86400
  TC-ISSUE-017:
    steps:
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_A
      - 0
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_B
      - 100
    - call: harness.request
      args:
      - u_issue_max_gt_count
      - req_issue_017
      kwargs:
        items:
          expr: harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B')
        score_threshold: 0.0
        max_claim_per_request: 10
        policy_id: policy_fallback_001
      save_as: body
    - call: harness.post_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
  TC-ISSUE-018:
    steps:
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_A
      - 0
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_B
      - 100
    - call: harness.request
      args:
      - u_issue_grpc_stock_next
      - req_issue_018
      kwargs:
        items:
          expr: harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B')
        score_threshold: 0.0
        max_claim_per_request: 2
        policy_id: policy_fallback_001
      save_as: body
    - call: harness.grpc_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is not None
    - assert: assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
    - assert: assert harness.stock('COUPON_ISSUE_A') == 0
  TC-ISSUE-019:
    steps:
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_A
      - 0
    - call: harness.set_stock
      args:
      - COUPON_ISSUE_B
      - 0
    - call: harness.request
      args:
      - u_issue_grpc_all_empty
      - req_issue_019
      kwargs:
        score_threshold: 0.0
        max_claim_per_request: 2
      save_as: body
    - call: harness.grpc_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is None
    - assert: assert resp['code'] != 1006
  TC-ISSUE-020:
    steps:
    - call: harness.request
      args:
      - u_issue_grpc_max_gt_count
      - req_issue_020
      kwargs:
        score_threshold: 0.0
        max_claim_per_request: 10
      save_as: body
    - call: harness.grpc_recommend
      args:
      - expr: body
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['coupon'] is None or resp['coupon']['item_id'] in {r['item_id'] for r in resp['results']}
```
