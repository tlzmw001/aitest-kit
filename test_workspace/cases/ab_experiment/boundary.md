# ab_experiment 边界测试用例

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
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "{{req_id}}",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [{"item_id": "COUPON_AB_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[{item_id:"COUPON_AB_BOUNDARY_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动
- 初始化库存：`SET coupon:stock:COUPON_AB_BOUNDARY_001 100 EX 86400`
- 需要修改实验配置或白名单时，使用 AB 服务 HTTP API，不直接改仓库配置文件

**通用断言**：`response.code == 0`，除明确异常用例外

**变量定义**：
- `exp` = `response.experiment_info`

---

## 一、hash 区间边界

### TC-AB-010：hash 命中区间左闭边界
- **优先级**：P2
- **场景变量**：通过 AB 服务创建实验 `ab_boundary_left`，策略 `left_hit` 的 `hash_range=[H,H+1]`；选择 `md5(user_id)%100 == H` 的 `user_id`；将 `scene_id=1001` 映射到该实验
- **断言**：`exp["ab_boundary_left"] == "left_hit"`

### TC-AB-011：hash 不命中区间右开边界
- **优先级**：P2
- **场景变量**：通过 AB 服务创建实验 `ab_boundary_right`，策略 `right_miss` 的 `hash_range=[0,H]`；选择 `md5(user_id)%100 == H` 的 `user_id`；将 `scene_id=1001` 映射到该实验
- **断言**：`exp` 不包含 `ab_boundary_right`

---

## 二、白名单容错

### TC-AB-012：白名单 strategy_id 无效时降级 hash 分流
- **优先级**：P2 / 异常
- **场景变量**：`PUT /api/v1/ab/whitelist/u_ab_invalid_white`，body 为 `{"strategy_map":{"coarse_rank_exp_game":"not_exists_strategy"}}`；HTTP 请求 `user_id="u_ab_invalid_white"`、`reqId="req-ab-012"`
- **断言**：`exp["coarse_rank_exp_game"] != "not_exists_strategy"`；`[manual]` AB 服务日志包含 `ab_sdk whitelist invalid`

### TC-AB-013：本地 SDK 白名单环境变量格式错误时忽略白名单
- **优先级**：P2 / 异常
- **场景变量**：使用本地 SDK 模式启动主服务，环境变量 `AB_SDK_WHITELIST_JSON="{invalid json"`；HTTP 请求 `user_id="u_ab_bad_env"`。[!可行性存疑: 需要测试环境支持本地 SDK 模式启动主服务]
- **断言**：请求不因白名单解析失败中断；`response.body.code == 0`；`exp` 来自 hash 分流或为空

---

## 三、远程 SDK 异常

### TC-AB-014：远程 SDK 超时直接导致请求失败
- **优先级**：P2 / 异常
- **场景变量**：AB 服务端点接受连接但 `/api/v1/ab/evaluate` 响应超过 SDK timeout；HTTP 请求 `user_id="u_ab_timeout"`。[!可行性存疑: 需要测试环境提供慢响应 AB 服务]
- **断言**：HTTP 推荐接口返回 `500`

### TC-AB-015：主服务早于 AB 服务启动时首个实验请求失败
- **优先级**：P2 / 异常
- **场景变量**：先启动主服务，不启动 AB 服务；发送 `external=0` 的 HTTP 推荐请求；随后启动 AB 服务再次发送同请求
- **断言**：AB 服务未启动时返回 `500`；AB 服务启动后同请求返回 `code == 0`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_experiment | hash 半开区间边界、白名单 strategy_id 无效降级、远程 SDK 超时、本地模式白名单环境变量异常、AB 服务启动顺序依赖 | 无 |
| L2/0404 | hash 分流边界、白名单容错 | 无（仅限 AB 实验分流范围） |
| L2/0405 | AB 服务网络依赖和启动顺序 | 无（仅限 AB 实验分流范围） |
