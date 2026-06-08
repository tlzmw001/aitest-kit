# AITest 配置文件手册

本文是 AITest workspace 的配置文件总览，说明每个配置文件的职责、字段归属和常见错误。

## 配置分层

```text
aitest_config/aitest.yaml
  全局 workspace 路径、codegen 默认规则、module_type、通用断言规则

test_workspace/targets/{target}/target.yaml
  一个目标系统的默认目录、文档引用、知识库引用

test_workspace/targets/{target}/modules/{module}.yaml
  一个模块的 fixture 注册、module_type、L1 知识引用、registered_suites

test_workspace/targets/{target}/profiles/profile_{module}.md
  module profile，放 L1 级稳定生成能力

test_workspace/suites/{target}/{suite}/suite.yaml
  一个用例批次绑定哪个 target/module，以及包含哪些 Markdown 用例文件

test_workspace/suites/{target}/{suite}/profile_{suite}_suite.md
  suite profile，放本批用例的 TC-ID 绑定生成规则

test_workspace/tasks/{task}.yaml
  多个 suite 的显式执行任务
```

核心原则：

- `target` 表示被测系统。
- `module` 表示被测系统中的测试模块，维护 fixture 和 module profile。
- `suite` 表示一批 Markdown 用例，通常对应一个 L2 需求、迭代、冒烟批次或临时调试批次。
- module profile 放稳定能力，suite profile 放具体 TC-ID 绑定规则。
- generated pytest 是产物，不是配置源。

## 字段归属表

| 字段/内容 | 应写位置 | 不应写位置 |
|---|---|---|
| workspace 路径、generated/reports 默认目录 | `aitest_config/aitest.yaml` | suite profile |
| 通用 `module_type` 定义 | `aitest_config/aitest.yaml` | suite profile |
| 通用断言规则 | `aitest_config/aitest.yaml.codegen.builtin_assertion_rules` | 单个 suite profile，除非只服务该 suite |
| target 默认目录 | `target.yaml` 或 `aitest.yaml.targets` | suite.yaml |
| module 的 fixture 文件 | `modules/{module}.yaml.fixture.file` | suite.yaml |
| module 的默认 fixture 名 | `modules/{module}.yaml.fixture.default_fixture` | suite.yaml |
| target 级 L0 知识引用 | `target.yaml.knowledge_refs.l0` | suite.yaml |
| module 级 L1 知识引用 | `modules/{module}.yaml.knowledge_refs.l1` | suite.yaml |
| suite 级 L2 知识引用 | `suite.yaml.knowledge_refs.l2` | module.yaml |
| module profile 路径 | 约定路径 `test_workspace/targets/{target}/profiles/profile_{module}.md` | `module.yaml`、suite.yaml |
| suite 属于哪个 target/module | `suite.yaml` | profile YAML |
| suite 包含哪些 Markdown 文件 | `suite.yaml.case_files` | module profile |
| suite profile 路径 | 约定路径 `{suite_dir}/profile_{suite}_suite.md` | `suite.yaml`、module profile |
| `case_flows` | suite profile | module profile |
| `case_bodies` | suite profile | module profile |
| `requests` | suite profile | module profile |
| `structured_assertions` | suite profile | module profile |
| `case_fixtures` | suite profile | module profile |
| `variables.cases` | suite profile | module profile |
| `variables.defaults` | module profile 或 suite profile | fixture 代码里硬编码 |
| `default_fixture/default_object/default_case_setup` | module profile 或 suite profile | suite.yaml |
| 环境变量真实值 | 本地 shell、`.env` 或 `AITEST_ENV_FILE` | profile、fixture、Markdown 用例 |
| 多 suite 组合执行 | `test_workspace/tasks/{task}.yaml` | module profile |

## `aitest_config/aitest.yaml`

职责：定义 workspace 默认路径、codegen 默认 helper、默认 API path、module_type、通用断言规则，并可选声明 target registry 的内联配置。

