# calibration module profile

This profile stores calibration-specific deterministic assertion rules and target-local fixture imports.

```yaml
module_type: standard_recommend
extra_imports:
  - "from test_workspace.targets.coupon_system.fixtures.calibration import http_base_url, ab_base_url, grpc_target"
assertion_rules:
  - pattern: 'mid = round(clamp(k_pw * s + b_pw), 4)'
    template: piecewise_cascade
    params:
      segments: [[0.3, 0.5, 0.1], [0.7, 1.0, 0.0], [1.0, 1.5, -0.2]]
      linear_k: 1.2
      linear_b: 0.05

  - pattern: 'mid = k_pw * s + b_pw'
    template: piecewise_cascade
    params:
      segments: [[0.3, 0.5, 0.1], [0.7, 1.0, 0.0], [1.0, 1.5, -0.2]]
      linear_k: 1.2
      linear_b: 0.05

  - pattern: 'cal == round(clamp(1.2 * mid + 0.05), 4)'
    template: skip
    params: {}

  - pattern: '按 `s` 所在区间计算'
    template: piecewise_only
    params:
      segments: [[0.3, 0.5, 0.1], [0.7, 1.0, 0.0], [1.0, 1.5, -0.2]]
```
