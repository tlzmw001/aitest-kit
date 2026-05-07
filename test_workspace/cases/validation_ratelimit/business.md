# validation_ratelimit 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/validation_ratelimit
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `gRPC coupon.CouponService/Recommend`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_rate_default",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "req_rate_default",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {
      "item_id": "COUPON_VAL_001",
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
  external: {{external}}
  req_id: "{{req_id}}"
  score_threshold: {{score_threshold}}
  max_claim_per_request: {{max_claim_per_request}}
  context: {}
  items: [
    {
      item_id: "COUPON_VAL_001"
      coupon_type: "discount"
      value: 80
      min_spend: 5000
      expire_days: 7
    }
  ]
}
```

**标准前置**：
- 主服务按项目命令启动：`python -m coupon_system.main`；HTTP 使用配置中的 `http://localhost:8000`，gRPC 使用 `localhost:50051`
- Redis 使用配置前缀 `coupon:`；每条用例执行前清理限流 key：`DEL coupon:rate:global coupon:rate:user:{{user_id}}`
- 初始化库存：`SET coupon:stock:COUPON_VAL_001 100 EX 86400`
- 路由表保持默认配置，`game/mobile` 可路由到非兜底场景；打分服务可用，除参数校验/限流短路用例外不影响断言

**通用断言**：
- HTTP 成功进入业务层的请求：`response.status_code == 200`
- gRPC 请求：收到 `coupon.RecommendResponse`

**变量定义**：
- `err` = 参数无效响应体：`{"code": 1001, "message": "参数无效", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`
- `limited` = 限流响应体：`{"code": 1010, "message": "请求过于频繁，请稍后重试", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`

---

## 一、业务层参数校验

### TC-VAL-001：user_id 为空时返回参数错误
- **优先级**：P0 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id=""`、`reqId="req-val-001"`、`external=0`、`score_threshold=0.5`、`max_claim_per_request=1`
- **断言**：`response.body == err`

### TC-VAL-002：scene_name 为空时返回参数错误
- **优先级**：P0 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id="u_val_scene_empty"`、`scene_name=""`、`reqId="req-val-002"`、`external=0`、`score_threshold=0.5`、`max_claim_per_request=1`
- **断言**：`response.body == err`

### TC-VAL-003：device 为空时返回参数错误
- **优先级**：P0 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id="u_val_device_empty"`、`device=""`、`reqId="req-val-003"`、`external=0`、`score_threshold=0.5`、`max_claim_per_request=1`
- **断言**：`response.body == err`

### TC-VAL-004：items 为空列表时返回参数错误
- **优先级**：P0 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id="u_val_items_empty"`、`items=[]`、`reqId="req-val-004"`、`external=0`、`score_threshold=0.5`、`max_claim_per_request=1`
- **断言**：`response.body == err`

### TC-VAL-005：缺少业务必填控制字段时返回参数错误
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：通过 gRPC 请求或业务层调用省略 `external`、`score_threshold`、`max_claim_per_request` 中任一字段，其他字段合法
- **断言**：`response == err`

### TC-VAL-006：HTTP 拒绝 external 非法值
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id="u_val_http_external_2"`、`reqId="req-val-006"`、`external=2`、`score_threshold=0.5`、`max_claim_per_request=1`
- **断言**：`response.body == err`

### TC-VAL-007：gRPC 拒绝 external 非法值
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求使用 `user_id="u_val_grpc_external_2"`、`req_id="req-val-007"`、`external=2`、`score_threshold=0.5`、`max_claim_per_request=1`
- **断言**：`response == err`

### TC-VAL-008：HTTP 拒绝 score_threshold 小于 0
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id="u_val_http_threshold_low"`、`reqId="req-val-008"`、`external=0`、`score_threshold=-0.01`、`max_claim_per_request=1`
- **断言**：`response.body == err`

### TC-VAL-009：gRPC 拒绝 score_threshold 大于 1
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求使用 `user_id="u_val_grpc_threshold_high"`、`req_id="req-val-009"`、`external=0`、`score_threshold=1.01`、`max_claim_per_request=1`
- **断言**：`response == err`

### TC-VAL-010：HTTP 拒绝 max_claim_per_request 小于 1
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id="u_val_http_max_claim_0"`、`reqId="req-val-010"`、`external=0`、`score_threshold=0.5`、`max_claim_per_request=0`
- **断言**：`response.body == err`

### TC-VAL-011：gRPC 拒绝 max_claim_per_request 小于 1
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求使用 `user_id="u_val_grpc_max_claim_0"`、`req_id="req-val-011"`、`external=0`、`score_threshold=0.5`、`max_claim_per_request=0`
- **断言**：`response == err`

---

## 二、请求标识

### TC-VAL-012：HTTP reqId 为空时自动生成请求标识
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用 `user_id="u_reqid_http_auto"`、`reqId=""`、`external=0`、`score_threshold=0.0`、`max_claim_per_request=1`
- **断言**：`response.body.code == 0`； 应用日志存在 `recommend request:`，其中 `reqId=` 的值匹配 UUID 正则 `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
- **标记**：`[manual]`

