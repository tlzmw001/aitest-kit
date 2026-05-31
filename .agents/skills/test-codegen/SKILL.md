---
name: test-codegen
description: 从 target-aware case suite、task manifest 或 target/module/all selector 生成 pytest，执行 profile gate、Case IR、freshness check，并处理少量 UNPARSED 补写
when_to_use: 当用户需要将 Markdown 测试用例编译为 pytest、检查 generated 是否过期，或针对 suite/task/module/target/all 维度执行 codegen 时
argument-hint: --suite-file <suite.yaml>|--task-file <task.yaml>|--target <target> [--module <module>]|--all [--dry-run|--check|--validate-profile|--dump-ir|--explain|--health-report|--analyze-promotion]
arguments: [suite_file, task_file, target, module, all, dry_run, check, validate_profile, dump_ir, explain, health_report, analyze_promotion, write_report, suggest_promotion_patch]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# 测试代码生成

将 Markdown case suite、task manifest 或 registry selector 编译为 pytest 代码。

codegen 支持四类入口：

- `--suite-file <suite.yaml>`：精确处理一个 suite，诊断能力最完整。
- `--task-file <task.yaml>`：处理 task manifest 中声明的一组 suite。
- `--target <target> [--module <module>]`：从 registry 发现 active registered suites。
- `--all`：发现全部 active suites。

`--case-id` 不是 codegen 入口，属于 `aitest run/report`。各入口的诊断命令支持矩阵见 `refs/selector_reference.md`。

主路径是 target-aware suite 结构：

```text
test_workspace/targets/{target}/
  target.yaml, modules/{module}.yaml, fixtures/{module}.py, helpers/, profiles/profile_{module}.md

test_workspace/suites/{target}/{suite}/
  suite.yaml, profile_{suite}_suite.md, *.md

test_workspace/generated/{target}/
```

## 参考文档

- `refs/emitter_rules.md` — 文件结构、命名、setup、断言生成、请求生成、case_body/flow 规则、标记处理、profile 编写指南
- `refs/selector_reference.md` — selector 能力矩阵、常用命令、聚合执行规则、能力缺口判定表
- `aitest_config/refs/config-files.md` — 判断配置字段归属时优先读取

## 生成策略

采用 **emitter 优先 + AI 补全** 模式。生成链路 `parser -> Case IR planner -> emitter/IR renderer -> pytest`：

1. parser 把 Markdown 转为 `ParseResult`，不读 profile、不判断协议/策略。
2. Case IR planner 结合 `ParseResult`、`aitest.yaml` 和 runtime profile 生成可解释的生成计划。
3. emitter 负责装载、诊断和落盘，IR renderer 确定性生成 .py。
4. AI 只处理 emitter 输出的 `# UNPARSED ASSERTION:` 部分。
5. `@pytest.mark.manual` 和 `# SKIPPED` 用例不需要 AI 补写。

## 新项目首次接入

如果 target/module profile 和 suite profile 都不存在，说明是新项目首次接入：

1. 检查 `aitest_config/aitest.yaml` 是否包含 `workspace`、`codegen` 配置。
2. profile 使用 Markdown 内 YAML；结构契约由 `codegen_profile.schema.json` 校验，再叠加语义校验。
3. 首个模块 UNPARSED / case_body 比例可能较高，选断言模式最典型的模块先做。
4. IR 或 generated 中出现 `/api/v1/replace-me`、示例 helper 时，说明配置未适配。

新项目允许 AI 先手写 pytest 探索 API 行为，但必须回到 codegen 链路：

```text
Markdown → AI 探索（可选）→ 回灌 fixture + profile → case_flows/case_bodies → codegen → --check 通过
```

交付要求：

1. `fixtures/{module}.py` 存在，只通过公开 API 准备测试条件。
2. `profiles/profile_{module}.md` 存在，`--validate-profile` 无 ERROR。
3. 手写探索逻辑必须迁入 `case_flows` 或 `case_bodies`；generated 不能作为唯一源头。
4. `--dump-ir` 不得出现占位路径或错误默认值。
5. `codegen --check` 必须通过。

路线选择：稳定多步骤 → `case_flows`；复杂控制流/mock/并发 → `case_bodies`；同类 `case_bodies` 重复出现后 → `/emitter-build` 评估晋升。用户贴出失败现象时，先修回灌链路，不要继续堆叠手写 generated。

## 前置：加载上下文

读取 `suite.yaml`，根据其中的 `target/module` 加载：

- `modules/{module}.yaml` — module registry（fixture 声明、module_type）
- `fixtures/{module}.py` — fixture 方法签名
- `helpers/` — 可用 helper
- `profiles/profile_{module}.md` — module profile
- `<suite_dir>/profile_{suite}_suite.md` — suite profile（如已存在）

如果 profile 存在，emitter 自动加载其 YAML 规则段。如果不存在：

1. 参考其他模块 profile 的结构，不复制特有逻辑。
2. 新模块至少声明 `module_type`、fixture 引用和必要的 `case_flows/case_bodies`。
3. 生成摘要中提示 profile 成熟度。

target/suite 规则：

1. module profile 放 L1 稳定能力；suite profile 放 `variables/case_flows/case_bodies/request_overrides`。
2. `suite.yaml` 只放 `target/module/suite/case_files/knowledge_refs`。
3. 生成文件名：`test_{module}_{suite}_{case_file_stem}.py`，输出到 `test_workspace/generated/{target}/`。
4. target registry 不存在时，切到 `test-scaffold`，不回退旧路径。

