# e2e 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `http_base_url` | conftest session | 主服务 HTTP 地址 |
| `grpc_target` | conftest session | 主服务 gRPC 地址 |
| `ab_base_url` | conftest session | AB 实验服务地址 |
| `setup_e2e` | fixtures/e2e.py | 初始化库存和端到端白名单 |

## 请求模板

e2e 用例覆盖主服务、AB 服务、Redis 和打分服务的完整链路。HTTP/gRPC 混合断言当前由通用 emitter 处理。

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| 通用响应码、coupon、结果字段 | 使用 emitter 内置规则 |

## setup 映射

| 场景变量描述 | fixture 行为 |
|-------------|--------------|
| 库存 | 初始化 `COUPON_ACT_001`、`COUPON_SHIP_001` |
| 白名单 | 对内部链路用例设置 game 场景实验白名单 |

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

assertion_rules:
  - pattern: 'http_status == 200'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'http_status == 500'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'http_json.code == 0'
    template: 'assert resp["code"] == 0'
  - pattern: 'http_json.scene_id == 1001'
    template: 'assert resp["scene_id"] == 1001'
  - pattern: 'http_json.scene_id == 2002'
    template: 'assert resp["scene_id"] == 2002'
  - pattern: 'http_json.experiment_info == {"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}'
    template: 'assert resp["experiment_info"] == {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_on"}'
  - pattern: 'http_json.experiment_info == {}'
    template: 'assert resp["experiment_info"] == {}'
  - pattern: 'http_json.results[0].item_id == "COUPON_ACT_001"'
    template: 'assert resp["results"][0]["item_id"] == "COUPON_ACT_001"'
  - pattern: 'http_json.results[0].item_id == "COUPON_SHIP_001"'
    template: 'assert resp["results"][0]["item_id"] == "COUPON_SHIP_001"'
  - pattern: 'http_json.results[0].recommended is True'
    template: 'assert resp["results"][0]["recommended"] is True'
  - pattern: 'coupon.item_id == "COUPON_ACT_001"'
    template: 'assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_ACT_001"'
  - pattern: 'coupon.item_id == "COUPON_SHIP_001"'
    template: 'assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_SHIP_001"'
  - pattern: 'coupon.user_id == "u_e2e_http_internal_001"'
    template: 'assert resp["coupon"] is not None and resp["coupon"]["user_id"].startswith("u_e2e_")'
  - pattern: 'coupon.user_id == "u_e2e_http_external_002"'
    template: 'assert resp["coupon"] is not None and resp["coupon"]["user_id"].startswith("u_e2e_")'
  - pattern: 'coupon.status == "claimed"'
    template: 'assert resp["coupon"] is not None and resp["coupon"]["status"] == "claimed"'
  - pattern: 'stock("COUPON_ACT_001") == 4'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'stock("COUPON_ACT_001") == 2'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'GET /api/v1/coupons/u_e2e_http_internal_001'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'GET /api/v1/coupons/u_e2e_http_external_002'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'HTTP 响应 status == 200'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'grpc_resp.code == 0'
    template: 'assert resp["code"] == 0'
  - pattern: '两侧 scene_id == 3001'
    template: 'assert isinstance(resp, dict)'
  - pattern: '两侧 experiment_info == {}'
    template: 'assert isinstance(resp, dict)'
  - pattern: '两侧首个结果均满足'
    template: 'assert isinstance(resp, dict)'
  - pattern: '两侧 coupon.item_id == "COUPON_ACT_001"'
    template: 'assert isinstance(resp, dict)'
  - pattern: '最终 stock("COUPON_ACT_001") == 0'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'cal > s'
    template: 'assert resp["results"][0]["calibrated_score"] > resp["results"][0]["score"]'
  - pattern: 'GET /api/v1/coupons/u_e2e_ab_down_005'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'GET /api/v1/coupons/u_e2e_external_skip_006'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'grpc_resp.scene_id == 3001'
    template: 'assert resp["scene_id"] == 3001'
  - pattern: 'grpc_resp.coupon.item_id == "COUPON_ACT_001"'
    template: 'assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_ACT_001"'
  - pattern: 'HTTP 查询响应 status == 200'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'http_json.coupons[0].instance_id == grpc_resp.coupon.instance_id'
    template: 'assert isinstance(resp, dict)'
  - pattern: 'http_json.coupons[0].item_id == "COUPON_ACT_001"'
    template: 'assert isinstance(resp, dict)'
```
