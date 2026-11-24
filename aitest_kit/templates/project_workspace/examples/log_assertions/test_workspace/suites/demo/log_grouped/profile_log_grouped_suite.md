# Demo log assertion profile

```yaml
profile_scope: case_suite
parent_module: log_demo
suite: log_grouped
variables:
  defaults:
    minimum_score: {value: 0.5}
case_flows:
  TC-DEMO-001:
    steps:
      - call: harness.query
        save_as: reply
      - assert: 'assert reply["code"] == 200'
    log_assertions:
      - request_step: reply
        select: {eventType: SCENE_HIT}
        expected:
          keyword: "命中"
          minimum: {from_var: minimum_score}
          response_score: {from_response: /score}
        cleanup: on_success
        checks:
          - 'assert len(events) == 1'
          - 'assert expected["keyword"] in events[0]["data"]["message"]'
          - 'assert events[0]["data"]["score"] >= expected["minimum"]'
          - 'assert events[0]["data"]["score"] == expected["response_score"]'
      - request_step: reply
        source: perf
        checks: ['assert len(events) == 1']
  TC-DEMO-002:
    steps:
      - call: harness.query
        save_as: reply
      - assert: 'assert reply["code"] == 200'
    log_assertions:
      - request_step: reply
        source: perf
        cleanup: on_success
        checks: ['assert len(events) == 1']
```
