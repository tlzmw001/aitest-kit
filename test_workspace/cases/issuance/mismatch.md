# issuance 规格偏差记录

> 生成方式：test-design skill
> 关联知识库：L1/issuance
> 生成日期：2026-04-26

---

### MISMATCH-001：发放库存扣减与领取记录保存不是原子事务
- **关联**：L1/issuance
- **知识库描述**：L1 描述发放为“扣库存 + 记录领取”，但未定义两步之间的失败处理和一致性保障。
- **实际实现**：`coupon_system/services/coupon_service.py` 中 `_do_claim()` 先调用 `redis.decr_stock()` 扣减库存，再依次调用 `record_claim()`、`save_coupon_instance()`、`add_user_coupon()` 保存记录；这些 Redis 写操作之间没有事务包裹，保存记录失败时没有回滚库存。
- **影响**：Redis 在扣库存后、保存实例前异常时，可能出现库存减少但用户券记录缺失的不一致状态。
- **建议**：修代码

### MISMATCH-002：未使用已领取检查，允许同一用户重复领取同一券
- **关联**：L1/issuance
- **知识库描述**：L1 只定义“选择最高分券并执行发放”，未说明同一用户是否允许重复领取同一 coupon item。
- **实际实现**：`RedisStore` 提供 `has_claimed()`，但 `_do_claim()` 发放前未调用；同一用户重复请求同一 item 且库存充足时会生成多个实例。
- **影响**：如果业务要求同一用户同一券只能领取一次，当前实现会违反发放约束；如果允许重复领取，则需在文档中明确。
- **建议**：待产品确认
