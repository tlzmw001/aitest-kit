# discount_policy 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/discount_policy
> 生成日期：2026-05-06

---

## 共享配置

**接口**：`GET /health` / `POST /api/v1/discount/policy` / `GET /api/v1/discount/decisions/{request_id}` / `DELETE /api/v1/discount/decisions/{request_id}`

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
- 每条成功评估用例使用唯一 `request_id`。
- 每条用例结束后通过公开 `DELETE /api/v1/discount/decisions/{request_id}` 清理本用例创建的决策记录。

**通用断言**：
- 成功策略评估：`response.status_code == 200`；`response.code == 0`

**变量定义**：
- `decision` = `response.body.decision`

---

## 一、健康检查与规则优先级

### TC-DP-001：健康检查返回 ok
- **优先级**：P0
- **场景变量**：接口调用：`GET /health`
- **断言**：`response.status_code == 200`；`response.body == {"status": "ok"}`

### TC-DP-002：黑名单用户优先于活动和库存
- **优先级**：P1
- **场景变量**：请求覆盖：`{"user_id": "u_dp_002", "user_level": "black", "scene": "campaign", "stock": 0, "request_id": "req_dp_002"}`
- **断言**：`response.status_code == 200`；`response.code == 0`；`response.eligible == false`；`response.discount_rate == 1.0`；`response.reason_code == "USER_BLOCKED"`；`response.request_id == "req_dp_002"`

### TC-DP-003：库存为空优先于活动规则
- **优先级**：P1
- **场景变量**：请求覆盖：`{"user_id": "u_dp_003", "user_level": "vip", "scene": "campaign", "stock": 0, "request_id": "req_dp_003"}`
- **断言**：`response.status_code == 200`；`response.code == 0`；`response.eligible == false`；`response.discount_rate == 1.0`；`response.reason_code == "STOCK_EMPTY"`；`response.request_id == "req_dp_003"`

### TC-DP-004：活动场景命中八折
- **优先级**：P1
- **场景变量**：请求覆盖：`{"user_id": "u_dp_004", "user_level": "normal", "scene": "campaign", "stock": 5, "request_id": "req_dp_004"}`
- **断言**：`response.status_code == 200`；`response.code == 0`；`response.eligible == true`；`response.discount_rate == 0.8`；`response.reason_code == "CAMPAIGN"`；`response.request_id == "req_dp_004"`

### TC-DP-005：VIP 结算命中九折
- **优先级**：P1
- **场景变量**：请求覆盖：`{"user_id": "u_dp_005", "user_level": "vip", "scene": "checkout", "stock": 5, "request_id": "req_dp_005"}`
- **断言**：`response.status_code == 200`；`response.code == 0`；`response.eligible == true`；`response.discount_rate == 0.9`；`response.reason_code == "VIP_CHECKOUT"`；`response.request_id == "req_dp_005"`

### TC-DP-006：普通结算走默认规则
- **优先级**：P1
- **场景变量**：请求覆盖：`{"user_id": "u_dp_006", "user_level": "normal", "scene": "checkout", "stock": 5, "request_id": "req_dp_006"}`
- **断言**：`response.status_code == 200`；`response.code == 0`；`response.eligible == true`；`response.discount_rate == 1.0`；`response.reason_code == "DEFAULT"`；`response.request_id == "req_dp_006"`

---

## 二、决策生命周期

### TC-DP-007：成功评估后可按 request_id 查询
- **优先级**：P1
- **场景变量**：
  - 接口调用：先 `POST /api/v1/discount/policy`，再 `GET /api/v1/discount/decisions/req_dp_007`
  - 请求覆盖：`{"user_id": "u_dp_007", "user_level": "vip", "scene": "checkout", "stock": 5, "request_id": "req_dp_007"}`
- **断言**：`response.status_code == 200`；`response.body.found == true`；`decision.reason_code == "VIP_CHECKOUT"`；`decision.request_id == "req_dp_007"`

### TC-DP-008：删除决策后查询返回不存在
- **优先级**：P1
- **场景变量**：
  - 接口调用：先 `POST /api/v1/discount/policy`，再 `DELETE /api/v1/discount/decisions/req_dp_008`，最后查询同一 `request_id`
  - 请求覆盖：`{"user_id": "u_dp_008", "user_level": "normal", "scene": "campaign", "stock": 5, "request_id": "req_dp_008"}`
- **断言**：`delete.status_code == 200`；`delete.body.deleted == true`；`query.status_code == 404`；`query.body.found == false`；`query.body.error == "DECISION_NOT_FOUND"`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/discount_policy | 健康检查、黑名单优先级、库存优先级、活动规则、VIP 结算、默认规则、成功评估查询、删除后查询不存在 | validation error、查询不存在、删除不存在、字段边界由 boundary.md 覆盖 |
| L2/discount_system_initial_public_api | 首批公开 API 主流程和生命周期 | 重复 request_id、重启后记录消失、校验错误 body 精确结构 |
