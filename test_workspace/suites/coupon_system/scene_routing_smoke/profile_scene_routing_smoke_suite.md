# scene_routing_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: scene_routing
suite: scene_routing_smoke
requests:
  TC-ROUTE-001:
    overrides:
      user_id: u_route_game_mobile
      scene_name: game
      device: mobile
      policy_id: ''
      external: 0
  TC-ROUTE-002:
    overrides:
      user_id: u_route_ad_pc
      scene_name: ad
      device: pc
      policy_id: ''
      external: 0
  TC-ROUTE-003:
    overrides:
      user_id: u_route_external
      scene_name: game
      device: mobile
      policy_id: ''
      external: 1
  TC-ROUTE-004:
    overrides:
      user_id: u_route_policy_fb
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
  TC-ROUTE-005:
    overrides:
      user_id: u_fallback
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
      score_threshold: 0.0
  TC-ROUTE-006:
    overrides:
      user_id: u_route_unknown
      scene_name: unknown_scene
      device: unknown_device
      policy_id: ''
      external: 0
  TC-ROUTE-007:
    overrides:
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
  TC-ROUTE-008:
    overrides:
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
  TC-ROUTE-009:
    overrides:
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
  TC-ROUTE-010:
    overrides:
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
  TC-ROUTE-011:
    overrides:
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
  TC-ROUTE-013:
    overrides:
      scene_name: game
      device: mobile
      policy_id: ''
      external: 0
  TC-ROUTE-014:
    overrides:
      scene_name: Game
      device: mobile
      policy_id: ''
      external: 0
  TC-ROUTE-017:
    overrides:
      scene_name: game
      device: mobile
      policy_id: policy_fallback_001
      external: 0
  TC-ROUTE-018:
    overrides:
      scene_name: game
      device: mobile
      policy_id: ''
      external: 0
```
