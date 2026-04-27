# issuance 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/issuance
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `gRPC coupon.CouponService/Recommend`；辅助断言接口 `GET /api/v1/admin/stock/{coupon_id}`、`GET /api/v1/coupons/{user_id}`

**基础请求体（HTTP）**：

```json
{
  "user_id": "{{user_id}}",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "{{req_id}}",
  "score_threshold": 0.5,
  "max_claim_per_request": {{max_claim_per_request}},
  "context": {},
  "items": {{items}}
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:0.5, max_claim_per_request:{{max_claim_per_request}},
  items: {{items}}
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动；粗排和校准实验关闭
- 每条用例使用唯一 `user_id` 和唯一 coupon id，避免领取记录互相影响
- 用例开始前清理相关库存、用户领取集合和实例集合 key

**通用断言**：`response.code == 0`

**变量定义**：
- `coupon` = `response.coupon`

---

## 一、库存边界

### TC-ISSUE-009：最高分券库存不足时尝试下一张券
- **优先级**：P2
- **场景变量**：A 分数 0.9、库存 0；B 分数 0.8、库存 100；`max_claim_per_request=2`
- **断言**：`coupon.item_id == "COUPON_ISSUE_B"`；`GET /api/v1/admin/stock/COUPON_ISSUE_A == 0`

### TC-ISSUE-010：所有候选券库存不足时返回成功但 coupon 为空
- **优先级**：P2 / 异常
- **场景变量**：A/B 分数均高于阈值，库存均为 0；`max_claim_per_request=2`
- **断言**：`response.code == 0`；`coupon == null`；不返回 `STOCK_EMPTY=1006`

### TC-ISSUE-011：并发请求同一库存只成功发放一次
- **优先级**：P2
- **场景变量**：`SET coupon:stock:COUPON_ISSUE_CONCURRENT 1 EX 86400`；两个不同 `user_id` 并发请求同一券，打分均高于阈值
- **断言**：两个响应中恰好 1 个 `coupon.item_id == "COUPON_ISSUE_CONCURRENT"`；最终库存为 `0`；另一个响应 `coupon == null`

---

## 二、领取记录边界

### TC-ISSUE-012：同一用户重复请求同一券不会因已领取被拦截
- **优先级**：P2
- **场景变量**：同一 `user_id="u_issue_repeat"` 两次请求同一券，库存初始为 2，打分均高于阈值
- **断言**：两次都可返回发放成功；用户券查询中该用户有两条实例记录。[!可行性存疑: L1 未规定去重限制，当前实现未调用 has_claimed，需产品确认是否允许重复领取]

### TC-ISSUE-013：Redis 保存发放记录失败时请求异常
- **优先级**：P2 / 异常
- **场景变量**：库存扣减成功后，Redis 写领取记录或实例记录时连接异常。[!可行性存疑: 需要测试环境能在扣库存后注入 Redis 写失败]
- **断言**：HTTP 返回 `500` 或 gRPC transport error；可能出现库存已扣但实例未保存的非原子状态，详见 mismatch.md

---

## 三、输入边界

### TC-ISSUE-014：expire_days 缺省时 HTTP item 默认值为 7 天
- **优先级**：P2
- **场景变量**：HTTP 请求 item 省略 `expire_days`，其他字段完整；成功发放
- **断言**：`coupon.expire_time - coupon.claim_time == 7 * 86400`

### TC-ISSUE-015：max_claim_per_request 大于候选数时最多尝试全部候选
- **优先级**：P2
- **场景变量**：两张候选券均高于阈值，A 库存 0，B 库存 100；`max_claim_per_request=10`
- **断言**：`coupon.item_id == "COUPON_ISSUE_B"`；不会因 `max_claim_per_request` 大于候选数报错

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/issuance | 库存不足尝试下一张、全库存不足成功空 coupon、并发扣减、重复领取、Redis 写失败、expire_days 默认值、max_claim_per_request 超候选数 | 无 |
| L2/0402 | max_claim_per_request 边界 | 无（仅限 issuance 范围） |
