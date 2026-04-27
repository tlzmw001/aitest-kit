# calibration 业务测试用例

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
  "items": [{"item_id": "COUPON_CAL_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[{item_id:"COUPON_CAL_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动
- 初始化库存：`SET coupon:stock:COUPON_CAL_001 100 EX 86400`
- 通过 AB 白名单强制命中 `calibration_exp_game` 指定策略；粗排关闭
- 校准文件使用独立测试目录，不修改仓库默认校准文件

**通用断言**：`response.code == 0`

**变量定义**：
- `s` = `response.results[0].score`
- `cal` = `response.results[0].calibrated_score`
- `clamp(x)` = `max(0, min(1, x))`

---

## 一、实验控制

### TC-CAL-001：HTTP 实验关闭时跳过校准
- **优先级**：P1
- **场景变量**：校准实验参数 `{"enable_calibration":false,"calibration_dir":{"linear":"/tmp/cal_linear_001"}}`，线性文件存在且匹配 `device=mobile`
- **断言**：`cal == s`

### TC-CAL-002：gRPC 根据 scene_id 选择 game 校准实验
- **优先级**：P1
- **场景变量**：`scene_id=1001` 的 `calibration_exp_game` 启用，线性规则 `k=1.5,b=0.1,conditions={"device":"mobile"}`；ad 校准实验配置不同参数
- **断言**：`cal == round(clamp(1.5 * s + 0.1), 4)`

---

## 二、条件匹配

### TC-CAL-003：多条件匹配时靠上的规则优先
- **优先级**：P1
- **场景变量**：线性文件两条规则都匹配：第 1 条 `k=1.2,b=0.0`，第 2 条 `k=2.0,b=0.0`
- **断言**：`cal == round(clamp(1.2 * s), 4)`

### TC-CAL-004：条件字段缺失时规则不匹配
- **优先级**：P1
- **场景变量**：线性规则 `conditions={"gender":"male"}`；Redis 不设置用户 `gender` 特征
- **断言**：`cal == s`

### TC-CAL-005：条件字段不在白名单时规则不匹配
- **优先级**：P1
- **场景变量**：线性规则 `conditions={"unknown_field":"x"}`，`k=2.0,b=0.0`
- **断言**：`cal == s`

---

## 三、校准计算

### TC-CAL-006：仅命中线性校准
- **优先级**：P1
- **场景变量**：只配置线性目录；规则 `conditions={"device":"mobile"}`、`k=1.5`、`b=0.0`
- **断言**：`cal == round(clamp(1.5 * s), 4)`

### TC-CAL-007：仅命中分段函数校准
- **优先级**：P1
- **场景变量**：只配置分段目录；分段 `[0,0.3)->k=0.5,b=0.1`、`[0.3,0.7)->k=1.0,b=0.0`、`[0.7,1.0]->k=1.5,b=-0.2`，条件 `device=mobile`
- **断言**：按 `s` 所在区间计算 `cal == round(clamp(k * s + b), 4)`

### TC-CAL-008：线性和分段都命中时先分段后线性
- **优先级**：P1
- **场景变量**：分段同 TC-CAL-007；线性规则 `k=1.2,b=0.05`；二者都匹配 `device=mobile`
- **断言**：`mid = k_pw * s + b_pw`；`cal == round(clamp(1.2 * mid + 0.05), 4)`

### TC-CAL-009：两类规则都不匹配时不校准
- **优先级**：P1
- **场景变量**：线性和分段规则条件均为 `device=ios`，请求为 `mobile`
- **断言**：`cal == s`

### TC-CAL-010：目录中选取序号最大的版本文件
- **优先级**：P1
- **场景变量**：线性目录包含 `1.json` 规则 `k=1.1,b=0` 和 `3.json` 规则 `k=1.8,b=0`，均匹配 `device=mobile`
- **断言**：`cal == round(clamp(1.8 * s), 4)`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/calibration | 实验关闭、scene_id 选取实验、多条件优先级、缺字段/未知字段不匹配、仅线性、仅分段、双重校准、双不命中、最新版本文件 | 目录和文件异常、分段边界、类型转换由 boundary.md 覆盖 |
| L2/0405 | 条件匹配、分段函数、版本化文件、双重校准叠加 | 无（仅限 calibration 范围） |
