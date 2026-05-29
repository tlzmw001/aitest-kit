# ab_service module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
module_type: multi_endpoint
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
default_fixture: setup_ab_service
default_object: ab
default_case_setup:
  call: setup_ab_service
  kwargs:
    case_id: '{case_id}'
  save_as: ab
```
