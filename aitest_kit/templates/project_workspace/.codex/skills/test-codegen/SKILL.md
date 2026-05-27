---
name: test-codegen
description: 从模块 Markdown 用例或 case suite 生成 pytest，执行 profile gate、Case IR、freshness check，并处理少量 UNPARSED 补写
when_to_use: 当用户需要将 Markdown 测试用例编译为 pytest、检查 generated 是否过期，或针对某个 case suite 执行 codegen 时
argument-hint: <target_module>|--cases <suite_dir> [--dry-run|--check|--dump-ir]
arguments: [target_module, cases_dir, dry_run, check, dump_ir]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# 测试代码生成

将 `$target_module` 模块的 Markdown 用例，或 `--cases <suite_dir>` 指定的 case suite，编译为 pytest 代码。

## 参考文档

详细的 emitter 规则、断言映射、fixture 检查清单和 profile 编写指南拆分到：
- `refs/emitter_rules.md` — 文件结构、命名、setup、断言生成、请求生成、case_body/flow 规则、标记处理、profile 指南

## 生成策略

采用 **emitter 优先 + AI 补全** 模式。当前生成链路为 `parser -> Case IR planner -> emitter/IR renderer -> pytest`：

1. parser 只把 Markdown 转为 `ParseResult`，不读取 profile，不判断协议/策略。
2. Case IR planner 结合 `ParseResult`、`project_config` 和 `codegen_profile` 生成可解释的生成计划。
3. emitter（`aitest_kit/codegen/emitter.py`）负责装载、诊断和落盘，IR renderer（`aitest_kit/codegen/ir_renderer.py`）确定性生成 .py，通用规则 + codegen_profile 特殊规则覆盖大部分断言。
4. AI 只处理 emitter 输出的 `# UNPARSED ASSERTION:` 部分，将其翻译为可执行的 pytest 代码。
5. `@pytest.mark.manual` 和 `# SKIPPED` 用例不需要 AI 补写。

如果迁移到其他仓库时尚未实现 Case IR CLI，仍按现有 parser/emitter 流程执行；不要因为缺少 dump/explain 命令阻断 codegen。

## 新项目迁移：探索与回灌

新项目首个模块允许 AI 先手写 pytest 探索公开 API 行为，但这只是探索态，不是最终交付态。最终必须回到可重复的 codegen 链路：

```text
Markdown 用例
  -> AI 手写/半手写探索（可选）
  -> 已验证测试逻辑回灌到 fixture + codegen_profile
  -> case_bodies 或 case_flows
  -> aitest codegen 重新生成 generated pytest
  -> aitest codegen --check 通过
```

交付前必须满足：

1. `test_workspace/tests/fixtures/{module}.py` 存在，且只通过公开 API/公开依赖准备测试条件。
2. `test_workspace/tests/fixtures/codegen_profile_{module}.md` 存在，`--validate-profile` 无 ERROR，且不应出现 `profile not found`。
3. 手写探索出的流程必须迁入 `case_flows` 或 `case_bodies`；`test_workspace/tests/generated/` 不能作为唯一源头。
4. `--dump-ir` 不得出现模板占位路径（如 `/api/v1/replace-me`）或明显错误的默认 helper/fixture。
5. `aitest codegen {module}` 后，`aitest codegen {module} --check` 必须通过。

路线选择：

- 稳定的"调用 helper -> 保存响应 -> 派生变量 -> 断言"流程，优先写成 `case_flows`。
- 包含复杂控制流、线程/进程、mock、文件生命周期或难以结构化的 Python 逻辑，先收纳到 `case_bodies`。
- 同类 `case_bodies` 通过真实测试验证并重复出现后，再用 `emitter-build` / promotion 报告评估是否晋升为 `case_flows`、`assertion_rules` 或项目配置规则。
- 如果用户贴出失败现象（profile 缺失、`--check` stale、IR 路径错误），先修回灌链路，不要继续堆叠手写 generated。

## 前置：新项目首次使用检查

如果这是一个新项目（没有任何 codegen_profile 存在），执行以下检查：

