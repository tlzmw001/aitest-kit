# discount_policy_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: discount_policy
suite: discount_policy_smoke
case_flows:
  TC-DP-001:
    steps:
    - call: dp.health
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: 'assert body == {''status'': ''ok''}'
  TC-DP-002:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_002
        user_level: black
        scene: campaign
        stock: 0
        request_id: req_dp_002
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: assert body["code"] == 0
    - assert: assert body["eligible"] is False
    - assert: assert body["discount_rate"] == pytest.approx(1.0)
    - assert: assert body["reason_code"] == "USER_BLOCKED"
    - assert: assert body["request_id"] == "req_dp_002"
  TC-DP-003:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_003
        user_level: vip
        scene: campaign
        stock: 0
        request_id: req_dp_003
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: assert body["code"] == 0
    - assert: assert body["eligible"] is False
    - assert: assert body["discount_rate"] == pytest.approx(1.0)
    - assert: assert body["reason_code"] == "STOCK_EMPTY"
    - assert: assert body["request_id"] == "req_dp_003"
  TC-DP-004:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_004
        user_level: normal
        scene: campaign
        stock: 5
        request_id: req_dp_004
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: assert body["code"] == 0
    - assert: assert body["eligible"] is True
    - assert: assert body["discount_rate"] == pytest.approx(0.8)
    - assert: assert body["reason_code"] == "CAMPAIGN"
    - assert: assert body["request_id"] == "req_dp_004"
  TC-DP-005:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_005
        user_level: vip
        scene: checkout
        stock: 5
        request_id: req_dp_005
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: assert body["code"] == 0
    - assert: assert body["eligible"] is True
    - assert: assert body["discount_rate"] == pytest.approx(0.9)
    - assert: assert body["reason_code"] == "VIP_CHECKOUT"
    - assert: assert body["request_id"] == "req_dp_005"
  TC-DP-006:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_006
        user_level: normal
        scene: checkout
        stock: 5
        request_id: req_dp_006
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: assert body["code"] == 0
    - assert: assert body["eligible"] is True
    - assert: assert body["discount_rate"] == pytest.approx(1.0)
    - assert: assert body["reason_code"] == "DEFAULT"
    - assert: assert body["request_id"] == "req_dp_006"
  TC-DP-007:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_007
        user_level: vip
        scene: checkout
        stock: 5
        request_id: req_dp_007
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: eval_resp
    - assert: assert eval_resp.status_code == 200
    - call: dp.query
      args:
      - req_dp_007
      save_as: query_resp
    - assert: assert query_resp.status_code == 200
    - assign: body
      expr: query_resp.json()
    - assert: assert body["found"] is True
    - assert: assert body["request_id"] == "req_dp_007"
    - assert: assert body["decision"]["reason_code"] == "VIP_CHECKOUT"
    - assert: assert body["decision"]["request_id"] == "req_dp_007"
  TC-DP-008:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_008
        user_level: normal
        scene: campaign
        stock: 5
        request_id: req_dp_008
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: eval_resp
    - assert: assert eval_resp.status_code == 200
    - call: dp.delete
      args:
      - req_dp_008
      save_as: delete_resp
    - assert: assert delete_resp.status_code == 200
    - assign: deleted
      expr: delete_resp.json()
    - assert: assert deleted["deleted"] is True
    - call: dp.query
      args:
      - req_dp_008
      save_as: query_resp
    - assert: assert query_resp.status_code == 404
    - assign: body
      expr: query_resp.json()
    - assert: assert body["found"] is False
    - assert: assert body["error"] == "DECISION_NOT_FOUND"
  TC-DP-009:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_009
        item_price: 0
        stock: 5
        request_id: req_dp_009
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: assert body["code"] == 0
    - assert: assert body["reason_code"] == "DEFAULT"
    - assert: assert body["request_id"] == "req_dp_009"
  TC-DP-010:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_010
        user_level: gold
        request_id: req_dp_010
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code >= 400
    - call: dp.query
      args:
      - req_dp_010
      save_as: query_resp
    - assert: assert query_resp.status_code == 404
    - assign: body
      expr: query_resp.json()
    - assert: assert body["error"] == "DECISION_NOT_FOUND"
  TC-DP-011:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_011
        scene: unknown
        request_id: req_dp_011
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code >= 400
    - call: dp.query
      args:
      - req_dp_011
      save_as: query_resp
    - assert: assert query_resp.status_code == 404
    - assign: body
      expr: query_resp.json()
    - assert: assert body["error"] == "DECISION_NOT_FOUND"
  TC-DP-012:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_012
        item_price: -0.01
        request_id: req_dp_012
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code >= 400
    - call: dp.query
      args:
      - req_dp_012
      save_as: query_resp
    - assert: assert query_resp.status_code == 404
    - assign: body
      expr: query_resp.json()
    - assert: assert body["error"] == "DECISION_NOT_FOUND"
  TC-DP-013:
    steps:
    - call: dp.payload
      kwargs:
        user_id: u_dp_013
        stock: -1
        request_id: req_dp_013
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code >= 400
    - call: dp.query
      args:
      - req_dp_013
      save_as: query_resp
    - assert: assert query_resp.status_code == 404
    - assign: body
      expr: query_resp.json()
    - assert: assert body["error"] == "DECISION_NOT_FOUND"
  TC-DP-014:
    steps:
    - call: dp.payload_without
      args:
      - user_id
      kwargs:
        request_id: req_dp_014
      save_as: payload
    - call: dp.evaluate
      args:
      - ref: payload
      save_as: resp
    - assert: assert resp.status_code >= 400
    - call: dp.query
      args:
      - req_dp_014
      save_as: query_resp
    - assert: assert query_resp.status_code == 404
    - assign: body
      expr: query_resp.json()
    - assert: assert body["error"] == "DECISION_NOT_FOUND"
  TC-DP-015:
    steps:
    - call: dp.query
      args:
      - req_dp_missing_015
      save_as: resp
    - assert: assert resp.status_code == 404
    - assign: body
      expr: resp.json()
    - assert: assert body["found"] is False
    - assert: assert body["request_id"] == "req_dp_missing_015"
    - assert: assert body["error"] == "DECISION_NOT_FOUND"
  TC-DP-016:
    steps:
    - call: dp.delete
      args:
      - req_dp_missing_016
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: body
      expr: resp.json()
    - assert: assert body["deleted"] is False
    - assert: assert body["request_id"] == "req_dp_missing_016"
```