```yaml
workspace:
  paths:
    knowledge_dir: test_workspace/knowledge
    test_spec: test_workspace/knowledge/TEST_SPEC.md
    l0_architecture: test_workspace/knowledge/L0_system_architecture.md
    generated_dir: test_workspace/generated
    profile_dir: test_workspace/targets
    reports_dir: test_workspace/reports
    results_dir: test_workspace/results
    docs_dir: docs
    refs_dir: aitest_config/refs

codegen:
  helper_import: from aitest_kit.helpers import http as http_helper
  grpc_helper_import: from aitest_kit.helpers import grpc_ops
  api_path: /api/v1/replace-me
  helper_call: http_helper.post
  grpc_helper_call: grpc_ops.call
  default_request:
    auto_fields: {}
  module_types:
    standard_http:
      description: 默认单接口 HTTP 模块
    multi_endpoint:
      description: 多端点或自定义流程模块
      requires:
        - case_bodies
  builtin_assertion_rules: []

targets: {}
```

注意：

- 新项目不要急着配置 `default_request.auto_fields`。只有字段命名稳定且跨用例一致时才配置。
- 多端点模块优先使用 fixture Client + suite profile `case_flows`。
- `api_path: /api/v1/replace-me` 是占位默认值，真实 suite 不应依赖它。

## `target.yaml`

职责：描述一个目标系统，设置该 target 下的默认 module、fixture、profile、suite、generated、reports 目录，并链接 L0 或系统级文档。

```yaml
target: your_service
source_root: /path/to/your_service
docs:
  - docs/public_api.md
knowledge_refs:
  l0: test_workspace/knowledge/L0_system_architecture.md
defaults:
  module_dir: test_workspace/targets/your_service/modules
  fixture_dir: test_workspace/targets/your_service/fixtures
  helper_dir: test_workspace/targets/your_service/helpers
  profile_dir: test_workspace/targets/your_service/profiles
  suite_dir: test_workspace/suites/your_service
  generated_dir: test_workspace/generated/your_service
  reports_dir: test_workspace/reports/your_service
```

注意：

- `source_root` 可以指向目标系统源码目录，但测试规则默认仍应来自公开文档、API schema、OpenAPI/proto 或用户确认的信息。
- `defaults` 只定义目录，不定义具体用例策略。
- `knowledge_refs.l0` 推荐写系统架构索引；外部知识库可写绝对路径或 `${ENV_NAME}`。

## `modules/{module}.yaml`

职责：描述某个 module 属于哪个 target，注册 fixture、module_type、L1 知识引用和 active suites，使 `--module`、`--target`、`--all` 能发现它们。module profile 不在这里配置路径，固定读取 `test_workspace/targets/{target}/profiles/profile_{module}.md`。

```yaml
target: your_service
module: gateway_api
module_type: multi_endpoint
knowledge_refs:
  l1: test_workspace/knowledge/L1/gateway_api.md
fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api
registered_suites:
  - test_workspace/suites/your_service/gateway_smoke/suite.yaml
```

如果需要非 active 状态，使用完整格式：

```yaml
registered_suites:
  - suite: gateway_smoke
    manifest: test_workspace/suites/your_service/gateway_smoke/suite.yaml
    status: paused
```

注意：

- `knowledge_refs.l1` 是 module 的推荐知识来源。缺少它不阻断 codegen/run，但 `doctor` 会提示追溯信息不足。
- 手写 `registered_suites` 时，优先用 suite manifest 路径字符串。
- 需要 `status` 时才写 mapping。
- 推荐使用 CLI 注册，减少路径写错：

```bash
aitest registry register-suite \
  --target your_service \
  --module gateway_api \
  --suite-file test_workspace/suites/your_service/gateway_smoke/suite.yaml
```

## module profile

路径：

```text
test_workspace/targets/{target}/profiles/profile_{module}.md
```

职责：放 L1 级稳定能力，例如 `module_type`、默认 fixture/object/setup、模块级稳定断言规则和跨 suite 通用的 `variables.defaults`。

````markdown
# profile_gateway_api

```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.targets.your_service.fixtures.gateway_api import setup_gateway_api"

default_fixture: setup_gateway_api
default_object: client

variables:
  defaults:
    base_url:
      env: YOUR_SERVICE_BASE_URL

assertion_rules:
  - name: success_code
    regex: ^response\.code\s*==\s*0$
    template: assert resp["code"] == 0
```
````

禁止写入 module profile 的内容：

```yaml
case_flows: {}
case_bodies: {}
requests: {}
structured_assertions: {}
case_fixtures: {}
variables:
  cases: {}
```

这些字段是具体 TC-ID 绑定配置，必须写入 suite profile。当前 suite 的 TC-ID 如果出现在 module profile 的这些字段里，profile gate 会报 `E526`。

