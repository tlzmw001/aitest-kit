---
name: emitter-build
description: 从已验证 pytest、Case IR 和 profile 中识别可沉淀模式，评估是否晋升为 assertion_rules、case_flows、fixture helper 或 emitter 规则
when_to_use: 当 generated pytest 已通过，需要复盘重复模式、减少 case_body/flow 重复，或评估是否值得沉淀为确定性生成规则时
argument-hint: <target_module>|--suite-file <suite.yaml>
arguments: [target_module, suite_file]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# Emitter 模板构建

从 `$target_module` 模块或某个 target-aware case suite 的已验证 pytest 代码中识别可沉淀模式，评估是否更新 profile、fixture/helper、`aitest.yaml.codegen` 或 emitter 规则。

`emitter-build` 的核心职责是把"已经跑通的 AI/人工补写经验"沉淀为确定性模式；不要从未验证的 pytest、失败用例或猜测出的业务语义中提取规则。

## 参考文档

断言模式表、晋升分类/条件、case_flow 提取规则和分类产出规则拆分到：
- `refs/patterns.md` — 通用/模块特有断言模式、case_bodies 提取、晋升分类与条件、case_flow 提取、分类产出规则

## 前提条件

该模块或 suite 的 codegen 生成 pytest 必须已全部通过（或 manual/skip 用例已标记）。未通过时不做沉淀，只先定位失败原因。

## 前置：项目配置检查

首次在新项目中使用 emitter 时：

1. 优先检查 `aitest_config/aitest.yaml` 是否存在且包含 `codegen` 配置
2. 读取 `aitest_config/aitest.yaml` 的 `codegen` section，了解当前项目的断言规则和模块分类
3. 如果缺少通用断言规则或 module_type，优先补 `aitest.yaml.codegen` 或 `modules/{module}.yaml`

## 前置：读取输入

1. **已验证的 .py** — 读取 `test_workspace/generated/{target}/test_{module}_{suite}_{case_file_stem}.py`
2. **parser 输出** — 读取 `<suite_dir>/suite.yaml` 声明的 case files
3. **Case IR 输出** — 如果仓库已支持 `--dump-ir` / `--explain`，读取每条用例的 strategy、protocol、fixtures、assertion resolution
4. **codegen profile** — 读取 `test_workspace/targets/{target}/profiles/profile_{module}.md` 和 `<suite_dir>/profile_{suite}_suite.md`
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
- **case_bodies 函数**：函数体不包含 `_req()` 调用，或结构完全自定义 → 进入 case_bodies 提取与晋升分析（参考 `refs/patterns.md#case_bodies-提取规则`）
- **case_flows 函数**：如果 profile 已有 `case_flows` 且 generated pytest 来自结构化 flow → 对齐 flow steps 与生成代码，不退化为 case_body

### 第二步：提取断言模板

对每条断言，判断它属于哪种模式，并提取为可复用的模板规则。通用模式和模块特有模式的完整表格参考 `refs/patterns.md#通用断言模式` 和 `refs/patterns.md#模块特有模式`。

### 第三步：case_bodies 提取与晋升分析

第一步中分流为 case_bodies 的函数，按 `refs/patterns.md#case_bodies-提取规则` 提取函数体并写入 profile。

晋升分类和条件参考 `refs/patterns.md#晋升分类` 和 `refs/patterns.md#晋升条件`。人工晋升闭环参考 `refs/patterns.md#人工晋升闭环`。

如果需要晋升为 case_flow，提取规则参考 `refs/patterns.md#case_flow-提取规则`。

### 第四步：提取文件级模板

从 .py 中提取文件级结构模板：

1. **header** — import 语句（固定）
2. **BASE_REQUEST** — 从 SharedConfig.base_request_http 生成，business 和 boundary 的 item_id 差异来自 codegen_profile
3. **`_req()` helper** — 固定模板，参数为 user_id + req_id + overrides
4. **class 壳** — 类名 = 模块首字母大写 + Business/Boundary
5. **section 注释** — `# ── {section} ──` 来自 TestCase.section

### 第五步：分类产出

分类判断规则参考 `refs/patterns.md#分类产出规则`。

根据分析结果分别更新：

**更新 `aitest.yaml.codegen` 的情况**：
- 发现新的通用断言模式（在 2+ 模块出现）→ 添加到 builtin_assertion_rules
- 发现现有通用规则的 bug（生成代码与验证通过的 .py 不一致）→ 修正规则
- 文件级模板有新的通用模式 → 更新模板

同类变更写回 `aitest_config/aitest.yaml` 或 target/module/suite profile。

**更新 codegen_profile 的情况**：
- 发现模块特有断言模式 → 添加到 profile 的 `## emitter 规则` 章节
- 发现模块特有的 BASE_REQUEST 差异 → 更新 profile 的请求模板章节
- case_bodies 提取或更新 → 写入 profile 的 `case_bodies` 和 `case_fixtures` 段
- case_bodies 晋升为结构化流程 → 写入 profile 的 `case_flows` 段，并在用户确认后移除对应旧 `case_bodies`
- 发现新的调试经验 → 更新 profile 的调试经验章节

## 质量检查

更新规则后，验证 emitter 能正确重新生成该模块的 .py：

1. 用 emitter 重新生成 → 写入 `test_workspace/generated/{target}/test_{module}_{suite}_{case_file_stem}.py`
2. `python3 -c "import ast; ast.parse(open('file').read())"` 验证语法
3. `diff` 对比重新生成的 .py 与原 .py，差异应仅限于空行/注释格式
4. 如果有实质性差异，说明规则提取不完整 → 回到第二步补充

最终验证标准：

1. `aitest codegen --suite-file <suite.yaml> --check` 通过（生成结果不变）
2. target/suite 模式：`aitest codegen --suite-file <suite_dir>/suite.yaml --check` 通过
3. 对应 generated pytest collect 或真实执行通过
4. emitter.py / ir_renderer.py 行数均 < 500

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
