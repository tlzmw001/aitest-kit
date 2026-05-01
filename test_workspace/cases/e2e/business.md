# e2e 业务测试用例

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
- 使用独立 e2e 测试环境启动 Redis、主服务、AB 实验服务和所需打分服务。
- HTTP 主服务地址使用 `{{http_base_url}}`，gRPC 主服务地址使用 `{{grpc_target}}`，AB 服务地址使用 `{{ab_base_url}}`。
- 主服务通过环境变量或独立测试配置读取 `AB_SERVICE_URL={{ab_base_url}}`，不修改仓库默认 `.env`。
- 用例之间隔离 `user_id`、`reqId`、库存 key 和白名单数据。

**通用断言**：请求完成后不产生跨用例共享脏数据；成功推荐场景均可通过用户券查询接口查询到同一条发放记录。

**变量定义**：
- `http_json` = HTTP 推荐响应 JSON。
- `grpc_resp` = gRPC 推荐响应 message。
- `coupon` = 推荐响应中的发放结果。
- `stock(coupon_id)` = `GET /api/v1/admin/stock/{coupon_id}` 返回的库存值。

---

## 一、HTTP 全链路

### TC-E2E-001：通过 HTTP 走内部打分时完成主服务到 AB 服务再到发放的全链路
- **优先级**：P0
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：启动 Redis、AB 实验服务、内部 gRPC mock 打分服务和主服务；主服务配置 `AB_SERVICE_URL={{ab_base_url}}`
  - 前置操作：在 AB 服务设置 `u_e2e_http_internal_001` 白名单，命中 `{"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}`
  - 前置操作：写入用户特征 `{"gender":"female","age":"24","total_spend":"12000","purchase_frequency":"8","register_days":"60","is_new_user":"True","is_member":"True"}`
  - 前置操作：设置 `COUPON_ACT_001` 库存为 `5`
  - 请求覆盖：`scene_name="game"`、`device="mobile"`、`external=0`、`score_threshold=0.2`、`max_claim_per_request=1`、items 只包含 `COUPON_ACT_001`
- **断言**：`http_status == 200`；`http_json.code == 0`；`http_json.scene_id == 1001`；`http_json.experiment_info == {"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}`；`http_json.results[0].item_id == "COUPON_ACT_001"`；`http_json.results[0].recommended is True`；`coupon.item_id == "COUPON_ACT_001"`；`coupon.user_id == "u_e2e_http_internal_001"`；`coupon.status == "claimed"`；`stock("COUPON_ACT_001") == 4`；`GET /api/v1/coupons/u_e2e_http_internal_001` 返回 `total == 1` 且 `coupons[0].instance_id == coupon.instance_id`

### TC-E2E-002：通过 HTTP 走外部打分时跳过实验但仍完成推荐与发放
- **优先级**：P0
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：启动 Redis、AB 实验服务、外部 HTTP mock 打分服务和主服务；主服务配置 `AB_SERVICE_URL={{ab_base_url}}`
  - 前置操作：写入用户特征 `{"gender":"male","age":"31","total_spend":"8000","purchase_frequency":"5","register_days":"120","is_new_user":"False","is_member":"True"}`
  - 前置操作：设置 `COUPON_SHIP_001` 库存为 `5`
  - 请求覆盖：`user_id="u_e2e_http_external_002"`、`scene_name="ad"`、`device="pc"`、`external=1`、`score_threshold=0.2`、`max_claim_per_request=1`、items 只包含 `COUPON_SHIP_001`
- **断言**：`http_status == 200`；`http_json.code == 0`；`http_json.scene_id == 2002`；`http_json.experiment_info == {}`；`http_json.results[0].item_id == "COUPON_SHIP_001"`；`http_json.results[0].recommended is True`；`coupon.item_id == "COUPON_SHIP_001"`；`coupon.user_id == "u_e2e_http_external_002"`；`GET /api/v1/coupons/u_e2e_http_external_002` 返回 `total == 1` 且首条 `item_id == "COUPON_SHIP_001"`

---

## 二、双协议对齐

### TC-E2E-003：同一兜底请求通过 HTTP 和 gRPC 返回一致的业务结果
- **优先级**：P0
- **场景变量**：
  - 协议：HTTP / gRPC
  - 环境覆盖：启动 Redis 和主服务；不依赖 AB 服务命中；不写入任何 `coupon:fallback:score:*` Redis key
  - 前置操作：设置 `COUPON_ACT_001` 库存为 `2`
  - 请求覆盖：HTTP 与 gRPC 使用同一业务请求，`user_id="u_e2e_dual_proto_003"`、`scene_name="game"`、`device="mobile"`、`policy_id="policy_fallback_001"`、`external=0`、`score_threshold=0.4`、`max_claim_per_request=1`、items 只包含 `COUPON_ACT_001`
- **断言**：HTTP 响应 `status == 200` 且 `code == 0`；`grpc_resp.code == 0`；两侧 `scene_id == 3001`；两侧 `experiment_info == {}`；两侧首个结果均满足 `item_id == "COUPON_ACT_001"`、`score == 0.5`、`calibrated_score == 0.5`、`recommended is True`；两侧 `coupon.item_id == "COUPON_ACT_001"`；最终 `stock("COUPON_ACT_001") == 0`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L0_system_architecture | HTTP 内部全链路、HTTP 外部全链路、HTTP/gRPC 双协议一致性 | 主服务与外部打分服务的异常恢复、跨进程并发压测 |
| L1/ab_experiment | 远程 AB 服务参与主链路、`external=1` 跳过实验评估 | AB 服务不可用时的端到端错误传播 |
| L1/issuance | 发放后库存扣减和查询闭环 | 并发库存竞争 |