## `suite.yaml`

职责：把一批 Markdown 用例绑定到 target/module/suite，并声明 Markdown case files。suite profile 不在这里配置路径，固定读取 `{suite_dir}/profile_{suite}_suite.md`。

```yaml
target: your_service
module: gateway_api
suite: gateway_smoke
case_files:
  - business.md
  - boundary.md
knowledge_refs:
  l2:
    - test_workspace/knowledge/L2/gateway_smoke.md
```

规则：

- `case_files` 只推荐写相对 `suite.yaml` 所在目录的路径，例如 `business.md`。
- 不要写 `test_workspace/suites/.../business.md`。
- 不要写系统绝对路径。
- `knowledge_refs.l2` 推荐写本 suite 对应的 L2/需求文档；不要重复写 module 的 L1，代码会从 `module.yaml` 合并 effective refs。
- `suite.yaml` 只放 suite 元数据，不放 fixture、helper、case_flow、profile 路径或执行参数。

不要把 `profile`、`fixture`、`case_flows`、`case_bodies`、`variables`、`env_file`、`pytest_args` 写入 `suite.yaml`；这些内容分别属于约定路径、module profile、suite profile 或 task manifest。

## knowledge_refs 写法

`knowledge_refs` 用于给 skill、health、promotion 等诊断入口提供追溯信息。普通 codegen/run 不会因为缺知识文件而失败。

推荐归属：

| 层级 | 推荐 key | 含义 |
|---|---|---|
| target.yaml | `l0` | 系统架构索引 |
| modules/{module}.yaml | `l1` | 模块可测试契约 |
| suite.yaml | `l2` | 需求变更、迭代或用例批次 |
| 任意层 | `test_spec` | 补充测试规范 |

每个 key 支持文件、目录或列表：

```yaml
knowledge_refs:
  l1: /path/to/L1/gateway_api.md
  l2:
    - /path/to/L2/quota_billing.md
    - /path/to/L2/auth_changes.md
  test_spec: /path/to/test_specs/
```

解析规则：

- 文件：直接引用。
- 目录：只展开当前目录下一级 `*.md`，按文件名排序；不递归。
- 列表：逐项解析并扁平化。
- 合并：处理 suite 时生成 effective refs，顺序为 `target -> module -> suite`，同 key 去重保序。
- 外部知识库：可写绝对路径，也可写 `${ENV_NAME}`；环境变量缺失会形成诊断。

## suite profile

路径：

```text
test_workspace/suites/{target}/{suite}/profile_{suite}_suite.md
```

职责：只覆盖当前 suite 的 case_id，放本批用例的 `variables.cases`、`requests`、`structured_assertions`、`case_flows`、`case_bodies`。文件名必须以 `_suite.md` 结尾；YAML 中建议写 `profile_scope: case_suite`、`parent_module` 和 `suite`。

````markdown
# profile_gateway_smoke_suite

```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke

variables:
  cases:
    TC-GW-001:
      token:
        env: YOUR_SERVICE_USER_TOKEN
    TC-GW-002:
      token:
        value: ""

case_flows:
  TC-GW-001:
    description: 查询当前用户信息
    steps:
      - call: client.current_user
        kwargs:
          token:
            var: token
        save_as: http_resp
      - assign: resp
        expr: http_resp.json()
      - assert: 'assert http_resp.status_code == 200'
      - assert: 'assert resp["code"] == 0'

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
````

`case_flow` step 规则：

| step | 含义 |
|---|---|
| `call` | 调用 fixture/client/helper 方法 |
| `args` | 位置参数，必须是 list |
| `kwargs` | 关键字参数，必须是 mapping；无参数时省略或写 `{}` |
| `save_as` | 保存调用结果，供后续 step 使用 |
| `assign` | 计算中间变量 |
| `expr` | `assign` 使用的 Python 表达式 |
| `assert` | Python 断言，必须以 `assert ` 开头 |
| `comment` | 生成代码中的注释；不能作为非 manual flow 的唯一内容 |
| `description` | 单条 flow 的 profile 元数据，不进入 generated pytest；纯人工 `[manual]` 不写 flow，半自动 manual flow 至少包含 `call` 或 `assert` |

`structured_assertions` 规则：

- default HTTP/gRPC 路线只能写 `target: resp`。
- `case_flow` 路线只能写当前 flow 中 `save_as` 或 `assign` 产出的变量。
- `case_bodies`、pure manual、skipped 用例不写 `structured_assertions`。
- JSONPath、集合遍历、字段存在性和长度断言优先写 `structured_assertions`。
- 复杂业务计算、循环、条件和等待逻辑封装到 fixture/helper 方法，再通过 `case_flow.call` 调用。

变量引用：

```yaml
kwargs:
  token:
    var: token
  request_id:
    value: req_demo_001
