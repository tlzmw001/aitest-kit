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

`emitter-build` 的核心职责是把“已经跑通的 AI/人工补写经验”沉淀为确定性模式；不要从未验证的 pytest、失败用例或猜测出的业务语义中提取规则。

## 前提条件

该模块的 codegen 生成的 pytest 必须已全部通过（或 manual/skip 用例已标记）。未通过的模块不应运行此 skill。

## 前置：项目配置检查

首次在新项目中使用 emitter 时：

1. 检查 `aitest_config/project_config.yaml` 是否存在且匹配当前项目
2. 读取 `aitest_config/project_config.yaml`，了解当前项目的断言规则和模块分类
3. 如果 project_config.yaml 不存在，需要先创建

## 前置：读取输入

1. **已验证的 .py** — `test_workspace/tests/generated/test_{module}_business.py` 和 `test_{module}_boundary.py`
2. **parser 输出** — 运行 `python3 -m aitest_kit.codegen.parser` 获取 SharedConfig + TestCase 列表
3. **Case IR 输出** — 如果仓库已支持 `--dump-ir` / `--explain`，读取每条用例的 strategy、protocol、fixtures、assertion resolution
4. **codegen profile** — `test_workspace/tests/fixtures/codegen_profile_{module}.md`（如果存在）
5. **emitter/renderer 现有规则** — `aitest_kit/codegen/emitter.py`、`aitest_kit/codegen/ir_renderer.py`、`aitest_kit/codegen/render_utils.py`（如果已存在）

如果当前仓库尚未实现 Case IR CLI，仍按 parser/profile/generated pytest 对齐，不因此阻断规则提取。

## 分析流程

### 第一步：逐函数对齐与分流

将每条 test 函数与 parser 输出的 TestCase 一一对齐。若 Case IR 已可用，同时对齐 IR 中的 strategy 和 assertion resolution：

| 对齐项 | parser / IR 输出 | .py 中的代码 |
|--------|------------------|-------------|
| 断言文本 | `TestCase.assertions` / `AssertionIR.source` | `assert ...` 语句 |
| setup 描述 | `TestCase.scenario_vars` / `setup_call` | `# SETUP:` 注释 + fixture 调用 |
| 请求体 | `SharedConfig.base_request_http` + 覆盖 / `RequestIR` | `_req()` 调用 |
| 标记 | `TestCase.markers` / `strategy=manual/skipped` | `@pytest.mark.manual` / `# SKIPPED` |
| 执行策略 | `CaseIR.strategy` | 默认模板、case_body 或 case_flow 函数体 |

**逐函数分流**：对齐时判断每个函数属于哪条路线：

- **标准模板函数**：函数体包含 `_req()` 调用 + 标准断言 → 进入第二步提取断言规则
- **case_bodies 函数**：函数体不包含 `_req()` 调用，或结构完全自定义（多请求、并发、非标准接口等）→ 进入 case_bodies 提取与晋升分析
- **case_flows 函数**：如果 profile 已有 `case_flows` 且 generated pytest 来自结构化 flow → 对齐 flow steps 与生成代码，不退化为 case_body

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

项目专属模式的完整清单见 `aitest_config/project_config.yaml` 的 `builtin_assertion_rules`。

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

### case_bodies 提取与晋升分析（针对非标准模板函数）

第一步中分流为 case_bodies 的函数，无法提取断言规则，改为提取完整函数体写入 profile：

1. **提取函数体**：从 .py 函数中去掉 emitter 自动生成的部分（docstring、`__tc_meta__`、`# SETUP:` 注释），剩余的业务代码即为 case_bodies 内容
2. **提取 fixture 依赖**：从函数签名中提取 fixture 参数列表（去掉 `self`），写入 profile 的 `case_fixtures`
3. **diff 对比**：与 profile 已有的 case_bodies 对比
   - 一致 → 无需更新
   - .py 中有修改（调试修复导致）→ 用验证通过的 .py 版本覆盖 profile 中的旧 case_bodies
   - profile 中无此用例的 case_bodies（首次提取）→ 新增
4. **晋升候选分析**：如果 3+ 个 case_bodies 函数结构相似，在输出摘要中标记候选，由用户决定是否晋升。不自动晋升，不静默改写 profile。

晋升为 `case_flow` 时，必须同时删除对应旧 `case_body`；同一个 case_id 同时存在于 `case_bodies` 和 `case_flows` 会被 codegen 视为 profile 错误。

晋升目标按下表分类：

| 晋升目标 | 适用场景 |
|----------|----------|
| `promote_to_default_template` | 可退回默认模板，只需补 `request_overrides` / `assertion_rules` |
| `promote_to_assertion_rule` | 请求流程标准，只有断言需要模板化 |
| `promote_to_named_template` | 断言需要 if/elif/else 或复杂代码生成 |
| `promote_to_case_flow` | 多步骤流程稳定，差异主要是参数、保存变量和期望值 |
| `promote_to_helper` | 多个 body 重复 Python 逻辑，应下沉 fixture/helper |
| `keep_case_body` | 少见、复杂、并发、进程、mock、文件生命周期等暂不晋升 |

建议晋升必须满足：

