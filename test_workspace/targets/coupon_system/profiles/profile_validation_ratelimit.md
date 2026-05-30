# validation_ratelimit module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
default_case_setup:
  call: client_factory
  kwargs:
    case_id: '{case_id}'
  save_as: case
default_fixture: setup_validation_ratelimit
module_type: isolated_service
default_object: client_factory
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
```
