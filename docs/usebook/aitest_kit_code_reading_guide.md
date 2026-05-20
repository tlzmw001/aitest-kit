# AITest Kit 代码通读指南

> 目标读者：第一次系统读这个项目的人。  
> 目标：理解当前 `aitest-kit 0.1.2` 的功能边界、模块职责、关键函数调用和数据流，后续可以按章节交互式学习。

本文只梳理 `aitest_kit/`、`aitest_config/`、`test_workspace/`、workspace 模板和 skills 的协作关系。`coupon_system/` 与 `ab_experiment_sdk/` 是历史演练中的待测/依赖服务，不是 AITest Kit 框架本体。

## 1. 先建立整体心智模型

这个项目不是一个“直接写 pytest 的工具”，而是一条测试资产生产线：

```text
开发文档
  -> 测试知识库 L0/L1/L2/TEST_SPEC
  -> Markdown 测试用例
  -> codegen_profile + fixture
  -> Case IR
  -> generated pytest
  -> pytest 执行
  -> result.json / report.md
  -> 修正与规则沉淀
```

核心哲学：

- AI 负责理解业务、设计初版、判断哪里值得沉淀。
- Python 代码负责稳定、可重复、可验证的解析、校验、生成和报告。
- Markdown 用例和 profile 是源数据，`test_workspace/tests/generated/` 是编译产物。

## 2. 仓库功能地图

### 2.1 框架代码

| 路径 | 职责 | 初学者阅读优先级 |
|---|---|---|
| `aitest_kit/cli.py` | 顶层 CLI 入口，注册 `init/codegen/run/report` | P0 |
| `aitest_kit/workspace.py` | workspace 初始化和 `--workspace` 切换目录 | P0 |
| `aitest_kit/init_workspace.py` | `aitest init` 命令包装 | P1 |
| `aitest_kit/codegen/` | Markdown/profile 到 pytest 的生成主链路 | P0 |
| `aitest_kit/report/` | `aitest run/report` 的执行报告链路 | P0 |
| `aitest_kit/templates/project_workspace/` | `aitest init` 复制给用户的新项目模板 | P1 |

### 2.2 项目配置和测试资产

| 路径 | 职责 |
|---|---|
| `aitest_config/config.yaml` | workspace 路径、服务信息、协议偏好，主要给 CLI 和 skills 定位目录 |
| `aitest_config/project_config.yaml` | codegen 引擎配置：默认 helper、API path、断言规则、module_type |
| `aitest_config/schemas/codegen_profile.schema.json` | profile 的 JSON Schema 硬门禁 |
| `test_workspace/knowledge/` | 测试知识库 |
| `test_workspace/cases/{module}/business.md` | 业务用例源数据 |
| `test_workspace/cases/{module}/boundary.md` | 边界用例源数据 |
| `test_workspace/tests/fixtures/{module}.py` | 模块测试 client、setup fixture、辅助方法 |
| `test_workspace/tests/fixtures/codegen_profile_{module}.md` | 模块生成配置 |
| `test_workspace/tests/generated/test_{module}_{category}.py` | codegen 生成的 pytest |
| `test_workspace/reports/` | `aitest run` 输出的运行报告 |
| `test_workspace/results/` | 待测系统 bug 和测试发现记录 |

### 2.3 本地 skills

| Skill | 位置 | 职责 |
|---|---|---|
| `doc-review` | `.codex/.claude/.agents/skills/doc-review` | 审查开发文档是否足够设计测试 |
| `doc-gen` | `.codex/.claude/.agents/skills/doc-gen` | 必要时从源码补测试设计输入 |
| `knowledge-build` | `.codex/.claude/.agents/skills/knowledge-build` | 文档到 L0/L1/L2 知识库 |
| `test-design` | `.codex/.claude/.agents/skills/test-design` | 知识库到 Markdown 用例 |
| `test-codegen` | `.codex/.claude/.agents/skills/test-codegen` | Markdown/profile 到 generated pytest |
| `test-fix` | `.codex/.claude/.agents/skills/test-fix` | 修用例、沉淀陷阱 |
| `emitter-build` | `.codex/.claude/.agents/skills/emitter-build` | 从已验证 pytest 分析可沉淀规则 |

