# 日志

请求级别的日志记录系统。

## 接口

- HTTP 端点：`POST /api/v1/recommend`（日志模块是 pipeline 的一环，通过推荐接口间接触发）
- gRPC 端点：`coupon.CouponService/Recommend`
- 请求/响应完整字段定义：[coupon.proto](../../../coupon_system/protos/coupon.proto)、[http_app.py CouponItemRequest/RecommendRequest](../../../coupon_system/http_app.py)

## 输入

每次推荐请求的关键信息。

## 输出

INFO 级别日志。

## 业务规则

1. 每次请求到达时打印一条 INFO 日志
2. 日志包含字段：reqId、用户 ID、item 的 ID、route、场景 ID
3. `route` 字段含义：1=内部打分服务，2=外部打分服务
4. route 字段不会下发给打分服务，仅用于日志记录

## 错误场景

- 日志写入失败 → Python logging 内部 handleError 吞掉异常，不影响业务流程，无重试、无自定义 fallback
- 项目未显式配置 logging，main.py 仅设 uvicorn log_level="info"，业务模块 logger 挂在未配置的 root logger 上
- Python 3.2+ lastResort handler 只把 WARNING 及以上写到 stderr，所有 logger.info() 在生产环境是死代码（低于 lastResort 的 WARNING 阈值）

## 可观测状态

- INFO 日志记录

## 已有测试覆盖

- [cases/old-cases/coupon_service.md] 日志（嵌入在外部打分路由用例中）
  - 已覆盖：日志包含 reqId/user_id/item_ids/route/scene_id 关键字段
- [test_workspace/cases/logging/business.md] 日志业务用例
  - 已覆盖：HTTP/gRPC 日志字段完整性、route=1/2、reqId 自动生成、兜底 scene_id、route 不下发给打分服务
- [test_workspace/cases/logging/boundary.md] 日志边界用例
  - 已覆盖：未配置 root logger 导致 INFO 不可见、显式配置 INFO 后可见、handler 写入失败、空 item_ids 专项风险
  - 未覆盖：无（默认日志不可见和空 items 黑盒限制见 mismatch.md）

## 关联 L2

- [0402](../L2/0402.md) — 新增日志系统
