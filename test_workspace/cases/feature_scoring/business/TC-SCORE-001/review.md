# TC-SCORE-001：external=0 时只走内部打分

- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：业务
- **评审状态**：draft

## 业务目标

验证打分请求在明确指定 `external=0` 时，只使用内部打分服务，不访问外部 HTTP 打分服务。

## 前置条件

- 内部打分服务可被观察，并固定返回 1 条分数：`COUPON_ACT_001 = 0.31`
- 外部 HTTP 打分服务可被观察，但本用例中不应收到请求

## 输入数据

| 字段 | 值 |
|------|----|
| request_id | `req-score-001` |
| user_id | `u_internal_route` |
| scene_id | `1001` |
| external | `0` |
| user_features | `{"is_member": "false"}` |
| context_features | `{"channel": "game"}` |
| item_id | `COUPON_ACT_001` |
| item features | `{"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}` |

## 测试步骤

1. 准备一笔使用内部打分路径的优惠券打分请求。
2. 将 `external` 设置为 `0`。
3. 发起打分。
4. 检查返回分数以及实际访问的打分服务。

## 业务预期

- **R1**：请求只访问内部打分服务。
- **R2**：请求不访问外部 HTTP 打分服务。
- **R3**：返回结果来自内部打分服务，包含 `COUPON_ACT_001`，分数为 `0.31`。
