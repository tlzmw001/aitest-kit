# scene_routing_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: scene_routing
suite: scene_routing_smoke
request_overrides:
  TC-ROUTE-001:
    user_id: u_route_game_mobile
    scene_name: game
    device: mobile
    policy_id: ''
    external: 0
  TC-ROUTE-002:
    user_id: u_route_ad_pc
    scene_name: ad
    device: pc
    policy_id: ''
    external: 0
  TC-ROUTE-003:
    user_id: u_route_external
    scene_name: game
    device: mobile
    policy_id: ''
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
    policy_id: ''
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
    policy_id: ''
    external: 0
  TC-ROUTE-014:
    scene_name: Game
    device: mobile
    policy_id: ''
    external: 0
  TC-ROUTE-017:
    scene_name: game
    device: mobile
    policy_id: policy_fallback_001
    external: 0
  TC-ROUTE-018:
    scene_name: game
    device: mobile
    policy_id: ''
    external: 0
```