## 3. 用户命令如何进入代码

顶层入口在 `aitest_kit/cli.py`：

```text
main()
  add_command(codegen)
  add_command(init_command)
  add_command(run_command)
  add_command(report_command)
```

用户看到的四个命令：

| 命令 | 入口函数 | 主要调用 |
|---|---|---|
| `aitest init` | `init_workspace.init_command()` | `workspace.init_workspace()` |
| `aitest codegen` | `codegen.cli.codegen()` | `_codegen_impl()` |
| `aitest run` | `report.cli.run_command()` | `_run_command_impl()` |
| `aitest report` | `report.cli.report_command()` | `_report_command_impl()` |

`--workspace` 的本质是临时 `chdir`：

```text
push_workspace(workspace)
  保存当前 cwd
  校验 workspace 存在且是目录
  os.chdir(target)
  执行实际命令
  finally 切回原 cwd
```

所以框架内部绝大多数路径都可以写成相对路径，例如 `test_workspace/cases`。

## 4. `aitest init` 调用链

目标：把包内模板复制到用户项目目录。

```text
用户命令
  aitest init --target /path/to/project

调用链
  aitest_kit/cli.py::main
  -> init_workspace.py::init_command
  -> workspace.py::init_workspace
  -> workspace.py::_template_files
  -> workspace.py::_collect_template_files
  -> destination.write_bytes(...)
```

关键数据对象：

```python
InitWorkspaceResult(
    target=target_path,
    created=0,
    overwritten=0,
    skipped=0,
)
```

关键逻辑：

- 模板源固定为 `aitest_kit.templates.project_workspace`。
- 默认不覆盖已存在的模板管理文件。
- 有冲突且没有 `--force` 时抛 `FileExistsError`。
- `_collect_template_files()` 会跳过 `__pycache__`、`.DS_Store`、`.pyc/.pyo`、模板包根部的 `__init__.py`。

阅读重点：

1. `resources.files(_TEMPLATE_PACKAGE)` 如何定位包内模板。
2. `conflicts` 如何保护用户已有文件。
3. 为什么模板唯一来源是 `aitest_kit/templates/project_workspace/`，而不是根目录再维护一份 `templates/`。

## 5. codegen 总调用链

codegen 是项目最核心的链路。

```text
用户命令
  aitest codegen discount_policy
  aitest codegen --all --check
  aitest codegen --all --dump-ir
  aitest codegen --all --validate-profile

入口
  codegen/cli.py::codegen
  -> push_workspace(...)
  -> codegen/cli.py::_codegen_impl
```

`_codegen_impl()` 先处理模式互斥：

- `--check` 和 `--dry-run` 互斥。
- `--dump-ir`、`--explain`、promotion、`--validate-profile`、`--health-report` 互斥。
- `--write-report` 只能配合 profile/health/promotion 报告类模式。

然后读取路径和配置：

```text
_load_codegen_paths()
  -> 读 aitest_config/config.yaml 的 paths
  -> 合并默认路径

load_project_config()
  -> 读 aitest_config/project_config.yaml
  -> 与 fallback 默认配置合并
```

最后根据模式分流：

| 模式 | 调用函数 | 是否 profile gate |
|---|---|---|
| `--validate-profile` | `_validate_profiles()` | 自身就是 profile 校验 |
| `--health-report` | `_health_report()` | 间接校验 |
| `--dump-ir` | `_dump_ir()` | 是 |
| `--explain TC-ID` | `_explain_case()` | 是 |
| `--analyze-promotion` | `_analyze_promotion()` | 是 |
| `--check` | `_check_consistency()` | 是 |
| 普通生成 | `emit_module()` | 是 |
| `--dry-run` | `parse_case_file()` | 否，只跑 parser |

关键原则：普通 codegen、`--check`、`--dump-ir`、`--explain`、promotion 分析都必须先过 profile gate。坏 profile 不允许进入 IR/emitter。

## 6. codegen 内部五层数据流

### 6.1 第一层：Markdown parser

文件：`aitest_kit/codegen/parser.py`

输入：

