# rough_ranking 边界测试用例

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
  "items": {{items}}
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
- 粗排策略通过 AB 白名单强制命中，校准实验关闭
- 默认候选券集合与 business.md 相同；边界用例按场景变量覆盖

**通用断言**：`response.code == 0`

**变量定义**：
- `score_items` = 打分服务实际收到的 item 顺序，或响应 `results[*].item_id`

---

## 一、空输入与截断边界

### TC-RANK-010：候选券为空时参数校验拦截
- **优先级**：P2 / 异常
- **场景变量**：HTTP 请求 `items=[]`
- **断言**：`response.body.code == 1001`；`response.body.results == []`

### TC-RANK-011：truncate_count 小于等于 0 时返回空推荐结果
- **优先级**：P2 / 异常
- **场景变量**：策略参数 `{"enable_coarse_rank":true,"truncate_count":0,"truncate_rule":"top_value"}`；HTTP 请求传入 3 张合法券
- **断言**：`response.body.code == 0`；`response.body.results == []`；`response.body.coupon == null`

### TC-RANK-012：truncate_count 非数字时默认不截断
- **优先级**：P2 / 异常
- **场景变量**：策略参数 `{"enable_coarse_rank":true,"truncate_count":"bad","truncate_rule":"top_value"}`；HTTP 请求传入 3 张合法券
- **断言**：`len(score_items) == 3`

---

## 二、异常规则降级

### TC-RANK-013：未知 truncate_rule 降级到 top_value
- **优先级**：P2 / 异常
- **场景变量**：策略参数 `{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"unknown_rule"}`；HTTP 请求传入 A/B/C
- **断言**：`score_items == ["COUPON_RANK_A","COUPON_RANK_B"]`；`[manual]` 应用日志包含 `未知粗排规则`

### TC-RANK-014：sort_keys 格式异常时跳过异常 key
- **优先级**：P2 / 异常
- **场景变量**：策略参数 `{"enable_coarse_rank":true,"truncate_count":2,"sort_keys":["bad",{"field":123,"weight":1},{"field":"value","weight":"bad"}]}`
- **断言**：请求不抛异常；`len(score_items) == 2`

### TC-RANK-015：filters 操作符未知时该条件不通过
- **优先级**：P2 / 异常
- **场景变量**：策略参数 `{"enable_coarse_rank":true,"truncate_count":3,"filters":[{"field":"value","op":"bad_op","value":80}]}`
- **断言**：`response.body.code == 0`；`response.body.results == []`；`[manual]` 应用日志包含 `未知过滤操作符`

### TC-RANK-016：diversity 参数异常时跳过打散
- **优先级**：P2 / 异常
- **场景变量**：策略参数 `{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_value","diversity":{"enabled":true,"group_field":123,"max_per_group":0}}`
- **断言**：按 `top_value` 直接截断，`score_items == ["COUPON_RANK_A","COUPON_RANK_B"]`

### TC-RANK-017：prior_count 大于 truncate_count 时截断到 truncate_count
- **优先级**：P2 / 异常
- **场景变量**：策略参数 `{"enable_coarse_rank":true,"truncate_count":1,"prior_count":3,"prior_rule":"top_value"}`；B 为 `isPrior=true`
- **断言**：`score_items == ["COUPON_RANK_B"]`；`[manual]` 应用日志包含 `prior_count=3 大于 truncate_count=1`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/rough_ranking | 空候选参数校验、truncate_count<=0、truncate_count 非数字、未知 rule、sort_keys 格式异常、filter 操作符未知、diversity 参数异常、prior_count 超限 | 无 |
| L2/0404 | 粗排增强异常参数降级 | 无（仅限 rough_ranking 范围） |
