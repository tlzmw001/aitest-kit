# issuance module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
module_type: multi_endpoint
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.issuance import setup_issuance
default_fixture: setup_issuance
default_object: issue
```
