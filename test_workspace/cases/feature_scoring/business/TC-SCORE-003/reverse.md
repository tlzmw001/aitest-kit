# TC-SCORE-003 反向解释

> 输入范围：仅 `contract.yaml`
> 目的：帮助人工判断执行契约是否偏离 `review.md` 的业务意图。

## 盲译结果

这条执行契约会创建一个带外部 HTTP 配置的 `ScoringClient`，盐值为 `coupon_external_uid_salt`，然后调用 `score` 方法并传入 `external=1`。调用请求使用明文用户 `u_ext_hash_001`，但契约会观察实际发出的 HTTP payload。

外部 HTTP 响应被固定为成功，并返回 `COUPON_ACT_001 = 0.62`。

该契约实际验证五件事：

- `R1`：发往外部 HTTP 的 payload 中，`request_id` 等于 `req-score-003`。
- `R2`：payload 中的 `user_id` 等于约定的带盐 SHA-256 哈希值 `8e21e887e6d8821c837ee2d8564ea90c756083954b4e7f18a03fbf64cac6b2ab`。
- `R3`：payload 中的 `user_id` 不等于明文 `u_ext_hash_001`。
- `R4`：payload 中不存在 `route` 字段。
- `R5`：最终返回结果是外部 HTTP 响应中的 `COUPON_ACT_001 = 0.62`。

## 复核提示

如果人工评审区期望的是“内部请求明文传递 user_id”“允许 route 下发”“只验证返回结果而不验证请求体”，则本执行契约与业务意图不一致。