1. **项目配置** — 检查 `aitest_config/project_config.yaml` 是否存在且匹配当前项目（helper_import、api_path、var_map、module_abbrevs、builtin_assertion_rules）
2. **如果不存在**，参考现有 project_config.yaml 创建一份
3. **项目配置** — 读取 `aitest_config/config.yaml`（路径、协议偏好、已知限制）和 `aitest_config/project_config.yaml`（断言规则、模块分类）
4. **profile 格式** — profile 继续使用 Markdown 内 YAML；结构契约由 `aitest_config/schemas/codegen_profile.schema.json` 校验，再叠加 case_id/module_type/case_flow 语义校验
5. **提醒用户**：首个模块的 UNPARSED / case_body 比例可能较高，建议选断言模式最典型的模块作为第一个
6. **占位配置检查** — 若 IR 或 generated 中出现 `/api/v1/replace-me`、示例 helper、示例模块缩写，说明项目配置/profile 尚未适配，不能进入真实 pytest

> 首个模块的 profile 交付要求见上方「新项目迁移：探索与回灌」章节。

## 前置：读取 codegen profile

模块模式检查 `test_workspace/tests/fixtures/codegen_profile_$target_module.md` 是否存在。case suite 模式还要检查 suite 目录中的 `aitest_suite.yaml` 和 `codegen_profile_{suite}_suite.md`。

**如果存在**，emitter 会自动加载其中的 YAML 规则段。AI 补写时也应参考 profile 中的断言模式、请求模板、setup 映射。

**如果不存在**：

1. 读取其他模块已有的 profile 作为参考（结构模板 + 通用模式），但不复制模块特有的断言逻辑
2. 新项目首个模块必须创建最小 profile，至少声明 `module_type`、fixture 引用，以及能覆盖非默认接口/多步骤流程的 `case_flows` 或 `case_bodies`
3. 如果先产生了探索用 generated pytest，应把其中已验证的执行流程迁入 profile，再删除对手写 generated 的依赖
4. 生成完毕后在摘要中提示 profile 的成熟度：探索态 `case_bodies`、结构化 `case_flows`，还是规则化 `assertion_rules`

### case suite 模式

如果用户给的是一批独立用例目录，而不是 `test_workspace/cases/{module}`，先检查该目录是否有 `aitest_suite.yaml`：

```yaml
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: codegen_profile_quota_billing_v2_suite.md
```

规则：

1. module profile 仍固定在 `test_workspace/tests/fixtures/codegen_profile_{module}.md`，放 L1 级稳定能力。
2. suite profile 跟用例目录走，文件名必须以 `_suite.md` 结尾，放本批用例的 `variables/case_flows/case_bodies/request_overrides`。
3. 如果没有 `aitest_suite.yaml`，执行时必须显式传 `--module {module}`。
4. 生成文件名为 `test_{module}_{suite}_{case_file_stem}.py`；拆分 pytest 文件由用户先拆分 Markdown 文件决定。

case suite 推荐门禁顺序：

```bash
python3 -m aitest_kit.cli codegen --cases <suite_dir> --validate-profile
python3 -m aitest_kit.cli codegen --cases <suite_dir> --dump-ir
python3 -m aitest_kit.cli codegen --cases <suite_dir>
python3 -m aitest_kit.cli codegen --cases <suite_dir> --check
```

### 新增用例的能力缺口判断

现有模块新增 Markdown 用例时，先按 `test-codegen` 处理。`test-codegen` 可以补 suite profile，但不能假装 fixture 已具备不存在的调用能力。

先读以下输入：

1. 新增 Markdown 用例和共享配置
2. module profile：`test_workspace/tests/fixtures/codegen_profile_{module}.md`
3. suite profile（如已存在）：`<suite_dir>/codegen_profile_{suite}_suite.md`
4. 模块 fixture：`test_workspace/tests/fixtures/{module}.py`
5. 相关 helper 和 conftest 注册

判定规则：

| 发现 | 处理 |
|------|------|
| 只是缺 `aitest_suite.yaml` 或 suite profile | 留在 `test-codegen`：创建 suite 元数据和 `codegen_profile_{suite}_suite.md` |
| 只是新增参数组合、断言组合或已有 client 方法的新调用顺序 | 留在 `test-codegen`：补 `variables/case_flows/request_overrides/assertion_rules` |
| 需要调用现有 fixture 没封装的新端点 | 切到 `test-scaffold incremental`：补 client/helper 方法后再回到 codegen |
| 需要新的认证方式、header、cookie、token 来源或 case-scoped env | 切到 `test-scaffold incremental`：补 env 契约和 fixture 注入 |
| 需要创建/清理测试数据或跨步骤状态管理 | 切到 `test-scaffold incremental`：补 setup/cleanup 能力 |
| 需要文件上传、流式响应、WebSocket、mock、外部依赖或复杂生命周期 | 切到 `test-scaffold incremental`，必要时允许 `case_bodies` |
| 只能靠大段 raw `case_body` 绕过 fixture 缺口 | 切到 `test-scaffold incremental`，先补测试能力再决定是否保留 `case_body` |
| generated 需要 import 当前 fixture/helper 中不存在的方法 | 切到 `test-scaffold incremental` |

