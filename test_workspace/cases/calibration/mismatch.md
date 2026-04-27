# calibration 规格偏差记录

> 生成方式：test-design skill
> 关联知识库：L1/calibration
> 生成日期：2026-04-26

---

### MISMATCH-001：校准条件可匹配字段白名单未包含 isPrior
- **关联**：L1/calibration
- **知识库描述**：L1 描述校准文件条件“由请求字段组成”，容易理解为请求 item 字段也可作为条件参与匹配。
- **实际实现**：`coupon_system/services/calibrator.py` 的 `_MATCHABLE_FIELDS` 仅包含 `item_id`、`coupon_type`、`device`、`external`、`gender`、`age`、`total_spend`，不包含请求 item 中的 `isPrior`、`value`、`min_spend`、`expire_days`。
- **影响**：使用 `isPrior`、`value` 等 item 字段配置校准条件时规则永远不匹配，最终分数原样透传，且没有日志提示条件字段被拒绝。
- **建议**：补文档
