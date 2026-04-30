# scene_routing 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `http_base_url` | conftest session | 主服务 HTTP 地址 |
| `grpc_target` | conftest session | 主服务 gRPC 地址 |
| `setup_scene_routing` | fixtures/scene_routing.py | 初始化场景路由用例库存 |

## 请求模板

场景路由用例通过推荐接口验证 `scene_name + device + policy_id` 到 `scene_id` 的映射和兜底行为。

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| `score == cal` | 提取首个 result 比较 `score` 与 `calibrated_score` |
| 兜底固定分 | 断言首个 result 分数字段 |
| `coupon != null` | 断言 coupon 非空 |

## setup 映射

| 场景变量描述 | fixture 行为 |
|-------------|--------------|
| 库存 | 初始化 route 相关 coupon 库存 |

## emitter 规则

```yaml
request_overrides:
  TC-ROUTE-001:
    user_id: u_route_game_mobile
    scene_name: game
    device: mobile
    policy_id: ""
    external: 0
  TC-ROUTE-002:
    user_id: u_route_ad_pc
    scene_name: ad
    device: pc
    policy_id: ""
    external: 0
  TC-ROUTE-003:
    user_id: u_route_external
    scene_name: game
    device: mobile
    policy_id: ""
    external: 1
  TC-ROUTE-004:
    user_id: u_route_policy_fb
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-005:
    user_id: u_fallback
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
    score_threshold: 0.0
  TC-ROUTE-006:
    user_id: u_route_unknown
    scene_name: unknown_scene
    device: unknown_device
    policy_id: ""
    external: 0
  TC-ROUTE-007:
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-008:
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-009:
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-010:
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-011:
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-013:
    scene_name: game
    device: mobile
    policy_id: ""
    external: 0
  TC-ROUTE-014:
    scene_name: Game
    device: mobile
    policy_id: ""
    external: 0
  TC-ROUTE-017:
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-018:
    scene_name: game
    device: mobile
    policy_id: ""
    external: 0
assertion_rules:
  - pattern: 'score == cal'
    template: 'assert resp["results"][0]["score"] == resp["results"][0]["calibrated_score"]'
  - pattern: 'response.body.coupon != null'
    template: 'assert resp["coupon"] is not None'
  - pattern: 'score == 0.8'
    template: 'assert resp["results"][0]["score"] == 0.8'
  - pattern: 'cal == 0.8'
    template: 'assert resp["results"][0]["calibrated_score"] == 0.8'
  - pattern: 'score == 0.6'
    template: 'assert resp["results"][0]["score"] == 0.6'
  - pattern: 'cal == 0.6'
    template: 'assert resp["results"][0]["calibrated_score"] == 0.6'
  - pattern: 'score == 0.5'
    template: 'assert resp["results"][0]["score"] == 0.5'
  - pattern: 'cal == 0.5'
    template: 'assert resp["results"][0]["calibrated_score"] == 0.5'
```
