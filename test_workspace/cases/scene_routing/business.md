# scene_routing 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/scene_routing
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
  "items": [{"item_id": "COUPON_ROUTE_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"{{scene_name}}", device:"{{device}}", policy_id:"{{policy_id}}",
  external:{{external}}, req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[{item_id:"COUPON_ROUTE_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、Redis、打分服务可用；非 `external=1` 用例要求 AB 服务可用
- 默认路由表：`game/mobile -> 1001`、`ad/pc -> 2002`，兜底 `fallback_scene_id=3001`
- 初始化库存：`SET coupon:stock:COUPON_ROUTE_001 100 EX 86400`
- 兜底分 Redis key：`coupon:fallback:score:{scene_id}`、`coupon:fallback:score:default`

**通用断言**：`response.code == 0`

**变量定义**：
- `score` = `response.results[0].score`
- `cal` = `response.results[0].calibrated_score`

---

## 一、基础路由

### TC-ROUTE-001：HTTP game/mobile 路由到 scene_id=1001
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求 `user_id="u_route_game_mobile"`、`scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=0`
- **断言**：`response.body.scene_id == 1001`

### TC-ROUTE-002：gRPC ad/pc 路由到 scene_id=2002
- **优先级**：P1
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求 `user_id="u_route_ad_pc"`、`scene_name="ad"`、`device="pc"`、`policy_id=""`、`external=0`
- **断言**：`response.scene_id == 2002`

### TC-ROUTE-003：external=1 时场景路由正常计算
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求 `user_id="u_route_external"`、`scene_name="game"`、`device="mobile"`、`policy_id=""`、`external=1`
- **断言**：`response.body.scene_id == 1001`

---

## 二、兜底策略

### TC-ROUTE-004：policy_id 命中兜底时跳过实验和打分
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求 `user_id="u_route_policy_fb"`、`scene_name="game"`、`device="mobile"`、`policy_id="policy_fallback_001"`、`external=0`
- **断言**：`response.body.scene_id == 3001`；`response.body.experiment_info == {}`；`score == cal`

### TC-ROUTE-005：兜底发放时 user_id 正确传递
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求 `user_id="u_fallback"`、`scene_name="game"`、`device="mobile"`、`policy_id="policy_fallback_001"`、`external=0`、`score_threshold=0.0`
- **断言**：`response.body.coupon != null`；`response.body.coupon.user_id == "u_fallback"`

### TC-ROUTE-006：未知场景组合走兜底场景
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求 `user_id="u_route_unknown"`、`scene_name="unknown_scene"`、`device="unknown_device"`、`policy_id=""`、`external=0`
- **断言**：`response.scene_id == 3001`；`response.experiment_info == {}`

---

## 三、兜底分三级读取

### TC-ROUTE-007：优先使用 Redis 场景级兜底分
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 前置操作：执行 `SET coupon:fallback:score:3001 0.8` 和 `SET coupon:fallback:score:default 0.6`
  - 请求覆盖：HTTP 请求命中 `policy_fallback_001`
- **断言**：`score == 0.8`；`cal == 0.8`

### TC-ROUTE-008：场景级不存在时使用 Redis 全局兜底分
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 前置操作：执行 `DEL coupon:fallback:score:3001` 和 `SET coupon:fallback:score:default 0.6`
  - 请求覆盖：HTTP 请求命中 `policy_fallback_001`
- **断言**：`score == 0.6`；`cal == 0.6`

### TC-ROUTE-009：Redis 兜底分都不存在时使用配置默认值
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 前置操作：执行 `DEL coupon:fallback:score:3001 coupon:fallback:score:default`
  - 请求覆盖：HTTP 请求命中 `policy_fallback_001`
- **断言**：`score == 0.5`；`cal == 0.5`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/scene_routing | HTTP/gRPC 基础路由、policy_id 兜底、兜底发放 user_id 透传、未知场景兜底、external=1 路由隔离、Redis 场景级/全局/配置三级兜底分读取 | Redis 异常、非数字兜底分、大小写敏感、空路由表由 boundary.md 覆盖 |
| L2/0402 | 兜底策略先读 Redis 再取配置、external=1 不影响场景划分 | 无（仅限 scene_routing 范围） |
