# profile_scene_routing_smoke_suite

```yaml
profile_scope: case_suite
parent_module: scene_routing
suite: scene_routing_smoke

case_flows:
  TC-ROUTE-001:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_game_mobile
            reqId: req-route-001
            scene_name: game
            device: mobile
            policy_id: ""
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 1001'

  TC-ROUTE-002:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_grpc
        kwargs:
          request_overrides:
            user_id: u_route_ad_pc
            req_id: req-route-002
            scene_name: ad
            device: pc
            policy_id: ""
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 2002'

  TC-ROUTE-003:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_external
            reqId: req-route-003
            scene_name: game
            device: mobile
            policy_id: ""
            external: 1
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 1001'

  TC-ROUTE-004:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_policy_fb
            reqId: req-route-004
            scene_name: game
            device: mobile
            policy_id: policy_fallback_001
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 3001'
      - assert: 'assert resp["experiment_info"] == {}'
      - assert: 'assert resp["results"][0]["score"] == resp["results"][0]["calibrated_score"]'

  TC-ROUTE-005:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_fallback
            reqId: req-route-005
            scene_name: game
            device: mobile
            policy_id: policy_fallback_001
            external: 0
            score_threshold: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["coupon"] is not None'
      - assert: 'assert resp["coupon"]["user_id"] == "u_fallback"'

  TC-ROUTE-006:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_grpc
        kwargs:
          request_overrides:
            user_id: u_route_unknown
            req_id: req-route-006
            scene_name: unknown_scene
            device: unknown_device
            policy_id: ""
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 3001'
      - assert: 'assert resp["experiment_info"] == {}'

  TC-ROUTE-007:
    steps:
      - call: harness.set_fallback_scores
        args:
          - "coupon:fallback:score:3001": "0.8"
            "coupon:fallback:score:default": "0.6"
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_007
            reqId: req-route-007
            scene_name: game
            device: mobile
            policy_id: policy_fallback_001
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["results"][0]["score"] == 0.8'
      - assert: 'assert resp["results"][0]["calibrated_score"] == 0.8'

  TC-ROUTE-008:
    steps:
      - call: harness.set_fallback_scores
        args:
          - "coupon:fallback:score:default": "0.6"
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_008
            reqId: req-route-008
            scene_name: game
            device: mobile
            policy_id: policy_fallback_001
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["results"][0]["score"] == 0.6'
      - assert: 'assert resp["results"][0]["calibrated_score"] == 0.6'

  TC-ROUTE-009:
    steps:
      - call: harness.clear_fallback_scores
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_009
            reqId: req-route-009
            scene_name: game
            device: mobile
            policy_id: policy_fallback_001
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["results"][0]["score"] == 0.5'
      - assert: 'assert resp["results"][0]["calibrated_score"] == 0.5'

  TC-ROUTE-011:
    steps:
      - call: harness.set_fallback_scores
        args:
          - "coupon:fallback:score:default": not-a-number
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_BOUNDARY_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_011
            reqId: req-route-011
            scene_name: game
            device: mobile
            policy_id: policy_fallback_001
            external: 0
            items:
              - item_id: COUPON_ROUTE_BOUNDARY_001
                coupon_type: discount
                value: 80
                min_spend: 5000
                expire_days: 7
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 3001'
      - assert: 'assert resp["results"][0]["score"] == 0.5'

  TC-ROUTE-013:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_BOUNDARY_001
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_route_013
            reqId: req-route-013
            scene_name: game
            device: mobile
            policy_id: ""
            external: 0
            items:
              - item_id: COUPON_ROUTE_BOUNDARY_001
                coupon_type: discount
                value: 80
                min_spend: 5000
                expire_days: 7
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 1001'

  TC-ROUTE-014:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_BOUNDARY_001
      - call: harness.recommend_grpc
        kwargs:
          request_overrides:
            user_id: u_route_014
            req_id: req-route-014
            scene_name: Game
            device: mobile
            policy_id: ""
            external: 0
            items:
              - item_id: COUPON_ROUTE_BOUNDARY_001
                coupon_type: discount
                value: 80
                min_spend: 5000
                expire_days: 7
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 3001'
      - assert: 'assert resp["experiment_info"] == {}'

  TC-ROUTE-018:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_ROUTE_BOUNDARY_001
      - call: harness.recommend_grpc
        kwargs:
          request_overrides:
            user_id: u_route_018
            req_id: req-route-018
            scene_name: game
            device: mobile
            policy_id: ""
            external: 0
            items:
              - item_id: COUPON_ROUTE_BOUNDARY_001
                coupon_type: discount
                value: 80
                min_spend: 5000
                expire_days: 7
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["scene_id"] == 1001'
```
