# 发放

选择最高分券并执行发放。

## 接口

- HTTP 端点：`POST /api/v1/recommend`（发放是 pipeline 的最后一环，通过推荐接口间接触发）
- gRPC 端点：`coupon.CouponService/Recommend`
- 请求/响应完整字段定义：[coupon.proto](../../../coupon_system/protos/coupon.proto)、[http_app.py CouponItemRequest/RecommendRequest](../../../coupon_system/http_app.py)
- 辅助接口（用于断言验证）：
  - `GET /api/v1/admin/stock/{coupon_id}` — 查询库存
  - `GET /api/v1/coupons/{user_id}` — 查询用户已领取的券

## 输入

- 校准后的分数列表
- `score_threshold`：分数阈值（由调用方传入）
- `max_claim_per_request`：最大发放数量（由调用方传入）

## 输出

发放结果：scene_id、实验信息、所有 item 打分结果、发放的券信息。

## 业务规则

1. 选择最高分的 item
2. 分数 >= score_threshold → 扣库存 + 记录领取
3. 分数 < score_threshold → 不发放
4. max_claim_per_request 控制单次请求最多发放的券数量

## 错误场景

- 库存不足 → 跳过该券，尝试下一个。Redis DECR 原子扣减，扣到 <0 时立即 INCR 回滚并返回 -1，业务层 continue 到下一个候选券。所有候选券都库存不足时返回 code=0, coupon=None（注意：虽定义了 STOCK_EMPTY=1006 错误码，但实际代码未使用）
- 所有候选券分数低于阈值 → 不发放，返回成功响应（非错误）：code=0, message="success", results 包含所有候选券完整打分信息（每个 recommended: false），coupon=null。调用方需检查 coupon is null 判断未发放

## 可观测状态

- 库存 API：`GET /api/v1/admin/stock/{coupon_id}`
- 用户券查询：`GET /api/v1/coupons/{user_id}`

## 已有测试覆盖

- [cases/old-cases/coupon_service.md] 发放与查询
  - 已覆盖：正常发放、库存扣减、低分不发放、库存为零跳过、多候选取最高分、查询空/有券/无效 user_id
- [test_workspace/cases/issuance/business.md] 发放业务用例
  - 已覆盖：HTTP/gRPC 最高分发放、低分不发放、库存扣减、发放记录查询、未领券查询为空、查询 user_id 为空、过期时间计算、score_threshold、max_claim_per_request
- [test_workspace/cases/issuance/boundary.md] 发放边界用例
  - 已覆盖：库存不足尝试下一张、全库存不足成功空 coupon、并发扣减、重复领取、Redis 写失败、expire_days 默认值、max_claim_per_request 超候选数
  - 未覆盖：无（库存与记录非原子、重复领取策略见 mismatch.md）

## 关联 L2

- [0402](../L2/0402.md) — score_threshold、max_claim_per_request 改为请求传参
