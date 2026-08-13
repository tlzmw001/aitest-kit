# profile_ab_experiment_smoke_suite

```yaml
profile_scope: case_suite
parent_module: ab_experiment
suite: ab_experiment_smoke

case_flows:
  TC-AB-001:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_AB_001
          stock: 100
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_ab_hash_http
            reqId: req-ab-001
            scene_name: game
            device: mobile
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.experiment_keys(resp) <= {"coarse_rank_exp_game", "calibration_exp_game"}'
      - assert: 'assert "coarse_rank_exp_ad" not in resp["experiment_info"] and "calibration_exp_ad" not in resp["experiment_info"]'

  TC-AB-002:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_AB_001
          stock: 100
      - call: harness.recommend_grpc
        kwargs:
          request_overrides:
            user_id: u_ab_hash_grpc
            req_id: req-ab-002
            scene_name: ad
            device: pc
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.experiment_keys(resp) <= {"coarse_rank_exp_ad", "calibration_exp_ad"}'
      - assert: 'assert "coarse_rank_exp_game" not in resp["experiment_info"] and "calibration_exp_game" not in resp["experiment_info"]'

  TC-AB-003:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_AB_001
          stock: 100
      - call: harness.set_whitelist
        kwargs:
          user_id: u_ab_white
          strategy_map:
            coarse_rank_exp_game: cr_off
            calibration_exp_game: cal_off
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_ab_white
            reqId: req-ab-003
            scene_name: game
            device: mobile
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["experiment_info"].get("coarse_rank_exp_game") == "cr_off"'
      - assert: 'assert resp["experiment_info"].get("calibration_exp_game") == "cal_off"'

  TC-AB-004:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_AB_001
          stock: 100
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_ab_scene_game
            reqId: req-ab-004
            scene_name: game
            device: mobile
            external: 0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.experiment_keys(resp) <= {"coarse_rank_exp_game", "calibration_exp_game"}'
      - assert: 'assert not any(k.endswith("_ad") for k in resp["experiment_info"])'

  TC-AB-006:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_AB_001
          stock: 100
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_ab_external_http
            reqId: req-ab-006
            scene_name: game
            device: mobile
            external: 1
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["experiment_info"] == {}'

  TC-AB-007:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_AB_001
          stock: 100
      - call: harness.recommend_grpc
        kwargs:
          request_overrides:
            user_id: u_ab_external_grpc
            req_id: req-ab-007
            scene_name: game
            device: mobile
            external: 1
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["experiment_info"] == {}'

  TC-AB-011:
    steps:
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_AB_BOUNDARY_001
          stock: 100
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_ab_boundary_right
            reqId: req-ab-011
            items:
              - item_id: COUPON_AB_BOUNDARY_001
                coupon_type: discount
                value: 80
                min_spend: 5000
                expire_days: 7
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert "ab_boundary_right" not in resp["experiment_info"]'
```
