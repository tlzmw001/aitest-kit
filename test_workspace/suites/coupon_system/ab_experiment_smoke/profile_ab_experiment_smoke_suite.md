# ab_experiment_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: ab_experiment
suite: ab_experiment_smoke
request_overrides:
  TC-AB-001:
    user_id: u_ab_hash_http
    reqId: req-ab-001
    scene_name: game
    device: mobile
    external: 0
  TC-AB-002:
    user_id: u_ab_hash_grpc
    req_id: req-ab-002
    scene_name: ad
    device: pc
    external: 0
  TC-AB-003:
    user_id: u_ab_white
    reqId: req-ab-003
    scene_name: game
    device: mobile
    external: 0
  TC-AB-004:
    user_id: u_ab_scene_game
    reqId: req-ab-004
    scene_name: game
    device: mobile
    external: 0
  TC-AB-005:
    user_id: u_ab_no_mapping
    reqId: req-ab-005
    scene_name: game
    device: mobile
    external: 0
  TC-AB-006:
    user_id: u_ab_external_http
    reqId: req-ab-006
    scene_name: game
    device: mobile
    external: 1
  TC-AB-007:
    user_id: u_ab_external_grpc
    req_id: req-ab-007
    scene_name: game
    device: mobile
    external: 1
  TC-AB-009:
    user_id: u_ab_unknown_exp
    reqId: req-ab-009
    scene_name: game
    device: mobile
    external: 0
```