```

可用变量来源：

- `{var: name}` 引用 profile `variables`。
- `{ref: previous_save_as}` 引用前面 step 的保存结果。
- `{expr: python_expr}` 使用 Python 表达式。

## task manifest

路径：

```text
test_workspace/tasks/{task}.yaml
```

推荐用 CLI 创建：

```bash
aitest task create \
  --name nightly_gateway \
  --suite-file test_workspace/suites/your_service/gateway_smoke/suite.yaml \
  --suite-file test_workspace/suites/your_service/billing_smoke/suite.yaml
```

典型结构：

```yaml
schema_version: 1
name: nightly_gateway
description: gateway nightly regression
env_files:
  - /tmp/your-service-test.env
defaults:
  include_manual: false
  pytest_args:
    - -q
units:
  - name: gateway smoke
    target: your_service
    module: gateway_api
    suite: gateway_smoke
    suite_file: ../suites/your_service/gateway_smoke/suite.yaml
```

注意：

- 多 suite 的回归任务用 task。
- 单 suite 调试直接用 `--suite-file`。
- task 中的 `suite_file` 可以由 CLI 生成，手写时保持相对 task 文件位置可读即可。

## env 文件

真实服务地址、账号、token、API key 不写入 profile，不写入 Markdown，不提交到仓库。

本地 env 文件示例：

```dotenv
YOUR_SERVICE_BASE_URL=http://127.0.0.1:8080
YOUR_SERVICE_USER_TOKEN=replace-with-local-token
YOUR_SERVICE_ADMIN_TOKEN=replace-with-local-admin-token
```

运行时使用：

```bash
AITEST_ENV_FILE=/tmp/your-service-test.env \
  aitest run --suite-file test_workspace/suites/your_service/gateway_smoke/suite.yaml
```

规则：

- shell 环境变量优先于 env 文件。
- 报告只记录变量名，不记录变量值。
- 缺少被引用的 env 时，应归类为运行前置条件缺失，而不是待测系统 bug。

## 常见错误

### `case_files` 写成 workspace 路径

错误：

```yaml
case_files:
  - test_workspace/suites/your_service/gateway_smoke/business.md
```

正确：

```yaml
case_files:
  - business.md
```

### `case_flows` 写进 module profile

错误：

```yaml
# test_workspace/targets/your_service/profiles/profile_gateway_api.md
case_flows:
  TC-GW-001:
    steps:
      - assert: 'assert True'
```

正确：

```yaml
# test_workspace/suites/your_service/gateway_smoke/profile_gateway_smoke_suite.md
case_flows:
  TC-GW-001:
    steps:
      - assert: 'assert True'
```

### `kwargs` 写成 list

错误：

```yaml
steps:
  - call: client.health
    kwargs: []
```

正确：

```yaml
steps:
  - call: client.health
```

或：

```yaml
steps:
  - call: client.health
    kwargs: {}
```

### 在配置文件中手写 profile 路径

错误：

```yaml
profile: profile_gateway_smoke.md
```

正确：

- module profile 固定放在 `test_workspace/targets/{target}/profiles/profile_{module}.md`。
- suite profile 固定放在 `{suite_dir}/profile_{suite}_suite.md`。
- `module.yaml` 和 `suite.yaml` 都不要写 `profile` 字段。

### 把执行参数写进 `suite.yaml`

错误：

```yaml
pytest_args:
  - -q
env_file: /tmp/test.env
```

正确：

- 单 suite 运行参数写在命令行。
- 多 suite 固定任务参数写进 task manifest。

## 验证命令

修改配置后按这个顺序检查：

```bash
aitest doctor
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

如果 suite 需要进入聚合入口：

```bash
aitest registry register-suite \
  --target <target> \
  --module <module> \
  --suite-file test_workspace/suites/<target>/<suite>/suite.yaml

aitest codegen --target <target> --module <module> --check
aitest run --target <target> --module <module> -- --collect-only -q
```
