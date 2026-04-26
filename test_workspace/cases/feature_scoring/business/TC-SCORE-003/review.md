# TC-SCORE-003：外部 HTTP 请求隐藏明文 user_id 且不下发 route

- **关联**：L2/0402
- **优先级**：P1
- **类型**：业务
- **评审状态**：draft

## 业务目标

验证走外部 HTTP 打分时，请求体不会泄露明文 `user_id`，而是使用带盐 SHA-256 哈希值，并且不会向外部服务下发 `route` 字段。

## 前置条件

- 外部打分客户端使用盐值 `coupon_external_uid_salt`
- 外部 HTTP 打分服务返回成功，分数为 `COUPON_ACT_001 = 0.62`
- 外部 HTTP 请求体可被观察

## 输入数据

| 字段 | 值 |
|------|----|
| request_id | `req-score-003` |
| user_id | `u_ext_hash_001` |
| expected hashed user_id | `8e21e887e6d8821c837ee2d8564ea90c756083954b4e7f18a03fbf64cac6b2ab` |
| scene_id | `1001` |
| external | `1` |
| user_features | `{"is_member": "true"}` |
| context_features | `{"channel": "ad"}` |
| item_id | `COUPON_ACT_001` |
| item features | `{"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}` |

## 测试步骤

1. 准备一笔走外部 HTTP 的优惠券打分请求。
2. 发起打分。
3. 检查发往外部 HTTP 服务的请求体。
4. 检查打分响应是否能被正常解析。

## 业务预期

- **R1**：外部 HTTP 请求体中的 `request_id` 保持为 `req-score-003`。
- **R2**：外部 HTTP 请求体中的 `user_id` 是 `sha256("coupon_external_uid_salt:u_ext_hash_001")` 的 64 位十六进制值 `8e21e887e6d8821c837ee2d8564ea90c756083954b4e7f18a03fbf64cac6b2ab`。
- **R3**：外部 HTTP 请求体不包含明文 `user_id`：`u_ext_hash_001`。
- **R4**：外部 HTTP 请求体不包含 `route` 字段。
- **R5**：返回结果正常解析为 1 条分数：`COUPON_ACT_001 = 0.62`。
