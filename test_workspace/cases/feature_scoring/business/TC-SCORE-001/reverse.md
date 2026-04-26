# TC-SCORE-001 反向解释

> 输入范围：仅 `contract.yaml`
> 目的：帮助人工判断执行契约是否偏离 `review.md` 的业务意图。

## 盲译结果

这条执行契约会创建一个 `ScoringClient`，然后调用它的 `score` 方法。调用时传入 `external=0`、`request_id=req-score-001`、`user_id=u_internal_route`、`scene_id=1001`，并传入 1 个优惠券 `COUPON_ACT_001`。

执行时，内部 gRPC 打分方法被替换为固定返回 `COUPON_ACT_001` 的 `0.31` 分；外部 HTTP 打分方法只用于观察是否被调用。

该契约实际验证三件事：

- `R1`：内部 gRPC 打分方法会被调用一次，且收到指定请求数据。
- `R2`：外部 HTTP 打分方法不会被调用。
- `R3`：最终返回结果是内部打分方法给出的 `COUPON_ACT_001 = 0.31`。

## 复核提示

如果人工评审区期望的是“走外部 HTTP”“同时尝试内部和外部”“返回值不要求来自内部服务”，则本执行契约与业务意图不一致。
