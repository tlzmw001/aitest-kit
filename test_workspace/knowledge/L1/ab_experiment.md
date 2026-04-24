# AB 实验分流

通过 AB 实验 SDK 获取用户在各实验中命中的策略，驱动后续粗排和校准逻辑。

## 输入

- `user_id`：用于 hash 分流
- `scene_id`：确定场景后，查找该场景关联的实验列表
- `external` 标记：是否使用外部打分

## 输出

每个实验的命中结果（策略 ID + 参数），传递给粗排和校准模块。

## 业务规则

1. 通过 SDK（远程模式）调用 AB 实验服务进行评估
2. 确定场景 ID 后，查找该场景映射的实验名列表，只评估这部分实验
3. 分流优先级：白名单 > hash 分流
4. hash 分流：MD5(user_id) % 100，落入策略的 hash_range [low, high) 区间即命中
5. 使用外部打分服务（external=1）时，**不获取任何实验**，避免泄露实验信息
6. SDK 支持两种模式：远程模式（RemoteABExperimentSDK）和本地模式（ConfigBasedABExperimentSDK），接口一致

## 错误场景

- AB 服务不可用（连接失败/HTTP 错误）→ **无降级**，异常直接上抛到 FastAPI 层，返回 HTTP 500（设计缺口：打分服务有降级处理，AB 服务没有）
- 实验名不存在 → 静默跳过，打 warning 日志（`ab_sdk unknown experiment: {name}`），返回结果中不包含该实验的 key，不报错

## 可观测状态

- SDK 响应中的 `trace_id`：服务端生成的追踪 ID
- `hit_reason`：命中原因，"hash" 或 "whitelist"

## 已有测试覆盖

- [cases/old-cases/coupon_service.md] AB 实验分流
  - 已覆盖：正常返回实验信息、白名单强制策略、场景映射只评估关联实验
  - 未覆盖：hash 分流正确性（MD5 % 100）、AB 服务不可用时无降级（知识库标注的设计缺口）、实验名不存在的静默跳过、SDK 远程/本地模式切换

## 关联 L2

- [0404](../L2/0404.md) — AB 实验 SDK 化 + 场景-实验映射
- [0405](../L2/0405.md) — AB 实验服务独立部署
