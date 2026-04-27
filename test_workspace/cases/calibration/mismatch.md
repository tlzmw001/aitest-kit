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

### MISMATCH-002：推荐接口无法稳定构造精确 score 分段边界
- **关联**：L1/calibration、boundary.md TC-CAL-020/021
- **知识库描述**：分段校准需要覆盖 `s=0.3` 左边界和 `s=1.0` 右边界闭区间。
- **实际实现**：HTTP/gRPC 推荐接口中的 `score` 来自独立打分服务输出，当前接口没有提供指定 `score` 的测试入口；mock 打分服务还包含随机噪声，无法通过普通请求稳定构造 `s == 0.3` 或 `s == 1.0`。
- **影响**：TC-CAL-020/021 只能通过响应中的实际 `s` 做分段关系断言，不能保证每次都覆盖精确边界值。
- **建议**：若必须自动覆盖精确分段边界，补充组件级校准测试入口，或提供可配置且确定性返回指定 score 的测试打分服务；否则在黑盒接口层保留为可行性存疑场景。
