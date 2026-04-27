# logging 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/logging
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
  "external": {{external}},
  "reqId": "{{req_id}}",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {"item_id": "COUPON_LOG_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7},
    {"item_id": "COUPON_LOG_002", "coupon_type": "fixed", "value": 5000, "min_spend": 20000, "expire_days": 7}
  ]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:{{external}},
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[
    {item_id:"COUPON_LOG_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7},
    {item_id:"COUPON_LOG_002", coupon_type:"fixed", value:5000, min_spend:20000, expire_days:7}
  ]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动
- 初始化库存：`SET coupon:stock:COUPON_LOG_001 100 EX 86400`、`SET coupon:stock:COUPON_LOG_002 100 EX 86400`
- 测试环境开启 INFO 日志采集，能读取业务 logger 输出

**通用断言**：`response.code == 0`

**变量定义**：
- `log` = 与当前 `reqId` 匹配的 `recommend request:` 日志行

---

## 一、日志字段完整性

### TC-LOG-001：HTTP 内部打分请求记录 route=1
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_log_http_internal"`、`external=0`、`reqId="req-log-001"`
- **断言**：`log` 包含 `reqId=req-log-001`、`user_id=u_log_http_internal`、`item_ids=COUPON_LOG_001,COUPON_LOG_002`、`route=1`、`scene_id=1001`

### TC-LOG-002：gRPC 内部打分请求记录 route=1
- **优先级**：P1
- **场景变量**：gRPC 请求 `user_id="u_log_grpc_internal"`、`external=0`、`req_id="req-log-002"`
- **断言**：`log` 包含 `reqId=req-log-002`、`user_id=u_log_grpc_internal`、`route=1`、`scene_id=1001`

### TC-LOG-003：HTTP 外部打分请求记录 route=2
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_log_http_external"`、`external=1`、`reqId="req-log-003"`
- **断言**：`log` 包含 `reqId=req-log-003`、`user_id=u_log_http_external`、`route=2`、`scene_id=1001`

### TC-LOG-004：gRPC 外部打分请求记录 route=2
- **优先级**：P1
- **场景变量**：gRPC 请求 `user_id="u_log_grpc_external"`、`external=1`、`req_id="req-log-004"`
- **断言**：`log` 包含 `reqId=req-log-004`、`user_id=u_log_grpc_external`、`route=2`、`scene_id=1001`

---

## 二、reqId

### TC-LOG-005：reqId 为空时日志记录自动生成 UUID
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_log_auto_reqid"`、`external=0`、`reqId=""`
- **断言**：`log` 中 `reqId=` 后的值匹配 UUID 正则 `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`

### TC-LOG-006：兜底场景也记录 scene_id
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_log_fallback"`、`policy_id="policy_fallback_001"`、`external=0`、`reqId="req-log-006"`
- **断言**：`log` 包含 `scene_id=3001`

---

## 三、route 隔离

### TC-LOG-007：route 字段不下发给内部打分服务
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_log_no_route_internal"`、`external=0`、`reqId="req-log-007"`
- **断言**：`[manual]` 内部打分服务收到的请求字段中不存在 `route`

### TC-LOG-008：route 字段不下发给外部打分服务
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_log_no_route_external"`、`external=1`、`reqId="req-log-008"`
- **断言**：`[manual]` 外部打分服务收到的 JSON body 中不存在 `route`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/logging | HTTP/gRPC 日志字段完整性、route=1/2、reqId 自动生成、兜底 scene_id、route 不下发给打分服务 | logging 未配置、写入失败由 boundary.md 覆盖 |
| L2/0402 | 请求日志字段完整性、route 字段仅用于日志 | 无（仅限 logging 范围） |