```text
test_workspace/cases/{module}/business.md
test_workspace/cases/{module}/boundary.md
```

输出：

```python
ParseResult(
    module="discount_policy",
    source_file="...",
    shared_config=SharedConfig(...),
    cases=[TestCase(...), ...],
    errors=[...],
)
```

核心 dataclass：

| 类 | 含义 |
|---|---|
| `SharedConfig` | `## 共享配置` 中的接口、基础请求体、通用断言、变量定义 |
| `TestCase` | 单条 `### TC-XXX-001` 用例 |
| `ParseResult` | 一个 Markdown 文件的解析结果 |

关键函数：

| 函数 | 做什么 |
|---|---|
| `parse_case_file(path)` | parser 对外入口 |
| `_parse_shared_config(lines)` | 解析共享配置 |
| `_extract_json_block(lines, start)` | 找 `json` 代码块并用 `json.loads` 校验 |
| `_find_template_placeholders(value)` | 禁止 JSON 中出现 `{{var}}` 占位符 |
| `_parse_cases(lines, config_end)` | 解析所有 TC 用例 |
| `_split_assertions(raw)` | 按 `;` / `；` 拆断言 |

重要行为：

- parser 不理解业务，只按固定 Markdown 结构提取字段。
- HTTP 基础请求体必须是合法 JSON。
- JSON 中不能出现 `{{user_id}}` 这类模板占位符。
- parser 错误进入 `ParseResult.errors`，后续会变成 `E001`。

### 6.2 第二层：profile loader 和 profile gate

文件：

- `aitest_kit/codegen/profile.py`
- `aitest_kit/codegen/profile_validator.py`

profile 路径固定：

```text
test_workspace/tests/fixtures/codegen_profile_{module}.md
```

profile loader 只提取 Markdown 中第一个 YAML 代码块：

```text
load_profile_yaml()
  -> regex 找 ```yaml ... ```
  -> yaml.safe_load
  -> 返回 dict 或 {}
```

loader 系列函数：

| 函数 | 读取 YAML 字段 |
|---|---|
| `load_profile_rules()` | `assertion_rules` |
| `load_profile_request_overrides()` | `request_overrides` |
| `load_profile_extra_imports()` | `extra_imports` |
| `load_profile_case_fixtures()` | `case_fixtures` |
| `load_profile_case_bodies()` | `case_bodies` |
| `load_profile_case_flows()` | `case_flows` |
| `load_profile_module_type()` | `module_type` |

profile gate 做三类校验：

```text
validate_profile_module()
  -> _collect_markdown_cases()
  -> _load_profile_yaml_strict()
  -> _validate_profile_schema()
  -> _validate_top_level_shape()
  -> validate_profile_strategy_conflicts()
  -> validate_case_flows()
  -> _validate_case_references()
  -> _validate_module_type()
```

关键错误：

| 错误码 | 含义 |
|---|---|
| `E501` | YAML/JSON Schema/top-level shape 错 |
| `E502` | 同一 case 同时存在 `case_bodies` 和 `case_flows` |
| `E503` | `case_flows` 结构错误 |
| `E505` | profile 引用了 Markdown 中不存在的 case_id |
| `E510/E511` | 模块用例目录或用例文件缺失 |

### 6.3 第三层：ProjectConfig

文件：`aitest_kit/codegen/project_config.py`

输入：

```text
aitest_config/project_config.yaml
```

输出：

```python
ProjectConfig(
    helper_import=...,
    api_path=...,
    helper_call=...,
    grpc_helper_import=...,
    grpc_helper_call=...,
    var_map={...},
    module_abbrevs={...},
    builtin_assertion_rules=[...],
    named_templates={...},
    module_types={...},
    modules={...},
)
```

关键点：

- `FALLBACK_PROJECT_CONFIG_DATA` 是兼容默认值，不是当前项目配置的主编辑入口。
- 当前项目的主配置入口是 `aitest_config/project_config.yaml`。
- `load_project_config()` 会把 fallback 和 YAML 合并。
- `builtin_assertion_rules` 会被转换成 `AssertionRule` 对象。

### 6.4 第四层：Case IR planner

文件：

- `aitest_kit/codegen/ir.py`
- `aitest_kit/codegen/planner.py`

