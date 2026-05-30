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

- `refs/patterns.md` — 通用/模块特有断言模式、case_bodies 提取、晋升分类与条件、case_flow 提取、分类产出规则
- `aitest_config/refs/config-files.md` — target/module/suite/profile/task/env 字段归属。涉及配置字段时必须先读它

## 前提条件

必须先确认当前分析对象满足以下条件：

1. `aitest codegen --suite-file <suite.yaml> --check` 或对应 selector 的 `--check` 已通过。
2. generated pytest 至少通过 collect。
3. 如果要从真实断言结果沉淀业务规则，必须有对应真实 run 通过记录。
4. manual / skipped 用例只能作为“人工确认或不可自动化”信息，不能作为业务断言模板来源。
5. 缺环境变量、测试数据缺失、fixture 错误、服务未启动、上游不可用等结果，不得作为可沉淀模式。

未满足前提时，不做晋升；先返回 test-codegen / test-scaffold / test-fix / test-maintain 处理断裂层。

## 配置归属硬约束

当前项目使用 target-aware suite 结构，profile 路径由约定推导：

- module profile 固定为 `test_workspace/targets/{target}/profiles/profile_{module}.md`
- suite profile 固定为 `{suite_dir}/profile_{suite}_suite.md`
- `module.yaml` 不允许写 `profile`
- `suite.yaml` 不允许写 `profile`

写入归属：

- `aitest_config/aitest.yaml`：跨模块通用 assertion_rules、module_type requires、默认 codegen 配置
- module profile：L1 稳定能力、`module_type`、`default_fixture/default_object/default_case_setup`、模块级 `assertion_rules`、`variables.defaults`
- suite profile：TC-ID 绑定的 `case_flows`、`case_bodies`、`request_overrides`、`case_fixtures`、`variables.cases`
- fixture/helper：多个 suite 或多个 case 重复使用的公开测试动作
- emitter/renderer：跨项目、跨模块稳定且无法靠 profile/fixture 表达的框架级能力

禁止把 TC-ID 绑定内容写入 module profile。禁止为了消除 profile gate 报错而给 pure manual case 写 comment-only `case_flow`。

## 前置：读取输入

### suite 入口

如果用户给出 `--suite-file <suite.yaml>`：

1. 读取 `suite.yaml` 的 `target/module/suite/case_files/knowledge_refs`
2. 按约定路径读取 module profile 和 suite profile
3. 读取 `case_files` 中声明的 Markdown case
4. 读取对应 generated 文件：`test_workspace/generated/{target}/test_{module}_{suite}_{case_file_stem}.py`
5. 运行或读取 `--dump-ir` / `--explain` 输出，确认每条 case 的 `strategy`、`fixtures`、`assertion resolution`

### module / target 入口

如果用户给出 `--target <target> --module <module>`：

1. 读取 `test_workspace/targets/{target}/target.yaml`
2. 读取 `test_workspace/targets/{target}/modules/{module}.yaml`
3. 从 `registered_suites` 中发现 active suites
4. 对每个 suite 按 suite 入口逐一分析

如果用户只给出 `--target <target>`，先遍历该 target 下所有 module 的 active registered suites，再逐 suite 分析。

## 分析流程

### 第一步：Case IR 对齐与分流

以 `CaseIR.strategy` 为主线，不以 generated pytest 中是否存在 `_req()` 为主线。

| strategy | 主要检查 | 处理方向 |
|---|---|---|
| `default_http` / `default_grpc` | 默认请求、request_overrides、断言解析 | 提取 assertion_rules 或默认请求规则 |
| `structured_case_flow` | `profile.case_flows.{tc_id}.steps` 与 generated 代码是否一致 | 对齐 flow，寻找可抽 helper 或更通用 flow 模式 |
| `custom_case_body` | `profile.case_bodies.{tc_id}` 与 generated 函数体是否一致 | 分析是否保留 body、抽 helper 或晋升 flow |
| `manual` | pure manual 还是半自动 manual | pure manual 不写 flow；半自动可保留 flow/body |
| `skipped` | 是否来自 `[!可行性存疑]` 或显式 skip | 不生成执行逻辑，只记录恢复条件 |
| `UNPARSED` | 哪条断言未解析、是否能模板化 | 作为待补规则，不直接晋升 |

对齐项：

| 对齐项 | IR/profile/parser 输出 | generated pytest |
|---|---|---|
| case identity | `case_id/module/suite/source_file` | `__tc_meta__` |
| 断言文本 | `TestCase.assertions` / `AssertionIR.source` | `assert ...` / manual check / UNPARSED 注释 |
| 执行策略 | `CaseIR.strategy` | 默认模板、case_flow、case_body、manual skip |
| fixture | `CaseIR.fixtures` / profile defaults | 函数参数、fixture import、对象创建 |
| flow steps | `case_flows.{tc_id}.steps` | call / assign / assert / comment 代码 |
| skipped | `__codegen_skipped__` / strategy skipped | 未生成 test 函数或显式 skip |

### 第二步：提取断言模板

对每条断言判断是否适合沉淀：

- 在 2+ 模块出现，且语义与项目无关 → 写入 `aitest_config/aitest.yaml.codegen.builtin_assertion_rules`
- 只在当前 module 出现，且是 L1 稳定能力 → 写入 module profile 的 `assertion_rules`
- 只服务当前 suite / 当前 TC-ID → 写入 suite profile 的 `case_flows` 或 `case_bodies`
- 断言需要循环、分支或复杂遍历 → 优先抽 fixture/helper 方法，再由 `case_flow` 调用；不要直接把复杂控制流塞进 case_flow

