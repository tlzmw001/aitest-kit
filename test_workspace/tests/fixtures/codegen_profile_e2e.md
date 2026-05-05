# e2e 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `http_base_url` | conftest session | 主服务 HTTP 地址 |
| `grpc_target` | conftest session | 主服务 gRPC 地址 |
| `ab_base_url` | conftest session | AB 实验服务地址 |
| `setup_e2e` | fixtures/e2e.py | 初始化库存和端到端白名单 |

## 请求模板

e2e 用例覆盖主服务、AB 服务、Redis 和打分服务的完整链路。由于断言需要多次调用推荐、库存查询和用户券查询，本模块使用 `case_flows` 显式描述执行步骤。

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| HTTP/gRPC 推荐、库存、用户券查询闭环 | 使用 `case_flows` 调用 `setup_e2e(...).post_recommend_response / grpc_recommend / query_coupons / stock` |

## setup 映射

| 场景变量描述 | fixture 行为 |
|-------------|--------------|
| 库存 | 各 `case_flow` 按用例设置 `COUPON_ACT_001` 或 `COUPON_SHIP_001` 的精确库存 |
| 白名单 | `TC-E2E-001`、`TC-E2E-004` 通过 `setup_e2e(case_id)` 设置 game 场景实验白名单 |

## emitter 规则

```yaml
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
    fixture: setup_e2e
    steps:
      - call: setup_e2e
        kwargs:
          case_id: TC-E2E-001
        save_as: e2e
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
    fixture: setup_e2e
    steps:
      - call: setup_e2e
        kwargs:
          case_id: TC-E2E-002
        save_as: e2e
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
    fixture: setup_e2e
    steps:
      - call: setup_e2e
        kwargs:
          case_id: TC-E2E-003
        save_as: e2e
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
    fixture: setup_e2e
    steps:
      - call: setup_e2e
        kwargs:
          case_id: TC-E2E-004
        save_as: e2e
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
    fixture: setup_e2e
    steps:
      - call: setup_e2e
        kwargs:
          case_id: TC-E2E-006
        save_as: e2e
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
    fixture: setup_e2e
    steps:
      - call: setup_e2e
        kwargs:
          case_id: TC-E2E-007
        save_as: e2e
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
