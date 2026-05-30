# test-codegen emitter 生成规则参考

## 文件结构

- target/suite 中的 `{case_file}.md` -> `test_workspace/generated/{target}/test_{module}_{suite}_{case_file_stem}.py`

## 类和函数命名

- 类名：`Test{Module}Business`（模块名首字母大写 + Business/Boundary）
- 函数名：`test_tc_mod_001`（TC ID 小写，连字符转下划线）
- docstring：`"""TC-MOD-001：{title}"""`

## setup 处理

场景变量 -> `# SETUP:` 注释 + `setup_{module}(case_id="TC-XXX")` 调用。

target/suite 模式下，fixture 由 `test_workspace/targets/{target}/fixtures/{module}.py` 提供，helper 由 `test_workspace/targets/{target}/helpers/` 提供。codegen 根据 `module.yaml.fixture.file/default_fixture` 自动注入 fixture import；target helper 文件存在时优先生成 target helper import。

新增模块时需要：
1. 创建 `test_workspace/targets/{target}/fixtures/{module}.py`
2. 创建或更新 `test_workspace/targets/{target}/modules/{module}.yaml`
3. 创建 `test_workspace/targets/{target}/profiles/profile_{module}.md`
4. 确认 generated pytest 能引用到 target fixture/helper

## fixture 编写检查清单

编写新模块的 `setup_{module}` fixture 前，确认：

1. **部署拓扑** — 服务间调用关系，确认环境变量（服务 URL、外部依赖地址等）
2. **可用 API** — fixture 需要调用的管理接口或数据准备接口
3. **隔离策略** — 每条用例的数据如何隔离（tmp_path、唯一 user_id、teardown 恢复）
4. **teardown** — 所有副作用都能恢复（配置、测试数据、外部依赖状态）
5. **profile 映射** — case_flows/case_bodies/request_overrides 是否覆盖当前用例
6. **服务地址** — 从项目专属环境变量读取（如 `SERVICE_BASE_URL` 或 `{TARGET}_BASE_URL`），可兼容 `HTTP_BASE_URL`；不要硬编码端口或 URL
7. **环境缺失** — 可执行 API 测试缺少服务地址时用 `pytest.fail`，不要用 `pytest.skip` 掩盖环境未配置
8. **HTTP 客户端** — 使用 `httpx` 时显式指定 `httpx.HTTPTransport()`，避免 macOS/CI 系统代理影响本地 HTTP 测试
9. **黑盒边界** — fixture 不 import 待测系统内部模块，不读取目标项目源码/内部测试来推断业务规则

## 断言生成

断言匹配优先级：profile assertion_rules > `aitest.yaml.codegen.builtin_assertion_rules` > named_templates。

通用断言模式（框架内置）：

| 断言模式 | 生成方式 |
|---------|---------|
| `response.code == 固定值` | `assert resp["code"] == 固定值` |
| `response.xxx == 固定值` | `assert resp["xxx"] == 固定值` |
| `set(response.results[*].item_id) == {集合}` | `assert {r["item_id"] for r in resp["results"]} == {集合}` |
| `len(xxx) == N` | `assert len(xxx) == N` |
| `[manual]` 标记 | `# MANUAL CHECK: {原文}` |
| 无法翻译 | `# UNPARSED ASSERTION: {原文}` |

项目专属断言模式见 `aitest_config/aitest.yaml` 的 `codegen.builtin_assertion_rules`。

`round(..., 4)` -> `pytest.approx(..., abs=1e-4)`。`clamp(x)` -> `max(0, min(1, x))`。

## 请求生成

1. 从共享配置取基础请求体，场景变量 `请求覆盖` 合并
2. gRPC 用例通过场景变量中的 `协议：gRPC` 标识，Case IR 应记录该判断来源
3. 共享配置中的 HTTP 基础请求体必须是合法 JSON，不使用 `{{placeholder}}`；case 级差异通过场景变量或 profile `request_overrides` 合并

## case_body 与 case_flow

