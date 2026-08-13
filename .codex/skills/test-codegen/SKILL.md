---
name: test-codegen
description: 从 target-aware suite、task 或 registry selector 生成 pytest，补 suite profile，执行 profile gate、Case IR、freshness 和 collect 验证
when_to_use: 当 Markdown 用例已存在，需要补 suite profile、编译 pytest、检查 generated 是否过期或诊断 IR/UNPARSED 时
argument-hint: --suite-file <suite.yaml>|--task-file <task.yaml>|--target <target> [--module <module>]|--all [--dry-run|--check|--validate-profile|--dump-ir|--explain|--health-report|--analyze-promotion]
arguments: [suite_file, task_file, target, module, all, dry_run, check, validate_profile, dump_ir, explain, health_report, analyze_promotion, write_report, suggest_promotion_patch]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# 测试代码生成

把 Markdown suite 和 profile 编译为 generated pytest。generated 是编译产物，不直接手写。

支持入口：

- `--suite-file`：一个 suite，诊断最完整。
- `--task-file`：任务中声明的一组 suite。
- `--target [--module]`：registry 中 active registered suites。
- `--all`：全部 active suites。

selector 能力矩阵见 `refs/selector_reference.md`。

## Canonical 输入

```text
test_workspace/targets/{target}/
  target.yaml
  helpers/                         # 已证实跨 module 复用时可选
  modules/{module}/
    module.yaml
    profile.md
    fixture.py
    harness.py

test_workspace/suites/{target}/{suite}/
  suite.yaml
  *.md
  profile_{suite}_suite.md
```

Module binding 由 registry 推导：

```text
setup_{module} -> {Module}Harness -> generated variable: harness
```

profile 不选择 fixture/object，也不提供 factory setup。

## 必读参考

- `refs/emitter_rules.md`：固定 Harness binding、请求/断言/flow/body 生成规则。
- `refs/selector_reference.md`：selector 能力和命令。
- `aitest_config/refs/config-files.md`：配置字段归属。

## 编译链

```text
suite context + profiles
  -> profile gate
  -> Markdown parser
  -> Case IR planner
  -> IR renderer
  -> generated pytest
  -> freshness / collect
```

- parser 只解析 Markdown。
- planner 结合配置、profiles 和 ModuleBinding 选择 strategy。
- renderer 确定性生成 pytest。
- AI 负责补 profile/Harness 缺口，不直接修改 generated。

## Step 0：加载上下文

读取：

1. suite manifest 和声明的 Markdown case files。
2. `modules/{module}/module.yaml`：module_type、L1、registered suites。
3. `modules/{module}/profile.md`：稳定 rules/defaults。
4. `modules/{module}/fixture.py` 和 `harness.py`：公开 capability。
5. suite profile（如存在）。
6. target helpers 仅用于理解 Harness 已有 import，不由 suite 直接调用。

target/module registry 不存在或 canonical module package 不完整时，切到 `test-scaffold`，不回退旧目录。

## 知识库读取边界

纯编译不读知识库。以下情况可只读 effective refs：

- 缺 suite profile，需要理解 Markdown 业务意图和字段映射。
- 解释 UNPARSED/skipped/profile gap。
- 检查 Markdown 与知识库冲突。

effective refs = target L0 + module L1 + suite L2。知识库只辅助理解，不能覆盖已 review 的 Markdown 预期，也不能凭空增加断言。读取过的路径写入摘要。

## Step 1：判断能力是否足够

对新增 case 逐条判断：

- 留在 `test-codegen`：已有 Harness capability 足够，只缺参数、请求 patch、断言组合或 suite profile。
- 切到 `test-scaffold incremental`：需要新端点、认证、env、资源准备、cleanup、文件/进程/mock 能力。

一句话：**新增用例表达由 codegen 处理；新增 module 测试能力由 scaffold 处理。**

列出判断结果。有 capability 缺口时先修 Harness，不在 suite profile 用 extra import 绕过。

## Step 2：补 suite profile

Harness 能力足够但 profile 缺失或不完整时：

1. 确认 `suite.yaml` 的 target/module/suite/case_files。
2. 只使用 Harness 已公开方法。
3. 用 `variables.cases` 表达 case 数据/env 差异。
4. 用 `requests.patches` 表达精确请求变化。
5. 用 structured assertions 表达 JSONPath/集合/长度/字段检查。
6. 多步骤用 `case_flow`，根对象固定 `harness`。
7. 测试函数本身必须复杂控制时才保留 `case_body`，也只使用 `harness`。
8. pure manual 不写执行 entry；可行性存疑保持 skipped。

suite profile 禁止 fixture/object/extra imports。module profile 不放 TC-ID 绑定内容。

## Step 3：执行 codegen 门禁

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --explain <TC-ID>
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml>
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --check
```

重点复核：

- structured flow/custom body 的 fixture 是 `setup_{module}`，object 是 `harness`。
- request binding、structured assertion target、profile variables 符合用例。
- 无占位 URL、错误默认值或未知根对象。
- manual/skipped 数量符合预期。

profile gate 有 ERROR 时不进入 IR/emitter。`--check` stale 时重新生成，不修改 generated 让 diff 消失。

## Step 4：处理 UNPARSED

UNPARSED 不是“手改 generated”的许可。对每条回到事实源：

1. Markdown 表达不清：路由 `test-fix`。
2. 可用 structured assertion：写 suite profile。
3. 模块稳定自然语言模式：写 module `assertion_rules`。
4. 需要复杂计算：增加 Harness capability，再由 flow 断言返回值。
5. 必须保留复杂测试函数：写 suite `case_body`。
6. 框架通用能力缺失：修改 codegen 并补回归测试。

修完后重新 codegen，确认 UNPARSED 消失。不要把 generated 作为唯一修复来源。

## Step 5：验证

```bash
python3 -m aitest_kit.cli doctor
python3 -m compileall test_workspace/targets/{target}/modules/{module}
python3 -m compileall test_workspace/generated/{target}
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --check
python3 -m aitest_kit.cli run --suite-file <suite.yaml> -- --collect-only -q
```

已注册 suite 再执行 module selector 验证。真实运行属于 `aitest run`，缺 env 应暴露 `PRECONDITION_MISSING`，不改成 skip。

## 质量要求

1. generated 通过语法和 collect，且 freshness 为最新。
2. 不 import 待测系统内部实现，不硬编码地址或凭证。
3. 不发明 Markdown/知识库没有的断言。
4. 不恢复旧 fixture/profile 路径或 profile 注入字段。
5. 不在 suite profile 绕过 Harness 调任意 helper/import。
6. parser、profile gate、IR、renderer 和 runtime 失败归属清晰。

## 输出摘要

```text
target/module/suite：...
knowledge refs read：...
generated files：...
strategy distribution：default_http / structured_case_flow / custom_case_body / manual / skipped
ModuleBinding：setup_{module} -> harness
UNPARSED：0 或逐条归属
validation：doctor / profile gate / check / compileall / collect
next：真实 run，或返回 scaffold/fix/emitter-build
```
