# feature_scoring 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/feature_scoring
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`POST /api/v1/recommend` / `gRPC coupon.CouponService/Recommend`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_feat_default",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "req_feat_default",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [{"item_id": "COUPON_FEAT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]
}
```

**基础请求体（gRPC）**：

```text
coupon.RecommendRequest{
  user_id:"{{user_id}}", scene_name:"game", device:"mobile", policy_id:"", external:0,
  req_id:"{{req_id}}", score_threshold:0.0, max_claim_per_request:1,
  items:[{item_id:"{{item_id}}", coupon_type:"discount", value:80, min_spend:5000, expire_days:7}]
}
```

**标准前置**：
- 主服务、AB 实验服务、Redis、打分服务均已启动；校准实验关闭
- 初始化库存：`SET coupon:stock:{{item_id}} 100 EX 86400`
- 用例需要替换 item 特征文件时，使用独立测试文件路径启动服务，不修改仓库默认 TSV

**通用断言**：除明确异常外，`response.code == 0`

**变量定义**：
- `err_scoring` = `{"code": 1003, "message": "打分服务异常", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`

---

## 一、Redis 特征读取边界

### TC-FEAT-004：用户特征 key 不存在时静默省略
- **优先级**：P2
- **场景变量**：
  - 协议：HTTP
  - 前置操作：删除用户全部特征 key：`DEL coupon:user_feature:gender:u_feat_missing ...`
  - 请求覆盖：HTTP 请求 `user_id="u_feat_missing"`、`item_id="COUPON_FEAT_MISSING"`
- **断言**：`response.body.code == 0`； 打分服务收到的 `user_features == {}`
- **标记**：`[manual]`

### TC-FEAT-005：Redis 用户特征读取异常时请求失败
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：启动服务后停止 Redis，或使用不可连接 Redis 测试配置
  - 请求覆盖：HTTP 请求 `user_id="u_feat_redis_down"`
- **断言**：`response.status_code == 500`
- **标记**：`[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`

---

## 二、Item 特征文件降级

### TC-FEAT-006：TSV 文件不存在时安全降级为空 item 特征
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 环境覆盖：使用独立测试配置启动服务，`item_feature_file="/tmp/not_exists_item_features.tsv"`
  - 请求覆盖：HTTP 请求 `item_id="COUPON_FEAT_NO_FILE"`
- **断言**：`response.body.code == 0`； 应用日志包含 `item 特征文件不存在`
- **标记**：`[manual]`

### TC-FEAT-007：TSV 行格式错误时跳过该行
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 前置操作：测试 TSV 内容包含一行 `BAD_LINE_WITHOUT_TAB` 和一行合法 `COUPON_FEAT_OK\t{"brand":"A"}`
  - 请求覆盖：HTTP 请求 `item_id="COUPON_FEAT_OK"`
- **断言**：`response.body.code == 0`； 日志包含 `item 特征文件第 1 行格式错误`
- **标记**：`[manual]`

### TC-FEAT-008：TSV JSON 解析失败时跳过该行
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 前置操作：测试 TSV 内容包含 `COUPON_FEAT_BAD\t{bad json`
  - 请求覆盖：HTTP 请求 `item_id="COUPON_FEAT_BAD"`
- **断言**：`response.body.code == 0`； 日志包含 `JSON 解析失败`
- **标记**：`[manual]`

### TC-FEAT-009：不存在的 item 返回空特征但 pipeline 不中断
- **优先级**：P2
- **场景变量**：
  - 协议：HTTP
  - 前置操作：HTTP 请求 `item_id="COUPON_FEAT_NOT_IN_TSV"`，该 item 不在 TSV 中
- **断言**：`response.body.code == 0`；`response.body.results[0].item_id == "COUPON_FEAT_NOT_IN_TSV"`

---

## 三、打分故障兜底

### TC-SCORE-006：打分超时且 fallback allow 时使用默认分继续
- **优先级**：P2 / 异常
- **场景变量**：
  - 请求覆盖：内部打分服务超时
  - 请求覆盖：配置 `fallback.enabled=true`、`on_scoring_timeout.action="allow"`、`default_score=0.5`
- **断言**：`response.body.code == 0`；`response.body.results[0].score == 0.5`
- **标记**：`[!可行性存疑: 当前集成环境的内部 gRPC mock 打分服务没有公开控制接口可按用例触发超时]`

### TC-SCORE-007：打分不可用且 fallback allow 时使用默认分继续
- **优先级**：P2 / 异常
- **场景变量**：
  - 请求覆盖：内部打分服务不可用
  - 请求覆盖：配置 `fallback.enabled=true`、`on_scoring_unavailable.action="allow"`、`default_score=0.3`
- **断言**：`response.body.code == 0`；`response.body.results[0].score == 0.3`
- **标记**：`[!可行性存疑: 当前集成环境的内部 gRPC mock 打分服务没有公开控制接口可按用例触发不可用]`

### TC-SCORE-008：打分超时且 fallback deny 时返回打分异常
- **优先级**：P2 / 异常
- **场景变量**：
  - 请求覆盖：内部打分服务超时
  - 环境覆盖：测试配置 `fallback.on_scoring_timeout.action="deny"`
- **断言**：`response.body == err_scoring`
- **标记**：`[!可行性存疑: 需要测试环境支持独立 fallback 配置启动服务]`

### TC-SCORE-009：打分故障兜底分优先读取 Redis
- **优先级**：P2 / 异常
- **场景变量**：
  - 请求覆盖：内部打分服务抛出 `RuntimeError`
  - 请求覆盖：配置 `fallback.enabled=true`、`on_scoring_unavailable.action="allow"`、`default_score=0.3`
  - 前置操作：Redis 设置 `SET coupon:fallback:score:1001 0.9`
- **断言**：`response.body.code == 0`；`response.body.results[0].score == 0.9`；`response.body.coupon != null`
- **标记**：`[!可行性存疑: 当前集成环境的内部 gRPC mock 打分服务没有公开控制接口可按用例触发 RuntimeError]`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/feature_scoring | 用户特征缺失、Redis 特征读取异常、TSV 文件不存在/行格式错误/JSON 解析失败、不存在 item、打分超时/不可用兜底、fallback deny、打分故障时 Redis 兜底分优先 | 无 |
| L2/0402 | 内外部打分故障路径与 fallback 行为、Redis 兜底分优先级 | 无（仅限 feature_scoring 范围） |
