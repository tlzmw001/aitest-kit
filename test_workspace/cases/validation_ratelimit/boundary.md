# validation_ratelimit 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/validation_ratelimit
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `gRPC coupon.CouponService/Recommend`

**基础请求体（HTTP）**：

```json
{
  "user_id": "{{user_id}}",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "{{req_id}}",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {
      "item_id": "COUPON_BOUNDARY_001",
      "coupon_type": "discount",
      "value": 80,
      "min_spend": 5000,
      "expire_days": 7
    }
  ]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id: "{{user_id}}"
  scene_name: "game"
  device: "mobile"
  policy_id: ""
  external: 0
  req_id: "{{req_id}}"
  score_threshold: 0.0
  max_claim_per_request: 1
  context: {}
  items: [
    {
      item_id: "COUPON_BOUNDARY_001"
      coupon_type: "discount"
      value: 80
      min_spend: 5000
      expire_days: 7
    }
  ]
}
```

**标准前置**：
- 主服务按项目命令启动：`python -m coupon_system.main`
- Redis 使用配置前缀 `coupon:`；每条用例执行前清理限流 key：`DEL coupon:rate:global coupon:rate:user:{{user_id}}`
- 初始化库存：`SET coupon:stock:COUPON_BOUNDARY_001 100 EX 86400`
- 除明确要求 Redis 不可用的用例外，Redis、HTTP 服务、gRPC 服务和打分服务均保持可用

**通用断言**：
- HTTP 成功进入业务层的请求：`response.status_code == 200`
- gRPC 请求：收到 `coupon.RecommendResponse`

**变量定义**：
- `limited` = 限流响应体：`{"code": 1010, "message": "请求过于频繁，请稍后重试", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`

---

## 一、限流窗口

### TC-RATE-006：HTTP 用户级限流窗口过期后恢复请求
- **优先级**：P2
- **场景变量**：服务配置 `rate_limit.enabled=true`、`max_qps=100`、`per_user_qps=1`、`window_seconds=1`；HTTP 请求固定 `user_id="u_rate_http_window"`；第 2 次请求触发限流后，轮询 `EXISTS coupon:rate:user:u_rate_http_window` 直到返回 `0`，最长等待 3 秒，再发送第 3 次请求
- **断言**：第 1 次 `response.body.code == 0`；第 2 次 `response.body == limited`；Redis 限流 key 过期后第 3 次 `response.body.code == 0`

### TC-RATE-007：gRPC 用户级限流窗口过期后恢复请求
- **优先级**：P2
- **场景变量**：服务配置 `rate_limit.enabled=true`、`max_qps=100`、`per_user_qps=1`、`window_seconds=1`；gRPC 请求固定 `user_id="u_rate_grpc_window"`；第 2 次请求触发限流后，轮询 `EXISTS coupon:rate:user:u_rate_grpc_window` 直到返回 `0`，最长等待 3 秒，再发送第 3 次请求
- **断言**：第 1 次 `response.code == 0`；第 2 次 `response == limited`；Redis 限流 key 过期后第 3 次 `response.code == 0`

---

## 二、限流后端异常

### TC-RATE-008：HTTP 限流 Redis 不可用时返回 500
- **优先级**：P2 / 异常
- **场景变量**：服务配置 `rate_limit.enabled=true`；启动服务后停止 Redis，或使用测试环境配置将 Redis 指向不可连接实例并重启服务；发送 HTTP 请求 `user_id="u_rate_http_redis_down"`。[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 `.env` 或配置文件]
- **断言**：`response.status_code == 500`；请求不返回 `limited` 或参数错误体

### TC-RATE-009：gRPC 限流 Redis 不可用时返回 UNKNOWN
- **优先级**：P2 / 异常
- **场景变量**：服务配置 `rate_limit.enabled=true`；启动服务后停止 Redis，或使用测试环境配置将 Redis 指向不可连接实例并重启服务；发送 gRPC 请求 `user_id="u_rate_grpc_redis_down"`。[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 `.env` 或配置文件]
- **断言**：gRPC 调用返回 transport error，`status_code == UNKNOWN`；请求不返回业务层 `limited`

---

## 三、实现细节边界

### TC-RATE-010：同一时间戳的 3 次请求仍应按 3 次计数
- **优先级**：P2
- **场景变量**：服务配置 `rate_limit.enabled=true`、`max_qps=2`、`per_user_qps=10`、`window_seconds=1`；在可控时钟测试环境中让 3 次限流检查的 `time.time()` 都返回 `1000.0`，连续发送 3 次请求，`user_id` 分别为 `u_rate_same_ts_1`、`u_rate_same_ts_2`、`u_rate_same_ts_3`。[!可行性存疑: 黑盒接口测试无法直接固定服务进程内 `time.time()`，需要测试环境提供可控时钟或专项白盒验证；详见 mismatch.md]
- **断言**：前 2 次 `code == 0`；第 3 次 `response == limited`

### TC-SCHEMA-004：HTTP item 缺少 value 时应被 Schema 拦截
- **优先级**：P2 / 异常
- **场景变量**：HTTP 请求使用 `user_id="u_schema_item_missing_value"`、`policy_id="policy_fallback_001"`，并将 `items[0]` 改为 `{"item_id":"COUPON_BOUNDARY_001","coupon_type":"discount","min_spend":5000,"expire_days":7}`，即缺少 `value` 字段。[!可行性存疑: 当前实现的 `RecommendRequest.items` 是裸 `list`，不会使用已定义的 `CouponItemRequest` 校验子字段；详见 mismatch.md]
- **断言**：期望 `response.status_code == 422`，响应体 `detail[*].loc` 包含 `["body", "items", 0, "value"]`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/validation_ratelimit | 限流窗口过期恢复、限流 Redis 异常时接口表现、同时间戳限流精度、HTTP item 子结构 Schema 校验 | 无（本模块已知未覆盖维度均已生成用例或 mismatch） |
| L2/0402 | 新请求字段进入 HTTP Schema 后的子结构校验影响 | external 打分路由切换、外部打分 user_id 加密、base_score、route 字段下发控制属于特征抽取与打分/日志模块，不在本模块新增 |
