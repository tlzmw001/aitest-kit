# 参数校验与限流

请求入口的校验和流控。

## 接口

- HTTP 端点：`POST /api/v1/recommend`
- gRPC 端点：`coupon.CouponService/Recommend`
- 请求/响应完整字段定义：[coupon.proto](../../../coupon_system/protos/coupon.proto)、[http_app.py CouponItemRequest/RecommendRequest](../../../coupon_system/http_app.py)
- 打分服务接口定义：[scoring.proto](../../../coupon_system/protos/scoring.proto)

## 输入

来自客户端的 HTTP/gRPC 请求。

### 推荐接口请求字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `user_id` | 是 | 用户 ID |
| `scene_name` | 是 | 场景名 |
| `device` | 是 | 设备类型 |
| `items` | 是 | 候选券列表 |
| `max_claim_per_request` | 是 | 最大发放数量，由调用方传入（无默认值） |
| `score_threshold` | 是 | 分数阈值，由调用方传入（无默认值）；取值范围 [0.0, 1.0] |
| `external` | 是 | int，0=内部打分，1=外部打分；仅允许 0 或 1 |
| `reqId` | 否 | 请求标识，字符串，用于 debug；默认空字符串，为空时自动生成 UUID |

### 接口契约（完整字段定义）

- 推荐接口请求/响应结构：[coupon.proto](../../../coupon_system/protos/coupon.proto)（RecommendRequest / RecommendResponse / ScoredItem / ClaimedCoupon）
- 查券接口：同 proto（QueryUserCouponsRequest / QueryUserCouponsResponse）
- 打分服务接口：[scoring.proto](../../../coupon_system/protos/scoring.proto)（ScoreRequest / ScoreResponse）

## 输出

校验通过 → 进入限流；校验失败 → 返回错误。

## 业务规则

1. 两层校验机制：
   - Pydantic 层：必填字段缺失 → HTTP 422，响应体为 FastAPI 标准格式 `{"detail": [{"loc": [...], "msg": "field required", ...}]}`
   - 业务层：字段值不合法（如 `external=2`、`score_threshold=1.5`、`user_id=""`）→ `{"code": 1001, "message": "参数无效"}`
2. 限流有开关控制（`config.rate_limit.enabled`）
3. 全局限流：配置项 `config.rate_limit.max_qps`（默认 1000 QPS），key=`"global"`
4. 单用户限流：配置项 `config.rate_limit.per_user_qps`（默认 10 QPS），key=`"user:{user_id}"`
5. 限流窗口：配置项 `config.rate_limit.window_seconds`
6. 限流触发（任一级别）→ 返回 `{"code": 1010, "message": "请求过于频繁，请稍后重试"}`

## 错误场景

| 条件 | 错误码 | 说明 |
|------|--------|------|
| 必填字段缺失 | HTTP 422 | Pydantic 拦截，FastAPI 标准错误格式 |
| 字段值不合法 | 1001 | 业务层校验，如 external 非 0/1、score_threshold 超范围 |
| 超过 QPS 限制 | 1010 | 全局或用户级限流触发 |

## 可观测状态

- 零可观测性：redis_store.py 未 import logging，限流触发直接返回错误码 1010 无日志，参数校验失败返回 1001 同样无日志

## 已有测试覆盖

- [cases/old-cases/coupon_service.md] 参数校验与限流
  - 已覆盖：基础必填字段为空校验（user_id/scene_name/device/items）、gRPC 全字段正向校验、用户级限流触发
  - 未覆盖：由新版 validation_ratelimit 用例补齐
- [test_workspace/cases/validation_ratelimit/business.md] 参数校验与限流
  - 已覆盖：基础空值校验（user_id/scene_name/device/items）、HTTP Schema 必填字段校验、gRPC optional 字段缺失/完整字段校验、external 非法值、score_threshold 越界、max_claim_per_request 非法值、HTTP/gRPC 全局限流触发、HTTP/gRPC 用户级限流触发、reqId 为空自动生成
  - 未覆盖：限流窗口过期恢复、限流 Redis 异常、并发/同时间戳限流精度由 boundary.md 覆盖
- [test_workspace/cases/validation_ratelimit/boundary.md] 参数校验与限流边界
  - 已覆盖：限流窗口过期恢复、限流 Redis 异常时接口表现、同时间戳限流精度、HTTP item 子结构 Schema 校验
  - 未覆盖：无（本模块已知未覆盖维度均已生成用例或 mismatch）

## 关联 L2

- [0402](../L2/0402.md) — 新增 max_claim_per_request、score_threshold、external、reqId 请求字段
