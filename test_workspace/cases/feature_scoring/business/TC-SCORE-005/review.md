# TC-SCORE-005：fallback 关闭时打分超时返回打分错误

- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：异常
- **评审状态**：draft

## 业务目标

验证当 fallback 全局关闭且打分服务超时时，推荐发券流程不会继续兜底发券，而是返回打分服务异常错误。

## 前置条件

- 推荐发券业务服务已初始化
- `COUPON_ACT_001` 有库存 `100`
- fallback 全局开关关闭：`fallback.enabled = false`
- 打分服务调用超时

## 输入数据

| 字段 | 值 |
|------|----|
| req_id | `req-score-005` |
| user_id | `u_timeout_disabled` |
| scene_name | `game` |
| device | `mobile` |
| policy_id | 空字符串 |
| external | `0` |
| score_threshold | `0.5` |
| max_claim_per_request | `1` |
| context | `{}` |
| items | `[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}]` |

## 测试步骤

1. 准备推荐发券业务服务和优惠券库存。
2. 关闭 fallback 全局开关。
3. 让打分服务调用发生超时。
4. 发起推荐发券请求。
5. 检查业务返回。

## 业务预期

- **R1**：返回错误码 `1012`。
- **R2**：返回错误消息 `打分服务异常`。
- **R3**：返回 `scene_id = 0`。
- **R4**：返回空实验信息：`experiment_info = {}`。
- **R5**：返回空推荐结果：`results = []`。
- **R6**：不发放优惠券：`coupon = null`。
