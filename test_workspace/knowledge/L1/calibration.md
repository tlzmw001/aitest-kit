# 校准

对打分结果进行分数校准，由实验开关控制。

## 接口

- HTTP 端点：`POST /api/v1/recommend`（校准是 pipeline 的一环，通过推荐接口间接触发）
- gRPC 端点：`coupon.CouponService/Recommend`
- 请求/响应完整字段定义：[coupon.proto](../../../coupon_system/protos/coupon.proto)、[http_app.py CouponItemRequest/RecommendRequest](../../../coupon_system/http_app.py)
- 请求体必填字段：`user_id`(str)、`scene_name`(str)、`device`(str)、`items`(list, 每项含 `item_id`/`coupon_type`/`value` 必填)、`max_claim_per_request`(int)、`score_threshold`(float)、`external`(int)

## 输入

校准模块在 pipeline 中消费的数据：
- 打分结果（分数列表）— 来自上游 feature_scoring 模块的输出，**测试无法直接控制此值**
- `scene_id` — 由场景路由模块决定
- 校准实验参数 — 由配置和实验开关控制

## 输出

校准后的分数列表（响应中 `results[i].calibrated_score` 字段）。

## 业务规则

### 校准流程

1. 根据 `scene_id` 选取对应的校准实验
2. 先检查校准实验开关是否打开
3. 根据请求字段构成的条件判断命中哪类校准

### 校准条件匹配

4. 校准文件中包含命中校准的条件，由请求字段组成
5. 越靠上的条件优先级越高
6. 可能命中：一类校准、两类都命中、都没命中

### 两类校准方式

7. **第一类（线性校准）**：`y = k * x + b`，根据场景取对应的 k、b
8. **第二类（分段函数校准）**：根据分数落在不同区间，使用不同的 k、b 计算
9. 两类校准文件放在不同的目录

### 校准文件加载

10. 校准实验中配置校准文件的目录路径
11. 每次选取目录中序号最大的文件加载，代表最新版本

### 多重校准叠加

12. 都没命中 → 不校准
13. 命中一类 → 按该类计算
14. 两类都命中 → 先按分段函数算，再按线性校准算

### 实验控制

15. 实验关闭 → 跳过校准

## 错误场景

- 校准文件不存在 → 安全降级，不报错：
  - 目录路径不存在或不是目录 → 返回空规则列表，校准变 no-op
  - 目录存在但 JSON 文件读取/解析失败 → warning 日志 + 返回空列表
  - dir_path 为 None 或空字符串 → 返回空列表
  - 最终效果：分数原样透传（仅 clamp 到 [0, 1]）
- 校准目录为空 → 静默降级，只认 `^\d+\.json$` 格式文件名，无匹配文件则返回 []，无 warning/error（可观测性盲区：目录为空和不存在表现一样且都无日志）
- 校准条件字段缺失 → 规则不匹配，跳过该规则：
  - 字段不在白名单 _MATCHABLE_FIELDS（item_id, coupon_type, device, external, gender, age, total_spend）→ 返回 False
  - 字段在白名单但 match_fields 中无该值 → 返回 False
  - 所有规则都不匹配时，分数原样透传

## 可观测状态

- INFO 日志：每次校准完成后输出 scene_id、linear/piecewise 规则数、item 数
- WARNING 日志：文件读取/解析失败、文件格式错误（非 list）
- 盲区（无日志）：目录不存在或为空、没有规则匹配某 item、实际 k/b 系数值、校准前后分数变化

## 已有测试覆盖

- [cases/old-cases/coupon_service.md] 校准
  - 已覆盖：线性校准 y=kx+b + clamp、分段+线性串联、最新版本文件选取、无效条件字段不匹配
  - 未覆盖：实验关闭跳过校准、校准目录不存在/为空的静默降级（知识库标注的可观测盲区）、校准文件 JSON 解析失败、分段函数区间边界值（恰好在分段点上）、多条件匹配优先级（靠上优先）

## 关联 L2

- [0405](../L2/0405.md) — 校准功能增强：条件匹配、分段函数、版本化文件
