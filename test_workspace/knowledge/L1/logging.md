# 日志

请求级别的日志记录系统。

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
  - 未覆盖：内部打分 route=1 的日志验证、reqId 为空时自动生成 UUID、logging 未配置导致 INFO 日志在生产环境为死代码（知识库标注的风险点）

## 关联 L2

- [0402](../L2/0402.md) — 新增日志系统
