# feature_scoring 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `http_base_url` | conftest session | 主服务 HTTP 地址 |
| `grpc_target` | conftest session | 主服务 gRPC 地址 |
| `setup_feature_scoring` | fixtures/feature_scoring.py | 初始化库存和用户特征 |

## 请求模板

请求经推荐接口进入特征抽取和打分链路。内部打分走 gRPC mock，外部打分走 HTTP mock。

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| `coupon != null` | `resp["coupon"] is not None` |

## setup 映射

| 场景变量描述 | fixture 行为 |
|-------------|--------------|
| 用户特征 | 调 `/api/v1/admin/user-features` 写入基础特征 |
| 库存 | 初始化 feature scoring 用例涉及的 coupon 库存 |

## emitter 规则

```yaml
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
assertion_rules:
  - pattern: '除明确异常外，response.code == 0'
    template: 'assert resp["code"] == 0'
  - pattern: 'response.body.coupon != null'
    template: 'assert resp["coupon"] is not None'
```
