# calibration target profile

This module profile is used by target-aware suite codegen for `coupon_system`.
The fixture remains registered through the legacy pytest plugin path during
Phase 4; this profile proves that suite codegen can read module rules from the
target profile directory.

```yaml
module_type: standard_recommend

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
