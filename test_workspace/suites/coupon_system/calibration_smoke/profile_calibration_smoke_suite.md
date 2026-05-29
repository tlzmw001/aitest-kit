# calibration_smoke suite profile

This suite profile intentionally keeps suite-specific rules empty. It validates
the target-aware merge path: module rules come from
`test_workspace/targets/coupon_system/profiles/profile_calibration.md`, while
this file only declares suite identity.

```yaml
profile_scope: case_suite
parent_module: calibration
suite: calibration_smoke
```