IR 是 codegen 的中间表示。它回答一个问题：

```text
这条 Markdown 用例最终应该用什么策略生成 pytest？
```

核心 dataclass：

| 类 | 含义 |
|---|---|
| `FileIR` | 一个 business/boundary 文件的计划 |
| `CaseIR` | 一条用例的计划 |
| `RequestIR` | 默认 HTTP/gRPC 模板需要的请求数据 |
| `CallIR` | 默认模板调用哪个 helper |
| `AssertionIR` | 断言源文本、生成代码、解析来源 |
| `CaseFlowIR` | profile `case_flows` 的结构化流程 |
| `CustomBodyIR` | profile `case_bodies` 的原始 Python body |
| `SourceTraceIR` | 记录某个决策来自哪里 |
| `DiagnosticIR` | planner 诊断 |

核心入口：

```text
build_file_ir(parse_result, category, profile_path, project)
```

planner 的策略优先级：

```text
可行性存疑 skipped
  > profile.case_bodies custom_case_body
  > profile.case_flows structured_case_flow
  > manual
  > gRPC marker default_grpc
  > default_http
```

对应函数：

| 函数 | 做什么 |
|---|---|
| `_strategy_for()` | 决定生成策略 |
| `_fixtures_for()` | 决定 pytest 函数参数里需要哪些 fixture |
| `_request_for()` | 默认模板生成 `RequestIR` |
| `_call_for()` | 默认模板生成 `CallIR` |
| `_needed_variables()` | 判断断言里是否用到 `s/cal` 等变量 |
| `_assertions_for()` | 把 Markdown 断言转成 `AssertionIR` |
| `_case_flow_for()` | 把 profile `case_flows` 转成 `CaseFlowIR` |
| `_case_diagnostics()` | 生成 E202/E203 等诊断 |

阅读重点：

- 为什么 `case_bodies` 和 `case_flows` 不需要 `RequestIR`。
- 为什么默认模板必须有 `shared_config.base_request_http`。
- `source_trace` 如何解释“这条用例为什么走这个策略”。

### 6.5 第五层：renderer / emitter

文件：

- `aitest_kit/codegen/render_utils.py`
- `aitest_kit/codegen/ir_renderer.py`
- `aitest_kit/codegen/emitter.py`

分工：

| 文件 | 职责 |
|---|---|
| `render_utils.py` | 字符串、断言规则、Python 字面量渲染工具 |
| `ir_renderer.py` | 把 `FileIR` 渲染成 pytest 文件文本 |
| `emitter.py` | 对外封装 emit 文件/模块，处理阻断和落盘 |

`resolve_assertion()` 的匹配顺序：

```text
profile assertion_rules
  -> project_config builtin_assertion_rules
  -> named_templates
  -> UNPARSED
```

`ir_renderer.py` 的三条渲染分支：

| strategy | 渲染函数 |
|---|---|
| `custom_case_body` | `_render_custom_body()` |
| `structured_case_flow` | `_render_case_flow()` |
| `default_http/default_grpc/manual` | `_render_default_body()` |

普通生成调用链：

```text
emit_module(module)
  -> parse_case_file(business.md/boundary.md)
  -> emit_file(parse_result, file_type, profile_path, ...)
  -> build_file_ir(...)
  -> render_file_from_ir(...)
  -> output_path.write_text(...)
```

`emit_file()` 的阻断点：

- parser 有 `ParseResult.errors`。
- `module_type` 要求复杂流程，但没有 `case_bodies` 或 `case_flows`。
- 缺少 HTTP 基础请求体，且用例没有被 profile 覆盖。
- `FileIR.diagnostics` 非空。
- renderer 诊断非空。

## 7. 生成出来的 pytest 长什么样

generated 文件通常包含：

```text
# Auto-generated from ...
import pytest
from test_workspace.tests.helpers import http as http_helper
额外 imports

BASE_REQUEST = {...}

def _req(...):
    ...

class TestXxxBusiness:
    def test_tc_xxx_001(...):
        __tc_meta__ = {...}
        ...

__codegen_skipped__ = [...]
```

