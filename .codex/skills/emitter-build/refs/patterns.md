# emitter-build 模式与晋升参考

## 通用断言模式

跨模块复用，写入 `project_config.yaml` 的 `builtin_assertion_rules`。

| 模式 | 匹配正则 | 生成模板 |
|------|----------|----------|
| 状态码 | `` `response.code == {v}` `` | `assert resp["code"] == {v}` |
| 状态码(HTTP) | `` `response.status_code == {v}` `` | `assert resp.status_code == {v}` |
| 完整响应体 | `` `response.body == {var}` `` | `assert resp == {var}` |
| 字段等值 | `` `response.{path} == {v}` `` | `assert resp{["path"]} == {v}` |
| 集合匹配 | `` `set(response.{path}) == {set}` `` | `assert {comprehension} == {set}` |
| 长度 | `` `len({x}) == {n}` `` | `assert len({x}) == {n}` |
| 近似相等 | `` `{x} == round(clamp({expr}), 4)` `` | `assert {x} == pytest.approx(max(0, min(1, {expr})), abs=1e-4)` |
| 恒等 | `` `{x} == {y}` ``（两个变量） | `assert {x} == pytest.approx({y})` |
| manual 标记 | `[manual]` 在 markers 中 | `@pytest.mark.manual` + `# MANUAL CHECK:` |
| 可行性存疑 | `[!可行性存疑` 在 markers 中 | 跳过不生成，末尾 `# SKIPPED:` |
| 无法解析 | 以上都不匹配 | `# UNPARSED ASSERTION: {原文}` |

项目专属模式的完整清单见 `aitest_config/project_config.yaml` 的 `builtin_assertion_rules`。

## 模块特有模式

当 .py 中的断言代码无法用通用模式或项目专属模式覆盖时，提取为模块特有规则。写入 codegen_profile 的 `## emitter 规则` 章节：

```yaml
assertion_rules:
  - pattern: "`field == round(expr, 4)`"
    template: |
      assert field == pytest.approx(expr, abs=1e-4)
    extract_vars:
      - "field = resp[\"results\"][0][\"your_field\"]"

  - pattern: "按某维度分段计算"
    template: your_named_template
    params:
      segments_source: "_CASE_CONFIGS[case_id].segments"
```

## case_bodies 提取规则

第一步分流为 case_bodies 的函数，无法提取断言规则，改为提取完整函数体写入 profile：

1. **提取函数体**：从 .py 函数中去掉 emitter 自动生成的部分（docstring、`__tc_meta__`、`# SETUP:` 注释），剩余的业务代码即为 case_bodies 内容
2. **提取 fixture 依赖**：从函数签名中提取 fixture 参数列表（去掉 `self`），写入 profile 的 `case_fixtures`
3. **diff 对比**：与 profile 已有的 case_bodies 对比
   - 一致 → 无需更新
   - .py 中有修改（调试修复导致）→ 用验证通过的 .py 版本覆盖 profile 中的旧 case_bodies
   - profile 中无此用例的 case_bodies（首次提取）→ 新增
4. **晋升候选分析**：如果 3+ 个 case_bodies 函数结构相似，在输出摘要中标记候选，由用户决定是否晋升。不自动晋升，不静默改写 profile。

晋升为 `case_flow` 时，必须同时删除对应旧 `case_body`；同一个 case_id 同时存在于 `case_bodies` 和 `case_flows` 会被 codegen 视为 profile 错误。

## 晋升分类

| 晋升目标 | 适用场景 |
|----------|----------|
| `promote_to_default_template` | 可退回默认模板，只需补 `request_overrides` / `assertion_rules` |
| `promote_to_assertion_rule` | 请求流程标准，只有断言需要模板化 |
| `promote_to_named_template` | 断言需要 if/elif/else 或复杂代码生成 |
| `promote_to_case_flow` | 多步骤流程稳定，差异主要是参数、保存变量和期望值 |
| `promote_to_helper` | 多个 body 重复 Python 逻辑，应下沉 fixture/helper |
| `keep_case_body` | 少见、复杂、并发、进程、mock、文件生命周期等暂不晋升 |

## 晋升条件

建议晋升必须满足：

1. 至少 3 条已验证通过的 case_body 结构相似。
2. 差异主要是参数、期望值、case_id。
3. 使用 fixture/helper 的公开测试能力。
4. 不依赖复杂循环、分支、线程、进程生命周期或 monkeypatch。
5. 晋升后比原 case_body 更可读、更可解释、更容易校验。

不满足时保留 case_body，并在输出摘要中说明原因。

## 晋升 CLI 命令

```bash
python3 -m aitest_kit.cli codegen $target_module --validate-profile
python3 -m aitest_kit.cli codegen $target_module --validate-profile --write-report
python3 -m aitest_kit.cli codegen $target_module --analyze-promotion --write-report
python3 -m aitest_kit.cli codegen $target_module --suggest-promotion-patch
python3 -m aitest_kit.cli codegen --all --health-report --write-report
```

target/suite 模式使用 `python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml ...` 完成同类验证和分析，generated pytest 默认位于 `test_workspace/generated/{target}/`。

`promotion_report.md/json` 用于解释和工具消费；`promotion_patch.md/diff` 是 review-only 草案，默认不自动修改 profile。

## 人工晋升闭环

1. 先确认对应 generated pytest 已验证通过。
2. 运行 `--analyze-promotion --write-report` 生成候选依据。
3. 运行 `--suggest-promotion-patch` 生成 review-only 草案。
4. 人工修改 profile：新增 `case_flows`，同时删除对应旧 `case_bodies`。
5. 运行 `--validate-profile`、`codegen --check` 和 pytest collect/run。
6. 用 `--health-report --write-report` 确认 case_body/UNPARSED 数量下降。

## case_flow 提取规则

`case_flow` 是 `case_bodies` 的一种晋升目标，适合稳定的 Arrange/Act/Observe/Assert 多步骤流程。第一版只支持：

- 调用 fixture/helper 对象方法。
- `args` / `kwargs` 传入字面量、`ref` 引用或显式 `expr`。
- `save_as` 保存中间变量。
- `assign` 用显式 `expr` 派生中间变量，例如从 raw response 提取 `locs`。
- `assert` 使用可执行 Python 断言，必须以 `assert ` 开头，例如 `assert resp["code"] == 0`。
- `comment` 渲染受控注释，例如 manual check 说明。

不要把以下场景晋升为 case_flow：

- 线程池、子进程、服务生命周期管理。
- 复杂 `for` / `while` / `if` 控制流。
- monkeypatch、mock transport、日志 handler 注入。
- 文件持久化和临时目录生命周期本身就是测试主体。

这些场景继续保留 case_body，或者先抽取 fixture/helper 后再评估。

## 分类产出规则

- 在 2+ 模块出现的断言模式 → 通用，写入 `project_config.yaml` 的 `builtin_assertion_rules`
- 只在 1 个模块出现的断言模式 → 模块特有，写入该模块的 codegen_profile
- 需要生成 if/elif/else 块的复杂模式 → named_template（Python 实现）
- 简单的"匹配文本 → 替换生成代码" → YAML assertion_rule
