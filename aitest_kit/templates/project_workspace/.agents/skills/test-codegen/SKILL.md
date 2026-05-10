---
name: test-codegen
description: 从 parser 结构化输出 + emitter 确定性生成 pytest 代码，AI 补写 UNPARSED 部分
when_to_use: 当用户需要将 Markdown 测试用例编译为 pytest 可执行代码时
argument-hint: <target_module> [--dry-run]
arguments: [target_module, dry_run]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# 测试代码生成

将 `$target_module` 模块的 Markdown 用例编译为 pytest 代码。

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

检查 `test_workspace/tests/fixtures/codegen_profile_$target_module.md` 是否存在。

**如果存在**，emitter 会自动加载其中的 YAML 规则段。AI 补写时也应参考 profile 中的断言模式、请求模板、setup 映射。

**如果不存在**：

1. 读取其他模块已有的 profile 作为参考（结构模板 + 通用模式），但不复制模块特有的断言逻辑
2. 新项目首个模块必须创建最小 profile，至少声明 `module_type`、fixture 引用，以及能覆盖非默认接口/多步骤流程的 `case_flows` 或 `case_bodies`
3. 如果先产生了探索用 generated pytest，应把其中已验证的执行流程迁入 profile，再删除对手写 generated 的依赖
4. 生成完毕后在摘要中提示 profile 的成熟度：探索态 `case_bodies`、结构化 `case_flows`，还是规则化 `assertion_rules`

## 前置：运行 parser

1. 执行 `python3 -m aitest_kit.codegen.parser test_workspace/cases/$target_module/business.md`，获取结构化输出
2. 如果存在 `boundary.md`，同样执行 parser
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

## 第二步：AI 补写 UNPARSED

读取 emitter 生成的 .py 文件，找到所有 `# UNPARSED ASSERTION:` 注释。

对每条 UNPARSED 断言：

1. 读取对应 TestCase 的完整上下文（scenario_vars、assertions、markers）
2. 读取 codegen_profile 中的断言模式表（如果存在）
3. 将 UNPARSED 注释替换为可执行的 pytest 断言代码

补写规则参考下方"断言生成"章节的映射表。自然语言描述无法翻译为代码的，保留 `# UNPARSED ASSERTION:` 不动。

**如果 UNPARSED 为 0**，跳过此步骤。

## 第三步：验证

1. `python3 -m aitest_kit.cli codegen $target_module --validate-profile` — profile/schema/语义校验
2. `python3 -m aitest_kit.cli codegen $target_module --dump-ir` — 检查 strategy、fixtures、接口路径和 source_trace
3. `python3 -m aitest_kit.cli codegen $target_module` — 重新生成 pytest
4. `python3 -m aitest_kit.cli codegen $target_module --check` — 确认 generated 可由当前 Markdown/profile/config 复现
5. `python3 -m compileall test_workspace/tests/fixtures/{module}.py test_workspace/tests/generated` — 语法检查
6. `python3 -m pytest test_workspace/tests/generated/test_{module}_*.py --collect-only -q` — 收集检查
7. 如果模块 fixture 和服务已就绪：`python3 -m pytest test_workspace/tests/generated/test_{module}_*.py -q`

## emitter 生成规则参考

以下规则已内置于 emitter.py，供 AI 补写 UNPARSED 时参考。

### 文件结构

- `business.md` -> `test_workspace/tests/generated/test_{module}_business.py`
- `boundary.md` -> `test_workspace/tests/generated/test_{module}_boundary.py`

### 类和函数命名

- 类名：`Test{Module}Business`（模块名首字母大写 + Business/Boundary）
- 函数名：`test_tc_mod_001`（TC ID 小写，连字符转下划线）
- docstring：`"""TC-MOD-001：{title}"""`

### setup 处理

场景变量 -> `# SETUP:` 注释 + `setup_{module}(case_id="TC-XXX")` 调用。

fixture 由 `test_workspace/tests/fixtures/{module}.py` 提供。按当前项目的 generated import/profile 机制接线；只有项目采用 `pytest_plugins` 注册时，才需要维护 `conftest.py` 中的 `pytest_plugins` 列表。

新增模块时需要：
1. 创建 `test_workspace/tests/fixtures/{module}.py`
2. 确认 `codegen_profile_{module}.md` 或 generated pytest 能引用到对应 fixture；如果项目使用 `pytest_plugins`，同步添加插件注册

### fixture 编写检查清单

编写新模块的 `setup_{module}` fixture 前，确认：

1. **部署拓扑** — 服务间调用关系，确认环境变量（服务 URL、外部依赖地址等）
2. **可用 API** — fixture 需要调用的管理接口或数据准备接口
3. **隔离策略** — 每条用例的数据如何隔离（tmp_path、唯一 user_id、teardown 恢复）
4. **teardown** — 所有副作用都能恢复（配置、测试数据、外部依赖状态）
5. **`_CASE_CONFIGS` 结构** — 参考 codegen_profile 的 setup 映射章节
6. **服务地址** — 从项目专属环境变量读取（如 `DISCOUNT_SYSTEM_BASE_URL`），可兼容 `HTTP_BASE_URL`；不要硬编码端口或 URL
7. **环境缺失** — 可执行 API 测试缺少服务地址时用 `pytest.fail`，不要用 `pytest.skip` 掩盖环境未配置
8. **HTTP 客户端** — 使用 `httpx` 时显式指定 `httpx.HTTPTransport()`，避免 macOS/CI 系统代理影响本地 HTTP 测试
9. **黑盒边界** — fixture 不 import 待测系统内部模块，不读取目标项目源码/内部测试来推断业务规则