### TC-VAL-013：gRPC req_id 为空时自动生成请求标识
- **优先级**：P1
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求使用 `user_id="u_reqid_grpc_auto"`、`req_id=""`、`external=0`、`score_threshold=0.0`、`max_claim_per_request=1`
- **断言**：`response.code == 0`； 应用日志存在 `recommend request:`，其中 `reqId=` 的值匹配 UUID 正则 `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
- **标记**：`[manual]`

---

## 三、HTTP Schema 校验

### TC-SCHEMA-001：HTTP 请求缺少 external 字段返回 422
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用完整基础请求体，但删除 `external` 字段
- **断言**：`response.status_code == 422`；`response.body.detail[*].loc` 包含 `["body","external"]`

### TC-SCHEMA-002：HTTP 请求缺少 score_threshold 字段返回 422
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用完整基础请求体，但删除 `score_threshold` 字段
- **断言**：`response.status_code == 422`；`response.body.detail[*].loc` 包含 `["body","score_threshold"]`

### TC-SCHEMA-003：HTTP 请求缺少 max_claim_per_request 字段返回 422
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求使用完整基础请求体，但删除 `max_claim_per_request` 字段
- **断言**：`response.status_code == 422`；`response.body.detail[*].loc` 包含 `["body","max_claim_per_request"]`

---

## 四、gRPC 协议字段校验

### TC-GRPC-001：gRPC 请求缺少 external 字段返回参数错误
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 前置操作：gRPC 请求设置 `score_threshold=0.5`、`max_claim_per_request=1`，不设置 optional `external`
- **断言**：`response == err`

### TC-GRPC-002：gRPC 请求缺少 score_threshold 字段返回参数错误
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 前置操作：gRPC 请求设置 `external=0`、`max_claim_per_request=1`，不设置 optional `score_threshold`
- **断言**：`response == err`

### TC-GRPC-003：gRPC 请求缺少 max_claim_per_request 字段返回参数错误
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 前置操作：gRPC 请求设置 `external=0`、`score_threshold=0.5`，不设置 optional `max_claim_per_request`
- **断言**：`response == err`

### TC-GRPC-004：gRPC 请求包含所有必填字段可通过校验
- **优先级**：P0
- **场景变量**：
  - 协议：gRPC
  - 前置操作：gRPC 请求完整设置 `external=0`、`score_threshold=0.5`、`max_claim_per_request=1`，其他字段使用基础请求体合法值
- **断言**：`response.code == 0`

---

## 五、限流

### TC-RATE-001：用户级限流达到上限时拒绝同用户第 3 个请求
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：服务配置 `rate_limit.enabled=true`、`max_qps=100`、`per_user_qps=2`、`window_seconds=1`
  - 请求覆盖：1 秒窗口内连续发送 3 个 HTTP 请求，均使用 `user_id="u_rate_old_user"`，`reqId` 分别为 `req-rate-001-1`、`req-rate-001-2`、`req-rate-001-3`
- **断言**：前 2 次 `response.body.code == 0`；第 3 次 `response.body == limited`

### TC-RATE-002：HTTP 全局限流达到上限时拒绝第 3 个请求
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：服务配置 `rate_limit.enabled=true`、`max_qps=2`、`per_user_qps=10`、`window_seconds=1`
  - 请求覆盖：1 秒窗口内连续发送 3 个 HTTP 请求，`user_id` 依次为 `u_rate_http_global_1`、`u_rate_http_global_2`、`u_rate_http_global_3`，其余字段使用基础请求体合法值
- **断言**：前 2 次 `response.body.code == 0`；第 3 次 `response.body == limited`

### TC-RATE-003：gRPC 全局限流达到上限时拒绝第 3 个请求
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 环境覆盖：服务配置 `rate_limit.enabled=true`、`max_qps=2`、`per_user_qps=10`、`window_seconds=1`
  - 请求覆盖：1 秒窗口内连续发送 3 个 gRPC 请求，`user_id` 依次为 `u_rate_grpc_global_1`、`u_rate_grpc_global_2`、`u_rate_grpc_global_3`，其余字段使用基础请求体合法值
- **断言**：前 2 次 `response.code == 0`；第 3 次 `response == limited`

### TC-RATE-004：HTTP 用户级限流达到上限时拒绝同用户第 2 个请求
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：服务配置 `rate_limit.enabled=true`、`max_qps=100`、`per_user_qps=1`、`window_seconds=1`
  - 请求覆盖：1 秒窗口内发送 2 个 HTTP 请求，均使用 `user_id="u_rate_http_user"`，`reqId` 分别为 `req-rate-004-1`、`req-rate-004-2`
- **断言**：第 1 次 `response.body.code == 0`；第 2 次 `response.body == limited`

### TC-RATE-005：gRPC 用户级限流达到上限时拒绝同用户第 2 个请求
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 环境覆盖：服务配置 `rate_limit.enabled=true`、`max_qps=100`、`per_user_qps=1`、`window_seconds=1`
  - 请求覆盖：1 秒窗口内发送 2 个 gRPC 请求，均使用 `user_id="u_rate_grpc_user"`，`req_id` 分别为 `req-rate-005-1`、`req-rate-005-2`
- **断言**：第 1 次 `response.code == 0`；第 2 次 `response == limited`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/validation_ratelimit | 基础空值校验、external 非法值、score_threshold 越界、max_claim_per_request 非法值、HTTP/gRPC 全局限流触发、HTTP/gRPC 用户级限流触发、gRPC 完整字段正向校验 | 限流窗口过期恢复、限流 Redis 异常、并发/同时间戳限流精度由 boundary.md 覆盖 |
| L2/0402 | HTTP Schema 必填字段校验、gRPC optional 字段缺失校验、reqId 为空时自动生成 UUID、请求级 score_threshold/max_claim_per_request/external 字段的业务层校验 | external 打分路由切换、外部打分 user_id 加密、base_score、route 字段下发控制属于特征抽取与打分/日志模块，不在本模块新增 |
