# calibration 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/calibration
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
  "items": [{"item_id": "COUPON_CAL_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[{item_id:"COUPON_CAL_BOUNDARY_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动
- 初始化库存：`SET coupon:stock:COUPON_CAL_BOUNDARY_001 100 EX 86400`
- 通过 AB 白名单强制命中校准开启策略；校准文件使用独立测试目录

**通用断言**：`response.code == 0`

**变量定义**：
- `s` = `response.results[0].score`
- `cal` = `response.results[0].calibrated_score`
- `clamp(x)` = `max(0, min(1, x))`

---

## 一、目录与文件异常

### TC-CAL-011：校准目录不存在时降级为不校准
- **优先级**：P2 / 异常
- **场景变量**：`calibration_dir.linear="/tmp/not_exists_cal_linear_011"`，目录不存在
- **断言**：`cal == s`

### TC-CAL-012：校准目录为空时静默降级
- **优先级**：P2 / 异常
- **场景变量**：执行 `mkdir -p /tmp/cal_empty_012/linear`，目录存在但没有 `*.json`
- **断言**：`cal == s`；`[manual]` 无 WARNING/ERROR 日志

### TC-CAL-013：校准文件 JSON 解析失败时降级
- **优先级**：P2 / 异常
- **场景变量**：线性目录 `1.json` 内容为 `{bad json`
- **断言**：`cal == s`；`[manual]` 应用日志包含 `校准文件读取失败`

### TC-CAL-014：校准文件不是 list 时降级
- **优先级**：P2 / 异常
- **场景变量**：线性目录 `1.json` 内容为 `{"conditions":{"device":"mobile"},"k":2,"b":0}`
- **断言**：`cal == s`；`[manual]` 应用日志包含 `校准文件格式错误`

### TC-CAL-015：calibration_dir 为空字符串时降级
- **优先级**：P2 / 异常
- **场景变量**：实验参数 `{"calibration_dir":{"linear":"","piecewise":""}}`
- **断言**：`cal == s`

---

## 二、分段边界

### TC-CAL-016：分段左边界命中当前区间
- **优先级**：P2
- **场景变量**：控制打分服务返回 `s=0.3`；分段 `[0,0.3)->k=0.5,b=0.1`、`[0.3,0.7)->k=1.0,b=0.0`
- **断言**：`cal == round(clamp(1.0 * 0.3 + 0.0), 4)`

### TC-CAL-017：最后一个分段右边界闭区间命中
- **优先级**：P2
- **场景变量**：控制打分服务返回 `s=1.0`；最后分段 `[0.7,1.0] -> k=1.5,b=-0.2`
- **断言**：`cal == round(clamp(1.5 * 1.0 - 0.2), 4)`

### TC-CAL-018：分段区间配置非法时跳过该段
- **优先级**：P2 / 异常
- **场景变量**：第一段 `range=[0.7,0.3]`，第二段 `range=[0,1] k=1,b=0`；请求命中条件
- **断言**：非法第一段不生效；`cal == s`

---

## 三、条件类型转换

### TC-CAL-019：external 条件支持字符串和数字等值匹配
- **优先级**：P2
- **场景变量**：线性规则 `conditions={"external":"0"}`、`k=1.5,b=0`；请求 `external=0`
- **断言**：`cal == round(clamp(1.5 * s), 4)`

### TC-CAL-020：布尔条件支持字符串和布尔等值匹配
- **优先级**：P2
- **场景变量**：请求 item 包含 `isPrior=true` 但 `isPrior` 不在校准匹配白名单；线性规则 `conditions={"isPrior":"true"}`、`k=2,b=0`
- **断言**：`cal == s`；详见 mismatch.md

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/calibration | 目录不存在/为空/空字符串、JSON 解析失败、文件非 list、分段边界、非法分段跳过、条件类型转换 | 无 |
| L2/0405 | 分段函数边界、校准文件降级、条件匹配类型转换 | 无（仅限 calibration 范围） |
