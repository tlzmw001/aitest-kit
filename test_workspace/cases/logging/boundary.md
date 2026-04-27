# logging 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/logging
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
  "items": [{"item_id": "COUPON_LOG_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[{item_id:"COUPON_LOG_BOUNDARY_001", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动
- 初始化库存：`SET coupon:stock:COUPON_LOG_BOUNDARY_001 100 EX 86400`
- 用例需要检查 logging 配置时，使用独立进程启动服务并采集 stdout/stderr

**通用断言**：业务响应 `code == 0`，除明确异常外

**变量定义**：
- `log` = 与当前 `reqId` 匹配的日志行

---

## 一、日志配置风险

### TC-LOG-009：未配置 root logger 时 INFO 业务日志不可见
- **优先级**：P2 / 异常
- **场景变量**：以默认 `python -m coupon_system.main` 启动服务，不额外调用 `logging.basicConfig(level=logging.INFO)`；HTTP 请求 `reqId="req-log-009"`。[!可行性存疑: 需要测试环境能区分 uvicorn 日志和业务 logger 输出]
- **断言**：业务请求返回 `code == 0`；stdout/stderr 中找不到 `recommend request: reqId=req-log-009`；详见 mismatch.md

### TC-LOG-010：显式配置 INFO 后业务日志可见
- **优先级**：P2
- **场景变量**：测试启动入口显式配置 `logging.basicConfig(level=logging.INFO)` 后启动服务；HTTP 请求 `reqId="req-log-010"`
- **断言**：stdout/stderr 或采集器中存在 `recommend request: reqId=req-log-010`

---

## 二、日志写入失败

### TC-LOG-011：日志 handler 写入失败不影响业务响应
- **优先级**：P2 / 异常
- **场景变量**：测试进程安装一个会在 `emit()` 抛异常的 logging handler；HTTP 请求 `reqId="req-log-011"`。[!可行性存疑: 需要测试环境能注入 logging handler]
- **断言**：业务响应仍为 `code == 0`；logging 内部 `handleError` 处理异常，无业务错误码

### TC-LOG-012：日志中的 item_ids 为空字符串时仍输出字段名
- **优先级**：P2 / 异常
- **场景变量**：无法通过接口发送空 items（会被参数校验拦截）；使用专项组件测试构造空 items 调用日志代码路径。[!可行性存疑: 黑盒接口无法覆盖，需组件级专项验证]
- **断言**：日志仍包含 `item_ids=` 字段；详见 mismatch.md

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/logging | 未配置 root logger 导致 INFO 不可见、显式配置 INFO 后可见、handler 写入失败、空 item_ids 专项风险 | 无 |
| L2/0402 | 日志系统可观测性边界 | 无（仅限 logging 范围） |
