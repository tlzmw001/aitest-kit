# Codegen Profile Guide

`codegen_profile_{module}.md` 是模块级生成配置。它告诉 codegen：这个模块属于什么类型、哪些用例要覆盖请求字段、哪些断言有专属模板、哪些复杂流程需要走 `case_flows` 或 `case_bodies`。

独立 case suite 也可以在用例目录旁放 `codegen_profile_{suite}_suite.md`。module profile 放 L1 稳定能力；suite profile 跟随用例批次，优先放本批用例的 `variables`、`case_flows`、`case_bodies` 和 `request_overrides`。

profile 文件必须包含一个 YAML 代码块：

~~~markdown
# demo codegen profile

```yaml
module_type: standard_http
```
~~~

profile 会先经过 JSON Schema 和语义校验。校验失败时，普通 codegen、`--check`、`--dump-ir`、`--explain` 和 promotion 分析都会阻断。

## module_type

`module_type` 是必填字段，取值来自 `aitest_config/project_config.yaml` 的 `module_types`。

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

如果某类模块可以由 `case_flows` 满足，也可以在项目配置中把它设计为需要 `case_bodies`，profile gate 会把 `case_bodies` 或 `case_flows` 都视为可满足复杂流程要求。

## request_overrides

当 Markdown 用例中的“请求覆盖”不足以表达稳定差异时，可以在 profile 中按 case_id 明确覆盖请求字段：
当前确定性 codegen 生成真实请求体时，以这里的 `request_overrides` 为准；Markdown 场景变量中的“请求覆盖”主要用于人类 review 和 trace。

```yaml
module_type: standard_http
request_overrides:
  TC-DEMO-001:
    user_id: "u_demo_001"
    value: 2
```

约束：

- key 必须是 `TC-XXX-001` 这类格式。
- value 必须是对象。
- 只写 case 级差异，不要复制完整基础请求体。

## assertion_rules

当某类自然语言或表达式断言会重复出现时，用 `assertion_rules` 固化：

```yaml
module_type: standard_http
assertion_rules:
  - name: demo_score
    regex: '^score == (?P<value>\d+)$'
    template: 'assert resp["score"] == {value}'
```

匹配优先级：

```text
profile assertion_rules > project_config builtin_assertion_rules > named_templates
```

适用：

- 断言表达稳定。
- 生成代码是确定性的。
- 同类断言会重复出现。

不适用：

- 需要多步骤前置动作。
- 断言依赖复杂临时变量。
- 只有一条用例临时出现，尚不值得沉淀。

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

`case_flow` 的 `args` / `kwargs` 通过 `{var: name}` 引用：

```yaml
case_flows:
  TC-AUTH-001:
    fixture: setup_management_auth_user
    object: client
    steps:
      - call: client.login
        kwargs:
          username:
            var: username
          password:
            var: password
        save_as: resp
      - assert: 'assert resp.status_code == 200'
```

约束：

- 变量名必须是合法 Python 标识符。
- 每个变量只能声明 `env` 或 `value` 之一。
- `{var: name}` 必须能在 `variables.defaults` 或 `variables.cases.{case_id}` 中找到。
- 缺 env 且 `.env` / `AITEST_ENV_FILE` 也无法提供时，测试失败，错误信息只显示 env 名，不显示 env 值。
- 不要让 fixture 按 case_id 分发不同账号或 token；case 级数据差异放到 `variables`。

## case_flows

`case_flows` 是结构化多步骤流程，适合稳定的 API 组合调用：

```yaml
module_type: multi_endpoint
default_fixture: setup_demo_client
default_object: client_factory
default_case_setup:
  call: client_factory
  kwargs:
    case_id: "{case_id}"
  save_as: client
case_flows:
  TC-DEMO-002:
    steps:
      - call: client.create
        kwargs:
          user_id: "u_demo_002"
          value: 3
        save_as: create_resp
      - assert: 'assert create_resp["code"] == 0'
      - call: client.get
        kwargs:
          user_id: "u_demo_002"
        save_as: get_resp
      - assert: 'assert get_resp["value"] == 3'
```

`default_fixture` / `default_object` / `default_case_setup` 是 case_flow 的默认注入规则：

- `default_fixture`：没有单独声明 `fixture` 的 case_flow 使用这个 fixture 进入 pytest 函数签名。
- `default_object`：renderer 会先生成 `default_object = default_fixture`，例如 `client_factory = setup_demo_client`。
- `default_case_setup`：自动插入到每条 case_flow 的第一步，常用于 `case = client_factory(case_id="{case_id}")`。
- `{case_id}` 会在生成 IR 时替换成当前用例 ID。
- 单条 case_flow 仍可以显式写 `fixture` 或 `object` 覆盖默认值。

适用场景：同一个模块或 suite 下，每条用例都需要相同的 factory setup，但后续业务动作不同。

约束：

- case_id 必须匹配 `^TC-[A-Z0-9]+-[0-9]+$`。
- 每条 case_flow 必须能通过自身或顶层 `default_fixture` 得到非空 fixture。
- `object` / `default_object` 必须是合法 Python 标识符。
- `steps` 至少一项。
- `assert` 必须写成可执行 Python 断言，例如 `'assert resp["code"] == 0'`；不要写裸表达式。

适用：

- 多端点 CRUD。
- 先写入再查询。
- 先执行动作再验证状态。
- 流程稳定，值得代码确定性生成。

## case_bodies

`case_bodies` 是逃生通道，可以直接提供测试函数 body 行：

```yaml
module_type: isolated_service
case_bodies:
  TC-DEMO-003:
    - 'resp = client.reload_config()'
    - 'assert resp["code"] == 0'
```

适用：

- 进程生命周期。
- 并发竞争。
- mock patch。
- 文件系统生命周期。
- 复杂日志捕获。

不建议长期滥用。稳定后应优先晋升为：

```text
case_bodies -> case_flows -> assertion_rules / project_config builtin rules
```

## strategy 优先级

当一条用例有多种生成线索时，planner 的策略优先级是：

```text
manual/skipped > custom_case_body > structured_case_flow > default_grpc > default_http
```

profile gate 会阻断同一 case_id 同时存在 `case_bodies` 和 `case_flows` 的情况，避免迁移中间态让旧 `case_body` 悄悄覆盖新 `case_flow`。

## 常见校验失败

- `E501`：profile 不是合法 YAML 或不符合 JSON Schema。
- `E502`：未知 `module_type`。
- `E503`：module_type 要求复杂流程，但 profile 没有提供 `case_bodies` 或 `case_flows`。
- `E510/E511`：`case_flows` 结构或断言格式不符合约定。

排查方式见 [codegen_troubleshooting.md](./codegen_troubleshooting.md)。

## 稳定性边界

v0.1 中，以下内容按稳定契约维护：

- profile 文件路径：`test_workspace/tests/fixtures/codegen_profile_{module}.md`
- YAML 顶层字段：`module_type`、`request_overrides`、`assertion_rules`、`case_flows`、`case_bodies`
- case_id 格式：`^TC-[A-Z0-9]+-[0-9]+$`
- profile gate 的原则：ERROR 阻断生成，WARNING 允许继续但需要 review

以下内容仍可能继续演进：

- `case_flows.steps` 的 step 类型和参数词汇表
- health/promotion report 的成熟度口径
- promotion patch 的具体文件格式
- `aitest_kit.codegen` 内部 Python API

迁移新项目时，不要把内部 Python API 当成扩展点；优先通过 Markdown、profile、fixture、helper 和 `project_config.yaml` 表达规则。