`__tc_meta__` 很重要。报告系统靠它把 pytest 结果反查回：

- TC ID
- module
- category
- source Markdown
- title
- priority
- markers

`__codegen_skipped__` 记录 codegen 没有生成 pytest 函数的用例，例如“可行性存疑”。

## 8. `aitest run` 调用链

目标：执行 generated pytest，并生成结构化报告。

```text
用户命令
  aitest run calibration

调用链
  report/cli.py::run_command
  -> push_workspace(...)
  -> _run_command_impl()
  -> _codegen_check()
  -> subprocess.run(pytest ...)
  -> collector.collect_result()
  -> renderer.render_markdown()
  -> _write_result()
```

重要行为：

- 默认先跑 generated freshness check。
- freshness check 失败时不执行 pytest，而是生成 `BLOCKED_RUN` 报告。
- 默认排除 `@pytest.mark.manual`。
- pytest 输出 JUnit XML。
- collector 从 generated pytest 的 AST 中读取 `__tc_meta__`。
- collector 再把 JUnit XML 的 testcase 和 `__tc_meta__` 对齐。
- 最终写入：

```text
test_workspace/reports/runs/{run_id}/junit.xml
test_workspace/reports/runs/{run_id}/result.json
test_workspace/reports/runs/{run_id}/report.md
test_workspace/reports/latest/*
```

## 9. report 子包数据流

### 9.1 collector

文件：`aitest_kit/report/collector.py`

核心入口：

```text
collect_result(...)
```

内部流程：

```text
_extract_generated_metadata(files)
  -> ast.parse(generated pytest)
  -> _function_meta()
  -> _module_skipped()

_parse_junit(junit_path, meta)
  -> ElementTree 解析 XML
  -> _case_from_testcase()
  -> _outcome_and_failure()

_summary()
_module_summary()
```

关键点：

- metadata 来自 generated pytest，不来自 Markdown。
- JUnit XML 只告诉你 pytest 结果，不知道业务 TC ID。
- 所以 `__tc_meta__` 是报告可读性的核心。

### 9.2 classifier

文件：`aitest_kit/report/classifier.py`

把失败粗分为：

| 分类 | 典型情况 |
|---|---|
| `ENVIRONMENT_ERROR` | setup 阶段连接失败、超时 |
| `FIXTURE_ERROR` | setup 阶段非环境类错误 |
| `CODEGEN_ERROR` | call 阶段 `NameError/TypeError/AttributeError/SyntaxError` |
| `ASSERTION_FAILURE` | call 阶段 `AssertionError` |
| `TEARDOWN_ERROR` | teardown 阶段失败 |
| `UNKNOWN` | 未归类 |

注意：断言失败不自动等于待测系统 bug，需要人工判断。

### 9.3 renderer 和 sanitizer

文件：

- `report/renderer.py`
- `report/sanitizer.py`

`renderer.render_markdown(result)` 把 `result.json` 渲染成中文报告。

`sanitizer` 做两件事：

- `sanitize_message()`：脱敏和截断错误信息。
- `traceback_summary()`：提取短 traceback 位置，避免报告里充满绝对路径。

## 10. health 和 promotion

### 10.1 health report

文件：`aitest_kit/codegen/health.py`

目标：给每个模块算 codegen 健康度。

调用链：

```text
build_codegen_health_report()
  -> validate_profile_module()
  -> parse_case_file()
  -> build_file_ir()
  -> _module_health()
  -> _maturity_for()
```

成熟度当前口径：

| 等级 | 含义 |
|---|---|
| `L0` | profile 有 ERROR |
| `L1` | 有 UNPARSED |
| `L2` | 无错误、无 UNPARSED、但没有 case_flow |
| `L3` | 已使用 case_flow |

### 10.2 promotion 分析

文件：`aitest_kit/codegen/promotion.py`

目标：只读分析 profile 中的 `case_bodies`，判断哪些可能晋升为 `case_flows`。

核心入口：

```text
analyze_case_body_promotion(module, profile_path)
```

当前能力：

- 扫描 `case_bodies` 的 Python 文本。
- 识别对象方法调用，例如 `client.evaluate(...)`。
- 标记复杂行为，例如并发、循环、子进程、mock、文件生命周期。
- 按方法和 flags 分组。
- 输出 review-only report 和 patch draft。

