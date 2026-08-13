# profile_feature_scoring_smoke_suite

```yaml
profile_scope: case_suite
parent_module: feature_scoring
suite: feature_scoring_smoke

case_flows:
  TC-SCORE-003:
    steps:
      - call: harness.prepare_user
        kwargs:
          user_id: u_score_external_http
          features:
            gender: male
            age: 28
            total_spend: 30000
            purchase_frequency: 4
            register_days: 120
            is_new_user: true
            is_member: true
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_FEAT_001
          stock: 100
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_score_external_http
            reqId: req-score-003
            external: 1
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["results"][0]["score"] >= 0.2'
      - assert: 'assert resp["experiment_info"] == {}'

  TC-SCORE-004:
    steps:
      - call: harness.prepare_user
        kwargs:
          user_id: u_score_external_grpc
          features:
            gender: male
            age: 28
            total_spend: 30000
            purchase_frequency: 4
            register_days: 120
            is_new_user: true
            is_member: true
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_FEAT_001
          stock: 100
      - call: harness.recommend_grpc
        kwargs:
          request_overrides:
            user_id: u_score_external_grpc
            req_id: req-score-004
            external: 1
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["results"][0]["score"] >= 0.2'
      - assert: 'assert resp["experiment_info"] == {}'

  TC-FEAT-009:
    steps:
      - call: harness.prepare_user
        kwargs:
          user_id: u_feat_not_in_tsv
          features:
            gender: male
            age: 28
            total_spend: 30000
            purchase_frequency: 4
            register_days: 120
            is_new_user: true
            is_member: true
      - call: harness.prepare_stock
        kwargs:
          coupon_id: COUPON_FEAT_NOT_IN_TSV
          stock: 100
      - call: harness.recommend_http
        kwargs:
          request_overrides:
            user_id: u_feat_not_in_tsv
            items:
              - item_id: COUPON_FEAT_NOT_IN_TSV
                coupon_type: discount
                value: 80
                min_spend: 5000
                expire_days: 7
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert resp["results"][0]["item_id"] == "COUPON_FEAT_NOT_IN_TSV"'
```
