# rough_ranking 规格偏差记录

> 生成方式：test-design skill
> 关联知识库：L1/rough_ranking
> 生成日期：2026-04-26

---

### MISMATCH-001：接口层空候选列表无法进入粗排空列表分支
- **关联**：L1/rough_ranking
- **知识库描述**：L1 错误场景写明“候选券为空 → 直接返回空列表，不报错，pipeline 继续”。
- **实际实现**：`coupon_system/services/coupon_service.py` 在 pipeline 起点先执行参数校验：`if not user_id or not scene_name or not device or not items`，因此通过 HTTP/gRPC 推荐接口传入 `items=[]` 会直接返回 `code=1001`，不会进入 `CoarseRanker.rank([])`。
- **影响**：黑盒接口用例无法验证粗排模块的“空列表继续”契约；该契约只适用于直接调用粗排组件或上游已保证 items 非空的内部场景。
- **建议**：待产品确认
