# TC-SCORE-005 反向解释

> 输入范围：仅 `contract.yaml`
> 目的：帮助人工判断执行契约是否偏离 `review.md` 的业务意图。

## 盲译结果

这条执行契约会使用推荐发券业务服务，并准备 `COUPON_ACT_001` 的库存为 `100`。执行前会把 `biz.config.fallback.enabled` 设置为 `false`，并让打分客户端在调用 `score` 时抛出 `TimeoutError("timeout")`。

随后契约会调用 `biz.recommend_and_claim`，请求用户为 `u_timeout_disabled`，场景为 `game`，设备为 `mobile`，并传入 1 个优惠券 `COUPON_ACT_001`。

该契约实际验证六件事：

- `R1`：响应 `code` 等于 `1012`。
- `R2`：响应 `message` 等于 `打分服务异常`。
- `R3`：响应 `scene_id` 等于 `0`。
- `R4`：响应 `experiment_info` 为空对象。
- `R5`：响应 `results` 为空列表。
- `R6`：响应 `coupon` 为 `null`。

## 复核提示

如果人工评审区期望 fallback 关闭后仍然发券、返回兜底券、保留实验信息，或不要求校验 coupon 为空，则本执行契约与业务意图不一致。
