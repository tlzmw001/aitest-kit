# discount_policy 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/discount_policy
> 生成日期：2026-05-06

---

## 共享配置

**接口**：`POST /api/v1/discount/policy` / `GET /api/v1/discount/decisions/{request_id}` / `DELETE /api/v1/discount/decisions/{request_id}`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_dp_default",
  "user_level": "normal",
  "item_id": "item_dp_default",
  "item_price": 120.5,
  "scene": "checkout",
  "stock": 5,
  "request_id": "req_dp_default"
}
```

**标准前置**：
- discount_system 服务已启动；测试通过 `DISCOUNT_SYSTEM_BASE_URL` 指定服务地址，缺失时测试应 fail fast。
- 校验失败用例使用唯一 `request_id`，并在断言中确认查询该 `request_id` 返回不存在。

**通用断言**：
- 校验错误：HTTP `4xx`

**变量定义**：
- `validation_request_id` = 校验失败请求体中的 `request_id`

---

## 一、字段边界

### TC-DP-009：item_price 为 0 仍可评估
- **优先级**：P2
- **场景变量**：请求覆盖：`{"user_id": "u_dp_009", "item_price": 0, "stock": 5, "request_id": "req_dp_009"}`
- **断言**：`response.status_code == 200`；`response.code == 0`；`response.reason_code == "DEFAULT"`；`response.request_id == "req_dp_009"`

### TC-DP-010：非法 user_level 触发校验错误且不存储
- **优先级**：P1 / 异常
- **场景变量**：请求覆盖：`{"user_id": "u_dp_010", "user_level": "gold", "request_id": "req_dp_010"}`
- **断言**：`response.status_code >= 400`；`query.status_code == 404`；`query.body.error == "DECISION_NOT_FOUND"`

### TC-DP-011：非法 scene 触发校验错误且不存储
- **优先级**：P1 / 异常
- **场景变量**：请求覆盖：`{"user_id": "u_dp_011", "scene": "unknown", "request_id": "req_dp_011"}`
- **断言**：`response.status_code >= 400`；`query.status_code == 404`；`query.body.error == "DECISION_NOT_FOUND"`

### TC-DP-012：负数 item_price 触发校验错误且不存储
- **优先级**：P1 / 异常
- **场景变量**：请求覆盖：`{"user_id": "u_dp_012", "item_price": -0.01, "request_id": "req_dp_012"}`
- **断言**：`response.status_code >= 400`；`query.status_code == 404`；`query.body.error == "DECISION_NOT_FOUND"`

### TC-DP-013：负数 stock 触发校验错误且不存储
- **优先级**：P1 / 异常
- **场景变量**：请求覆盖：`{"user_id": "u_dp_013", "stock": -1, "request_id": "req_dp_013"}`
- **断言**：`response.status_code >= 400`；`query.status_code == 404`；`query.body.error == "DECISION_NOT_FOUND"`

### TC-DP-014：缺少必填字段触发校验错误且不存储
- **优先级**：P1 / 异常
- **场景变量**：请求体：删除 `user_id`，保留 `request_id="req_dp_014"`
- **断言**：`response.status_code >= 400`；`query.status_code == 404`；`query.body.error == "DECISION_NOT_FOUND"`

---

## 二、决策记录边界

### TC-DP-015：查询不存在决策返回 404
- **优先级**：P1 / 异常
- **场景变量**：接口调用：`GET /api/v1/discount/decisions/req_dp_missing_015`
- **断言**：`response.status_code == 404`；`response.body.found == false`；`response.body.request_id == "req_dp_missing_015"`；`response.body.error == "DECISION_NOT_FOUND"`

### TC-DP-016：删除不存在决策返回 deleted false
- **优先级**：P1
- **场景变量**：接口调用：`DELETE /api/v1/discount/decisions/req_dp_missing_016`
- **断言**：`response.status_code == 200`；`response.body.deleted == false`；`response.body.request_id == "req_dp_missing_016"`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/discount_policy | item_price 下界、非法 user_level、非法 scene、负数 item_price、负数 stock、缺少必填字段、查询不存在、删除不存在 | 空字符串字段、重复 request_id、校验错误 body 精确字段 |
| L2/discount_system_initial_public_api | 公开字段边界、校验失败不存储、决策记录不存在场景 | 重启后记录消失 |
