# 特征抽取与打分

从存储层获取用户和 Item 特征，调用打分服务获取候选券的分数。

## 接口

- HTTP 端点：`POST /api/v1/recommend`（特征抽取与打分是 pipeline 的一环，通过推荐接口间接触发）
- gRPC 端点：`coupon.CouponService/Recommend`
- 请求/响应完整字段定义：[coupon.proto](../../../coupon_system/protos/coupon.proto)、[http_app.py CouponItemRequest/RecommendRequest](../../../coupon_system/http_app.py)

## 输入

- 经粗排筛选后的候选券列表
- `user_id`
- `external` 标记：0=内部打分，1=外部打分

## 输出

每个候选券的打分结果（分数列表）。

## 业务规则

### 特征抽取

1. 用户特征：从 Redis 读取，共 7 个特征字段：gender、age、total_spend、purchase_frequency、register_days、is_new_user、is_member（配置在 YAML，启动时注入 FeatureStore）
2. Item 特征：从 TSV 文件读取，启动时加载到内存

### 打分路由

3. `external=0` → 调用内部打分服务（gRPC），base_score=0.1
4. `external=1` → 调用外部打分服务（HTTP），base_score=0.2
5. 外部打分服务接口使用 HTTP，不支持 gRPC

### 用户 ID 加密

6. 请求外部打分服务时，对 user_id 进行 SHA-256 加盐哈希，格式 `sha256("{salt}:{user_id}")`，salt 可配置（默认 "coupon_external_uid_salt"）；内部 gRPC 打分时 user_id 明文发送

## 错误场景

- 打分服务不可用 → 捕获 TimeoutError / RuntimeError，返回失败枚举（TIMEOUT / UNAVAILABLE）；fallback 未启用则返回 SCORING_ERROR；fallback 启用则按失败类型查 action（on_scoring_timeout / on_scoring_unavailable），action 为 "allow" 时用默认分兜底继续流程，否则返回 SCORING_ERROR
- Redis 特征读取失败 →
  - key 不存在：返回 None，该特征静默省略，不报错
  - Redis 连接异常：无 try/except，异常直接向上抛出，整个请求失败（潜在风险点）
- TSV 文件加载失败 → 安全降级，不抛异常：
  - 文件不存在 → warning 日志 + _item_features 保持空 dict
  - 行格式错误（非 id\tJSON）→ 跳过该行 + warning
  - JSON 解析失败 → 跳过该行 + warning
  - 后果：get_item_features() 对所有 item 返回空 dict，打分时特征缺失，但 pipeline 不中断

## 可观测状态

- Redis 用户特征 Key：按 user_id 存储，逐字段读取
- 日志中 `route` 字段：1=内部服务，2=外部服务
- TSV 加载异常时输出 warning 日志

## 已有测试覆盖

- [cases/old-cases/coupon_service.md] 特征抽取与打分
  - 已覆盖：用户特征读取、Item 特征读取、不存在 Item 返回空、打分超时兜底（allow）、打分不可用兜底（allow）、打分超时 deny 返回错误
  - 未覆盖：Redis 连接异常直接上抛（知识库标注的风险点）、TSV 文件不存在/格式错误的安全降级、外部打分 user_id SHA-256 加密正确性、内部/外部打分 base_score 验证（0.1/0.2）

## 关联 L2

- [0402](../L2/0402.md) — 新增外部打分服务、用户 ID 加密、降低内部 base_score
