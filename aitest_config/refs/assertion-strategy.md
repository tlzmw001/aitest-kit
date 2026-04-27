# 断言策略

> 本文档定义测试用例中预期结果的三种断言方式。
> 引用方：test-design skill（生成用例时选择断言类型）、codegen（翻译为 pytest 断言代码）

## 三种断言方式

### 1. 结构断言（值可从业务规则直接确定）

写固定值。适用于业务规则明确规定了返回值的场景。

**示例**：
- `response.code == 0`
- `response.scene_id == 3001`
- `response.coupon == null`

### 2. 关系断言（值不可预知但字段间关系已知）

用响应中的其他字段计算。适用于断言值依赖 pipeline 中间产物（如模型打分结果）的场景。

**判断标准**：如果断言值依赖的某个变量不是请求输入而是系统计算结果，就必须用关系断言。

**示例**：
- 校准场景（已知 k 和 b）：`response.results[i].calibrated_score == clamp(k * response.results[i].score + b, 0, 1)`
- 未校准时：`calibrated_score == score`
- 发放最高分券：`response.coupon.item_id == max(response.results, key=lambda r: r.score).item_id`
- 响应只要求包含集合、不要求顺序：`set(response.results[*].item_id) == expected_set`

**典型场景**：校准分数、排序后位次、打分结果

### 3. 不可程序化断言（需要检查日志、监控等无法通过 API 获取的内容）

标注 `[manual]`，写清预期现象，交给人类验证。

**示例**：
- `[manual] 应用日志包含 "calibration skipped"`
- `[manual] Prometheus 指标 coupon_ratelimit_total 计数 +1`

## 禁忌

- 不要为了凑固定值而猜测不可预知的数值（如模型打分结果）
- 不要把"打分服务返回 A=0.8"写成前置条件，除非用例同时写明了可执行的外部测试打分服务/代理构造方式
- 不要把 `response.results[*].item_id` 的顺序当成粗排送入打分服务的顺序；前者只能做响应集合断言，后者必须通过可观察的打分服务入参或日志断言
- 能从响应里读到的值，就用响应字段做关系断言
- pipeline 中间产物（score 等）绝不能用结构断言硬编码固定值（见 TEST_SPEC 陷阱-003）

## codegen 映射参考

| 断言类型 | pytest 代码模式 |
|---------|---------------|
| 结构断言 | `assert resp["code"] == 0` |
| 关系断言 | `assert cal == pytest.approx(max(0, min(1, k * s + b)))` |
| 不可程序化 | `pytest.mark.manual("检查日志包含 xxx")` 或跳过自动化 |
