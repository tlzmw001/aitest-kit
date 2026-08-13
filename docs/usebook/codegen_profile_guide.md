# Codegen Profile Guide

`profile.md` 是 target/module 级生成配置。它记录模块稳定的变量默认值和断言规则；模块类型由同目录的 `module.yaml` 声明。

独立 case suite 在用例目录旁放 `profile_{suite}_suite.md`。module profile 固定为 `test_workspace/targets/{target}/modules/{module}/profile.md`；suite profile 跟随用例批次，优先放本批用例的 `variables`、`requests`、`structured_assertions`、`case_flows` 和 `case_bodies`。

profile 的定位是“AI 生成、代码校验、人工 review 的稳定中间态”。人类不需要把它当业务文档手写到底；更推荐让 AI 根据 Markdown、Module Harness、target helper 和知识库生成 profile，再用 `--validate-profile`、`--explain`、`--health-report`、generated pytest 和执行报告 review。

profile 文件必须包含一个 YAML 代码块：

~~~markdown
# demo codegen profile

```yaml
assertion_rules: []
```
~~~

profile 会先经过 JSON Schema 和语义校验。校验失败时，普通 codegen、`--check`、`--dump-ir`、`--explain` 和 promotion 分析都会阻断。

## module_type

`module_type` 是模块能力分类，写在 `test_workspace/targets/{target}/modules/{module}/module.yaml`，取值来自 `aitest_config/aitest.yaml` 的 `codegen.module_types`。

```yaml
target: demo_system
module: demo
module_type: multi_endpoint
```

模板 workspace 默认包含：

```yaml
module_types:
  standard_http:
    description: "Default single-endpoint HTTP module"
  multi_endpoint:
    description: "Module with multiple endpoints or custom flows"
    requires: [case_bodies]
  isolated_service:
    description: "Module requiring isolated service/runtime control"
    requires: [case_bodies]
```

如果某类模块要求复杂流程，profile gate 会检查 suite 是否提供了 `case_flows` 或 `case_bodies`。不要在 module profile 或 suite profile 中重复声明 `module_type`。

## requests

`requests` 是统一请求绑定层。默认 HTTP 路线和 `case_flows` 都可以使用它构造请求体。

当前确定性 codegen 生成真实请求体时，以这里的 `requests.<case_id>` 为准；Markdown 场景变量中的“请求覆盖”主要用于人类 review 和 trace。

新项目优先使用 `patches` 表达精确请求变更。`overrides` 只适合少量简单字段覆盖；涉及 dict 整体替换、list 指定位置、追加、删除或变量注入时，用 `patches`。

```yaml
variables:
  defaults:
    expected_status:
      value: 0
requests:
  TC-DEMO-001:
    overrides:
      user_id: "u_demo_001"
    patches:
      - op: replace
        path: /payload
        value:
          kind: demo
          items: []
      - op: add
        path: /payload/items/-
        value_from: expected_status
      - op: remove
        path: /debug
```

约束：

- key 必须是 `TC-XXX-001` 这类格式。
- `overrides` 必须是对象，只写普通简单覆盖；不要依赖它表达复杂 list 语义。
- `patches` 使用 JSON Patch 子集，支持 `add`、`replace`、`remove`。
- `patches.path` 是 JSON Pointer，必须以 `/` 开头；list 追加使用 `/-`。
- `add` / `replace` 必须且只能写 `value` 或 `value_from` 其中一个。
- `remove` 不允许写 `value` 或 `value_from`。
- `value_from` 引用 `variables.defaults` 或 `variables.cases.<case_id>` 中定义的变量。
- 只写 case 级差异，不要复制完整基础请求体。
- 不要把 JSON 对象写成字符串传给 `case_flow.kwargs.body`；需要请求体时用 `{request_ref: self}`。

## assertion_rules

当某类自然语言或表达式断言会重复出现时，用 `assertion_rules` 固化：

```yaml
assertion_rules:
  - name: demo_score
    regex: '^score == (?P<value>\d+)$'
    template: 'assert resp["score"] == {value}'
```

匹配优先级：

```text
profile assertion_rules > aitest.yaml builtin_assertion_rules > UNPARSED
```

适用：

- 断言表达稳定。
- 生成代码是确定性的。
- 同类断言会重复出现。

不适用：

- 需要多步骤前置动作。
- 断言依赖复杂临时变量。
- 只有一条用例临时出现，尚不值得沉淀。

## structured_assertions

`structured_assertions` 是 TC-ID 绑定的结构化断言，适合表达 JSONPath、集合遍历和长度断言。它的目标是减少这类断言退化为 raw assert 或 `case_bodies`。