当前边界：

- 不会自动从任意 pytest 精确反向生成 case_flow。
- 不会自动修改 profile。
- promotion patch 是 review draft，不是自动应用补丁。

## 11. 两个典型 codegen 分支

### 11.1 默认 HTTP 模板

适用：单接口、只需要改请求字段、断言可被规则匹配。

```text
Markdown:
  shared_config.base_request_http
  TC-DP-xxx 断言

profile:
  request_overrides 可选

planner:
  strategy = default_http
  request = RequestIR(...)
  call = CallIR(helper="http_helper.post", target="http_base_url")
  assertions = resolve_assertion(...)

renderer:
  resp = http_helper.post(http_base_url, api_path, json=_req(...))
  assert ...
```

### 11.2 structured case_flow

适用：多端点、多步骤，但流程稳定。

```text
profile:
  case_flows:
    TC-DP-008:
      fixture: setup_discount_policy
      object: client
      steps:
        - call: client.evaluate
          save_as: policy_resp
        - call: client.delete
          save_as: delete_resp
        - call: client.query_response
          save_as: query_http
        - assign: query_resp
          expr: query_http.json()
        - assert: 'assert query_http.status_code == 404'

planner:
  strategy = structured_case_flow
  case_flow = CaseFlowIR(...)

renderer:
  client = setup_discount_policy
  policy_resp = client.evaluate(...)
  delete_resp = client.delete(...)
  query_http = client.query_response(...)
  query_resp = query_http.json()
  assert query_http.status_code == 404
```

## 12. 配置如何影响生成

### 12.1 `aitest_config/config.yaml`

主要影响 CLI 和 skills 的目录定位。

`codegen/cli.py::_load_codegen_paths()` 会读取：

- `paths.cases_dir`
- `paths.generated_dir`
- `paths.fixtures_dir`
- `paths.reports_dir`
- `paths.project_config`

### 12.2 `aitest_config/project_config.yaml`

主要影响生成代码内容。

关键字段：

| 字段 | 影响 |
|---|---|
| `helper_import` | generated 文件 import 哪个 HTTP helper |
| `helper_call` | 默认 HTTP 分支如何调用请求 |
| `grpc_helper_import` | gRPC generated 文件 import |
| `grpc_helper_call` | 默认 gRPC 分支如何调用 |
| `api_path` | 默认 HTTP API path |
| `var_map` | `s/cal` 等断言变量如何落到 Python 表达式 |
| `module_abbrevs` | 默认 user_id/req_id 如何生成 |
| `named_templates` | 复杂断言模板白名单 |
| `module_types` | profile 的 module_type 合法值和 requires |
| `builtin_assertion_rules` | Markdown 断言到 Python assert 的规则 |

### 12.3 `codegen_profile_{module}.md`

模块级配置优先级最高。

可控制：

- `module_type`
- `extra_imports`
- `request_overrides`
- `assertion_rules`
- `case_fixtures`
- `case_bodies`
- `case_flows`

## 13. 初学者应该按什么顺序读代码

### 第一轮：只读主干，不追所有 helper

1. `aitest_kit/cli.py`
2. `aitest_kit/workspace.py`
3. `aitest_kit/init_workspace.py`
4. `aitest_kit/codegen/cli.py::_codegen_impl`
5. `aitest_kit/codegen/emitter.py::emit_module`
6. `aitest_kit/report/cli.py::_run_command_impl`

目标：知道每个命令从哪里进、到哪里出。

### 第二轮：读 codegen 数据结构

1. `codegen/parser.py` 的三个 dataclass：`SharedConfig/TestCase/ParseResult`
2. `codegen/ir.py` 的 dataclass：`FileIR/CaseIR/RequestIR/AssertionIR/CaseFlowIR`
3. `codegen/project_config.py::ProjectConfig`
4. `codegen/profile_validator.py::ProfileValidationReport`

目标：先理解数据对象，再读函数逻辑。

### 第三轮：完整走一条 case

建议用 `discount_policy` 的一条 `case_flow` 用例，例如 `TC-DP-008`：

