# rough_ranking_smoke suite profile

Case-specific setup is explicit: each flow prepares ranking parameters, request identity, and optional items before invoking the Harness.

```yaml
profile_scope: case_suite
parent_module: rough_ranking
suite: rough_ranking_smoke
case_flows:
  TC-RANK-001:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_001
        request_id: req-rank-001
        strategy_map:
          coarse_rank_exp_game: cr_off
          calibration_exp_game: cal_off
        params:
          enable_coarse_rank: false
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']
  TC-RANK-002:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_002
        request_id: req-rank-002
        params:
          enable_coarse_rank: true
          truncate_count: 3
    - call: harness.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']
  TC-RANK-003:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_003
        request_id: req-rank-003
        params:
          enable_coarse_rank: true
          truncate_count: 2
          truncate_rule: top_value
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-004:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_004
        request_id: req-rank-004
        params:
          enable_coarse_rank: true
          truncate_count: 2
          truncate_rule: top_min_spend
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-005:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_005
        request_id: req-rank-005
        params:
          enable_coarse_rank: true
          truncate_count: 2
          truncate_rule: random
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(harness.rank_input_items) == 2
    - assert: assert set(harness.rank_input_items) <= {'COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C'}
  TC-RANK-006:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_006
        request_id: req-rank-006
        params:
          enable_coarse_rank: true
          truncate_count: 2
          prior_count: 1
          prior_rule: top_value
          truncate_rule: top_value
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items[0] == 'COUPON_RANK_B'
    - assert: assert len(harness.rank_input_items) == 2
  TC-RANK-007:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_007
        request_id: req-rank-007
        params:
          enable_coarse_rank: true
          truncate_count: 3
          filters:
          - field: value
            op: gte
            value: 80
          - field: coupon_type
            op: in
            value: [discount, fixed]
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-008:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_008
        request_id: req-rank-008
        params:
          enable_coarse_rank: true
          truncate_count: 3
          sort_keys:
          - field: value
            weight: 1.0
          - field: min_spend
            weight: -1.0
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items[0] == 'COUPON_RANK_B'
  TC-RANK-009:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_009
        request_id: req-rank-009
        params:
          enable_coarse_rank: true
          truncate_count: 3
          truncate_rule: top_value
          diversity:
            enabled: true
            group_field: coupon_type
            max_per_group: 1
        items:
        - {item_id: COUPON_RANK_D1, coupon_type: discount, value: 100, min_spend: 1000, expire_days: 7}
        - {item_id: COUPON_RANK_D2, coupon_type: discount, value: 90, min_spend: 1000, expire_days: 7}
        - {item_id: COUPON_RANK_F1, coupon_type: fixed, value: 80, min_spend: 1000, expire_days: 7}
        - {item_id: COUPON_RANK_D3, coupon_type: discount, value: 70, min_spend: 1000, expire_days: 7}
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(harness.rank_input_items) == 3
    - assert: assert harness.rank_input_items[:2] == ['COUPON_RANK_D1', 'COUPON_RANK_F1']
  TC-RANK-010:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_010
        request_id: req-rank-010
        params:
          enable_coarse_rank: true
          truncate_count: 10
          truncate_rule: top_value
        items:
        - {item_id: COUPON_RANK_A, coupon_type: discount, value: 100, min_spend: 9000, expire_days: 7}
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(harness.rank_input_items) == 1
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A']
  TC-RANK-011:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_011
        request_id: req-rank-011
        params:
          enable_coarse_rank: true
          truncate_count: 1
          prior_count: 1
          prior_rule: top_value
    - call: harness.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_B']
  TC-RANK-012:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_012
        request_id: req-rank-012
        params:
          enable_coarse_rank: true
          truncate_count: 5
          prior_count: 2
          prior_rule: top_value
          filters:
          - {field: expire_days, op: gte, value: 3}
          sort_keys:
          - {field: value, weight: 1.0}
          diversity:
            enabled: true
            group_field: coupon_type
            max_per_group: 1
        items:
        - {item_id: P1, coupon_type: discount, value: 1000, min_spend: 1000, expire_days: 7, isPrior: true}
        - {item_id: P2, coupon_type: fixed, value: 900, min_spend: 1000, expire_days: 7, isPrior: true}
        - {item_id: P3, coupon_type: free_shipping, value: 100, min_spend: 1000, expire_days: 7, isPrior: true}
        - {item_id: A, coupon_type: discount, value: 800, min_spend: 1000, expire_days: 7}
        - {item_id: B, coupon_type: discount, value: 700, min_spend: 1000, expire_days: 1}
        - {item_id: C, coupon_type: fixed, value: 600, min_spend: 1000, expire_days: 7}
        - {item_id: D, coupon_type: fixed, value: 500, min_spend: 1000, expire_days: 1}
        - {item_id: E, coupon_type: free_shipping, value: 400, min_spend: 1000, expire_days: 7}
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['P1', 'P2', 'A', 'C', 'E']
    - assert: assert harness.rank_input_items[:2] == ['P1', 'P2']
  TC-RANK-013:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_013
        request_id: req-rank-013
        items: []
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 1001
    - assert: assert resp['results'] == []
    - assert: assert harness.rank_input_items == []
  TC-RANK-014:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_014
        request_id: req-rank-014
        params:
          enable_coarse_rank: true
          truncate_count: 0
          truncate_rule: top_value
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['results'] == []
    - assert: assert resp['coupon'] is None
    - assert: assert harness.rank_input_items == []
  TC-RANK-015:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_015
        request_id: req-rank-015
        params:
          enable_coarse_rank: true
          truncate_count: bad
          truncate_rule: top_value
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(harness.rank_input_items) == 3
  TC-RANK-016:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_016
        request_id: req-rank-016
        params:
          enable_coarse_rank: true
          truncate_count: 2
          truncate_rule: unknown_rule
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 未知粗排规则'
  TC-RANK-017:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_017
        request_id: req-rank-017
        params:
          enable_coarse_rank: true
          truncate_count: 2
          sort_keys:
          - bad
          - {field: 123, weight: 1}
          - {field: value, weight: bad}
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(harness.rank_input_items) == 2
  TC-RANK-018:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_018
        request_id: req-rank-018
        params:
          enable_coarse_rank: true
          truncate_count: 3
          filters:
          - {field: value, op: bad_op, value: 80}
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['results'] == []
    - assert: assert harness.rank_input_items == []
    - comment: 'MANUAL CHECK: 应用日志包含 未知过滤操作符'
  TC-RANK-019:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_019
        request_id: req-rank-019
        params:
          enable_coarse_rank: true
          truncate_count: 2
          truncate_rule: top_value
          diversity:
            enabled: true
            group_field: 123
            max_per_group: 0
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-020:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_020
        request_id: req-rank-020
        params:
          enable_coarse_rank: true
          truncate_count: 1
          prior_count: 3
          prior_rule: top_value
    - call: harness.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1'
  TC-RANK-021:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_021
        request_id: req-rank-021
        params:
          enable_coarse_rank: true
          truncate_count: bad
          truncate_rule: top_value
    - call: harness.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(harness.rank_input_items) == 3
  TC-RANK-022:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_022
        request_id: req-rank-022
        params:
          enable_coarse_rank: true
          truncate_count: 2
          truncate_rule: unknown_rule
    - call: harness.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 未知粗排规则'
  TC-RANK-023:
    steps:
    - call: harness.prepare
      kwargs:
        user_id: u_rank_023
        request_id: req-rank-023
        params:
          enable_coarse_rank: true
          truncate_count: 1
          prior_count: 3
          prior_rule: top_value
    - call: harness.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert harness.rank_input_items == ['COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1'
```
