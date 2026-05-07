# issuance 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/issuance
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `gRPC coupon.CouponService/Recommend`；辅助断言接口 `GET /api/v1/admin/stock/{coupon_id}`、`GET /api/v1/coupons/{user_id}`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_issue_default",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "req_issue_default",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {"item_id": "COUPON_ISSUE_A", "coupon_type": "discount", "value": 100, "min_spend": 5000, "expire_days": 7},
    {"item_id": "COUPON_ISSUE_B", "coupon_type": "fixed", "value": 80, "min_spend": 3000, "expire_days": 7}
  ]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:{{score_threshold}}, max_claim_per_request:{{max_claim_per_request}},
  items: {{items}}
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动；粗排和校准实验关闭
- 候选券默认集合：`COUPON_ISSUE_A(value=100,min_spend=5000)`、`COUPON_ISSUE_B(value=80,min_spend=3000)`
- 按用例设置库存：`SET coupon:stock:{coupon_id} {stock} EX 86400`
- 发放后通过库存 API 和用户券查询 API 验证持久化状态
- 不指定打分服务返回的固定分数；需要判断最高分时，以当前响应 `results[*].score` 计算

**通用断言**：`response.code == 0`

**变量定义**：
- `coupon` = `response.coupon`
- `results` = `response.results`
- `top_result` = `max(results, key=lambda r: r.score)`

---

## 一、发放选择

### TC-ISSUE-001：HTTP 正常发放最高分券
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 前置操作：HTTP 请求 `user_id="u_issue_http_ok"`，两张券库存均为 100
  - 请求覆盖：`score_threshold=0.0`、`max_claim_per_request=1`
- **断言**：`coupon.item_id == top_result.item_id`；`coupon.user_id == "u_issue_http_ok"`；`coupon.status == "claimed"`

### TC-ISSUE-002：gRPC 正常发放最高分券
- **优先级**：P1
- **场景变量**：
  - 协议：gRPC
  - 前置操作：gRPC 请求 `user_id="u_issue_grpc_ok"`，两张券库存均为 100
  - 请求覆盖：`score_threshold=0.0`、`max_claim_per_request=1`
- **断言**：`coupon.item_id == top_result.item_id`；`coupon.user_id == "u_issue_grpc_ok"`；`coupon.status == "claimed"`

### TC-ISSUE-003：score_threshold 等于分数上界时不发放
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 前置操作：HTTP 请求 `user_id="u_issue_high_threshold"`，两张券库存均为 100
  - 请求覆盖：`score_threshold=1.0`
- **断言**：`coupon == null`；`all(r.recommended == false for r in results)`

---

## 二、库存与查询

### TC-ISSUE-004：发放成功后库存扣减 1
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 前置操作：`SET coupon:stock:COUPON_ISSUE_A 2 EX 86400`
  - 请求覆盖：HTTP 请求只传 A
  - 请求覆盖：`score_threshold=0.0`
- **断言**：发放前 `GET /api/v1/admin/stock/COUPON_ISSUE_A` 返回 `2`；发放后返回 `1`

### TC-ISSUE-005：发放记录可通过用户券查询接口查到
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求 `user_id="u_issue_query"` 成功发放 A
- **断言**：`GET /api/v1/coupons/u_issue_query` 返回 `code == 0`、`total >= 1`，且 `coupons[*].item_id` 包含 `COUPON_ISSUE_A`

### TC-ISSUE-006：coupon 过期时间按 expire_days 计算
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求 item A 的 `expire_days=3`，成功发放
- **断言**：`coupon.expire_time - coupon.claim_time == 3 * 86400`

---

## 三、请求级控制

### TC-ISSUE-007：score_threshold 请求参数控制是否推荐
- **优先级**：P1
- **场景变量**：
  - 前置操作：同一用户隔离请求，只传 `COUPON_ISSUE_A` 且库存为 100
  - 请求覆盖：第一次 `score_threshold=1.0`，第二次 `score_threshold=0.0`
- **断言**：第一次 `coupon == null`；第二次 `coupon.item_id == "COUPON_ISSUE_A"`

### TC-ISSUE-008：max_claim_per_request 控制尝试发放数量
- **优先级**：P1
- **场景变量**：
  - 请求覆盖：先用同一 `user_id` 和 A/B 候选发送探测请求，按响应 `results[*].score` 得到 `top_item` 与 `second_item`
  - 前置操作：清理探测用户领取记录并重置库存后，设置 `top_item` 库存为 0、`second_item` 库存为 100
  - 请求覆盖：第一次 `max_claim_per_request=1`，第二次 `max_claim_per_request=2`，两次 `score_threshold=0.0`
- **断言**：第一次 `coupon == null`；第二次 `coupon.item_id == second_item.item_id`

---

## 四、查询接口

### TC-ISSUE-009：未领券用户查询返回空列表
- **优先级**：P1
- **场景变量**：接口调用：调用 `GET /api/v1/coupons/user_no_coupons`，该用户没有领取记录
- **断言**：`response.body.code == 0`；`response.body.coupons == []`；`response.body.total == 0`

### TC-ISSUE-010：查询接口 user_id 为空返回参数错误
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：通过 gRPC 或业务层查询接口传入 `user_id=""`
- **断言**：`response.code == 1001`；`response.message == "user_id不能为空"`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/issuance | HTTP/gRPC 最高分发放、低分不发放、库存扣减、发放记录查询、未领券查询为空、查询 user_id 为空、过期时间计算、score_threshold、max_claim_per_request | 库存不足、并发扣减、持久化异常由 boundary.md 覆盖 |
| L2/0402 | score_threshold 和 max_claim_per_request 请求级控制 | 无（仅限 issuance 范围） |
