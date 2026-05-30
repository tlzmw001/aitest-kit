# rough_ranking_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: rough_ranking
suite: rough_ranking_smoke
case_flows:
  TC-RANK-001:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']
  TC-RANK-002:
    steps:
    - call: case.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']
  TC-RANK-003:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-004:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-005:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(case.rank_input_items) == 2
    - assert: assert set(case.rank_input_items) <= {'COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C'}
  TC-RANK-006:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items[0] == 'COUPON_RANK_B'
    - assert: assert len(case.rank_input_items) == 2
  TC-RANK-007:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-008:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items[0] == 'COUPON_RANK_B'
  TC-RANK-009:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(case.rank_input_items) == 3
    - assert: assert case.rank_input_items[:2] == ['COUPON_RANK_D1', 'COUPON_RANK_F1']
  TC-RANK-010:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(case.rank_input_items) == 1
    - assert: assert case.rank_input_items == ['COUPON_RANK_A']
  TC-RANK-011:
    steps:
    - call: case.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_B']
  TC-RANK-012:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['P1', 'P2', 'A', 'C', 'E']
    - assert: assert case.rank_input_items[:2] == ['P1', 'P2']
  TC-RANK-013:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 1001
    - assert: assert resp['results'] == []
    - assert: assert case.rank_input_items == []
  TC-RANK-014:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['results'] == []
    - assert: assert resp['coupon'] is None
    - assert: assert case.rank_input_items == []
  TC-RANK-015:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(case.rank_input_items) == 3
  TC-RANK-016:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 未知粗排规则'
  TC-RANK-017:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(case.rank_input_items) == 2
  TC-RANK-018:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert resp['results'] == []
    - assert: assert case.rank_input_items == []
    - comment: 'MANUAL CHECK: 应用日志包含 未知过滤操作符'
  TC-RANK-019:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
  TC-RANK-020:
    steps:
    - call: case.recommend_http
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1'
  TC-RANK-021:
    steps:
    - call: case.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert len(case.rank_input_items) == 3
  TC-RANK-022:
    steps:
    - call: case.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 未知粗排规则'
  TC-RANK-023:
    steps:
    - call: case.recommend_grpc
      save_as: resp
    - assert: assert resp['code'] == 0
    - assert: assert case.rank_input_items == ['COUPON_RANK_B']
    - comment: 'MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1'
```
