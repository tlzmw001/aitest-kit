# rough_ranking module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
module_type: isolated_service
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
default_fixture: setup_rough_ranking
default_object: case
default_case_setup:
  call: setup_rough_ranking
  kwargs:
    case_id: '{case_id}'
  save_as: case
```
