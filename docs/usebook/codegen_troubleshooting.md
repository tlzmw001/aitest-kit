# Codegen Troubleshooting

本文记录 codegen 迁移和日常生成中最常见的失败类型。原则是先看门禁，再看 IR，最后看 generated pytest。

推荐顺序：

```bash
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --explain TC-XXX-001
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest run --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

## 空 workspace

现象：

```text
No modules found under the configured cases directory.
Next step: create a target/module registry and a suite.yaml, or keep using legacy module cases.
```

含义：

- CLI 正常。
- workspace 还没有 target/module/suite 测试资产。

处理：

- 创建 `test_workspace/targets/{target}/target.yaml`。
- 创建 `test_workspace/targets/{target}/modules/{module}.yaml`。
- 创建 `test_workspace/targets/{target}/profiles/profile_{module}.md`。
- 创建 `test_workspace/suites/{target}/{suite}/suite.yaml` 和 Markdown 用例。

## E001: JSON 解析失败

常见原因：

- Markdown 的 JSON 基础请求体不是合法 JSON。
- JSON 中出现 `{{user_id}}` 这类模板占位符。
- 使用了单引号、尾逗号、注释。

处理：

- 基础请求体必须能被 `json.loads` 解析。
- 变化字段填合法默认值。
- case 级变化写到“请求覆盖”供 review；真实执行差异优先写 profile 的 `requests.<case_id>.patches`，简单字段覆盖可用 `overrides`。

## E002: 缺少基础请求体

常见原因：

- Markdown 没有 JSON 基础请求体；可写 `基础请求体`、`基础请求体（JSON）` 或兼容旧写法 `基础请求体（HTTP）`。
- 模块不是默认 HTTP，或用例需要 gRPC/SDK/多端点动作，但也没有 `case_bodies` 或 `case_flows`。

处理：

- 单请求模块：补完整基础请求体。
- 多步骤模块：在 profile 中补 `case_flows`。
- 复杂控制流模块：临时使用 `case_bodies`。

## E202: gRPC 用例缺少显式执行策略

常见原因：

- Markdown 场景变量写了 `协议：gRPC`。
- suite profile 没有为该 case 配置 `case_flows` 或 `case_bodies`。

处理：

- 在 fixture/helper 中封装真实 gRPC 调用。
- 在 suite profile 的 `case_flows` 中显式调用该 helper。
- 若控制流复杂、需要 mock/并发/生命周期管理，先用 `case_bodies`，稳定后再评估是否晋升为 `case_flows`。

## profile schema 错误

现象：

```text
Profile validation summary: modules=1, errors=1, warnings=0
```

常见原因：

- profile 没有 YAML 代码块。
- YAML 字段名拼错。
- `case_bodies` / `case_flows` 的 case_id 不符合 `TC-XXX-001`。
- `case_flows.steps` 为空。

处理：

- 对照 [codegen_profile_guide.md](./codegen_profile_guide.md)。
- 先修到 `--validate-profile` 为 OK，再继续 codegen。

## 诊断入口怎么读

profile gate 通过后，优先用这三个入口排查：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --explain TC-XXX-001
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --health-report
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
```

含义：

- `--explain TC-ID`：人类可读的单 case 诊断卡片。重点看 `Strategy`、`Case flow`、`Request bindings`、`Request review`、`Assertions`、`Diagnostics`、`Review hint`。
- `--health-report`：suite/module 健康度和下一步行动。重点看 `unparsed_cases`、`case_body_cases`、`manual_cases`、`structured_assertion_target_counts`、`request_binding_counts`、`profile_variable_counts`、`review_focus`、`next_actions`。
- `--dump-ir`：机器可读 JSON。适合给 AI 或脚本做精确分析，不适合人工直接浏览大批 case。

典型判断：

- `Review hint` 提示 UNPARSED：优先补 `structured_assertions`、`assertion_rules` 或 fixture/helper。
- `Case flow` 中没有预期的 `save_as`：修 suite profile 的 `case_flows.steps`。
- `Request bindings` 没有预期 patches/overrides：修 suite profile 的 `requests.<case_id>`。
- `Request bindings` 里的 `value_from` 来源不符合预期：修 suite profile 的 `variables.defaults` / `variables.cases.<case_id>`，不要把 env 值写进 profile。
- `review_focus` 出现 request patch env 变量：确认 env 名正确、运行环境能提供该变量，并用 `--explain TC-ID` 复核单条 case。
- `structured_assertion_target_counts` 中 target 异常：检查 `structured_assertions.target` 是否应该来自 `resp`、`save_as` 或 `assign`。

## requests / JSON Patch 错误

常见诊断：

- `E501`：`requests.<case_id>.patches` 格式不合法，例如 `path` 不是 JSON Pointer、`add/replace` 同时写了 `value` 和 `value_from`、`remove` 携带了 `value` 或 `value_from`。
- `E507`：`requests.<case_id>.patches[].value_from` 引用了未定义的 profile variable。

处理：