### 断言生成

断言匹配优先级：profile assertion_rules > project_config builtin_assertion_rules > named_templates。

通用断言模式（框架内置）：

| 断言模式 | 生成方式 |
|---------|---------|
| `response.code == 固定值` | `assert resp["code"] == 固定值` |
| `response.xxx == 固定值` | `assert resp["xxx"] == 固定值` |
| `set(response.results[*].item_id) == {集合}` | `assert {r["item_id"] for r in resp["results"]} == {集合}` |
| `len(xxx) == N` | `assert len(xxx) == N` |
| `[manual]` 标记 | `# MANUAL CHECK: {原文}` |
| 无法翻译 | `# UNPARSED ASSERTION: {原文}` |

项目专属断言模式见 `aitest_config/project_config.yaml` 的 `builtin_assertion_rules`。

`round(..., 4)` -> `pytest.approx(..., abs=1e-4)`。`clamp(x)` -> `max(0, min(1, x))`。

### 请求生成

1. 从共享配置取基础请求体，场景变量 `请求覆盖` 合并
2. gRPC 用例通过场景变量中的 `协议：gRPC` 标识，Case IR 应记录该判断来源
3. 共享配置中的 HTTP 基础请求体必须是合法 JSON，不使用 `{{placeholder}}`；case 级差异通过场景变量或 profile `request_overrides` 合并

### case_body 与 case_flow

- `case_bodies` 是复杂场景的逃生通道，适合多端点、多请求、副作用、日志、隔离服务、并发等默认模板难以覆盖的用例。
- `case_flows` 是已验证且结构稳定的 `case_bodies` 晋升形态，适合"调用 helper -> 保存结果 -> 派生变量 -> 观察副作用 -> 断言/注释"这类重复多步骤流程；当前支持 `call`、`assign`、`assert`、`comment` 四类 step。
- 同一个 case_id 不允许同时出现在 `case_bodies` 和 `case_flows`；正式晋升为 `case_flow` 时必须删除旧 `case_body`，否则 codegen 会报错。
- `case_flow` 的 `assert` step 必须写成可执行 Python 断言，例如 `assert resp["code"] == 0`；裸表达式如 `` `resp == ERR` `` 会被 profile 校验拒绝。
- 不要把复杂 Python 控制流硬塞进 `case_flow`；包含线程、进程、mock、复杂文件生命周期时继续保留 `case_body`。
- 新增 `case_flow` 前必须能解释它比原 `case_body` 更稳定、更可读、更可校验。
- 生成或迁移前显式运行 `python3 -m aitest_kit.cli codegen $target_module --validate-profile`；普通生成也会自动硬门禁，用于提前发现 JSON Schema 格式、case_id 引用、case_flow assert 和 module_type 必需字段问题。
- `--analyze-promotion --write-report` 和 `--suggest-promotion-patch` 的产物写入 `test_workspace/reports/codegen/latest/`，不要放到 `plans/`；patch 草案默认只供 review，不自动修改 profile。
- `--health-report --write-report` 输出模块成熟度、case_flow/case_body/UNPARSED 和断言命中统计，用来决定下一轮沉淀优先级。

### 标记处理

- `[manual]` -> `@pytest.mark.manual` + 断言为注释
- `[!可行性存疑: ...]` -> 跳过不生成，末尾 `# SKIPPED:`

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
- test_{module}_business.py — N 条（emitter X 条，AI 补写 Y 条）
- test_{module}_boundary.py — N 条

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

## 后续：编写 codegen profile

测试调通后编写 `test_workspace/tests/fixtures/codegen_profile_{module}.md`，必须包含：

| 章节 | 内容 |
|------|------|
| **fixture 依赖** | fixture 名称、来源、调用方式 |
| **setup_{module} 做了什么** | fixture 内部操作步骤 |
| **新增用例时如何扩展** | dict/map 添加条目格式 |
| **请求模板** | 固定字段、差异字段、helper 用法 |
| **断言模式** | 断言 -> pytest 映射表 |
| **setup 映射** | 场景变量 -> _CASE_CONFIGS 映射 |
| **case_bodies / case_flows** | 复杂用例的自定义执行体，或已晋升的结构化多步骤流程 |
| **已知阻塞项** | 无法自动化的用例及原因 |
| **调试经验** | 模块特有排错经验 |
| **emitter 规则** | YAML code block，模块特有断言规则 |

参考已有模块的 codegen_profile 作为结构模板。

## 后续：emitter-build

测试全部通过且 profile 编写完成后，调用 `/emitter-build` 提取确定性模板。