简化判断：**只是新增用例表达 → `test-codegen`；需要新增测试调用能力 → `test-scaffold incremental`。**

### suite profile 补齐流程

当新增用例属于现有模块、fixture 能力足够，但缺 suite profile 时，借用 `test-scaffold` 的结构化步骤做最小补齐：

1. 确认 module、suite 名称和 case 文件列表。
2. 创建或修正 `<suite_dir>/aitest_suite.yaml`，不要把 suite profile 索引写回 module profile。
3. 读取 module fixture 的 client 方法签名，只使用已存在的方法。
4. 逐条 case 选择 `variables`、`case_flow`、`request_overrides`、`skipped/manual`；不要生成 case_id 分发表。
5. 对可行性存疑 case，保持 skipped，不要为了覆盖率强行写可执行 flow。
6. 生成 `<suite_dir>/codegen_profile_{suite}_suite.md` 后立即跑 suite 级 profile gate 和 dump-ir。

## 前置：运行 parser

1. 模块模式：解析 `test_workspace/cases/$target_module/` 下的 Markdown 用例文件（通常是 `business.md` / `boundary.md`）
2. case suite 模式：解析 `<suite_dir>` 中 `aitest_suite.yaml` 声明的 `case_files`，或目录下的 Markdown 用例文件
3. 读取 parser 输出，理解共享配置和每条用例的结构

如果 `$dry_run` 为 true，只输出可生成/不可生成用例列表，不生成代码。

## 前置：构建或解释 Case IR

Case IR 的职责是解释"这条用例为什么这么生成"，不是替代 parser 做 Markdown 解析，也不是做业务推理。

Case IR 第一版应覆盖以下 strategy：

| strategy | 含义 |
|----------|------|
| `default_http` | 标准 HTTP 单接口 |
| `default_grpc` | 场景变量标注 gRPC 的标准单接口 |
| `custom_case_body` | profile 中存在 `case_bodies[case_id]` |
| `manual` | marker 包含 manual |
| `skipped` | marker 包含可行性存疑 |
| `structured_case_flow` | profile 中存在 `case_flows[case_id]` |

如果 CLI 已支持，优先用 dump/explain 排查生成策略：

```bash
python3 -m aitest_kit.cli codegen $target_module --validate-profile
python3 -m aitest_kit.cli codegen $target_module --validate-profile --write-report
python3 -m aitest_kit.cli codegen $target_module --dump-ir
python3 -m aitest_kit.cli codegen $target_module --explain TC-XXX
python3 -m aitest_kit.cli codegen $target_module --analyze-promotion --write-report
python3 -m aitest_kit.cli codegen $target_module --suggest-promotion-patch
python3 -m aitest_kit.cli codegen --all --health-report --write-report
```

普通生成、`--check`、`--dump-ir`、`--explain` 和 promotion 分析已经接入 profile 硬门禁；profile 有 ERROR 时不要绕过门禁继续生成。如果 CLI 尚未支持，手动对齐 parser 输出、project_config 和 codegen_profile，不要发明 IR 中没有来源的策略。

## 前置：读取 helpers API

读取 `aitest_config/config.yaml` 获取项目路径，然后读取以下文件了解可用的 fixtures 和 helper 函数签名：

- 全局 conftest.py
- 模块 fixture（如果已存在）
- HTTP/gRPC/外部依赖 helpers

## 第一步：codegen 生成

执行 codegen 生成 .py 文件；该入口会先执行 profile 硬门禁，再进入 IR/emitter：

```bash
python3 -m aitest_kit.cli codegen $target_module
```

检查输出摘要中的 UNPARSED 数量。若 Case IR 已接入，先确认每条用例的 strategy/protocol/fixtures 与预期一致，再分析 generated pytest。

