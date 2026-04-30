# rough_ranking 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/rough_ranking
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
    {"item_id": "COUPON_RANK_A", "coupon_type": "discount", "value": 100, "min_spend": 9000, "expire_days": 7},
    {"item_id": "COUPON_RANK_B", "coupon_type": "fixed", "value": 80, "min_spend": 1000, "expire_days": 7, "isPrior": true},
    {"item_id": "COUPON_RANK_C", "coupon_type": "free_shipping", "value": 50, "min_spend": 500, "expire_days": 7}
  ]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items: {{items}}
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动
- 候选券默认集合：`COUPON_RANK_A(value=100,min_spend=9000,type=discount)`、`COUPON_RANK_B(value=80,min_spend=1000,type=fixed,isPrior=true)`、`COUPON_RANK_C(value=50,min_spend=500,type=free_shipping)`
- 初始化库存：`SET coupon:stock:COUPON_RANK_A 100 EX 86400`、`SET coupon:stock:COUPON_RANK_B 100 EX 86400`、`SET coupon:stock:COUPON_RANK_C 100 EX 86400`
- 粗排策略通过 AB 白名单强制命中 `coarse_rank_exp_game` 的指定策略；校准实验固定关闭，避免校准影响断言
- 验证粗排入选集合或顺序时，复制 `coupon_system/config/settings.yaml` 到独立测试目录，将 `scoring_service.port` 改为测试打分代理端口，并用 `COUPON_CONFIG_PATH` 指向该测试配置启动主服务；测试打分代理实现 `scoring.ScoringService/Score`，记录请求 `items[*].item_id` 顺序后按原 mock 逻辑返回分数，不指定或改写固定分数

**通用断言**：`response.code == 0`

**变量定义**：
- `rank_input_items` = 打分服务实际收到的 `items[*].item_id` 顺序，用于验证粗排实际送入打分的候选顺序
- `result_item_set` = `set(response.results[*].item_id)`，仅用于验证最终响应包含哪些 item，不用于断言粗排顺序

---

## 一、实验控制

### TC-RANK-001：HTTP 实验关闭时跳过粗排
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 前置操作：白名单命中粗排关闭策略 `enable_coarse_rank=false`
  - 请求覆盖：HTTP 请求按 `A,B,C` 顺序传入 3 张券
- **断言**：`rank_input_items == ["COUPON_RANK_A","COUPON_RANK_B","COUPON_RANK_C"]`

### TC-RANK-002：gRPC 实验开启且不配置增强能力时保持向后兼容
- **优先级**：P1
- **场景变量**：
  - 协议：gRPC
  - 策略参数：白名单命中`{"enable_coarse_rank":true,"truncate_count":3}`，不配置 `prior_count`、`filters`、`sort_keys`、`diversity`
  - 请求覆盖：gRPC 请求按 `A,B,C` 顺序传入 3 张券
- **断言**：`rank_input_items == ["COUPON_RANK_A","COUPON_RANK_B","COUPON_RANK_C"]`

---

## 二、基础截断

### TC-RANK-003：top_value 按面额降序截断
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 策略参数：`{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_value"}`
  - 请求覆盖：HTTP 请求传入 A/B/C
- **断言**：`rank_input_items == ["COUPON_RANK_A","COUPON_RANK_B"]`

### TC-RANK-004：top_min_spend 按门槛降序截断
- **优先级**：P1
- **场景变量**：
  - 协议：HTTP
  - 策略参数：`{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_min_spend"}`
  - 请求覆盖：HTTP 请求传入 A/B/C
- **断言**：`rank_input_items == ["COUPON_RANK_A","COUPON_RANK_B"]`

### TC-RANK-005：random 截断只保证数量和来源
- **优先级**：P2
- **场景变量**：
  - 协议：HTTP
  - 策略参数：`{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"random"}`
  - 请求覆盖：HTTP 请求传入 A/B/C
