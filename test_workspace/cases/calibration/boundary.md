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
- 不指定打分服务返回的固定分数；精确分段边界值不能通过推荐接口稳定构造时，按响应实际 `s` 做关系断言并保留可行性标记

**通用断言**：`response.code == 0`

**变量定义**：
- `s` = `response.results[0].score`
- `cal` = `response.results[0].calibrated_score`
- `clamp(x)` = `max(0, min(1, x))`

---

## 一、目录与文件异常

### TC-CAL-015：校准目录不存在时降级为不校准
- **优先级**：P2 / 异常
- **场景变量**：环境覆盖：`calibration_dir.linear="/tmp/not_exists_cal_linear_011"`，目录不存在
- **断言**：`cal == s`

### TC-CAL-016：校准目录为空时静默降级
- **优先级**：P2 / 异常
- **场景变量**：前置操作：执行 `mkdir -p /tmp/cal_empty_012/linear`，目录存在但没有 `*.json`
- **断言**：`cal == s`； 无 WARNING/ERROR 日志
- **标记**：`[manual]`

### TC-CAL-017：校准文件 JSON 解析失败时降级
- **优先级**：P2 / 异常
- **场景变量**：前置操作：线性目录 `1.json` 内容为 `{bad json`
- **断言**：`cal == s`； 应用日志包含 `校准文件读取失败`
- **标记**：`[manual]`

### TC-CAL-018：校准文件不是 list 时降级
- **优先级**：P2 / 异常
- **场景变量**：前置操作：线性目录 `1.json` 内容为 `{"conditions":{"device":"mobile"},"k":2,"b":0}`
- **断言**：`cal == s`； 应用日志包含 `校准文件格式错误`
- **标记**：`[manual]`

### TC-CAL-019：calibration_dir 为空字符串时降级
- **优先级**：P2 / 异常
- **场景变量**：环境覆盖：实验参数 `{"calibration_dir":{"linear":"","piecewise":""}}`
- **断言**：`cal == s`

---

## 二、分段边界

### TC-CAL-020：分段左边界命中当前区间
- **优先级**：P2
- **场景变量**：
  - 协议：HTTP
  - 前置操作：分段 `[0,0.3)->k=0.5,b=0.1`、`[0.3,0.7)->k=1.0,b=0.0`
  - 请求覆盖：通过 HTTP 推荐接口读取实际 `s`
- **断言**：若实际 `s == 0.3`，则 `cal == round(clamp(1.0 * s + 0.0), 4)`；否则按实际 `s` 所在分段计算 `cal == round(clamp(k * s + b), 4)`，并记录本次未覆盖精确 `0.3` 边界
- **标记**：`[!可行性存疑: 推荐接口无法稳定构造 s == 0.3，精确左边界需组件级测试或可控打分测试入口]`

### TC-CAL-021：最后一个分段右边界闭区间命中
- **优先级**：P2
- **场景变量**：
  - 协议：HTTP
  - 前置操作：最后分段 `[0.7,1.0] -> k=1.5,b=-0.2`
  - 请求覆盖：通过 HTTP 推荐接口读取实际 `s`
- **断言**：若实际 `s == 1.0`，则 `cal == round(clamp(1.5 * s - 0.2), 4)`；否则按实际 `s` 所在分段计算 `cal == round(clamp(k * s + b), 4)`，并记录本次未覆盖精确 `1.0` 边界
- **标记**：`[!可行性存疑: 推荐接口无法稳定构造 s == 1.0，精确右边界需组件级测试或可控打分测试入口]`

### TC-CAL-022：分段区间配置非法时跳过该段
- **优先级**：P2 / 异常
- **场景变量**：
  - 请求覆盖：第一段 `range=[0.7,0.3]`，第二段 `range=[0,1] k=1,b=0`
  - 请求覆盖：请求命中条件
- **断言**：`cal == s`
- **说明**：第一段 `range=[0.7,0.3]` 非法，应不参与匹配；第二段 `[0,1] k=1,b=0` 生效，因此校准后分数等于原始分数。

---

## 三、条件类型转换

### TC-CAL-023：external 条件支持字符串和数字等值匹配
- **优先级**：P2
- **场景变量**：
  - 前置操作：线性规则 `conditions={"external":"0"}`、`k=1.5,b=0`
  - 请求覆盖：请求 `external=0`
- **断言**：`cal == round(clamp(1.5 * s), 4)`

### TC-CAL-025：gRPC 校准目录不存在时降级为不校准
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：gRPC
  - 环境覆盖：`calibration_dir.linear="/tmp/not_exists_cal_linear_grpc_025"`，目录不存在
  - 请求覆盖：发送 gRPC 推荐请求
- **断言**：`response.code == 0`；`cal == s`

### TC-CAL-026：gRPC 校准文件 JSON 解析失败时降级
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：gRPC
  - 前置操作：线性目录 `1.json` 内容为 `{bad json`
  - 请求覆盖：发送 gRPC 推荐请求
- **断言**：`response.code == 0`；`cal == s`； 应用日志包含 `校准文件读取失败`
- **标记**：`[manual]`

### TC-CAL-027：gRPC external 条件支持字符串和数字等值匹配
- **优先级**：P2
- **场景变量**：
  - 协议：gRPC
  - 前置操作：线性规则 `conditions={"external":"0"}`、`k=1.5,b=0`
  - 请求覆盖：gRPC 请求 `external=0`
- **断言**：`response.code == 0`；`cal == round(clamp(1.5 * s), 4)`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/calibration | 目录不存在/为空/空字符串、JSON 解析失败、文件非 list、分段边界、非法分段跳过、条件类型转换、gRPC 校准边界 | 无 |
| L2/0405 | 分段函数边界、校准文件降级、条件匹配类型转换 | 无（仅限 calibration 范围） |