- 精确请求变更优先写 `patches`，不要把 JSON 对象作为字符串塞进 `case_flow.kwargs`。
- dict 整体替换：`op: replace` + `path: /field` + `value: {...}`。
- list 追加：`op: add` + `path: /items/-`。
- list 指定位置替换：`op: replace` + `path: /items/0`。
- 删除字段：`op: remove` + `path: /debug`。
- 需要 case/env 变量时，用 `value_from: name`，并在 `variables.defaults` 或 `variables.cases.<case_id>` 定义。

## structured_assertions 错误

常见诊断：

- `E529`：结构化断言字段不合法，例如 `type` 不支持、缺必填字段、`target` 不是变量名、JSONPath 不合法。
- `E530`：结构化断言的 `target` 在当前生成策略下不可用。

处理：

- default HTTP/gRPC 用例只能写 `target: resp`。
- `case_flow` 用例只能引用该 flow 中 `save_as` 或 `assign` 产出的变量。
- `case_bodies`、pure manual、skipped 用例不挂 `structured_assertions`。
- 复杂业务计算不要扩展 YAML 控制流，封装到 fixture/helper 方法，再通过 `case_flow.call` 调用。

## case_flow 引用未注入变量

现象：

```text
NameError: name 'tmp_path' is not defined
NameError: name 'caplog' is not defined
```

常见原因：

- `case_flow.args` / `kwargs` 直接引用了 pytest fixture 名，例如 `tmp_path`、`caplog`、`monkeypatch`、`mocker`。
- 当前 renderer 不会把这些名字自动加入 generated pytest 函数签名。

处理：

- `case_flow` 只引用 codegen 生成的变量：`object`、前序 `save_as`、`assign`、`{var: name}`、`{request_ref: ...}`。
- 临时目录、日志捕获、mock、monkeypatch 和 cleanup 封装到 fixture/helper 方法。
- suite profile 只调用该方法并断言返回结果。

## unknown module_type

常见原因：

- profile 写了 `module_type: xxx`，但 `aitest_config/aitest.yaml` 的 `codegen.module_types` 没有定义。

处理：

- 如果是拼写错误，改 profile。
- 如果是新模块类别，在 `aitest.yaml` 中新增 module_type，并明确是否需要 `case_bodies` 或 `case_flows`。

## stale generated

现象：

```text
Generated files are stale
```

或 `--check` 提示生成文件与当前 Markdown/profile 不一致。

含义：

- Markdown、profile、`aitest.yaml` 或 emitter 已改变。
- generated pytest 还没有重新生成。

处理：

```bash
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
```

期望第二条输出：

```text
All generated files are up to date.
```

## pytest collect 找不到 test_workspace

现象：

```text
ModuleNotFoundError: No module named 'test_workspace'
```

常见原因：

- 从 workspace 外层目录直接执行 `python -m pytest /path/to/project/test_workspace/generated`。

处理：

推荐：

```bash
cd /path/to/project
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

或显式设置：

```bash
PYTHONPATH=/path/to/project python -m pytest /path/to/project/test_workspace/generated --collect-only -q
```

## fixture 缺失

现象：

```text
fixture 'setup_xxx' not found
```

常见原因：

- generated pytest 引用了 `setup_{module}`。
- target/suite 模式下，`test_workspace/targets/{target}/fixtures/{module}.py` 没有定义该 fixture，或 `module.yaml.fixture.default_fixture` 写错。
- 旧 workspace 模块模式下，`test_workspace/tests/fixtures/{module}.py` 没有定义该 fixture，或 fixture 文件没有被 `test_workspace/tests/conftest.py` 注册。

处理：

- 在 target 模块 fixture 文件中补 `setup_{module}`。
- 检查 `module.yaml` 的 `fixture.file/default_fixture`。
- 旧 workspace 模块模式再检查 `conftest.py` 的插件注册方式。
- 不要直接改 generated pytest。

## 环境变量缺失

现象：

```text
DISCOUNT_SYSTEM_BASE_URL is required for discount_policy tests
```

含义：

- fixture 要求外部服务地址，但环境变量未设置。

处理：

- 启动待测服务。
- 设置模块约定的环境变量。
- 如果服务未就绪，先记录为环境问题，不要放宽断言或 skip 用例。

## UNPARSED ASSERTION

现象：

generated pytest 中出现：

```python
# UNPARSED ASSERTION:
```

含义：

- parser 找到了断言文本。
- emitter 没有匹配到稳定规则。

处理：

1. 少量一次性断言：由 AI 补写 generated 片段，再评估是否需要沉淀。
2. 重复断言：写入 profile `assertion_rules`。
3. 项目通用断言：写入 `aitest_config/aitest.yaml` 的 `codegen.builtin_assertion_rules`。
4. 多步骤流程：改为 `case_flows`。

## 待测系统 bug 与用例问题分流

不要为了让测试通过而：

- 放宽断言。
- skip 失败用例。
- 伪造响应。
- 直接修改 generated pytest。

建议分流：

- 文档不清楚：知识库标 `[?]`。
- 用例不可测：修改 Markdown 或记录为测试基础设施需求。
- fixture/codegen 问题：修改 fixture/profile/helper/`aitest.yaml`。
- 待测系统 bug：记录到 `test_workspace/results/`，保留复现命令、实际结果和期望结果。
