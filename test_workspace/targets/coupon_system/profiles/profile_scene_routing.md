# scene_routing module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
assertion_rules:
- pattern: score == cal
  template: assert resp["results"][0]["score"] == resp["results"][0]["calibrated_score"]
- pattern: response.body.coupon != null
  template: assert resp["coupon"] is not None
- pattern: score == 0.8
  template: assert resp["results"][0]["score"] == 0.8
- pattern: cal == 0.8
  template: assert resp["results"][0]["calibrated_score"] == 0.8
- pattern: score == 0.6
  template: assert resp["results"][0]["score"] == 0.6
- pattern: cal == 0.6
  template: assert resp["results"][0]["calibrated_score"] == 0.6
- pattern: score == 0.5
  template: assert resp["results"][0]["score"] == 0.5
- pattern: cal == 0.5
  template: assert resp["results"][0]["calibrated_score"] == 0.5
module_type: standard_recommend
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
```
