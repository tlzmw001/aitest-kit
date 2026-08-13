# scene_routing module profile

Stable module-level assertion rules. Suite-specific execution stays with suite profiles.

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
```
