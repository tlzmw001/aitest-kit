---
name: emitter-build
description: 从已验证 pytest、Case IR 和 profile 中识别可沉淀模式，评估是否晋升为 assertion_rules、case_flows、fixture helper 或 emitter 规则
when_to_use: 当 generated pytest 已通过，需要复盘重复模式、减少 case_body/flow 重复，或评估是否值得沉淀为确定性生成规则时
argument-hint: --suite-file <suite.yaml>|--target <target> [--module <module>] [--analyze-promotion|--health-report|--suggest-promotion-patch]
arguments: [suite_file, target, module, analyze_promotion, health_report, suggest_promotion_patch, write_report]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# Emitter 模板构建

`emitter-build` 的职责是把**已经跑通的 AI/人工补写经验**沉淀为确定性模式，减少后续重复写 `case_bodies`、重复 raw assert 或重复 fixture 逻辑。

它不是探索入口，也不是失败修复入口。不要从未验证的 pytest、失败用例、缺环境变量的运行结果，或猜测出的业务语义中提取规则。

默认先分析并输出建议；只有用户明确确认后，才修改 profile、fixture/helper、`aitest.yaml` 或 emitter 代码。`--suggest-promotion-patch` 生成的是 review-only 草案，不自动应用。

## 参考文档

- `refs/patterns.md` — 断言模式表、晋升分类与条件、case_bodies/case_flow 提取规则、IR 对齐项、CLI 命令参考、分类产出规则
- `aitest_config/refs/config-files.md` — 判断配置字段归属时优先读取

## 前提条件

必须先确认当前分析对象满足以下条件：

1. `codegen --check` 或对应 selector 的 `--check` 已通过。
2. generated pytest 至少通过 collect。
3. 从真实断言结果沉淀业务规则时，必须有对应真实 run 通过记录。
4. manual / skipped 用例不能作为业务断言模板来源。
5. 缺环境变量、fixture 错误、服务未启动等结果，不得作为可沉淀模式。

未满足前提时，先返回 test-codegen / test-scaffold / test-fix / test-maintain 处理断裂层。

## 前置：读取输入

### suite 入口

如果用户给出 `--suite-file <suite.yaml>`：

1. 读取 `suite.yaml` 的 `target/module/suite/case_files/knowledge_refs`
2. 按约定路径读取 module profile 和 suite profile
3. 读取 `case_files` 中声明的 Markdown case
4. 读取对应 generated 文件：`test_workspace/generated/{target}/test_{module}_{suite}_{case_file_stem}.py`
5. 运行或读取 `--dump-ir` / `--explain` 输出，确认每条 case 的 `strategy`、`fixtures`、`assertion resolution`

### module / target 入口

如果用户给出 `--target <target> [--module <module>]`：

1. 从 target/module registry 发现 active registered suites
2. 对每个 suite 按 suite 入口逐一分析
3. 3+ suites 时委托子 Agent 逐 suite 分析，主 Agent 聚合跨 suite 模式

## Step 1：Case IR 对齐与分流

以 `CaseIR.strategy` 为主线，不以 generated pytest 中是否存在 `_req()` 为主线。

| strategy | 处理方向 |
|---|---|
| `default_http` / `default_grpc` | 提取 assertion_rules 或默认请求规则 |
| `structured_case_flow` | 对齐 flow，寻找可抽 helper 或更通用 flow 模式 |
| `custom_case_body` | 分析是否保留 body、抽 helper 或晋升 flow |
| `manual` | pure manual 不写 flow；半自动可保留 flow/body |
| `skipped` | 不生成执行逻辑，只记录恢复条件 |
| `UNPARSED` | 待补规则，不直接晋升 |

对每条 case 检查 IR/profile/parser 输出与 generated pytest 是否对齐。对齐项详表见 `refs/patterns.md#IR-对齐项`。

**呈现不阻塞**：展示 strategy 分布和异常对齐项，自动推进；用户有异议可打断。

## Step 2：模式提取与晋升分析

依次执行三类提取，规则细节见 `refs/patterns.md`：

1. **断言模板提取**：逐条断言判断归属层级（通用 → 模块 → suite → fixture/helper）。分类规则见 `refs/patterns.md#断言模式分类`。

