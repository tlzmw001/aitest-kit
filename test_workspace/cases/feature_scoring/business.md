# feature_scoring 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/feature_scoring
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
  "context": {"channel": "test"},
  "items": [
    {"item_id": "COUPON_FEAT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}
  ]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:{{external}},
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  context:{"channel":"test"},
  items:[{item_id:"COUPON_FEAT_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、内部 gRPC 打分服务、外部 HTTP 打分服务均已启动
- 初始化库存：`SET coupon:stock:COUPON_FEAT_001 100 EX 86400`
- 关闭粗排和校准实验，避免候选顺序和分数被其他模块改变
- 设置用户特征示例：`SET coupon:user_feature:gender:{{user_id}} male`、`SET coupon:user_feature:total_spend:{{user_id}} 1200`

**通用断言**：`response.code == 0`

**变量定义**：
- `s` = `response.results[0].score`
- `cal` = `response.results[0].calibrated_score`

---

## 一、特征抽取

### TC-FEAT-001：HTTP 读取 Redis 用户特征并透传给打分
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_feat_http"`、`external=0`；Redis 设置 `gender=male`、`total_spend=1200`
- **断言**：`response.body.code == 0`；`[manual]` 打分服务收到的 `user_features` 包含 `gender="male"`、`total_spend="1200"`

### TC-FEAT-002：gRPC 读取 Redis 用户特征并透传给打分
- **优先级**：P1
- **场景变量**：gRPC 请求 `user_id="u_feat_grpc"`、`external=0`；Redis 设置 `age=30`、`is_member=true`
- **断言**：`response.code == 0`；`[manual]` 打分服务收到的 `user_features` 包含 `age="30"`、`is_member="true"`

### TC-FEAT-003：请求 item 字段与 TSV item 特征合并后进入打分
- **优先级**：P1
- **场景变量**：HTTP 请求 item 为 `COUPON_FEAT_001`，请求体包含 `coupon_type="discount"`、`value=80`、`min_spend=5000`、`expire_days=7`；TSV 中存在该 item 的其他特征
- **断言**：`[manual]` 打分服务收到的 item features 同时包含 TSV 特征和请求体中的 `coupon_type/value/min_spend/expire_days`

---

## 二、打分路由

### TC-SCORE-001：HTTP external=0 调用内部 gRPC 打分
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_score_internal_http"`、`external=0`、`reqId="req-score-001"`
- **断言**：`response.body.code == 0`；`response.body.results[0].score >= 0.1`；`[manual]` 内部打分服务收到明文 `user_id="u_score_internal_http"`

### TC-SCORE-002：gRPC external=0 调用内部 gRPC 打分
- **优先级**：P1
- **场景变量**：gRPC 请求 `user_id="u_score_internal_grpc"`、`external=0`、`req_id="req-score-002"`
- **断言**：`response.code == 0`；`response.results[0].score >= 0.1`；`[manual]` 内部打分服务收到明文 `user_id="u_score_internal_grpc"`

### TC-SCORE-003：HTTP external=1 调用外部 HTTP 打分
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_score_external_http"`、`external=1`、`reqId="req-score-003"`
- **断言**：`response.body.code == 0`；`response.body.results[0].score >= 0.2`；`response.body.experiment_info == {}`

### TC-SCORE-004：gRPC external=1 调用外部 HTTP 打分
- **优先级**：P1
- **场景变量**：gRPC 请求 `user_id="u_score_external_grpc"`、`external=1`、`req_id="req-score-004"`
- **断言**：`response.code == 0`；`response.results[0].score >= 0.2`；`response.experiment_info == {}`

### TC-SCORE-005：外部打分 user_id 使用加盐 SHA-256
- **优先级**：P1
- **场景变量**：HTTP 请求 `user_id="u_score_encrypt"`、`external=1`；外部打分服务 salt 使用默认 `coupon_external_uid_salt`
- **断言**：`[manual]` 外部打分服务收到的 `user_id == sha256("coupon_external_uid_salt:u_score_encrypt")`；不包含明文 `u_score_encrypt`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/feature_scoring | HTTP/gRPC 用户特征读取、item 特征合并、external=0 内部打分、external=1 外部打分、外部 user_id 加密 | 打分服务故障兜底、Redis 异常、TSV 降级由 boundary.md 覆盖 |
| L2/0402 | 内部/外部打分路由、外部打分 base_score、user_id 加密 | 无（仅限 feature_scoring 范围） |
