# scene_routing 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/scene_routing
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `gRPC coupon.CouponService/Recommend`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_route_default",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "req_route_default",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [{"item_id": "COUPON_ROUTE_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"{{scene_name}}", device:"{{device}}", policy_id:"{{policy_id}}",
  external:0, req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[{item_id:"COUPON_ROUTE_BOUNDARY_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、Redis、打分服务可用，除明确异常场景外
- 初始化库存：`SET coupon:stock:COUPON_ROUTE_BOUNDARY_001 100 EX 86400`
- 不直接编辑仓库配置；需要变更路由表时使用独立测试配置启动服务

**通用断言**：`response.code == 0`，除明确异常用例外

**变量定义**：
- `score` = `response.results[0].score`

---

## 一、兜底分容错

### TC-ROUTE-010：Redis 场景级兜底分非数字时回退到全局兜底分
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 前置操作：执行 `SET coupon:fallback:score:3001 not-a-number` 和 `SET coupon:fallback:score:default 0.6`
  - 请求覆盖：HTTP 请求命中 `policy_fallback_001`
- **断言**：`response.body.scene_id == 3001`；`score == 0.6`
- **标记**：`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`

### TC-ROUTE-011：Redis 全局兜底分非数字时回退到配置默认值
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 前置操作：执行 `DEL coupon:fallback:score:3001` 和 `SET coupon:fallback:score:default not-a-number`
  - 请求覆盖：HTTP 请求命中 `policy_fallback_001`
- **断言**：`response.body.scene_id == 3001`；`score == 0.5`

### TC-ROUTE-012：兜底分 Redis 读取异常时请求失败
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：启动服务后停止 Redis，或用测试配置将 Redis 指向不可连接实例
  - 请求覆盖：HTTP 请求命中 `policy_fallback_001`
- **断言**：`response.status_code == 500`
- **标记**：`[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`

---

## 二、路由匹配边界

### TC-ROUTE-013：policy_id 为空字符串时不触发兜底策略
- **优先级**：P2
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：HTTP 请求 `scene_name="game"`、`device="mobile"`、`policy_id=""`
- **断言**：`response.body.scene_id == 1001`

### TC-ROUTE-014：scene_name 大小写不同视为未匹配并走兜底
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求 `scene_name="Game"`、`device="mobile"`、`policy_id=""`
- **断言**：`response.scene_id == 3001`；`response.experiment_info == {}`

### TC-ROUTE-015：路由表为空时所有非 policy 兜底请求走兜底场景
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：使用测试配置启动主服务，`routes=[]`、`fallback_scene_id=3001`
  - 请求覆盖：HTTP 请求 `scene_name="game"`、`device="mobile"`、`policy_id=""`
- **断言**：`response.body.scene_id == 3001`
- **标记**：`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`

---

## 三、配置生命周期

### TC-ROUTE-016：运行中修改路由配置不会热更新
- **优先级**：P2
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：服务启动后，将独立测试配置中的 `game/mobile` 从 `1001` 改为 `1999`，不重启服务
  - 请求覆盖：发送 HTTP 请求 `scene_name="game"`、`device="mobile"`
- **断言**：响应仍为启动时加载的 `scene_id == 1001`；详见 mismatch.md
- **标记**：`[!可行性存疑: 该行为依赖独立测试配置，不应修改仓库默认配置]`

### TC-ROUTE-017：gRPC Redis 场景级兜底分非数字时回退到全局兜底分
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：gRPC
  - 前置操作：执行 `SET coupon:fallback:score:3001 not-a-number` 和 `SET coupon:fallback:score:default 0.6`
  - 请求覆盖：gRPC 请求命中 `policy_fallback_001`
- **断言**：`response.scene_id == 3001`；`score == 0.6`
- **标记**：`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`

### TC-ROUTE-018：gRPC policy_id 为空字符串时不触发兜底策略
- **优先级**：P2
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求 `scene_name="game"`、`device="mobile"`、`policy_id=""`
- **断言**：`response.scene_id == 1001`

### TC-ROUTE-019：gRPC 路由表为空时所有非 policy 兜底请求走兜底场景
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：gRPC
  - 环境覆盖：使用测试配置启动主服务，`routes=[]`、`fallback_scene_id=3001`
  - 请求覆盖：gRPC 请求 `scene_name="game"`、`device="mobile"`、`policy_id=""`
- **断言**：`response.scene_id == 3001`
- **标记**：`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/scene_routing | Redis 兜底分非数字降级、Redis 连接异常、policy_id 空字符串、scene_name 大小写敏感、路由表空配置、运行中配置不热更新、gRPC 路由边界 | 无 |
| L2/0402 | Redis 兜底读取异常与非法值边界 | 无（仅限 scene_routing 范围） |
