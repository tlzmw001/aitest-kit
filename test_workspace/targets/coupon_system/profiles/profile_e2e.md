# e2e module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
module_type: multi_endpoint
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
default_fixture: setup_e2e
default_object: e2e
default_case_setup:
  call: setup_e2e
  kwargs:
    case_id: '{case_id}'
  save_as: e2e
```