```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: publish_status_smoke

case_flows:
  TC-GW-001:
    steps:
      - call: harness.list_items
        save_as: resp

structured_assertions:
  TC-GW-001:
    - type: jsonpath_all_equals
      target: resp
      path: $.data.items[*].publishStatus
      equals: 0
    - type: jsonpath_len_gte
      target: resp
      path: $.data.items
      value: 1
```

第一版支持：

- `jsonpath_equals`
- `jsonpath_exists`
- `jsonpath_not_exists`
- `jsonpath_all_equals`
- `jsonpath_any_equals`
- `jsonpath_len_equals`
- `jsonpath_len_gte`
- `jsonpath_field_in_set`

约束：

- `structured_assertions` 属于 suite profile，不写进 module profile。
- key 必须是当前 suite Markdown 中存在的 case_id。
- `target` 必须是当前 generated pytest 中已经存在的变量名。
- default HTTP 路线只允许 `target: resp`。
- `case_flow` 路线只允许引用当前 flow 中 `save_as` 或 `assign` 产生的变量，例如 `resp`、`query_resp`。
- `case_bodies`、manual、skipped 用例不使用 `structured_assertions`；复杂业务计算应封装为 Harness capability。
- `path` 必须是合法 JSONPath。
- `jsonpath_equals`、`jsonpath_all_equals`、`jsonpath_any_equals` 使用 `equals`。
- `jsonpath_len_equals`、`jsonpath_len_gte` 使用非负整数 `value`。
- `jsonpath_field_in_set` 使用非空数组 `values`。
- 复杂业务计算应封装为 Harness capability，不在 YAML 里扩展循环或条件语言。

调试方式：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --explain TC-GW-001
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --health-report
```

`--explain` 中应能看到：

```text
Assertions:
  - kind: structured_assertion
    source: jsonpath_all_equals resp $.data.items[*].publishStatus == 0
    resolved_by: profile.structured_assertions.TC-GW-001
```

如果 `target` 写错，profile gate 会先报 `E530`，不会进入 IR/emitter。`--health-report` 会汇总 `structured_assertion_target_counts`，用于批量检查 structured assertion 主要绑定在哪些中间变量上。

当 suite profile 使用 `requests.<case_id>.patches[].value_from` 时，`--explain` 会在 `Request bindings` 中展示变量来源，例如 `provider=value source=profile.variables.defaults.expected_status` 或 `provider=env env=SUB2API_USER_TOKEN source=profile.variables.cases.TC-XXX-001.auth_token`。输出只显示 env 名，不显示 env 值。

`--explain` 还会输出 `Request review`，用于快速检查该 case 是否使用了 request overrides、JSON Patch、env 变量或复杂 JSON Pointer path。`--health-report` 会汇总 `profile_variable_counts` 和 `review_focus`，用于批量定位需要人工 review 的 request/profile binding。

## variables

`variables` 是 suite/profile 的变量面板，适合把不同 case 使用的账号、密码、token、URL path、非法值等从 fixture 和 case_flow 里拆出来。

第一版只支持两种来源：

- `env`：运行时从环境变量读取。generated pytest 只写 env 名，不写 env 值。
- `value`：profile 字面量，适合错误密码、非法枚举、固定 path 片段等。

`env` 的读取顺序：

1. 先读当前进程的真实环境变量。
2. 如果缺失，再读 dotenv 文件：默认是当前工作目录下的 `.env`。
3. 如需指定其他 dotenv 文件，可设置 `AITEST_ENV_FILE=/path/to/.env`；设置后使用该文件替代当前目录 `.env`。

`.env` 文件只作为本地运行时输入，不会被 codegen 写入 generated pytest；报告和错误信息只显示 env 名，不显示 env 值。

`aitest run` 也会读取同一套 dotenv 配置，并把缺失于当前 shell 的变量注入 pytest 子进程。因此 fixture 中读取必需变量时应使用：

```python
from aitest_kit.runtime_variables import require_env

base_url = require_env("SUB2API_BASE_URL")
```

这样缺失 env 会在报告中归类为 `PRECONDITION_MISSING`，而不是普通 fixture error。变量可以通过以下方式提供：

```bash
AITEST_ENV_FILE=/tmp/sub2api-test.env aitest run --target sub2api --module gateway_api
```

优先级保持一致：真实 shell 环境变量优先，dotenv 文件只补缺失变量。显式设置 `AITEST_ENV_FILE` 但文件不存在时，本次运行会生成 `BLOCKED_RUN`，不会继续执行 pytest。

```yaml
profile_scope: case_suite
parent_module: management_auth_user
suite: login_smoke
variables:
  defaults:
    base_url:
      env: SUB2API_BASE_URL
  cases:
    TC-AUTH-001:
      username:
        env: SUB2API_NORMAL_USER_EMAIL
      password:
        env: SUB2API_NORMAL_USER_PASSWORD
    TC-AUTH-002:
      username:
        env: SUB2API_NORMAL_USER_EMAIL
      password:
        value: wrong-password
