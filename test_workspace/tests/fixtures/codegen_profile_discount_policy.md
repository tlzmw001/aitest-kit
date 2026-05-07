# discount_policy 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `setup_discount_policy` | `fixtures/discount_policy.py` | 通过 discount_system 公开 HTTP API 调用健康检查、策略评估、决策查询和删除 |

## setup_discount_policy 做了什么

- 从 `DISCOUNT_SYSTEM_BASE_URL` 读取 discount_system 服务地址；未设置时复用全局 `HTTP_BASE_URL`。
- 提供 `health()`、`evaluate(payload)`、`query(request_id)`、`delete(request_id)` 四类公开 API 调用。
- 通过 `payload(**overrides)` 构造合法基础请求体。
- 对调用过评估接口的 `request_id` 在 teardown 中调用公开删除接口清理。

## 请求模板

`discount_policy` 是多端点 HTTP 模块，不使用默认 `/api/v1/recommend` 模板。所有自动化用例通过 `case_flows` 显式描述：

- `dp.health()` -> `GET /health`
- `dp.evaluate(payload)` -> `POST /api/v1/discount/policy`
- `dp.query(request_id)` -> `GET /api/v1/discount/decisions/{request_id}`
- `dp.delete(request_id)` -> `DELETE /api/v1/discount/decisions/{request_id}`

## 断言模式

- 成功评估先断言 HTTP `200` 和业务 `code == 0`。
- 业务决策字段使用结构断言：`eligible`、`discount_rate`、`reason_code`、`request_id`。
- 校验错误只断言 HTTP `4xx`，因为公开文档说明 body 为 HTTP 框架标准格式，未固定具体字段。
- 校验失败不创建记录，通过随后查询同一 `request_id` 返回 `404` 和 `DECISION_NOT_FOUND` 断言。

## 已知阻塞项

- 重复 `request_id` 行为未在公开文档定义，暂不生成自动化用例。
- 空字符串 `user_id`、`item_id`、`request_id` 是否允许未在公开文档定义，暂不生成自动化用例。
- 重启后内存记录消失需要控制服务生命周期，公开文档只说明记录可能消失，暂不自动化。

## emitter 规则

```yaml
module_type: multi_endpoint
case_flows:
  TC-DP-001:
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-001
        save_as: dp
      - call: dp.health
        save_as: resp
      - assert: assert resp.status_code == 200
      - assign: body
        expr: resp.json()
      - assert: "assert body == {'status': 'ok'}"
  TC-DP-002:
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-002
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-003
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-004
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-005
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-006
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-007
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-008
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-009
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-010
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-011
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-012
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-013
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-014
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-015
        save_as: dp
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
    fixture: setup_discount_policy
    steps:
      - call: setup_discount_policy
        kwargs:
          case_id: TC-DP-016
        save_as: dp
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
