---
name: emitter-build
description: 从已验证的 pytest .py 提取确定性模板，构建/更新 emitter 规则
when_to_use: 当某模块的 codegen 生成的 pytest 全部通过后，将手写模式固化为确定性模板
argument-hint: <target_module>
arguments: [target_module]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# Emitter 模板构建

从 `$target_module` 模块已验证的 pytest 代码中提取确定性模板，更新 emitter 规则。

## 前提条件

该模块的 codegen 生成的 pytest 必须已全部通过（或 manual/skip 用例已标记）。未通过的模块不应运行此 skill。

## 前置：项目配置检查

首次在新项目中使用 emitter 时：

1. 检查 `aitest_config/project_config.yaml` 是否存在且匹配当前项目
2. 读取本 skill 目录下的 `project_context.md`，了解当前项目的断言模式清单和分类规则
3. 如果 project_config.yaml 不存在，需要先创建

## 前置：读取输入

1. **已验证的 .py** — `test_workspace/tests/generated/test_{module}_business.py` 和 `test_{module}_boundary.py`
2. **parser 输出** — 运行 `python3 -m aitest_kit.codegen.parser` 获取 SharedConfig + TestCase 列表
3. **codegen profile** — `test_workspace/tests/fixtures/codegen_profile_{module}.md`（如果存在）
4. **emitter 现有规则** — `aitest_kit/codegen/emitter.py`（如果已存在）

## 分析流程

### 第一步：逐函数对齐

将每条 test 函数与 parser 输出的 TestCase 一一对齐：

| 对齐项 | parser 输出 | .py 中的代码 |
|--------|-------------|-------------|
| 断言文本 | `TestCase.assertions` | `assert ...` 语句 |
| setup 描述 | `TestCase.scenario_vars` | `# SETUP:` 注释 + fixture 调用 |
| 请求体 | `SharedConfig.base_request_http` + 覆盖 | `_req()` 调用 |
| 标记 | `TestCase.markers` | `@pytest.mark.manual` |

### 第二步：提取断言模板

对每条断言，判断它属于哪种模式，并提取为可复用的模板规则：

**通用模式**（跨模块复用，写入 project_config.yaml 的 builtin_assertion_rules）：

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

项目专属模式的完整清单见 `project_context.md`。

**模块特有模式**（写入 codegen_profile）：

当 .py 中的断言代码无法用通用模式或项目专属模式覆盖时，提取为模块特有规则。

模块特有规则写入 codegen_profile 的 `## emitter 规则` 章节（结构化 YAML code block）：

```yaml
# codegen_profile_{module}.md 中的 emitter 规则段
assertion_rules:
  - pattern: "`cal == round(clamp({k} * s + {b}), 4)`"
    template: |
      assert cal == pytest.approx(max(0, min(1, {k} * s + {b})), abs=1e-4)
    extract_vars:
      - "s = resp[\"results\"][0][\"score\"]"
      - "cal = resp[\"results\"][0][\"calibrated_score\"]"

  - pattern: "按 `s` 所在区间计算"
    template: piecewise_calibration
    params:
      segments_source: "_CASE_CONFIGS[case_id].piecewise"
```

### 第三步：提取文件级模板

从 .py 中提取文件级结构模板：

1. **header** — import 语句（固定）
2. **BASE_REQUEST** — 从 SharedConfig.base_request_http 生成，business 和 boundary 的 item_id 差异来自 codegen_profile
3. **`_req()` helper** — 固定模板，参数为 user_id + req_id + overrides
4. **class 壳** — 类名 = 模块首字母大写 + Business/Boundary
5. **section 注释** — `# ── {section} ──` 来自 TestCase.section

### 第四步：分类产出

根据分析结果分别更新：

**更新 project_config.yaml 的情况**：
- 发现新的通用断言模式（在 2+ 模块出现）→ 添加到 builtin_assertion_rules
- 发现现有通用规则的 bug（生成代码与验证通过的 .py 不一致）→ 修正规则
- 文件级模板有新的通用模式 → 更新模板
- 同步更新 `project_context.md` 的断言模式清单

**更新 codegen_profile 的情况**：
- 发现模块特有断言模式 → 添加到 profile 的 `## emitter 规则` 章节
- 发现模块特有的 BASE_REQUEST 差异 → 更新 profile 的请求模板章节
- 发现新的调试经验 → 更新 profile 的调试经验章节

## 质量检查

更新规则后，验证 emitter 能正确重新生成该模块的 .py：

1. 用 emitter 重新生成 → `test_workspace/tests/generated/test_{module}_*.py`
2. `python3 -c "import ast; ast.parse(open('file').read())"` 验证语法
3. `diff` 对比重新生成的 .py 与原 .py，差异应仅限于空行/注释格式
4. 如果有实质性差异，说明规则提取不完整 → 回到第二步补充

## 输出摘要

```markdown
## emitter-build 摘要

模块：{module}
分析用例数：{N} business + {M} boundary

通用规则变更：
- 新增：{列表}
- 修正：{列表}
- 无变更

模块特有规则：
- 新增到 codegen_profile：{列表}
- 无变更

覆盖率：
- emitter 可覆盖：{X}/{total} 条断言
- UNPARSED：{Y} 条（列出）
- MANUAL/SKIP：{Z} 条

验证：
- AST parse: PASS
- diff vs 原 .py: {PASS / 差异列表}
```

## 经验反馈

如果在提取过程中发现以下问题，记录到 codegen_profile 的调试经验章节：

- parser 输出的断言文本与 .py 代码对不上 → 说明 AI codegen 做了隐式转换，需要固化为规则
- 某个断言模式只在本模块出现但很可能在其他模块也有 → 标记为"待升级为通用规则"
- .py 中有 `# UNPARSED ASSERTION:` 但实际可以模板化 → 说明之前 AI codegen 漏识别了

如果发现 **test-codegen skill 本身的规则有缺陷**（如断言映射表不完整、setup 处理规则有歧义），同步更新 test-codegen SKILL.md。
