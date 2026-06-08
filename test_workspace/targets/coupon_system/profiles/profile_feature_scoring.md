# feature_scoring module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
assertion_rules:
- pattern: 除明确异常外，response.code == 0
  template: assert resp["code"] == 0
- pattern: response.body.coupon != null
  template: assert resp["coupon"] is not None
module_type: standard_recommend
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.feature_scoring import setup_feature_scoring
default_fixture: setup_feature_scoring
default_object: client
```
