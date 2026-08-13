# feature_scoring module profile

Stable module-level assertion rules. Suite-specific execution stays with suite profiles.

```yaml
assertion_rules:
- pattern: 除明确异常外，response.code == 0
  template: assert resp["code"] == 0
- pattern: response.body.coupon != null
  template: assert resp["coupon"] is not None
```
