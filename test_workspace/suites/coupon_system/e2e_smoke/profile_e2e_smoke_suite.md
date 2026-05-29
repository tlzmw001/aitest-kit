# e2e_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: e2e
suite: e2e_smoke
request_overrides:
  TC-E2E-002:
    scene_name: ad
    device: pc
    external: 1
    items:
    - item_id: COUPON_SHIP_001
      coupon_type: free_shipping
      value: 1
      min_spend: 0
      expire_days: 7
  TC-E2E-003:
    policy_id: policy_fallback_001
    score_threshold: 0.4
  TC-E2E-006:
    scene_name: ad
    device: pc
    external: 1
    items:
    - item_id: COUPON_SHIP_001
      coupon_type: free_shipping
      value: 1
      min_spend: 0
      expire_days: 7
  TC-E2E-007:
    policy_id: policy_fallback_001
    score_threshold: 0.4
case_flows:
  TC-E2E-001:
    steps:
    - call: e2e.set_stock
      args:
      - COUPON_ACT_001
      - 5
    - call: e2e.request
      args:
      - u_e2e_http_internal_001
      - req_e2e_001
      save_as: body
    - call: e2e.post_recommend_response
      args:
      - expr: body
      save_as: response
    - assert: assert response.status_code == 200
    - assign: resp
      expr: response.json()
    - call: e2e.query_coupons
      args:
      - u_e2e_http_internal_001
      save_as: coupons
    - assert: assert resp["code"] == 0
    - assert: assert resp["scene_id"] == 1001
    - assert: 'assert resp["experiment_info"] == {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_on"}'
    - assert: assert resp["results"][0]["item_id"] == "COUPON_ACT_001"
    - assert: assert resp["results"][0]["recommended"] is True
    - assert: assert resp["coupon"] is not None
    - assert: assert resp["coupon"]["item_id"] == "COUPON_ACT_001"
    - assert: assert resp["coupon"]["user_id"] == "u_e2e_http_internal_001"
    - assert: assert resp["coupon"]["status"] == "claimed"
    - assert: assert e2e.stock("COUPON_ACT_001") == 4
    - assert: assert coupons["total"] == 1
    - assert: assert coupons["coupons"][0]["instance_id"] == resp["coupon"]["instance_id"]
  TC-E2E-002:
    steps:
    - call: e2e.set_stock
      args:
      - COUPON_SHIP_001
      - 5
    - call: e2e.request
      args:
      - u_e2e_http_external_002
      - req_e2e_002
      kwargs:
        coupon_id: COUPON_SHIP_001
        scene_name: ad
        device: pc
        external: 1
      save_as: body
    - call: e2e.post_recommend_response
      args:
      - expr: body
      save_as: response
    - assert: assert response.status_code == 200
    - assign: resp
      expr: response.json()
    - call: e2e.query_coupons
      args:
      - u_e2e_http_external_002
      save_as: coupons
    - assert: assert resp["code"] == 0
    - assert: assert resp["scene_id"] == 2002
    - assert: assert resp["experiment_info"] == {}
    - assert: assert resp["results"][0]["item_id"] == "COUPON_SHIP_001"
    - assert: assert resp["results"][0]["recommended"] is True
    - assert: assert resp["coupon"] is not None
    - assert: assert resp["coupon"]["item_id"] == "COUPON_SHIP_001"
    - assert: assert resp["coupon"]["user_id"] == "u_e2e_http_external_002"
    - assert: assert coupons["total"] == 1
    - assert: assert coupons["coupons"][0]["item_id"] == "COUPON_SHIP_001"
  TC-E2E-003:
    steps:
    - call: e2e.set_stock
      args:
      - COUPON_ACT_001
      - 2
    - call: e2e.request
      args:
      - u_e2e_dual_proto_003
      - req_e2e_003
      kwargs:
        policy_id: policy_fallback_001
        score_threshold: 0.4
      save_as: body
    - call: e2e.post_recommend_response
      args:
      - expr: body
      save_as: http_response
    - assert: assert http_response.status_code == 200
    - assign: http_json
      expr: http_response.json()
    - call: e2e.grpc_recommend
      args:
      - expr: body
      save_as: grpc_resp
    - assert: assert http_json["code"] == 0
    - assert: assert grpc_resp["code"] == 0
    - assert: assert http_json["scene_id"] == 3001
    - assert: assert grpc_resp["scene_id"] == 3001
    - assert: assert http_json["experiment_info"] == {}
    - assert: assert grpc_resp["experiment_info"] == {}
    - assert: assert http_json["results"][0]["item_id"] == "COUPON_ACT_001"
    - assert: assert grpc_resp["results"][0]["item_id"] == "COUPON_ACT_001"
    - assert: assert http_json["results"][0]["score"] == 0.5
    - assert: assert grpc_resp["results"][0]["score"] == 0.5
    - assert: assert http_json["results"][0]["calibrated_score"] == 0.5
    - assert: assert grpc_resp["results"][0]["calibrated_score"] == 0.5
    - assert: assert http_json["results"][0]["recommended"] is True
    - assert: assert grpc_resp["results"][0]["recommended"] is True
    - assert: assert http_json["coupon"]["item_id"] == "COUPON_ACT_001"
    - assert: assert grpc_resp["coupon"]["item_id"] == "COUPON_ACT_001"
    - assert: assert e2e.stock("COUPON_ACT_001") == 0
  TC-E2E-004:
    steps:
    - call: e2e.set_stock
      args:
      - COUPON_ACT_001
      - 3
    - call: e2e.request
      args:
      - u_e2e_calibration_004
      - req_e2e_004
      save_as: body
    - call: e2e.post_recommend_response
      args:
      - expr: body
      save_as: response
    - assert: assert response.status_code == 200
    - assign: resp
      expr: response.json()
    - assert: assert resp["code"] == 0
    - assert: assert resp["scene_id"] == 1001
    - assert: 'assert resp["experiment_info"] == {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_on"}'
    - assert: assert resp["results"][0]["item_id"] == "COUPON_ACT_001"
    - assert: assert resp["results"][0]["calibrated_score"] > resp["results"][0]["score"]
    - assert: assert resp["coupon"] is not None
    - assert: assert resp["coupon"]["item_id"] == "COUPON_ACT_001"
    - assert: assert e2e.stock("COUPON_ACT_001") == 2
  TC-E2E-006:
    steps:
    - call: e2e.set_stock
      args:
      - COUPON_SHIP_001
      - 3
    - call: e2e.request
      args:
      - u_e2e_external_skip_006
      - req_e2e_006
      kwargs:
        coupon_id: COUPON_SHIP_001
        scene_name: ad
        device: pc
        external: 1
      save_as: body
    - call: e2e.post_recommend_response
      args:
      - expr: body
      save_as: response
    - assert: assert response.status_code == 200
    - assign: resp
      expr: response.json()
    - call: e2e.query_coupons
      args:
      - u_e2e_external_skip_006
      save_as: coupons
    - assert: assert resp["code"] == 0
    - assert: assert resp["scene_id"] == 2002
    - assert: assert resp["experiment_info"] == {}
    - assert: assert resp["coupon"] is not None
    - assert: assert resp["coupon"]["item_id"] == "COUPON_SHIP_001"
    - assert: assert coupons["total"] == 1
  TC-E2E-007:
    steps:
    - call: e2e.set_stock
      args:
      - COUPON_ACT_001
      - 1
    - call: e2e.request
      args:
      - u_e2e_shared_state_007
      - req_e2e_007
      kwargs:
        policy_id: policy_fallback_001
        score_threshold: 0.4
      save_as: body
    - call: e2e.grpc_recommend
      args:
      - expr: body
      save_as: grpc_resp
    - call: e2e.query_coupons
      args:
      - u_e2e_shared_state_007
      save_as: http_json
    - assert: assert grpc_resp["code"] == 0
    - assert: assert grpc_resp["scene_id"] == 3001
    - assert: assert grpc_resp["coupon"] is not None
    - assert: assert grpc_resp["coupon"]["item_id"] == "COUPON_ACT_001"
    - assert: assert http_json["code"] == 0
    - assert: assert http_json["total"] == 1
    - assert: assert http_json["coupons"][0]["instance_id"] == grpc_resp["coupon"]["instance_id"]
    - assert: assert http_json["coupons"][0]["item_id"] == "COUPON_ACT_001"
```
