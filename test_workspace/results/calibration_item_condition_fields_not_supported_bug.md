# calibration item 字段无法作为校准条件的问题记录

## 背景

`calibration` 边界用例中曾包含 `TC-CAL-024：布尔条件支持字符串和布尔等值匹配`，前置规则为：

```text
conditions={"isPrior":"true"}, k=2, b=0
```

测试意图是验证请求 item 中的布尔字段 `isPrior=true` 可以作为校准条件参与匹配。

## 当前结论

当前待测系统不支持 item 字段作为校准条件。校准条件匹配白名单只包含：

```text
item_id, coupon_type, device, external, gender, age, total_spend
```

不包含：

```text
isPrior, value, min_spend, expire_days
```

因此 `conditions={"isPrior":"true"}` 不会命中规则，最终表现为校准不生效，`cal == s`。

## 影响

- 无法通过配置 `isPrior`、`value`、`min_spend`、`expire_days` 等 item 字段实现更细粒度的校准条件。
- 如果测试用例把当前 `cal == s` 行为作为正常断言，会把“item 字段不支持校准条件”固化为预期行为。
- 这与期望的产品能力不一致：后续希望校准条件可以包含 item 字段。

## 测试侧处理

`TC-CAL-024` 已从 `test_workspace/cases/calibration/boundary.md` 的正常自动化用例中移除，不再作为当前通过项生成。

现有规格偏差保留在：

```text
test_workspace/cases/calibration/mismatch.md
```

对应条目：

```text
MISMATCH-001：校准条件可匹配字段白名单未包含 isPrior
```

## 后续需求建议

建议待测系统补充 item 字段参与校准条件匹配的能力，至少覆盖：

- `isPrior`
- `value`
- `min_spend`
- `expire_days`

修复后再恢复或新增正向自动化用例，期望断言应类似：

```text
conditions={"isPrior":"true"}, k=2, b=0
请求 item 包含 isPrior=true
cal == round(clamp(2 * s), 4)
```

在待测系统支持该能力前，不应通过放宽断言或保留 `cal == s` 来让这条能力验证“通过”。