不要把具体 TC-ID 的断言流程写入 module profile。

### 第三步：case_bodies 提取与晋升分析

对 `custom_case_body`：

1. 确认该 body 对应的 pytest 已验证通过。
2. 与 suite profile 中现有 `case_bodies` 对齐。
3. 如果 body 只是临时修复 generated，应回写 suite profile 后重新 codegen。
4. 如果 3+ 条 body 结构相似，按 `refs/patterns.md#晋升分类` 输出候选。
5. 晋升为 `case_flow` 时，必须在同一次 profile 修改中删除同 case_id 的旧 `case_body`。

保留 `case_body` 的合理场景包括：线程/进程生命周期、复杂 if/for/while、mock/monkeypatch、日志 handler 注入、文件生命周期本身就是测试主体、难以抽成公开 fixture/helper 的一次性复杂流程。

### 第四步：case_flow 与 fixture/helper 下沉

`case_flow` 适合表达稳定的 Arrange / Act / Observe / Assert 流程。

如果多个 flow 重复以下内容，优先下沉到 fixture/helper：

- 认证、登录、token 刷新
- 创建/删除测试资源
- 固定查询 + 标准 not found 断言
- 响应列表遍历断言，例如“每条记录 publishStatus == 0”
- 多字段业务断言块

下沉后，suite profile 保留简洁步骤：

```yaml
case_flows:
  TC-XXX-001:
    fixture: setup_xxx
    object: client
    steps:
      - call: client.query_items
        save_as: resp
      - call: client.assert_all_publish_status
        args:
          - {ref: resp}
          - 0
```

如果循环/分支逻辑本身就是测试主体，保留 `case_body`，不要强行 flow 化。

### 第五步：文件级结构检查

不要假设所有 generated 文件都有 `BASE_REQUEST`、`_req()`、business/boundary 类名。

当前生成文件名为：

```text
test_workspace/generated/{target}/test_{module}_{suite}_{case_file_stem}.py
```

检查重点：

- 纯 `structured_case_flow` / `custom_case_body` 文件是否仍生成无用默认 HTTP boilerplate
- default_http/default_grpc case 是否仍需要 `_req()` 和默认请求模板
- generated import 是否来自 target/module fixture 自动注入
- class 名、section 注释、`__tc_meta__` 是否可读且可追踪
- manual/skipped/UNPARSED 是否在 report 和 health-report 中可解释

文件级模板问题只有跨模块稳定出现时才考虑改 `ir_renderer.py` / `emitter.py`。

### 第六步：分类产出

按归属输出建议和修改：

1. `aitest_config/aitest.yaml`
   - 跨模块通用断言规则
   - module_type requires
   - 默认 codegen 配置
2. module profile
   - 模块级 assertion_rules
   - default_fixture/default_object/default_case_setup
   - variables.defaults
3. suite profile
   - case_flows
   - case_bodies
   - request_overrides
   - case_fixtures
   - variables.cases
4. fixture/helper
   - 重复测试动作
   - 复杂循环/分支断言 helper
   - 资源准备与 cleanup
5. emitter/renderer
   - 只有 profile/fixture/helper 无法表达，且跨模块稳定时才改

## 质量检查

修改后按范围验证。

suite 级：

```bash
aitest codegen --suite-file <suite.yaml> --validate-profile
aitest codegen --suite-file <suite.yaml> --dump-ir
aitest codegen --suite-file <suite.yaml> --check
aitest run --suite-file <suite.yaml> -- --collect-only -q
aitest codegen --suite-file <suite.yaml> --health-report --write-report
```

module / target 聚合：

```bash
aitest codegen --target <target> --module <module> --analyze-promotion --write-report
aitest codegen --target <target> --module <module> --health-report --write-report
aitest codegen --target <target> --module <module> --check

aitest codegen --target <target> --analyze-promotion --write-report
aitest codegen --target <target> --health-report --write-report
aitest codegen --target <target> --check
```

如果只是把已验证 generated 回灌到 profile，`--check` 应无差异。如果做了晋升重构，允许 generated 结构变化，但必须重新生成后稳定，并通过 collect；有环境时再做真实 run。

## 输出摘要

```markdown
## emitter-build 摘要

输入范围：
- target：{target}
- module：{module 或 all}
- suite：{suite 或 selector}
- case_files：{列表}

读取文件：
- generated：{列表}
- module profile：{path}
- suite profile：{列表}

分析结果：
- 总 case：{total}
- default_http/grpc：{N}
- case_flows：{N}
- case_bodies：{N}
- manual：{N}
- skipped：{N}
- UNPARSED：{N}

建议修改：
- aitest.yaml：{列表或无}
- module profile：{列表或无}
- suite profile：{列表或无}
- fixture/helper：{列表或无}
- emitter/renderer：{列表或无}

case_bodies 晋升候选：
- case_flow：{列表或无}
- helper：{列表或无}
- assertion_rule：{列表或无}
- keep_case_body：{列表和原因或无}

实际修改：
- {文件列表或“无，仅分析”}

验证：
- validate-profile：PASS/FAIL
- dump-ir/explain：PASS/FAIL
- check：PASS/FAIL
- collect/run：PASS/FAIL/未执行，原因
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
- 迁移经验 → migration guide / usebook

如果发现 test-codegen 或 test-scaffold skill 本身规则有缺陷，同步更新对应 skill；不要只在当前 profile 里写经验导致下次继续踩坑。