```bash
aitest codegen discount_policy --explain TC-DP-008
aitest codegen discount_policy --dump-ir
```

按这个顺序对照代码：

```text
Markdown TC-DP-008
  -> parser.TestCase
  -> profile.case_flows.TC-DP-008
  -> planner.CaseIR(strategy=structured_case_flow)
  -> ir_renderer._render_case_flow()
  -> generated pytest 函数
```

### 第四轮：读默认 HTTP 分支

建议找一个 `default_http` 模块或临时看没有 `case_flows` 覆盖的 IR。

重点读：

- `_request_for()`
- `_call_for()`
- `_assertions_for()`
- `resolve_assertion()`
- `_render_default_body()`

### 第五轮：读报告链路

建议先执行：

```bash
aitest run discount_policy
```

再读：

```text
report/cli.py::_run_command_impl
report/collector.py::collect_result
report/collector.py::_extract_generated_metadata
report/collector.py::_parse_junit
report/renderer.py::render_markdown
```

目标：理解为什么 generated pytest 里必须有 `__tc_meta__`。

## 14. 重要代码逐行学习清单

后续交互式学习时，我们可以按下面粒度一段段读。

| 章节 | 文件/函数 | 需要真正读懂的点 |
|---|---|---|
| 入口 | `cli.py::main` | click group 如何注册命令 |
| workspace | `workspace.py::push_workspace` | `--workspace` 为什么能跨目录运行 |
| init | `workspace.py::init_workspace` | 模板复制、冲突保护、force 覆盖 |
| codegen CLI | `codegen/cli.py::_codegen_impl` | 模式互斥、profile gate、分流 |
| path | `codegen/cli.py::_load_codegen_paths` | 默认路径和配置路径如何合并 |
| profile gate | `profile_validator.py::validate_profile_module` | Schema、case 引用、module_type 校验 |
| parser | `parser.py::parse_case_file` | Markdown 到结构化数据 |
| parser | `parser.py::_extract_json_block` | JSON 错误和占位符拦截 |
| planner | `planner.py::_strategy_for` | 用例走哪条生成路线 |
| planner | `planner.py::_fixtures_for` | pytest 函数参数怎么来 |
| planner | `planner.py::_request_for` | 默认请求体怎么生成 |
| planner | `planner.py::_assertions_for` | common/case 断言如何合并 |
| planner | `planner.py::_case_flow_for` | YAML steps 如何变成 IR |
| render utils | `render_utils.py::resolve_assertion` | 断言匹配优先级 |
| renderer | `ir_renderer.py::render_file_from_ir` | 文件整体结构如何生成 |
| renderer | `ir_renderer.py::_render_default_body` | 默认 HTTP/gRPC pytest 体 |
| renderer | `ir_renderer.py::_render_case_flow` | case_flow pytest 体 |
| emitter | `emitter.py::emit_file` | 生成前阻断和落盘 |
| run | `report/cli.py::_run_command_impl` | freshness check、pytest、报告写入 |
| report | `collector.py::collect_result` | JUnit + metadata 合并 |
| report | `classifier.py::classify_failure` | 失败分流规则 |
| report | `renderer.py::render_markdown` | result.json 到 report.md |
| health | `health.py::build_codegen_health_report` | 成熟度如何计算 |
| promotion | `promotion.py::analyze_case_body_promotion` | case_body 晋升候选如何判断 |

## 15. 常见误区

### 15.1 “parser 为什么不直接生成 pytest？”

parser 只负责把 Markdown 变成结构化事实。  
是否走默认 HTTP、gRPC、case_flow、case_body，是 planner 的职责。  
这样排查时可以分层：

```text
Markdown 没解析出来 -> parser 问题
策略选错 -> planner/profile 问题
代码渲染错 -> renderer/emitter 问题
pytest 跑错 -> fixture/待测系统/用例问题
```

### 15.2 “为什么需要 Case IR？”

Case IR 是解释层。它保存：

- strategy
- protocol
- fixtures
- request
- call
- assertions
- case_flow
- diagnostics
- source_trace