新模块推荐顺序：

```bash
python3 -m aitest_kit.cli codegen $target_module --validate-profile
python3 -m aitest_kit.cli codegen $target_module --dump-ir
python3 -m aitest_kit.cli codegen $target_module
python3 -m aitest_kit.cli codegen $target_module --check
```

`--validate-profile` 有 `profile not found`、`--dump-ir` 走错接口/fixture、或 `--check` stale 时，说明还没有完成回灌；先补 fixture/profile/case_flow/case_body，再重新生成。

case suite 用例推荐顺序：

```bash
python3 -m aitest_kit.cli codegen --cases <suite_dir> --validate-profile
python3 -m aitest_kit.cli codegen --cases <suite_dir> --dump-ir
python3 -m aitest_kit.cli codegen --cases <suite_dir>
python3 -m aitest_kit.cli codegen --cases <suite_dir> --check
```

## 第二步：AI 补写 UNPARSED

读取 emitter 生成的 .py 文件，找到所有 `# UNPARSED ASSERTION:` 注释。

对每条 UNPARSED 断言：

1. 读取对应 TestCase 的完整上下文（scenario_vars、assertions、markers）
2. 读取 codegen_profile 中的断言模式表（如果存在）
3. 将 UNPARSED 注释替换为可执行的 pytest 断言代码

补写规则参考 `refs/emitter_rules.md#断言生成` 的映射表。自然语言描述无法翻译为代码的，保留 `# UNPARSED ASSERTION:` 不动。

**如果 UNPARSED 为 0**，跳过此步骤。

## 第三步：验证

模块模式：

1. `python3 -m aitest_kit.cli codegen $target_module --validate-profile` — profile/schema/语义校验
2. `python3 -m aitest_kit.cli codegen $target_module --dump-ir` — 检查 strategy、fixtures、接口路径和 source_trace
3. `python3 -m aitest_kit.cli codegen $target_module` — 重新生成 pytest
4. `python3 -m aitest_kit.cli codegen $target_module --check` — 确认 generated 可由当前 Markdown/profile/config 复现
5. `python3 -m compileall test_workspace/tests/fixtures/{module}.py test_workspace/tests/generated` — 语法检查
6. `python3 -m pytest test_workspace/tests/generated/test_{module}_*.py --collect-only -q` — 收集检查
7. 如果模块 fixture 和服务已就绪：`python3 -m pytest test_workspace/tests/generated/test_{module}_*.py -q`

case suite 模式把前 4 步替换为 `python3 -m aitest_kit.cli codegen --cases <suite_dir> ...`，生成目标文件为 `test_{module}_{suite}_{case_file_stem}.py`。

## 质量要求

1. 生成的代码必须通过 `ast.parse`
2. 每个 test 函数独立，不依赖执行顺序
3. 不 import 待测服务内部模块
4. 不硬编码端口，通过 fixture 获取 base_url
5. 不发明用例中没有的断言
6. parser、Case IR、emitter 的错误边界清晰：Markdown 结构问题归 parser，策略/配置问题归 IR planner，渲染问题归 emitter
7. 新模块交付态不得停留在手写 generated；必须有 profile 回灌并通过 `--check`
8. `profile not found`、`/api/v1/replace-me`、`--check stale` 都是迁移未完成信号
9. 可执行 API 测试的服务地址缺失应失败暴露环境问题，不能悄悄 skip

## 输出

```
## codegen 摘要

模块：{module}
生成文件：
- 模块模式：test_{module}_{case_file_stem}.py — N 条（emitter X 条，AI 补写 Y 条）
- suite 模式：test_{module}_{suite}_{case_file_stem}.py — N 条（emitter X 条，AI 补写 Y 条）

跳过（可行性存疑）：
- TC-XXX：原因

仍未解析：
- TC-XXX：断言原文

TODO：
- （fixture 不存在时）setup_{module} fixture 需要补齐，并从环境变量读取服务地址
- （有 gRPC 用例时）gRPC helper 需要补充
- （无 codegen_profile 时）需要补齐 profile，并将探索逻辑迁入 case_bodies/case_flows
- （generated stale 时）先回灌 profile/config，再重新 `aitest codegen`，不要长期保留手写 generated
- （测试全部通过后）调用 /emitter-build 提取确定性模板
```