- **断言**：`len(rank_input_items) == 2`；`set(rank_input_items) <= {"COUPON_RANK_A","COUPON_RANK_B","COUPON_RANK_C"}`

---

## 三、增强能力

### TC-RANK-006：优先券保送后普通券补位
- **优先级**：P1
- **场景变量**：
  - 策略参数：`{"enable_coarse_rank":true,"truncate_count":2,"prior_count":1,"prior_rule":"top_value","truncate_rule":"top_value"}`
  - 请求覆盖：B 为 `isPrior=true`
- **断言**：`rank_input_items[0] == "COUPON_RANK_B"`；`len(rank_input_items) == 2`

### TC-RANK-007：多条件过滤取交集
- **优先级**：P1
- **场景变量**：策略参数：`{"enable_coarse_rank":true,"truncate_count":3,"filters":[{"field":"value","op":"gte","value":80},{"field":"coupon_type","op":"in","value":["discount","fixed"]}]}`
- **断言**：`rank_input_items == ["COUPON_RANK_A","COUPON_RANK_B"]`

### TC-RANK-008：多维排序按加权分排序
- **优先级**：P1
- **场景变量**：策略参数：`{"enable_coarse_rank":true,"truncate_count":3,"sort_keys":[{"field":"value","weight":1.0},{"field":"min_spend","weight":-1.0}]}`
- **断言**：`rank_input_items[0] == "COUPON_RANK_B"`（面额较高且门槛低优先）

### TC-RANK-009：类型打散限制同类型数量并回填
- **优先级**：P1
- **场景变量**：
  - 请求覆盖：请求传入 4 张券，其中 3 张 `coupon_type="discount"`、1 张 `coupon_type="fixed"`
  - 策略参数：`{"enable_coarse_rank":true,"truncate_count":3,"truncate_rule":"top_value","diversity":{"enabled":true,"group_field":"coupon_type","max_per_group":1}}`
- **断言**：`len(rank_input_items) == 3`；前 2 个入选 item 的 `coupon_type` 不相同；不足部分按排序结果回填

### TC-RANK-010：truncate_count 超过候选数时不截断
- **优先级**：P1
- **场景变量**：
  - 策略参数：`{"enable_coarse_rank":true,"truncate_count":10,"truncate_rule":"top_value"}`
  - 请求覆盖：请求只传入 1 张合法候选券
- **断言**：`len(rank_input_items) == 1`；`rank_input_items == ["COUPON_RANK_A"]`

### TC-RANK-011：gRPC is_prior 字段映射为内部 isPrior
- **优先级**：P1
- **场景变量**：
  - 协议：gRPC
  - 请求覆盖：gRPC 请求中 `COUPON_RANK_B.is_prior=true`
  - 策略参数：`{"enable_coarse_rank":true,"truncate_count":1,"prior_count":1,"prior_rule":"top_value"}`
- **断言**：`rank_input_items == ["COUPON_RANK_B"]`，证明 gRPC `is_prior` 已映射为粗排消费的 `isPrior`

### TC-RANK-012：完整粗排 pipeline 组合生效
- **优先级**：P1
- **场景变量**：
  - 请求覆盖：请求传入 8 个 item（含 3 个 `isPrior=true`）
  - 策略参数：策略参数同时配置 `prior_count=2`、过滤 `expire_days>=3`、加权排序、类型打散 `max_per_group=1`、`truncate_count=5`
- **断言**：`rank_input_items == ["P1","P2","A","C","E"]`；前 2 个为保送券，其余 3 个来自过滤、排序、打散后的目标位

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/rough_ranking | 实验开关、向后兼容、top_value/top_min_spend/random 截断、截断数量超过候选数、gRPC is_prior 映射、优先券保送、条件过滤、多维排序、类型打散、完整粗排 pipeline | 空候选、异常参数降级由 boundary.md 覆盖 |
| L2/0404 | 粗排增强四项能力及不配置时向后兼容、gRPC is_prior→isPrior 字段映射 | 无（仅限 rough_ranking 范围） |
