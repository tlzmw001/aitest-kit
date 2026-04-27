# issuance Mismatch 记录

> 生成方式：test-design skill（第二轮，规格与实现对比）
> 关联知识库：L1/issuance
> 生成日期：2026-04-25

---

### MISMATCH-001：max_claim_per_request 实际控制尝试范围而非最终发放张数
- **关联**：L1/issuance
- **知识库描述**：`max_claim_per_request` 控制单次请求最多发放的券数量。
- **实际实现**：`CouponBizService._do_claim` 在 [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py#L384) 中只遍历 `recommended[:max_claim_per_request]` 作为尝试范围，但一旦某张券发放成功就立即 `return coupon_data`。接口返回结构也只有单个 `coupon`，不存在一次请求返回多张券的实现。
- **影响**：当前实现下，`max_claim_per_request` 的真实语义是“最多尝试前 N 个推荐候选券”，而不是“最终成功发放 N 张券”。如果继续按知识库原表述设计用例，容易误写成“一次请求会返回多张券”的错误预期。
- **建议**：补文档 — 将 L1/issuance 中该字段说明改为“控制最多尝试发放的候选券数量”；如果产品目标确实是多张券发放，则需要新增返回结构和实现逻辑，属于功能变更而非测试修正。
