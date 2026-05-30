# discount_policy module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
module_type: multi_endpoint
default_fixture: setup_discount_policy
default_object: dp
default_case_setup:
  call: setup_discount_policy
  kwargs:
    case_id: '{case_id}'
  save_as: dp
```
