# validation_ratelimit_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: validation_ratelimit
suite: validation_ratelimit_smoke
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.validation_ratelimit import BOUNDARY_ITEM, ERR, LIMITED
case_flows:
  TC-VAL-001:
    steps:
    - call: case.http
      args:
      - ''
      - req-val-001
      kwargs:
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-002:
    steps:
    - call: case.http
      args:
      - u_val_scene_empty
      - req-val-002
      kwargs:
        scene_name: ''
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-003:
    steps:
    - call: case.http
      args:
      - u_val_device_empty
      - req-val-003
      kwargs:
        device: ''
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-005:
    steps:
    - call: case.grpc_missing
      args:
      - u_val_grpc_missing_control
      - req-val-005
      - external
      save_as: resp
    - assert: assert resp == ERR
  TC-GRPC-001:
    steps:
    - call: case.grpc_missing
      args:
      - u_grpc_external_missing
      - req-grpc-001
      - external
      save_as: resp
    - assert: assert resp == ERR
  TC-GRPC-002:
    steps:
    - call: case.grpc_missing
      args:
      - u_grpc_threshold_missing
      - req-grpc-002
      - score_threshold
      save_as: resp
    - assert: assert resp == ERR
  TC-GRPC-003:
    steps:
    - call: case.grpc_missing
      args:
      - u_grpc_max_claim_missing
      - req-grpc-003
      - max_claim_per_request
      save_as: resp
    - assert: assert resp == ERR
  TC-SCHEMA-001:
    steps:
    - call: case.body
      args:
      - u_schema_external_missing
      - req-schema-001
      kwargs:
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: body
    - call: body.pop
      args:
      - external
    - call: case.http_response
      args:
      - ref: body
      save_as: resp
    - assert: assert resp.status_code == 422
    - assign: locs
      expr: '[item["loc"] for item in resp.json()["detail"]]'
    - assert: assert ["body", "external"] in locs
  TC-SCHEMA-002:
    steps:
    - call: case.body
      args:
      - u_schema_threshold_missing
      - req-schema-002
      kwargs:
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: body
    - call: body.pop
      args:
      - score_threshold
    - call: case.http_response
      args:
      - ref: body
      save_as: resp
    - assert: assert resp.status_code == 422
    - assign: locs
      expr: '[item["loc"] for item in resp.json()["detail"]]'
    - assert: assert ["body", "score_threshold"] in locs
  TC-SCHEMA-003:
    steps:
    - call: case.body
      args:
      - u_schema_max_claim_missing
      - req-schema-003
      kwargs:
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: body
    - call: body.pop
      args:
      - max_claim_per_request
    - call: case.http_response
      args:
      - ref: body
      save_as: resp
    - assert: assert resp.status_code == 422
    - assign: locs
      expr: '[item["loc"] for item in resp.json()["detail"]]'
    - assert: assert ["body", "max_claim_per_request"] in locs
  TC-VAL-004:
    steps:
    - call: case.http
      args:
      - u_val_items_empty
      - req-val-004
      kwargs:
        items: []
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-006:
    steps:
    - call: case.http
      args:
      - u_val_http_external_2
      - req-val-006
      kwargs:
        external: 2
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-007:
    steps:
    - call: case.grpc
      args:
      - u_val_grpc_external_2
      - req-val-007
      kwargs:
        external: 2
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-008:
    steps:
    - call: case.http
      args:
      - u_val_http_threshold_low
      - req-val-008
      kwargs:
        external: 0
        score_threshold: -0.01
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-009:
    steps:
    - call: case.grpc
      args:
      - u_val_grpc_threshold_high
      - req-val-009
      kwargs:
        external: 0
        score_threshold: 1.01
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-010:
    steps:
    - call: case.http
      args:
      - u_val_http_max_claim_0
      - req-val-010
      kwargs:
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 0
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-011:
    steps:
    - call: case.grpc
      args:
      - u_val_grpc_max_claim_0
      - req-val-011
      kwargs:
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 0
      save_as: resp
    - assert: assert resp == ERR
  TC-VAL-012:
    steps:
    - call: case.http
      args:
      - u_reqid_http_auto
      - ''
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp['code'] == 0
    - comment: 'MANUAL CHECK: 应用日志存在 recommend request:，其中 reqId= 的值匹配 UUID 正则'
  TC-VAL-013:
    steps:
    - call: case.grpc
      args:
      - u_reqid_grpc_auto
      - ''
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp['code'] == 0
    - comment: 'MANUAL CHECK: 应用日志存在 recommend request:，其中 reqId= 的值匹配 UUID 正则'
  TC-GRPC-004:
    steps:
    - call: case.grpc
      args:
      - u_grpc_valid
      - req-grpc-004
      kwargs:
        external: 0
        score_threshold: 0.5
        max_claim_per_request: 1
      save_as: resp
    - assert: assert resp['code'] == 0
  TC-RATE-001:
    steps:
    - call: case.http
      args:
      - u_rate_old_user
      - req-rate-001-1
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r1
    - call: case.http
      args:
      - u_rate_old_user
      - req-rate-001-2
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r2
    - call: case.http
      args:
      - u_rate_old_user
      - req-rate-001-3
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r3
    - assert: assert r1['code'] == 0
    - assert: assert r2['code'] == 0
    - assert: assert r3 == LIMITED
  TC-RATE-002:
    steps:
    - call: case.http
      args:
      - u_rate_http_global_1
      - req-rate-002-1
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r1
    - call: case.http
      args:
      - u_rate_http_global_2
      - req-rate-002-2
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r2
    - call: case.http
      args:
      - u_rate_http_global_3
      - req-rate-002-3
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r3
    - assert: assert r1['code'] == 0
    - assert: assert r2['code'] == 0
    - assert: assert r3 == LIMITED
  TC-RATE-003:
    steps:
    - call: case.grpc
      args:
      - u_rate_grpc_global_1
      - req-rate-003-1
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r1
    - call: case.grpc
      args:
      - u_rate_grpc_global_2
      - req-rate-003-2
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r2
    - call: case.grpc
      args:
      - u_rate_grpc_global_3
      - req-rate-003-3
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r3
    - assert: assert r1['code'] == 0
    - assert: assert r2['code'] == 0
    - assert: assert r3 == LIMITED
  TC-RATE-004:
    steps:
    - call: case.http
      args:
      - u_rate_http_user
      - req-rate-004-1
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r1
    - call: case.http
      args:
      - u_rate_http_user
      - req-rate-004-2
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r2
    - assert: assert r1['code'] == 0
    - assert: assert r2 == LIMITED
  TC-RATE-005:
    steps:
    - call: case.grpc
      args:
      - u_rate_grpc_user
      - req-rate-005-1
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r1
    - call: case.grpc
      args:
      - u_rate_grpc_user
      - req-rate-005-2
      kwargs:
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r2
    - assert: assert r1['code'] == 0
    - assert: assert r2 == LIMITED
  TC-RATE-006:
    steps:
    - call: case.http
      args:
      - u_rate_http_window
      - req-rate-006-1
      kwargs:
        item:
          expr: BOUNDARY_ITEM
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r1
    - call: case.http
      args:
      - u_rate_http_window
      - req-rate-006-2
      kwargs:
        item:
          expr: BOUNDARY_ITEM
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r2
    - call: case.wait_rate_key_gone
      args:
      - u_rate_http_window
    - call: case.http
      args:
      - u_rate_http_window
      - req-rate-006-3
      kwargs:
        item:
          expr: BOUNDARY_ITEM
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r3
    - assert: assert r1['code'] == 0
    - assert: assert r2 == LIMITED
    - assert: assert r3['code'] == 0
  TC-RATE-007:
    steps:
    - call: case.grpc
      args:
      - u_rate_grpc_window
      - req-rate-007-1
      kwargs:
        item:
          expr: BOUNDARY_ITEM
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r1
    - call: case.grpc
      args:
      - u_rate_grpc_window
      - req-rate-007-2
      kwargs:
        item:
          expr: BOUNDARY_ITEM
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r2
    - call: case.wait_rate_key_gone
      args:
      - u_rate_grpc_window
    - call: case.grpc
      args:
      - u_rate_grpc_window
      - req-rate-007-3
      kwargs:
        item:
          expr: BOUNDARY_ITEM
        external: 0
        score_threshold: 0.0
        max_claim_per_request: 1
      save_as: r3
    - assert: assert r1['code'] == 0
    - assert: assert r2 == LIMITED
    - assert: assert r3['code'] == 0
```
