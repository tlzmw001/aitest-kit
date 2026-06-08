# logging module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
module_type: subprocess_capture
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.logging import setup_logging
default_fixture: setup_logging
default_object: case
```
