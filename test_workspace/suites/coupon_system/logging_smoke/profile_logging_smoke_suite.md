# profile_logging_smoke_suite

```yaml
profile_scope: case_suite
parent_module: logging
suite: logging_smoke

case_flows:
  TC-LOG-001:
    steps:
      - call: case.run_http_with_logs
        kwargs:
          user_id: u_log_http_internal
          req_id: req-log-001
          external: 0
        save_as: result
      - assert: 'assert result["resp"]["code"] == 0'
      - assert: 'assert "recommend request: reqId=req-log-001" in result["logs"]'
      - assert: 'assert "user_id=u_log_http_internal" in result["logs"]'
      - assert: 'assert "item_ids=COUPON_LOG_001,COUPON_LOG_002" in result["logs"]'
      - assert: 'assert "route=1" in result["logs"]'
      - assert: 'assert "scene_id=1001" in result["logs"]'

  TC-LOG-002:
    steps:
      - call: case.run_grpc_with_logs
        kwargs:
          user_id: u_log_grpc_internal
          req_id: req-log-002
          external: 0
        save_as: result
      - assert: 'assert result["resp"]["code"] == 0'
      - assert: 'assert "recommend request: reqId=req-log-002" in result["logs"]'
      - assert: 'assert "user_id=u_log_grpc_internal" in result["logs"]'
      - assert: 'assert "route=1" in result["logs"]'
      - assert: 'assert "scene_id=1001" in result["logs"]'

  TC-LOG-003:
    steps:
      - call: case.run_http_with_logs
        kwargs:
          user_id: u_log_http_external
          req_id: req-log-003
          external: 1
        save_as: result
      - assert: 'assert result["resp"]["code"] == 0'
      - assert: 'assert "recommend request: reqId=req-log-003" in result["logs"]'
      - assert: 'assert "user_id=u_log_http_external" in result["logs"]'
      - assert: 'assert "route=2" in result["logs"]'
      - assert: 'assert "scene_id=1001" in result["logs"]'

  TC-LOG-004:
    steps:
      - call: case.run_grpc_with_logs
        kwargs:
          user_id: u_log_grpc_external
          req_id: req-log-004
          external: 1
        save_as: result
      - assert: 'assert result["resp"]["code"] == 0'
      - assert: 'assert "recommend request: reqId=req-log-004" in result["logs"]'
      - assert: 'assert "user_id=u_log_grpc_external" in result["logs"]'
      - assert: 'assert "route=2" in result["logs"]'
      - assert: 'assert "scene_id=1001" in result["logs"]'

  TC-LOG-005:
    steps:
      - call: case.run_http_with_logs
        kwargs:
          user_id: u_log_auto_reqid
          req_id: ""
          external: 0
        save_as: result
      - assert: 'assert result["resp"]["code"] == 0'
      - assert: 'assert case.has_auto_req_id_log(result["logs"])'

  TC-LOG-006:
    steps:
      - call: case.run_http_with_logs
        kwargs:
          user_id: u_log_fallback
          req_id: req-log-006
          external: 0
          policy_id: policy_fallback_001
        save_as: result
      - assert: 'assert result["resp"]["code"] == 0'
      - assert: 'assert "recommend request: reqId=req-log-006" in result["logs"]'
      - assert: 'assert "scene_id=3001" in result["logs"]'

  TC-LOG-010:
    steps:
      - call: case.run_http_with_logs
        kwargs:
          user_id: u_log_010
          req_id: req-log-010
          external: 0
          items:
            - item_id: COUPON_LOG_BOUNDARY_001
              coupon_type: discount
              value: 80
              min_spend: 5000
              expire_days: 7
        save_as: result
      - assert: 'assert result["resp"]["code"] == 0'
      - assert: 'assert "recommend request: reqId=req-log-010" in result["logs"]'
```