如果 `$dry_run` 为 true，只输出可生成/不可生成用例列表，不生成代码。

## Step 1：能力缺口判断（新增 case 时）

现有模块新增 Markdown 用例时，先判断 fixture 能力是否足够。

读取新增 Markdown、suite manifest、module registry、module fixture 和现有 profile，逐条 case 判定：

- **留在 test-codegen**：只缺 suite.yaml/profile、只需新增参数/断言组合、只用已有 client 方法
- **切到 test-scaffold incremental**：需要新端点、新认证方式、新 env、setup/cleanup 能力、文件上传/WebSocket/mock 等

简化判断：**只是新增用例表达 → test-codegen；需要新增测试调用能力 → test-scaffold incremental。** 详细判定表见 `refs/selector_reference.md#能力缺口判定表`。

**用户确认**：列出每条新 case 的判定结果。有任何一条需要切 scaffold 时，阻塞等用户确认处理顺序。

### suite profile 补齐

fixture 能力足够但缺 suite profile 时，做最小补齐：

1. 创建 `<suite_dir>/suite.yaml`。
2. 读取 module fixture 的 client 方法签名，只使用已存在的方法。
3. 逐条 case 选择 `variables`、`case_flow`、`request_overrides`、`skipped/manual`。
4. 纯人工 `[manual]` 不写 profile entry；半自动 manual 写 `case_flow/case_body` 保留 manual marker。
5. 可行性存疑保持 skipped，不为覆盖率强行写可执行 flow。
6. 生成 `profile_{suite}_suite.md` 后立即跑 suite 级 profile gate 和 dump-ir。

**呈现不阻塞**：展示 profile 关键内容（variables + case_flows 路线分布），自动推进；用户有异议可打断。

## Step 2：codegen 生成

推荐门禁顺序：

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --check
```

profile 硬门禁有 ERROR 时不进入 IR/emitter，先修 profile。`profile not found`、占位路径、`--check stale` 都是回灌未完成信号。

Case IR strategy 覆盖：`default_http`、`default_grpc`、`custom_case_body`、`structured_case_flow`、`manual`、`skipped`。CLI 支持 `--dump-ir`/`--explain` 时优先用它们排查。

检查输出摘要中的 UNPARSED 数量，确认每条 case 的 strategy/protocol/fixtures 与预期一致。

## Step 3：UNPARSED 补写（子 Agent，>5 条时）

读取 generated .py，找到所有 `# UNPARSED ASSERTION:` 注释。UNPARSED 为 0 时跳过。

对每条 UNPARSED 断言：

1. 读取对应 TestCase 完整上下文（scenario_vars、assertions、markers）
2. 参考 profile 断言模式表和 `refs/emitter_rules.md#断言生成` 映射
3. 替换为可执行 pytest 断言；无法翻译的保留 `# UNPARSED ASSERTION:`

UNPARSED > 5 条时委托子 Agent 批量处理：

- 子 Agent 输入：generated .py、profile 断言模式、emitter 规则映射
- 子 Agent 产出：已补写的 .py（或 diff 列表）
- UNPARSED ≤ 5 条时主 Agent 直接处理

**呈现不阻塞**：展示补写结果，自动推进到验证；用户有异议可打断修改。

## Step 4：验证（子 Agent）

子 Agent 执行验证序列，产出 pass/fail 摘要表：

```bash
python3 -m compileall test_workspace/targets/{target}/fixtures/{module}.py test_workspace/generated/{target}
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --check
python3 -m aitest_kit.cli run --suite-file <suite_dir>/suite.yaml -- --collect-only -q
```

已注册 suite 追加 module/target selector 验证，详见 `refs/selector_reference.md#selector-级验证命令`。

验证通过 → 输出摘要，codegen 完成。
验证失败 → 主 Agent 呈现失败项 + 修复建议，用户确认后修复并重新验证。

## 子 Agent 策略

| 步骤 | 任务 | 输入 | 输出 | 确认方式 |
|------|------|------|------|----------|
| Step 3 | UNPARSED 补写 | generated .py、profile、emitter 规则 | 补写后 .py | 呈现不阻塞 |
| Step 4 | 验证闭环 | 生成产物、验证命令 | pass/fail 摘要 | 失败时阻塞 |

UNPARSED ≤ 5 条或验证命令 < 3 条时主 Agent 可直接处理不委托。

## 质量要求

1. 生成代码通过 `ast.parse`，每个 test 函数独立
2. 不 import 待测服务内部模块，不硬编码端口
3. 不发明用例中没有的断言
4. parser/IR/emitter 错误边界清晰：Markdown 问题归 parser，策略问题归 IR，渲染问题归 emitter
5. 新模块交付态不得停留在手写 generated；必须有 profile 回灌并通过 `--check`
6. 可执行 API 测试的服务地址缺失应失败暴露，不能 skip

## 输出

```
## codegen 摘要

模块：{module}
生成文件：
- suite 模式：test_{module}_{suite}_{case_file_stem}.py — N 条（emitter X 条，AI 补写 Y 条）

跳过（可行性存疑）：
- TC-XXX：原因

仍未解析：
- TC-XXX：断言原文

TODO：
- （fixture 不存在时）setup_{module} fixture 需要补齐
- （有 gRPC 用例时）gRPC helper 需要补充
- （无 profile 时）需要补齐 profile，并将探索逻辑迁入 case_bodies/case_flows
- （generated stale 时）先回灌 profile/config，再重新 codegen
- （测试全部通过后）调用 /emitter-build 提取确定性模板
```