- `case_bodies` 是复杂场景的逃生通道，适合多端点、多请求、副作用、日志、隔离服务、并发等默认模板难以覆盖的用例。
- `case_flows` 是已验证且结构稳定的 `case_bodies` 晋升形态，适合"调用 helper -> 保存结果 -> 派生变量 -> 观察副作用 -> 断言/注释"这类重复多步骤流程；当前支持 `call`、`assign`、`assert`、`comment` 四类 step。
- 同一个 case_id 不允许同时出现在 `case_bodies` 和 `case_flows`；正式晋升为 `case_flow` 时必须删除旧 `case_body`，否则 codegen 会报错。
- `case_flow` 的 `assert` step 必须写成可执行 Python 断言，例如 `assert resp["code"] == 0`；裸表达式如 `` `resp == ERR` `` 会被 profile 校验拒绝。
- `case_flow` 的 `args/kwargs` 可以用 `{var: name}` 引用 profile `variables`；变量来源只支持 `env` 或 `value`，`env` 可从进程环境变量、当前工作目录 `.env` 或 `AITEST_ENV_FILE` 指定文件读取；缺 env 时运行失败且只显示 env 名。
- profile 顶层可以写 `default_fixture`、`default_object`、`default_case_setup`，用于给多条 `case_flows` 统一补 fixture/object/factory setup；`default_case_setup.kwargs.case_id: "{case_id}"` 会替换为当前用例 ID。
- 如果 `case_flow` 自身没有 `fixture`，必须能从 `default_fixture` 得到；单条 flow 显式 `fixture/object` 时覆盖顶层默认值。
- 不要把复杂 Python 控制流硬塞进 `case_flow`；包含线程、进程、mock、复杂文件生命周期时继续保留 `case_body`。
- 新增 `case_flow` 前必须能解释它比原 `case_body` 更稳定、更可读、更可校验。
- 生成或迁移前显式运行 `--validate-profile`；普通生成也会自动硬门禁，用于提前发现 JSON Schema 格式、case_id 引用、case_flow assert 和 module_type 必需字段问题。
- `--analyze-promotion --write-report` 和 `--suggest-promotion-patch` 的产物写入 `test_workspace/reports/codegen/latest/`，不要放到 `plans/`；patch 草案默认只供 review，不自动修改 profile。
- `--health-report --write-report` 输出模块成熟度、case_flow/case_body/UNPARSED 和断言命中统计，用来决定下一轮沉淀优先级。

## 标记处理

- `[manual]` -> `@pytest.mark.manual` + 断言为注释
- `[!可行性存疑: ...]` -> 跳过不生成，末尾 `# SKIPPED:`

## 后续：编写 codegen profile

测试调通后编写 module profile 或 suite profile：

- module profile：`test_workspace/targets/{target}/profiles/profile_{module}.md`，承载 L1 级稳定能力
- suite profile：`{suite_dir}/profile_{suite}_suite.md`，只覆盖该 suite 的 case_id

profile 应包含：

| 章节 | 内容 |
|------|------|
| **fixture 依赖** | fixture 名称、来源、调用方式 |
| **setup_{module} 做了什么** | fixture 内部操作步骤 |
| **新增用例时如何扩展** | dict/map 添加条目格式 |
| **请求模板** | 固定字段、差异字段、helper 用法 |
| **profile variables** | 本 suite/case 使用的账号、token、URL path、非法值等变量面板 |
| **断言模式** | 断言 -> pytest 映射表 |
| **setup 映射** | 场景变量 -> fixture/case_flow 映射 |
| **case_bodies / case_flows** | 复杂用例的自定义执行体，或已晋升的结构化多步骤流程 |
| **已知阻塞项** | 无法自动化的用例及原因 |
| **调试经验** | 模块特有排错经验 |
| **emitter 规则** | YAML code block，模块特有断言规则 |

参考已有模块的 profile 作为结构模板。

## 后续：emitter-build

测试全部通过且 profile 编写完成后，调用 `/emitter-build` 提取确定性模板。
