# profile_calibration_smoke_suite

```yaml
profile_scope: case_suite
parent_module: calibration
suite: calibration_smoke

case_flows:
  TC-CAL-001:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-001
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 1.2
                b: 0.1
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_linear(resp, k=1.2, b=0.1)'

  TC-CAL-002:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-002
          piecewise_files:
            1:
              - conditions:
                  device: mobile
                segments:
                  - range: [0.0, 0.3]
                    k: 0.5
                    b: 0.1
                  - range: [0.3, 0.7]
                    k: 1.0
                    b: 0.0
                  - range: [0.7, 1.0]
                    k: 1.5
                    b: -0.2
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 1.2
                b: 0.05
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_piecewise_then_linear(resp, linear_k=1.2, linear_b=0.05)'

  TC-CAL-003:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-003
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 0.8
                b: 0.0
            3:
              - conditions:
                  device: mobile
                k: 1.3
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_linear(resp, k=1.3, b=0.0)'

  TC-CAL-004:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-004
          linear_files:
            1:
              - conditions:
                  unknown: x
                k: 2.0
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_unchanged(resp)'

  TC-CAL-005:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-005
          enable_calibration: false
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 2.0
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_unchanged(resp)'

  TC-CAL-006:
    steps:
      - call: harness.run_grpc_calibration
        kwargs:
          resource_key: TC-CAL-006
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 1.5
                b: 0.1
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_linear(resp, k=1.5, b=0.1)'

  TC-CAL-007:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-007
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 1.2
                b: 0.0
              - conditions:
                  device: mobile
                k: 2.0
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_linear(resp, k=1.2, b=0.0)'

  TC-CAL-008:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-008
          linear_files:
            1:
              - conditions:
                  gender: male
                k: 2.0
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_unchanged(resp)'

  TC-CAL-009:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-009
          linear_files:
            1:
              - conditions:
                  unknown_field: x
                k: 2.0
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_unchanged(resp)'

  TC-CAL-010:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-010
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 1.5
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_linear(resp, k=1.5, b=0.0)'

  TC-CAL-011:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-011
          piecewise_files:
            1:
              - conditions:
                  device: mobile
                segments:
                  - range: [0.0, 0.3]
                    k: 0.5
                    b: 0.1
                  - range: [0.3, 0.7]
                    k: 1.0
                    b: 0.0
                  - range: [0.7, 1.0]
                    k: 1.5
                    b: -0.2
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_piecewise(resp)'

  TC-CAL-012:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-012
          piecewise_files:
            1:
              - conditions:
                  device: mobile
                segments:
                  - range: [0.0, 0.3]
                    k: 0.5
                    b: 0.1
                  - range: [0.3, 0.7]
                    k: 1.0
                    b: 0.0
                  - range: [0.7, 1.0]
                    k: 1.5
                    b: -0.2
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 1.2
                b: 0.05
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_piecewise_then_linear(resp, linear_k=1.2, linear_b=0.05)'

  TC-CAL-013:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-013
          piecewise_files:
            1:
              - conditions:
                  device: ios
                segments:
                  - range: [0.0, 0.3]
                    k: 0.5
                    b: 0.1
                  - range: [0.3, 0.7]
                    k: 1.0
                    b: 0.0
                  - range: [0.7, 1.0]
                    k: 1.5
                    b: -0.2
          linear_files:
            1:
              - conditions:
                  device: ios
                k: 1.2
                b: 0.05
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_unchanged(resp)'

  TC-CAL-014:
    steps:
      - call: harness.run_http_calibration
        kwargs:
          resource_key: TC-CAL-014
          linear_files:
            1:
              - conditions:
                  device: mobile
                k: 1.1
                b: 0.0
            3:
              - conditions:
                  device: mobile
                k: 1.8
                b: 0.0
        save_as: resp
      - assert: 'assert resp["code"] == 0'
      - assert: 'assert harness.matches_linear(resp, k=1.8, b=0.0)'
```