2. **case_bodies 提取**：对 `custom_case_body` 策略的 case，确认 body 已验证通过，与 suite profile 对齐，分析 3+ 条结构相似是否可晋升。提取步骤和晋升条件见 `refs/patterns.md#case_bodies-提取规则` 和 `refs/patterns.md#晋升条件`。

3. **case_flow 与 fixture/helper 下沉**：多个 flow 重复认证、资源管理、标准断言等逻辑时，优先下沉到 fixture/helper。循环/分支逻辑本身就是测试主体时，保留 `case_body`。

4. **文件级结构检查**：不要假设所有 generated 文件都有 `BASE_REQUEST`、`_req()`。检查纯 flow/body 文件是否仍生成无用默认 boilerplate，以及 import、class 名、`__tc_meta__` 是否可追踪。文件级模板问题只有跨模块稳定出现时才考虑改 emitter。

## Step 3：分类产出与用户确认

按归属层输出建议。归属从高到低：

1. `aitest.yaml` — 跨模块通用断言规则
2. module profile — 模块级 assertion_rules、defaults
3. suite profile — case_flows、case_bodies、request_overrides、variables.cases
4. fixture/helper — 重复测试动作、复杂断言 helper
5. emitter/renderer — 只有 profile/fixture/helper 无法表达且跨模块稳定时

完整分类规则和晋升分类表见 `refs/patterns.md#晋升分类` 和 `refs/patterns.md#分类产出规则`。

禁止把 TC-ID 绑定内容写入 module profile。晋升 body → flow 时必须同时删除旧 body。

**阻塞**：呈现完整晋升候选表（含保留 case_body 的原因），等用户确认后再修改任何文件。

## Step 4：修改与验证（子 Agent）

用户确认后，按确认的分类修改对应文件。

子 Agent 执行验证序列，产出 pass/fail 摘要表。验证门禁顺序和 CLI 命令见 `refs/patterns.md#验证命令`。

- profile 修改 → `--validate-profile` + `--check` + collect
- fixture/helper 修改 → `compileall` + collect
- 晋升重构 → 允许 generated 结构变化，但必须重新生成后通过 `--check` 和 collect
- 用 `--health-report --write-report` 确认 case_body/UNPARSED 数量下降或不恶化

验证通过 → 输出摘要，emitter-build 完成。
验证失败 → 主 Agent 呈现失败项 + 修复建议，用户确认后修复并重新验证。

## 子 Agent 策略

| 步骤 | 任务 | 输入 | 输出 | 确认方式 |
|------|------|------|------|----------|
| 前置 | 多 suite IR 对齐 + 模式提取 | suite 列表、generated、profiles | 逐 suite 策略分布 + 模式候选 | 呈现不阻塞 |
| Step 4 | 验证闭环 | 修改后的文件、验证命令 | pass/fail 摘要 | 失败时阻塞 |

单 suite 或分析 case < 15 条时主 Agent 直接处理不委托。

## 输出摘要

```
## emitter-build 摘要

输入范围：
- target：{target}
- module：{module 或 all}
- suite：{suite 或 selector}

分析结果：
- 总 case：{total}
- default_http/grpc：{N}
- case_flows：{N}
- case_bodies：{N}
- manual：{N}
- skipped：{N}
- UNPARSED：{N}

晋升候选：
- assertion_rule：{列表或无}
- case_flow：{列表或无}
- helper：{列表或无}
- keep_case_body：{列表和原因或无}

建议修改：
- aitest.yaml：{列表或无}
- module profile：{列表或无}
- suite profile：{列表或无}
- fixture/helper：{列表或无}
- emitter/renderer：{列表或无}

实际修改：
- {文件列表或"无，仅分析"}

验证：
- validate-profile：PASS/FAIL
- check：PASS/FAIL
- collect：PASS/FAIL/未执行
- health-report：{case_body/UNPARSED 是否下降}
```

## 经验反馈

按问题归属沉淀：

- 用例格式问题 → `TEST_SPEC` 或 `aitest_config/refs/case-format.md`
- 配置字段归属问题 → `aitest_config/refs/config-files.md`
- suite 接线 / profile 写法 / fixture 能力问题 → `test-scaffold` 或 `test-codegen` skill
- 模块断言规则 → module profile
- TC-ID 绑定流程 → suite profile
- 生成器缺陷 → `aitest_kit/codegen/*`

如果发现 test-codegen 或 test-scaffold skill 本身规则有缺陷，同步更新对应 skill。