```

`case_flow` 的 `args` / `kwargs` 通过 `{var: name}` 引用；`requests.patches` 通过 `value_from` 引用：

```yaml
case_flows:
  TC-AUTH-001:
    steps:
      - call: harness.login
        kwargs:
          username:
            var: username
          password:
            var: password
        save_as: resp
      - assert: 'assert resp.status_code == 200'

requests:
  TC-AUTH-001:
    patches:
      - op: replace
        path: /auth/password
        value_from: password
```

约束：

- 变量名必须是合法 Python 标识符。
- 每个变量只能声明 `env` 或 `value` 之一。
- `{var: name}` 必须能在 `variables.defaults` 或 `variables.cases.{case_id}` 中找到。
- `value_from: name` 必须能在 `variables.defaults` 或 `variables.cases.{case_id}` 中找到。
- 缺 env 且 `.env` / `AITEST_ENV_FILE` 也无法提供时，测试失败，错误信息只显示 env 名，不显示 env 值。
- 不要让 fixture 按 case_id 分发不同账号或 token；case 级数据差异放到 `variables`。

## Module Harness

每个模块使用固定的 canonical module package：

```text
test_workspace/targets/{target}/modules/{module}/
├── module.yaml
├── profile.md
├── fixture.py
└── harness.py
```

- `harness.py` 定义 `{Module}Harness`，提供模块级测试能力。
- `fixture.py` 只负责 pytest 生命周期和依赖装配，公开 fixture 固定为 `setup_{module}`，返回或 yield `{Module}Harness`。
- codegen 自动把 `setup_{module}` 注入 generated pytest，并把它绑定为 `harness`。
- 单模块能力、业务动作、状态准备和复杂控制逻辑放在 module package 内。
- 只有同一 target 内至少两个 module 已经实际复用的纯技术适配，才放到 `test_workspace/targets/{target}/helpers/`。
- 不建立 `test_workspace/helpers/`。

Harness 是 `case_flow` 的固定能力入口。profile 不配置 fixture、object 或工厂初始化步骤，AI 和人只需要判断“该能力是否属于这个模块”。

## case_flows

`case_flows` 是结构化多步骤流程，适合编排稳定的 Harness capability：

```yaml
requests:
  TC-DEMO-002:
    patches:
      - op: replace
        path: /user_id
        value: "u_demo_002"
      - op: replace
        path: /value
        value: 3
case_flows:
  TC-DEMO-002:
    steps:
      - call: harness.create
        kwargs:
          body: {request_ref: self}
        save_as: create_resp
      - assert: 'assert create_resp["code"] == 0'
      - call: harness.get
        kwargs:
          user_id: "u_demo_002"
        save_as: get_resp
      - assert: 'assert get_resp["value"] == 3'
```

`harness` 由模块固定 fixture 自动提供，不是 profile 变量，也不能在单条 flow 中覆盖。每条 flow 直接从 `harness.<capability>` 开始；用例差异通过 `variables`、`requests`、参数和前序返回值表达。

约束：

- case_id 必须匹配 `^TC-[A-Z0-9]+-[0-9]+$`。
- `steps` 至少一项。
- `assert` 必须写成可执行 Python 断言，例如 `'assert resp["code"] == 0'`；不要写裸表达式。
- `kwargs` 中需要请求体时优先使用 `{request_ref: self}` 或 `{request_ref: TC-XXX-001}`。
- `call` 的根对象必须是 `harness` 或前序 `save_as` / `assign` 产生的变量。
- `case_flow` 只能引用 codegen 生成的变量：`harness`、前序 `save_as`、`assign`、`{var: name}` 和 `{request_ref: ...}`。
- 不要直接引用 pytest fixture 变量，例如 `tmp_path`、`caplog`、`monkeypatch`、`mocker`。当前 renderer 不会把这些名字自动加入 generated pytest 函数签名。
- 需要临时目录、日志捕获、mock、monkeypatch、循环、条件或 cleanup 时，封装为 Harness capability，`case_flow` 只调用该能力并断言返回结果。

适用：

- 多端点 CRUD。
- 先写入再查询。
- 先执行动作再验证状态。
- 流程稳定，值得代码确定性生成。

错误示例：

```yaml
case_flows:
  TC-DEMO-004:
    steps:
      - call: harness.load_from_temp_file
        args:
          - tmp_path
        save_as: result
      - assert: 'assert result is True'
```

这会生成类似 `harness.load_from_temp_file(tmp_path)`，但测试函数签名没有 `tmp_path`，运行时报 `NameError`。

正确做法是把 pytest 运行器细节下沉到 Harness capability：

```python
def load_from_temp_file_auto(self) -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "data.json"
        path.write_text("{}")
        return self.load_from_file(path)
