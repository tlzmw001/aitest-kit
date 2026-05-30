# feature_scoring_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: feature_scoring
suite: feature_scoring_smoke
request_overrides:
  TC-FEAT-001:
    user_id: u_feat_http
    external: 0
  TC-FEAT-002:
    user_id: u_feat_grpc
    external: 0
  TC-FEAT-003:
    user_id: u_feat_item_merge
    external: 0
    items:
    - item_id: COUPON_FEAT_001
      coupon_type: discount
      value: 80
      min_spend: 5000
      expire_days: 7
  TC-SCORE-001:
    user_id: u_score_internal_http
    reqId: req-score-001
    external: 0
  TC-SCORE-002:
    user_id: u_score_internal_grpc
    req_id: req-score-002
    external: 0
  TC-SCORE-003:
    user_id: u_score_external_http
    reqId: req-score-003
    external: 1
  TC-SCORE-004:
    user_id: u_score_external_grpc
    req_id: req-score-004
    external: 1
  TC-SCORE-005:
    user_id: u_score_encrypt
    external: 1
  TC-FEAT-004:
    user_id: u_feat_missing
    items:
    - item_id: COUPON_FEAT_MISSING
      coupon_type: discount
      value: 80
      min_spend: 5000
      expire_days: 7
  TC-FEAT-006:
    user_id: u_feat_no_file
    items:
    - item_id: COUPON_FEAT_NO_FILE
      coupon_type: discount
      value: 80
      min_spend: 5000
      expire_days: 7
  TC-FEAT-007:
    user_id: u_feat_ok
    items:
    - item_id: COUPON_FEAT_OK
      coupon_type: discount
      value: 80
      min_spend: 5000
      expire_days: 7
  TC-FEAT-008:
    user_id: u_feat_bad
    items:
    - item_id: COUPON_FEAT_BAD
      coupon_type: discount
      value: 80
      min_spend: 5000
      expire_days: 7
  TC-FEAT-009:
    user_id: u_feat_not_in_tsv
    items:
    - item_id: COUPON_FEAT_NOT_IN_TSV
      coupon_type: discount
      value: 80
      min_spend: 5000
      expire_days: 7
```
