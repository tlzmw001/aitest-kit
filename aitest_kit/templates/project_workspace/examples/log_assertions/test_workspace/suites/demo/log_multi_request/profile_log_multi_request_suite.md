# 多请求日志断言

```yaml
profile_scope: case_suite
parent_module: log_demo
suite: log_multi_request
case_flows:
  TC-DEMO-002:
    steps:
      - call: harness.query
        save_as: first
      - assert: 'assert first["code"] == 200'
      - call: harness.query
        save_as: second
      - assert: 'assert second["code"] == 200'
    log_assertions:
      - request_step: first
        select: {eventType: SCENE_HIT}
        expected:
          score: {from_response: /score}
        checks:
          - 'assert len(events) == 2'
          - 'assert all(event["data"]["score"] == expected["score"] for event in events)'
          - 'assert events[1]["data"]["counter"] == 9007199254740993'
      - request_step: second
        select: {eventType: SCENE_HIT}
        expected:
          score: {from_response: /score}
        checks:
          - 'assert len(events) == 2'
          - 'assert all(event["data"]["score"] == expected["score"] for event in events)'
          - 'assert all("命中" in event["data"]["message"] for event in events)'
          - 'assert events[0]["data"]["disabled"] is False'
          - 'assert events[1]["data"]["detail"] is None'
```
