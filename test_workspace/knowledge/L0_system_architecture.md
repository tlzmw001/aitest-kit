# 系统架构索引

## 系统概述

智能优惠券推荐策略系统 v3：根据用户特征和场景，对候选优惠券进行打分排序，选择最优券发放给用户。支持 HTTP 和 gRPC 双协议。

## 服务拓扑

```
客户端 → 主服务（HTTP/gRPC）→ 打分服务（gRPC 内部 / HTTP 外部）
                ↓
          AB 实验服务（HTTP，独立部署，端口 8100）
                ↓
            Redis（用户特征、兜底分）
```

## Pipeline 阶段概览

```
请求 → 参数校验 → 限流 → 场景路由 → 兜底判断
  → AB实验分流(按scene_id映射实验) → 粗排(实验控制) → 特征抽取
  → 打分(内部gRPC/外部HTTP) → 校准(实验控制) → 发放最优券 → 返回结果
```

## 接口契约

- 主服务接口（HTTP + gRPC）：[coupon_system/protos/coupon.proto](../../coupon_system/protos/coupon.proto)
- 打分服务接口（gRPC）：[coupon_system/protos/scoring.proto](../../coupon_system/protos/scoring.proto)

## 模块索引

| 模块 | 说明 | L1 | 相关 L2 |
|------|------|----|---------|
| 参数校验与限流 | 必填校验 + QPS 限流 | [L1/validation_ratelimit.md](L1/validation_ratelimit.md) | — |
| AB实验分流 | 通过 SDK 获取实验策略 | [L1/ab_experiment.md](L1/ab_experiment.md) | [0404](L2/0404.md), [0405](L2/0405.md) |
| 场景路由 | 场景映射 + 兜底策略 | [L1/scene_routing.md](L1/scene_routing.md) | [0402](L2/0402.md) |
| 粗排 | 候选券筛选与排序 | [L1/rough_ranking.md](L1/rough_ranking.md) | [0404](L2/0404.md) |
| 特征抽取与打分 | 用户/Item 特征 + 打分服务 | [L1/feature_scoring.md](L1/feature_scoring.md) | [0402](L2/0402.md) |
| 校准 | 分数校准 | [L1/calibration.md](L1/calibration.md) | [0405](L2/0405.md) |
| 发放 | 最优券选择与库存扣减 | [L1/issuance.md](L1/issuance.md) | [0402](L2/0402.md) |
| AB实验服务 | 独立部署的实验管理与分流服务 | [L1/ab_service.md](L1/ab_service.md) | [0405](L2/0405.md) |
| 日志 | 请求日志记录 | [L1/logging.md](L1/logging.md) | [0402](L2/0402.md) |

## 已有测试覆盖

- 端到端 pipeline 用例：**无**
  - 现有用例全部为模块级单测（mock 外部依赖），无真正的端到端链路验证
  - 缺失：一个请求经过完整 pipeline（校验→限流→AB实验→场景路由→粗排→特征→打分→校准→发放）的集成测试
  - 缺失：主服务 + AB 实验服务 + Redis 联合启动的跨服务集成测试
  - 缺失：HTTP 和 gRPC 双协议的对比验证（同一请求通过两种协议结果一致）