1. 至少 3 条已验证通过的 case_body 结构相似。
2. 差异主要是参数、期望值、case_id。
3. 使用 fixture/helper 的公开测试能力。
4. 不依赖复杂循环、分支、线程、进程生命周期或 monkeypatch。
5. 晋升后比原 case_body 更可读、更可解释、更容易校验。

不满足时保留 case_body，并在输出摘要中说明原因。

晋升分析报告和 patch 草案应落到 `test_workspace/reports/codegen/latest/`，不要写入 `test_workspace/plans/`。推荐命令：

```bash
python3 -m aitest_kit.cli codegen $target_module --validate-profile
python3 -m aitest_kit.cli codegen $target_module --validate-profile --write-report
python3 -m aitest_kit.cli codegen $target_module --analyze-promotion --write-report
python3 -m aitest_kit.cli codegen $target_module --suggest-promotion-patch
python3 -m aitest_kit.cli codegen --all --health-report --write-report
```

`promotion_report.md/json` 用于解释和工具消费；`promotion_patch.md/diff` 是 review-only 草案，默认不自动修改 `codegen_profile_{module}.md`。
如果新增或迁移了 `case_flow`，必须先通过 `--validate-profile`，再重新 codegen。普通生成、`--check`、IR explain/dump 和 promotion 分析也会自动执行 profile gate；有 ERROR 时不要绕过门禁。

人工晋升闭环：

1. 先确认对应 generated pytest 已验证通过。
2. 运行 `--analyze-promotion --write-report` 生成候选依据。
3. 运行 `--suggest-promotion-patch` 生成 review-only 草案。
4. 人工修改 profile：新增 `case_flows`，同时删除对应旧 `case_bodies`。
5. 运行 `--validate-profile`、`codegen --check` 和 pytest collect/run。
6. 用 `--health-report --write-report` 确认 case_body/UNPARSED 数量下降。

### case_flow 提取（针对稳定多步骤函数）

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

### 第三步：提取文件级模板

从 .py 中提取文件级结构模板：

1. **header** — import 语句（固定）
2. **BASE_REQUEST** — 从 SharedConfig.base_request_http 生成，business 和 boundary 的 item_id 差异来自 codegen_profile
3. **`_req()` helper** — 固定模板，参数为 user_id + req_id + overrides
4. **class 壳** — 类名 = 模块首字母大写 + Business/Boundary
5. **section 注释** — `# ── {section} ──` 来自 TestCase.section

### 第四步：分类产出

分类判断规则：

- 在 2+ 模块出现的断言模式 → 通用，写入 `project_config.yaml` 的 `builtin_assertion_rules`
- 只在 1 个模块出现的断言模式 → 模块特有，写入该模块的 codegen_profile
- 需要生成 if/elif/else 块的复杂模式 → named_template（Python 实现）
- 简单的"匹配文本 → 替换生成代码" → YAML assertion_rule

根据分析结果分别更新：

**更新 project_config.yaml 的情况**：
- 发现新的通用断言模式（在 2+ 模块出现）→ 添加到 builtin_assertion_rules
- 发现现有通用规则的 bug（生成代码与验证通过的 .py 不一致）→ 修正规则
- 文件级模板有新的通用模式 → 更新模板

**更新 codegen_profile 的情况**：
- 发现模块特有断言模式 → 添加到 profile 的 `## emitter 规则` 章节
- 发现模块特有的 BASE_REQUEST 差异 → 更新 profile 的请求模板章节
- case_bodies 提取或更新 → 写入 profile 的 `case_bodies` 和 `case_fixtures` 段
- case_bodies 晋升为结构化流程 → 写入 profile 的 `case_flows` 段，并在用户确认后移除对应旧 `case_bodies`
- 发现新的调试经验 → 更新 profile 的调试经验章节

## 质量检查

更新规则后，验证 emitter 能正确重新生成该模块的 .py：

1. 用 emitter 重新生成 → `test_workspace/tests/generated/test_{module}_*.py`
2. `python3 -c "import ast; ast.parse(open('file').read())"` 验证语法
3. `diff` 对比重新生成的 .py 与原 .py，差异应仅限于空行/注释格式
4. 如果有实质性差异，说明规则提取不完整 → 回到第二步补充

最终验证标准：

1. `aitest codegen --all --check` 通过（生成结果不变）
2. `pytest test_workspace/tests/generated/ -v` 全部通过
3. emitter.py / ir_renderer.py 行数均 < 500

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

case_bodies：
- 提取/更新：{A} 条
- 首次提取：{B} 条
- 晋升候选：
  - default_template：{列表或"无"}
  - assertion_rule：{列表或"无"}
  - named_template：{列表或"无"}
  - case_flow：{列表或"无"}
  - helper：{列表或"无"}
  - keep_case_body：{列表和原因或"无"}

case_flows：
- 已有对齐：{C} 条
- 新增候选：{D} 条
- 本次实际更新：{E} 条（仅用户确认后）

覆盖率：
- 标准模板覆盖：{X}/{total} 条
- case_bodies 覆盖：{A}/{total} 条
- case_flows 覆盖：{C}/{total} 条
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
