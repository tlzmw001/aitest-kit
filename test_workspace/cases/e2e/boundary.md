# e2e 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L0_system_architecture
> 生成日期：2026-04-27

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `GET /api/v1/coupons/{user_id}` / `GET /api/v1/admin/stock/{coupon_id}` / `gRPC coupon.CouponService/Recommend`

**基础请求体（HTTP）**：

```json
{
  "user_id": "{{user_id}}",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "{{req_id}}",
  "score_threshold": 0.2,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {"item_id": "COUPON_ACT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}
  ]
}
```

**基础请求体（gRPC）**：
`RecommendRequest(user_id="{{user_id}}", scene_name="{{scene_name}}", device="{{device}}", policy_id="{{policy_id}}", context={{context}}, items={{items}}, score_threshold={{score_threshold}}, max_claim_per_request={{max_claim_per_request}}, external={{external}}, req_id="{{req_id}}")`

**标准前置**：
- 使用独立 e2e 测试环境启动 Redis、主服务和用例所需的 mock 打分服务。
- HTTP 主服务地址使用 `{{http_base_url}}`，gRPC 主服务地址使用 `{{grpc_target}}`，AB 服务地址使用 `{{ab_base_url}}`。
- 需要模拟 AB 服务不可用时，主服务使用独立环境变量或测试配置 `AB_SERVICE_URL={{unreachable_ab_base_url}}` 启动，不修改仓库默认 `.env`。
- 用例之间隔离 `user_id`、`reqId`、库存 key、白名单数据和测试配置目录。

**通用断言**：异常链路需要同时断言业务响应和发放记录状态；成功链路需要断言推荐响应与用户券查询结果一致。

**变量定义**：
- `http_json` = HTTP 推荐响应 JSON。
- `grpc_resp` = gRPC 推荐响应 message。
- `coupon` = 推荐响应中的发放结果。
- `stock(coupon_id)` = `GET /api/v1/admin/stock/{coupon_id}` 返回的库存值。
- `s` = `response.results[0].score`。
- `cal` = `response.results[0].calibrated_score`。

---

## 一、校准与最新配置生效

### TC-E2E-004：远程 AB 命中 cal_on 且 game/mobile 请求在端到端链路中产生大于原分的校准分
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：启动 Redis、AB 实验服务、内部 gRPC mock 打分服务和主服务；主服务配置 `AB_SERVICE_URL={{ab_base_url}}`
  - 前置操作：确认测试配置中的 game/mobile 线性校准规则包含 `{"conditions":{"device":"mobile"},"k":1.2,"b":0.1}`
  - 前置操作：在 AB 服务设置 `u_e2e_calibration_004` 白名单，命中 `{"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}`
  - 前置操作：写入用户特征 `{"gender":"female","age":"28","total_spend":"12000","purchase_frequency":"9","register_days":"90","is_new_user":"True","is_member":"True"}`
  - 前置操作：设置 `COUPON_ACT_001` 库存为 `3`
  - 请求覆盖：`scene_name="game"`、`device="mobile"`、`external=0`、`score_threshold=0.2`、`max_claim_per_request=1`、items 只包含 `COUPON_ACT_001`
- **断言**：`http_status == 200`；`http_json.code == 0`；`http_json.scene_id == 1001`；`http_json.experiment_info == {"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}`；`http_json.results[0].item_id == "COUPON_ACT_001"`；`cal > s`；`coupon.item_id == "COUPON_ACT_001"`；`stock("COUPON_ACT_001") == 2`

---

## 二、跨服务故障边界

### TC-E2E-005：内部打分链路在 AB 服务不可用时直接返回 HTTP 500
- **优先级**：P1 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：启动 Redis、内部 gRPC mock 打分服务和主服务；主服务配置 `AB_SERVICE_URL={{unreachable_ab_base_url}}`
  - 前置操作：确认 `{{unreachable_ab_base_url}}/health` 不可访问
  - 前置操作：写入用户特征 `{"gender":"male","age":"30","total_spend":"5000","purchase_frequency":"3","register_days":"30","is_new_user":"False","is_member":"False"}`
  - 前置操作：设置 `COUPON_ACT_001` 库存为 `3`
  - 请求覆盖：`user_id="u_e2e_ab_down_005"`、`scene_name="game"`、`device="mobile"`、`external=0`、`score_threshold=0.2`、`max_claim_per_request=1`、items 只包含 `COUPON_ACT_001`
- **断言**：`http_status == 500`；`GET /api/v1/coupons/u_e2e_ab_down_005` 返回 `total == 0`

### TC-E2E-006：外部打分链路在 AB 服务不可用时仍可成功完成推荐
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：启动 Redis、外部 HTTP mock 打分服务和主服务；主服务配置 `AB_SERVICE_URL={{unreachable_ab_base_url}}`
  - 前置操作：确认 `{{unreachable_ab_base_url}}/health` 不可访问
  - 前置操作：写入用户特征 `{"gender":"male","age":"35","total_spend":"9000","purchase_frequency":"6","register_days":"120","is_new_user":"False","is_member":"True"}`
  - 前置操作：设置 `COUPON_SHIP_001` 库存为 `3`
  - 请求覆盖：`user_id="u_e2e_external_skip_006"`、`scene_name="ad"`、`device="pc"`、`external=1`、`score_threshold=0.2`、`max_claim_per_request=1`、items 只包含 `COUPON_SHIP_001`
- **断言**：`http_status == 200`；`http_json.code == 0`；`http_json.scene_id == 2002`；`http_json.experiment_info == {}`；`coupon.item_id == "COUPON_SHIP_001"`；`GET /api/v1/coupons/u_e2e_external_skip_006` 返回 `total == 1`

---

## 三、共享状态边界

### TC-E2E-007：gRPC 发放成功后可立即通过 HTTP 查询同一条领取记录
- **优先级**：P1
- **场景变量**：
  - 协议：gRPC / HTTP
  - 环境覆盖：启动 Redis 和主服务；不写入任何 `coupon:fallback:score:*` Redis key
  - 前置操作：设置 `COUPON_ACT_001` 库存为 `1`
  - 请求覆盖：gRPC 推荐请求使用 `user_id="u_e2e_shared_state_007"`、`scene_name="game"`、`device="mobile"`、`policy_id="policy_fallback_001"`、`external=0`、`score_threshold=0.4`、`max_claim_per_request=1`、items 只包含 `COUPON_ACT_001`
  - 请求覆盖：推荐成功后调用 HTTP `GET /api/v1/coupons/u_e2e_shared_state_007`
- **断言**：`grpc_resp.code == 0`；`grpc_resp.scene_id == 3001`；`grpc_resp.coupon.item_id == "COUPON_ACT_001"`；HTTP 查询响应 `status == 200`、`code == 0`、`total == 1`；`http_json.coupons[0].instance_id == grpc_resp.coupon.instance_id`；`http_json.coupons[0].item_id == "COUPON_ACT_001"`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L0_system_architecture | 真实校准文件在端到端链路中生效、gRPC 发放后 HTTP 可查询同一条记录 | HTTP 与 gRPC 在非兜底随机打分场景下的数值级一致性 |
| L1/ab_experiment | AB 服务不可用时内部链路 500、外部链路跳过实验仍成功 | AB 服务恢复后的自动重试/自愈 |
| L1/calibration | `cal_on` + `game/mobile` 的最新线性校准文件实际生效 | 分段函数校准在端到端链路中的区间边界 |
