# logging module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
module_type: subprocess_capture
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
```
