# rough_ranking Mismatch 记录

> 生成方式：test-design skill（第二轮，规格与实现对比）
> 关联知识库：L1/rough_ranking
> 生成日期：2026-04-25

---

### MISMATCH-001：filters 中出现非 dict 条件时缺少 warning 日志
- **关联**：L1/rough_ranking
- **知识库描述**：`filters` 中条件非 dict 或操作符未知时，应输出 warning 日志，并让该条件不通过。
- **实际实现**：`CoarseRanker._match_all_filters` 在遇到非 dict 条件时直接 `return False`，不会记录 warning；只有 `_match_filter` 遇到未知操作符时才会记录 `未知过滤操作符` 日志。
- **影响**：功能上该条件仍会导致 item 被过滤，但可观测性低于知识库描述；排查过滤配置错误时，日志信息不完整。
- **建议**：补文档或修代码。若保持现实现状，应把知识库中的“非 dict 条件会输出 warning”改为“该条件不通过，且当前实现无 warning”；若希望维持知识库契约，应在 `_match_all_filters` 中为非 dict 条件补 warning 日志。