没有 IR 时，生成错误只能看最终 pytest。  
有 IR 后，可以用 `--dump-ir` 和 `--explain` 精确定位“错在生成前哪一步”。

### 15.3 “为什么不直接长期用 AI 手写 pytest？”

初期可以。迁移新项目时，AI 手写是探索未知的合理方式。  
但一旦模式稳定，就应该沉淀到：

- Markdown 用例
- profile `case_flows`
- profile `assertion_rules`
- fixture helper
- `project_config.yaml`

否则每次生成都依赖 AI 重新理解，会出现不稳定、难 review、难复现的问题。

### 15.4 “generated pytest 能不能手改？”

短期调试可以看，但不应该作为长期源文件维护。  
正确修复位置通常是：

- Markdown 用例错误 -> 改 `test_workspace/cases/`
- profile 错误 -> 改 `codegen_profile_{module}.md`
- fixture 问题 -> 改 `fixtures/{module}.py`
- 通用生成问题 -> 改 `aitest_kit/codegen/`
- 报告问题 -> 改 `aitest_kit/report/`

## 16. 后续交互式学习建议

我们后面可以按 8 次学习推进，每次只读一条主线。

### 第 1 次：项目入口和命令分发

读：

- `aitest_kit/cli.py`
- `aitest_kit/workspace.py`
- `aitest_kit/init_workspace.py`

你需要能回答：

- `aitest codegen --workspace X` 为什么能在别的目录运行？
- `aitest init` 为什么不会默认覆盖已有文件？

### 第 2 次：Markdown parser

读：

- `parser.py::SharedConfig/TestCase/ParseResult`
- `parser.py::_parse_shared_config`
- `parser.py::_parse_cases`

你需要能回答：

- 共享配置和单条 TC 分别进了哪个对象？
- `{{var}}` 为什么会被拦截？

### 第 3 次：profile gate

读：

- `profile.py`
- `profile_validator.py::validate_profile_module`

你需要能回答：

- profile 的 YAML 是怎么从 Markdown 里抽出来的？
- 为什么同一个 case 不能同时出现在 `case_bodies` 和 `case_flows`？

### 第 4 次：Case IR

读：

- `ir.py`
- `planner.py::build_file_ir`
- `planner.py::_strategy_for`

你需要能回答：

- 一条用例的生成策略是怎么选出来的？
- `source_trace` 记录了什么？

### 第 5 次：断言解析

读：

- `render_utils.py::resolve_assertion`
- `project_config.yaml::builtin_assertion_rules`

你需要能回答：

- 为什么 profile 规则优先于 project_config 规则？
- UNPARSED 是怎么产生的？

### 第 6 次：pytest 渲染

读：

- `ir_renderer.py::render_file_from_ir`
- `_render_default_body`
- `_render_case_flow`

你需要能回答：

- generated pytest 的类名、函数名、`__tc_meta__` 是怎么来的？
- default_http 和 case_flow 渲染差异在哪里？

### 第 7 次：执行报告

读：

- `report/cli.py::_run_command_impl`
- `collector.py::collect_result`
- `renderer.py::render_markdown`

你需要能回答：

- `aitest run` 为什么先跑 `codegen --check`？
- JUnit XML 怎么和 TC ID 对齐？

### 第 8 次：health / promotion

读：

- `health.py`
- `promotion.py`

你需要能回答：

- 模块成熟度 L0/L1/L2/L3 怎么算？
- 当前 promotion 为什么只是 review-only，而不是自动修改 profile？

## 17. 一句话记忆版

```text
cli 接命令
workspace 切目录
parser 读 Markdown
profile_validator 守门
project_config 给默认规则
planner 产 Case IR
render_utils 解断言
ir_renderer 写 pytest 文本
emitter 落盘
run 调 pytest
collector 合并 JUnit 与 __tc_meta__
renderer 写 report.md
health 看成熟度
promotion 找可沉淀模式
```

如果后续学习中卡住，优先问这三个问题：

1. 现在的数据对象是什么？`ParseResult`、`CaseIR`、还是 `RenderedFile`？
2. 当前错误是在 parser、profile gate、planner、renderer、fixture、还是待测系统？
3. 这个逻辑属于框架层、项目配置层，还是模块配置层？