```

suite profile 只保留编排：

```yaml
case_flows:
  TC-DEMO-004:
    steps:
      - call: harness.load_from_temp_file_auto
        save_as: result
      - assert: 'assert result is True'
```

## case_bodies

`case_bodies` 是逃生通道，可以直接提供测试函数 body 行。codegen 仍会注入当前模块的 `harness`：

```yaml
case_bodies:
  TC-DEMO-003:
    - 'resp = harness.reload_config()'
    - 'assert resp["code"] == 0'
```

适用：

- 进程生命周期。
- 并发竞争。
- mock patch。
- 文件系统生命周期。
- 复杂日志捕获。

复杂循环、条件、异常处理和生命周期控制优先封装为 Harness capability；只有测试函数本身仍必须保留复杂编排时才使用 `case_bodies`。不建议长期滥用，稳定后应优先晋升为：

```text
case_bodies -> Harness capability + case_flows -> structured_assertions / assertion_rules / aitest.yaml builtin rules
```

## AI 编写 profile 的推荐顺序

1. 读 `suite.yaml`，确认 `target`、`module`、`suite` 和 `case_files`。
2. 读 canonical module package，确认 `module.yaml` 的 module_type 和 knowledge_refs，以及 `harness.py` 已有 capability。
3. 读 `profile.md`，复用模块级变量默认值和共享断言规则。
4. 优先复用 Harness 已有 capability；确有缺口时回到 scaffold 增量补充模块能力。
5. 只为当前 suite 写 suite profile。
6. 请求差异优先写 `requests.<case_id>.patches`；简单字段覆盖可用 `overrides`。
7. 多步骤流程写 `case_flows`。
8. JSONPath、列表遍历和长度断言写 `structured_assertions`。
9. 临时文件、日志、mock、并发、cleanup、循环、条件和复杂计算先下沉为 Harness capability。
10. 无法自然封装时才保留 `case_bodies`，并记录原因。
11. 依次运行 `--validate-profile`、`--explain TC-ID`、`--check` 和 collect。

## strategy 优先级

当一条用例有多种生成线索时，planner 的策略优先级是：

```text
manual/skipped > custom_case_body > structured_case_flow > default_http
```

`default_http` 是单请求模板：它只合并基础请求体、`requests`、profile variables 和断言。需要模块动作、状态准备或多步骤调用时，使用固定 Harness 的 `case_flow`；无法用线性 flow 表达的测试函数编排才使用 `case_body`。

profile gate 会阻断同一 case_id 同时存在 `case_bodies` 和 `case_flows` 的情况，避免迁移中间态让旧 `case_body` 悄悄覆盖新 `case_flow`。

## 常见校验失败

- `E501`：profile 不是合法 YAML 或不符合 JSON Schema。
- `E502`：未知 `module_type`。
- `E503`：module_type 要求复杂流程，但 profile 没有提供 `case_bodies` 或 `case_flows`。
- `E510/E511`：`case_flows` 结构或断言格式不符合约定。
- `E501`：`requests.patches` 结构不合法，例如 `add/replace` 没有且只有一个 `value` / `value_from`。
- `E507`：`requests.patches[].value_from` 或 `case_flows` 的 `{var: name}` 引用了未定义变量。
- `E529`：`structured_assertions` 类型、必填字段、target 或 JSONPath 不合法。
- `E530`：`structured_assertions.target` 在当前生成策略下不可用，例如 default 路线用了非 `resp` target，或 case_flow 未产出该变量。

排查方式见 [codegen_troubleshooting.md](./codegen_troubleshooting.md)。

## 稳定性边界

v0.1 中，以下内容按稳定契约维护：

- profile 文件路径：`test_workspace/targets/{target}/modules/{module}/profile.md` 和 `{suite_dir}/profile_{suite}_suite.md`
- module profile 顶层字段：`variables`、`assertion_rules`、`extra_imports`
- suite profile 顶层字段：`variables`、`requests`、`structured_assertions`、`assertion_rules`、`case_flows`、`case_bodies`
- Harness 绑定：`setup_{module} -> {Module}Harness -> harness`
- case_id 格式：`^TC-[A-Z0-9]+-[0-9]+$`
- profile gate 的原则：ERROR 阻断生成，WARNING 允许继续但需要 review

以下内容仍可能继续演进：

- `case_flows.steps` 的 step 类型和参数词汇表
- health/promotion report 的成熟度口径
- promotion patch 的具体文件格式
- `aitest_kit.codegen` 内部 Python API

迁移新项目时，不要把内部 Python API 当成扩展点；优先通过 Markdown、profile、Module Harness、target helper 和 `aitest.yaml` 表达规则。
