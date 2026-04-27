# ab_experiment 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/ab_experiment
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `gRPC coupon.CouponService/Recommend`

**基础请求体（HTTP）**：

```json
{
  "user_id": "{{user_id}}",
  "scene_name": "{{scene_name}}",
  "device": "{{device}}",
  "policy_id": "",
  "external": {{external}},
  "reqId": "{{req_id}}",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {"item_id": "COUPON_AB_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}
  ]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id: "{{user_id}}"
  scene_name: "{{scene_name}}"
  device: "{{device}}"
  policy_id: ""
  external: {{external}}
  req_id: "{{req_id}}"
  score_threshold: 0.0
  max_claim_per_request: 1
  context: {}
  items: [{item_id:"COUPON_AB_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动；AB 服务地址使用项目配置或环境变量
- 初始化库存：`SET coupon:stock:COUPON_AB_001 100 EX 86400`
- 场景实验映射保持默认：`game/mobile -> scene_id=1001 -> coarse_rank_exp_game, calibration_exp_game`
- AB 实验数据包含可 hash 命中的策略；需要白名单时通过 `PUT /api/v1/ab/whitelist/{user_id}` 设置

**通用断言**：
- HTTP：`response.status_code == 200`
- gRPC：收到 `coupon.RecommendResponse`
- 非兜底、非 external=1 场景：`response.code == 0`

**变量定义**：
- `exp` = `response.experiment_info`
- `no_exp` = `{}`

---

## 一、SDK 分流

### TC-AB-001：HTTP 通过 hash 命中场景关联实验
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_ab_hash_http"`、`scene_name="game"`、`device="mobile"`、`external=0`、`reqId="req-ab-001"`；不设置该用户白名单
- **断言**：`exp` 只包含 `coarse_rank_exp_game`、`calibration_exp_game` 中实际命中的实验 key；不包含 `coarse_rank_exp_ad`、`calibration_exp_ad`

### TC-AB-002：gRPC 通过 hash 命中场景关联实验
- **优先级**：P1
- **场景变量**：gRPC 请求 `user_id="u_ab_hash_grpc"`、`scene_name="ad"`、`device="pc"`、`external=0`、`req_id="req-ab-002"`；不设置该用户白名单
- **断言**：`exp` 只包含 `coarse_rank_exp_ad`、`calibration_exp_ad` 中实际命中的实验 key；不包含 `coarse_rank_exp_game`、`calibration_exp_game`

### TC-AB-003：白名单优先级高于 hash 分流
- **优先级**：P1
- **场景变量**：先执行 `PUT /api/v1/ab/whitelist/u_ab_white`，body 为 `{"strategy_map":{"coarse_rank_exp_game":"cr_off","calibration_exp_game":"cal_off"}}`；HTTP 请求 `user_id="u_ab_white"`、`scene_name="game"`、`device="mobile"`、`external=0`、`reqId="req-ab-003"`
- **断言**：`exp["coarse_rank_exp_game"] == "cr_off"`；`exp["calibration_exp_game"] == "cal_off"`

---

## 二、场景实验映射

### TC-AB-004：只评估当前 scene_id 映射的实验
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_ab_scene_game"`、`scene_name="game"`、`device="mobile"`、`external=0`；AB 服务中同时存在 game/ad 两组实验
- **断言**：`set(exp.keys())` 是 `{"coarse_rank_exp_game", "calibration_exp_game"}` 的子集；`exp` 不包含任何 `_ad` 实验

### TC-AB-005：场景无实验映射时返回空实验信息
- **优先级**：P1
- **场景变量**：测试环境将场景实验映射中目标 `scene_id` 配置为空列表后启动主服务；HTTP 请求命中该 `scene_id`
- **断言**：`response.code == 0`；`exp == no_exp`

---

## 三、外部打分隔离

### TC-AB-006：HTTP external=1 时不获取任何实验
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_ab_external_http"`、`scene_name="game"`、`device="mobile"`、`external=1`、`reqId="req-ab-006"`；AB 服务可用且存在可命中实验
- **断言**：`response.body.experiment_info == no_exp`

### TC-AB-007：gRPC external=1 时不获取任何实验
- **优先级**：P1
- **场景变量**：gRPC 请求 `user_id="u_ab_external_grpc"`、`scene_name="game"`、`device="mobile"`、`external=1`、`req_id="req-ab-007"`；AB 服务可用且存在可命中实验
- **断言**：`response.experiment_info == no_exp`

---

## 四、异常场景

### TC-AB-008：AB 服务不可用时主服务不降级
- **优先级**：P1 / 异常
- **场景变量**：停止 AB 实验服务或将主服务 AB SDK 地址指向不可连接端口后启动；HTTP 请求 `user_id="u_ab_down"`、`scene_name="game"`、`device="mobile"`、`external=0`。[!可行性存疑: 需要测试环境允许控制 AB 服务可用性或启动参数]
- **断言**：`response.status_code == 500`

### TC-AB-009：实验名不存在时静默跳过
- **优先级**：P2 / 异常
- **场景变量**：测试环境将 `scene_id=1001` 的实验映射设为 `["coarse_rank_exp_game","not_exists_exp"]`；HTTP 请求 `user_id="u_ab_unknown_exp"`、`scene_name="game"`、`device="mobile"`、`external=0`
- **断言**：`response.body.code == 0`；`exp` 不包含 `not_exists_exp`；`[manual]` 应用日志包含 `ab_sdk unknown experiment: not_exists_exp`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_experiment | HTTP/gRPC hash 分流、白名单优先、场景实验映射、external=1 跳过实验、AB 服务不可用无降级、实验名不存在静默跳过 | hash 区间边界、白名单无效策略、远程 SDK 超时由 boundary.md 覆盖 |
| L2/0404 | SDK 调用替代直接配置读取、白名单强制命中、按场景过滤实验、external=1 无实验返回 | 粗排增强兼容性由 rough_ranking 覆盖 |
| L2/0405 | AB 服务不可用时主服务行为 | AB 服务启动顺序依赖由 boundary.md 覆盖 |
