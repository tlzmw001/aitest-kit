# Codegen Troubleshooting

本文记录 codegen 迁移和日常生成中最常见的失败类型。原则是先看门禁，再看 IR，最后看 generated pytest。

推荐顺序：

```bash
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --workspace /path/to/project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
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

- Markdown 的 `基础请求体（HTTP）` 不是合法 JSON。
- JSON 中出现 `{{user_id}}` 这类模板占位符。
- 使用了单引号、尾逗号、注释。

处理：

- 基础请求体必须能被 `json.loads` 解析。
- 变化字段填合法默认值。
- case 级变化写到“请求覆盖”或 profile 的 `request_overrides`。

## E002: 缺少基础请求体

常见原因：

- Markdown 没有 `基础请求体（HTTP）`。
- 模块不是默认 HTTP/gRPC，但也没有 `case_bodies` 或 `case_flows`。

处理：

- 单请求模块：补完整基础请求体。
- 多步骤模块：在 profile 中补 `case_flows`。
- 复杂控制流模块：临时使用 `case_bodies`。

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

## unknown module_type

常见原因：

- profile 写了 `module_type: xxx`，但 `aitest_config/project_config.yaml` 的 `module_types` 没有定义。

处理：

- 如果是拼写错误，改 profile。
- 如果是新模块类别，在 `project_config.yaml` 中新增 module_type，并明确是否需要 `case_bodies` 或 `case_flows`。

## stale generated

现象：

```text
Generated files are stale
```

或 `--check` 提示生成文件与当前 Markdown/profile 不一致。

含义：

- Markdown、profile、project_config 或 emitter 已改变。
- generated pytest 还没有重新生成。

处理：

```bash
aitest codegen --workspace /path/to/project <module>
aitest codegen --workspace /path/to/project <module> --check
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

- 从 workspace 外层目录直接执行 `python -m pytest /path/to/project/test_workspace/tests/generated`。

处理：

推荐：

```bash
cd /path/to/project
python -m pytest test_workspace/tests/generated --collect-only -q
```

或显式设置：

```bash
PYTHONPATH=/path/to/project python -m pytest /path/to/project/test_workspace/tests/generated --collect-only -q
```

## fixture 缺失

现象：

```text
fixture 'setup_xxx' not found
```

常见原因：

- generated pytest 引用了 `setup_{module}`。
- target/suite 模式下，`test_workspace/targets/{target}/fixtures/{module}.py` 没有定义该 fixture，或 `module.yaml.fixture.default_fixture` 写错。
- legacy 模块模式下，`test_workspace/tests/fixtures/{module}.py` 没有定义该 fixture，或 fixture 文件没有被 `test_workspace/tests/conftest.py` 注册。

处理：

- 在 target 模块 fixture 文件中补 `setup_{module}`。
- 检查 `module.yaml` 的 `fixture.file/default_fixture`。
- legacy 模块模式再检查 `conftest.py` 的插件注册方式。
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
3. 项目通用断言：写入 `project_config.yaml` 的 `builtin_assertion_rules`。
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
- fixture/codegen 问题：修改 fixture/profile/helper/project_config。
- 待测系统 bug：记录到 `test_workspace/results/`，保留复现命令、实际结果和期望结果。
