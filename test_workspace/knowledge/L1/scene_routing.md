# 场景路由

根据请求参数确定场景 ID，处理兜底逻辑。

## 接口

- HTTP 端点：`POST /api/v1/recommend`
- gRPC 端点：`coupon.CouponService/Recommend`
- 请求/响应完整字段定义：[coupon.proto](../../../coupon_system/protos/coupon.proto)、[http_app.py CouponItemRequest/RecommendRequest](../../../coupon_system/http_app.py)

## 输入

本模块关注的路由决策字段：
- `scene_name`：场景名
- `device`：设备类型
- `policy_id`：请求传入，默认空字符串；非空且在 `config.fallback_policy_ids` 集合中时命中兜底

透传字段（本模块不消费，但请求体必须包含）：
- `items`：候选券列表，每项必须包含 `item_id`(str)、`coupon_type`(str)、`value`(int, 必填) ；可选字段 `min_spend`(int, 默认0)、`expire_days`(int, 默认7)
- `max_claim_per_request`(int)、`score_threshold`(float)、`external`(int)

## 输出

- `scene_id`：场景 ID，传递给后续粗排、校准等模块
- 或兜底结果（直接返回固定分数）

## 业务规则

1. 如果 `policy_id` 非空且在 fallback 列表中 → 返回兜底分数
2. 兜底分数获取顺序（三级 fallback）：
   - 先查 Redis 场景级兜底分 → 再查 Redis 全局兜底分 → 都没有则使用配置默认值（默认 0.5）
3. 不在 fallback 列表 → 通过 (scene_name, device) 查表得到 scene_id
4. (scene_name, device) 查不到 → 走兜底场景（使用 `config.fallback_scene_id`），标记 `is_fallback=True`，后续跳过实验和打分，直接用兜底分返回
5. 场景与 route 路由隔离：即使 external=1（外部打分），也正常计算场景划分

## 错误场景

- (scene_name, device) 查不到对应 scene_id → 不报错，走兜底场景（注：错误码 1002 SCENE_NOT_FOUND 已定义但未使用）

## 可观测状态

- Redis 兜底分 Key：
  - `coupon:fallback:score:{scene_id}` — 场景级兜底分（优先读取）
  - `coupon:fallback:score:default` — 全局默认兜底分
  - 读取顺序：场景级 → 全局 → 都没有返回 None，由调用方使用配置默认值

## 已有测试覆盖

- [cases/old-cases/coupon_service.md] 场景路由
  - 已覆盖：基本路由映射（game/mobile、ad/pc）、policyId 兜底跳过打分、兜底 user_id 传递、未知场景走兜底、兜底跳过实验评估
- [test_workspace/cases/scene_routing/business.md] 场景路由业务用例
  - 已覆盖：HTTP/gRPC 基础路由、policy_id 兜底、未知场景兜底、external=1 路由隔离、Redis 场景级/全局/配置三级兜底分读取
- [test_workspace/cases/scene_routing/boundary.md] 场景路由边界用例
  - 已覆盖：Redis 兜底分非数字降级、Redis 连接异常行为、policy_id 空字符串边界、scene_name 大小写敏感、路由表空配置、运行中配置不热更新
  - 未覆盖：无（热更新限制见 mismatch.md）

## 关联 L2

- [0402](../L2/0402.md) — 兜底策略改为先读 Redis
