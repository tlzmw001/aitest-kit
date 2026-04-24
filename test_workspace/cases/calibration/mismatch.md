# 校准模块 Mismatch 记录

> 生成方式：手动试跑（test-design 第二轮，规格与实现对比）
> 关联知识库：L1/calibration
> 生成日期：2026-04-25

---

### MISMATCH-001：条件匹配存在三级类型转换，知识库未记录
- **关联**：L1/calibration
- **知识库描述**：校准文件中包含命中校准的条件，由请求字段组成（未提及类型转换）
- **实际实现**：`_value_equals` 方法（calibrator.py:229）做了三级类型转换：先直接比较 → 再 bool 转换（1/0/"true"/"false" 互通）→ 再 number 转换 → 最后 str 兜底
- **影响**：条件 `{external: "1"}` 会匹配 external=1 或 external=true，可能导致非预期的规则命中
- **建议**：补文档 — 在 L1/calibration 的业务规则中补充条件匹配的类型转换逻辑

### MISMATCH-002：分段函数区间边界行为未明确
- **关联**：L1/calibration
- **知识库描述**：根据分数落在不同区间，使用不同的 k、b 计算（未说明区间开闭）
- **实际实现**：`_select_segment_coeff`（calibrator.py:187）非末段为左闭右开 `[left, right)`，末段为左闭右闭 `[left, right]`
- **影响**：分段点上的分数归属哪段会影响校准结果，测试和文档需要对齐
- **建议**：补文档 — 在 L1/calibration 中明确区间开闭规则

### MISMATCH-003：规则 k/b 不完整时的行为——跳过但不 fallback
- **关联**：L1/calibration
- **知识库描述**：未提及 k 或 b 缺失时的行为
- **实际实现**：`_select_linear_coeff`（calibrator.py:167）找到匹配规则后，如果 k/b 提取失败返回 None，直接返回 None 而非继续匹配下一条规则
- **影响**：如果排在前面的规则 k/b 格式错误，后面的有效规则不会被使用，分数不校准
- **建议**：待产品确认 — 这是 fail-fast 设计还是应该 fallback 到下一条规则
