# Target / Module / Suite / Task 解耦重构 Spec

## 背景

当前 AITest Kit 已支持：

- module 模式：`aitest codegen <module>` / `aitest run <module>`
- legacy all 模式：`aitest codegen --all` 按 `test_workspace/cases/*` 扫描模块
- suite 模式：`aitest codegen --cases <suite_dir>` / `aitest run --cases <suite_dir>`
- suite profile：module profile + suite profile 临时合并
- generated freshness check、profile gate、run/report、promotion 分析

这些能力验证了 codegen 飞轮可行，但当前架构仍有几个耦合点：

1. `--all` 语义依赖目录扫描，隐含“用例必须在 workspace 的 module 目录下”。
2. `aitest_workspace` 注入被测项目的模式适合试点，但不适合测试团队维护多个项目。
3. 用例、知识库、被测源码、测试执行产物之间的路径关系仍靠目录约定和命令参数拼接。
4. report 对 suite 的支持仍部分依赖路径推断，不能完全支持随机路径。
5. module / suite / task / target 的边界需要重新定义，避免后续功能继续堆在 suite_runner 或 module_runner 上。

本重构目标是把 AITest 从“注入某个被测项目的 testspace”升级为“独立测试项目”，通过显式配置连接多个被测 target、模块知识、fixture/profile、suite 用例和执行任务。

## 核心判断

### 保留的概念

- `target`：被测系统或被测服务，例如 `sub2api`、`coupon_system`。
- `module`：target 内的稳定测试能力边界，例如 `gateway_api`、`calibration`。
- `suite`：单个 module 下的一批 Markdown 用例，可以只有一个 md 文件。
- `task`：一次执行计划，可组合一个或多个 target/module/suite。
- `all`：保留用户心智，但改为“遍历已注册对象”，不再扫描目录。

### 调整的概念

- AITest workspace 不应长期默认注入被测项目。
- 用例可以放在独立用例项目。
- 知识库可以放在独立知识库项目。
- generated pytest 和 reports 默认仍放 AITest 测试项目内。
- promotion 仍以 module 为主归属，不上升为 task 级机制。

### 不再坚持的旧假设

- 不要求 `test_workspace/cases/{module}/business.md` / `boundary.md` 是唯一用例组织方式。
- 不要求 suite 目录在 AITest workspace 内。
- 不要求每个被测项目都有一个独立 `aitest_workspace`。
- 不要求 `--all` 立即物理删除，但旧的目录扫描式 all 要退出主路径。

## 目标架构

```text
AITest 测试项目
  ├── target registry
  │   ├── target: sub2api
  │   │   ├── modules
  │   │   ├── fixture / helper / module profile
  │   │   ├── generated pytest
  │   │   └── reports
  │   └── target: coupon_system
  ├── suites
  │   ├── target + module + suite + case_files + suite_profile
  │   └── case_files 可来自任意路径
  └── tasks
      ├── target/module/suite 组合
      └── target all 组合
```

### 概念职责

| 概念 | 主要职责 | 不负责 |
|---|---|---|
| target | 连接一个被测系统，声明源码/文档/运行时入口/默认目录 | 直接写测试逻辑 |
| module | 维护 L1 归属、fixture、helper、module profile、注册 suite | 发现任意用例文件 |
| suite | 声明单 module 的用例批次、case_files、suite profile、L2 引用 | 跨模块编排 |
| task | 编排一次执行计划，可组合多个 suite 或 target all | 维护 fixture/profile 细节 |
| all | 遍历已注册 active suite | 扫描目录猜测用例 |

## 路径与配置原则

### 配置尽量不重复

同一信息只在最上游配置一次，下游默认继承；只有确实不同才覆盖。

### 全局配置入口合并

新架构推荐只有一个全局配置入口：

```text
aitest_config/aitest.yaml
```

旧的 `aitest_config/config.yaml` + `aitest_config/project_config.yaml` 是历史拆分：

- `config.yaml`：workspace 路径、service/protocol/data 等 skill 辅助信息。
- `project_config.yaml`：codegen helper、断言规则、module_type、默认请求字段等。

对用户来说，这两者都属于“AITest 项目配置”。因此后续实现应按以下兼容策略推进：

1. 优先读取 `aitest_config/aitest.yaml`。
2. 如果不存在，再读取旧的 `config.yaml` + `project_config.yaml`。
3. 新模板、新文档、新 skill 只推荐 `aitest.yaml`。
4. 旧文件继续兼容，避免破坏现有 workspace。

`aitest.yaml` 不做扁平大配置，而是按职责分区：

```yaml
workspace:
  paths:
    docs_dir: docs
    refs_dir: aitest_config/refs
    generated_root: test_workspace/generated
    reports_root: test_workspace/reports
    results_dir: test_workspace/results
codegen:
  helper_import: ""
  grpc_helper_import: ""
  helper_call: ""
  grpc_helper_call: ""
  module_types: {}
  named_templates: []
  builtin_assertion_rules: []
targets: {}
```

全局配置只保留整个 AITest 测试项目共享的信息。描述具体被测系统的信息下沉到 target：

```yaml
service: {}
data: {}
protocols: {}
known_limitations: []
```

这些字段不再推荐放全局，因为多 target 测试项目里不同服务的语言、端点、依赖和限制可能完全不同。

推荐覆盖顺序：

```text
global defaults
  -> target config
    -> module registry
      -> suite manifest
        -> task unit override
```

例子：

- `target` 声明默认 `knowledge_base`、`generated_dir`、`reports_dir`。
- `module` 只声明自己的 L1、fixture、profile。
- `suite` 只声明自己的 case files、suite profile、L2。
- `task` 只声明要跑哪些 suite 或 target all。

### `knowledge_root` 不作为必须字段

不强制配置 `knowledge_root`。

原因：

1. 很多时候只需要 L1/L2 的具体文件路径。
2. root 本身不参与 codegen/run/report。
3. 如果同时配置 root 和具体文件，容易出现重复和不一致。

推荐配置：

```yaml
knowledge_refs:
  l0: ${SUB2API_KNOWLEDGE}/L0_system_architecture.md
```

```yaml
knowledge_refs:
  l1: ${SUB2API_KNOWLEDGE}/L1/gateway_api.md
```

```yaml
knowledge_refs:
  l2:
    - ${SUB2API_KNOWLEDGE}/L2/quota_billing_v2.md
```

只有当某个 skill 需要“遍历整个知识库”时，才允许配置：

```yaml
knowledge_refs:
  base_dir: ${SUB2API_KNOWLEDGE}
```

但 `base_dir` 只能作为便利字段，不能成为必填字段。

### 路径解析规则

1. 绝对路径：直接使用。
2. 相对路径：默认相对于当前 AITest 测试项目根目录。
3. `${ENV_NAME}`：先展开环境变量，再按绝对/相对路径处理。
4. suite manifest 中的 `case_files`：相对路径默认相对于 suite manifest 所在目录。
5. suite manifest 中的 `profile`：相对路径默认相对于 suite manifest 所在目录。
6. task manifest 中引用的 `suite_file`：相对路径默认相对于 task manifest 所在目录。

### 配置覆盖规则

代码读取配置时必须支持默认继承，减少人工重复配置。

例子：

```yaml
target: sub2api
defaults:
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
  profile_dir: test_workspace/targets/sub2api/profiles
  fixture_dir: test_workspace/targets/sub2api/fixtures
```

module 可以只写：

```yaml
module: gateway_api
profile: codegen_profile_gateway_api.md
fixture: gateway_api.py
```

代码解析后得到：

```text
profile = target.defaults.profile_dir / codegen_profile_gateway_api.md
fixture = target.defaults.fixture_dir / gateway_api.py
```

## `target.yaml` 边界

`target.yaml` 只回答：

```text
这个被测系统是什么，以及它的测试资产默认放哪。
```

它不负责具体用例、case_flow、fixture 实现或模块级规则。

### 推荐结构

```yaml
target: sub2api

source_root: /Users/zmw/DragonCode-sub2api

docs:
  - docs/public_api_doc.md

knowledge_refs:
  l0: test_workspace/knowledge/L0_system_architecture.md

service:
  language: go
  frameworks: [gin]
  endpoints:
    base_url: ${SUB2API_BASE_URL}

data:
  stores: []

protocols:
  primary: http

known_limitations: []

defaults:
  # 全部可省略，代码按 target 推导
```

### 必填规则

- `target` 必填。
- `source_root` 和 `docs` 至少一个要有：
  - 黑盒项目可以只给 `docs`。
  - 灰盒项目可以给 `source_root` + `docs`。

### 可选字段

- `knowledge_refs.l0` 可选。
- `service` 可选，由 scaffold/doc-gen 辅助生成。
- `data` 可选，由 scaffold/doc-gen 辅助生成。
- `protocols` 可选，默认 `primary: http`。
- `known_limitations` 可选。
- `defaults` 全部可选。

### 默认推导

如果用户不写 `defaults`，代码按 target 自动推导：

```yaml
defaults:
  module_dir: test_workspace/targets/{target}/modules
  fixture_dir: test_workspace/targets/{target}/fixtures
  helper_dir: test_workspace/targets/{target}/helpers
  profile_dir: test_workspace/targets/{target}/profiles
  suite_dir: test_workspace/suites/{target}
  generated_dir: test_workspace/generated/{target}
  reports_dir: test_workspace/reports/{target}
```

### 不放在 target.yaml 的内容

| 内容 | 所属层级 |
|---|---|
| `module_type` | `module.yaml` |
| `fixture` / `profile` | `module.yaml` |
| `registered_suites` | `module.yaml` |
| `case_files` | `suite.yaml` |
| `case_ids` | `task.yaml` 或 CLI 参数 |

## `module.yaml` 边界

`module.yaml` 只回答：

```text
这个模块怎么接入测试生成链路。
```

它是 L1 模块的稳定测试能力索引，不放具体用例，也不放 task 执行计划。

### 推荐结构

```yaml
target: sub2api
module: gateway_api

module_type: multi_endpoint

knowledge_refs:
  l1: test_workspace/knowledge/L1/gateway_api.md

fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api

profile:
  file: profile_gateway_api.md

helpers:
  - http.py
  - auth.py

registered_suites:
  - suite: quota_billing_v2
    manifest: test_workspace/suites/sub2api/quota_billing_v2/suite.yaml
    status: active
```

### 必填规则

- `module` 必填。
- `target` 可选；标准路径 `test_workspace/targets/{target}/modules/{module}.yaml` 下可推导。
- `module_type` 可选；默认 `standard_http`。

### module_type 事实来源

目标架构中，`module_type` 只允许两个来源：

```text
module.yaml.module_type
  -> default: standard_http
```

旧配置只用于兼容旧项目：

```text
如果 module.yaml 不存在：
  legacy module profile.module_type
    -> legacy project_config.modules[module].module_type
    -> default: standard_http
```

一旦 `module.yaml` 存在，就不再从 module profile 或 `project_config.modules` 偷偷推导 module_type。这样能保证事实来源唯一。

当前 Phase 3-3 已完成 legacy 入口一致性修复：validator 与 emitter 都通过同一个 `module_type` resolver 读取 legacy module profile / `project_config.modules`。`module.yaml` 接入仍属于后续 registry-driven 阶段。

### 默认推导

如果用户不写这些字段，代码按 target defaults 和 module 名推导：

```text
fixture.file            = {target.defaults.fixture_dir}/{module}.py
fixture.default_fixture = setup_{module}
profile.file            = {target.defaults.profile_dir}/profile_{module}.md
```

profile 旧命名兼容：

```text
优先读取 profile_{module}.md
如果不存在，再读取 codegen_profile_{module}.md
```

当前 Phase 3-3 已完成该兼容策略在 legacy module codegen/profile gate/suite runtime profile/health/promotion/explain 中的接入；旧文件不需要立即重命名。

### suite generated 文件名解析

suite generated pytest 文件名仍保持：

```text
test_{module}_{suite}_{case_file_stem}.py
```

但文件名拼接逻辑不能散落在 suite runner、run/report 或 task runner 中。Phase 3-3 先提供统一 helper，保持旧文件名不变，只统一事实入口。

### 可选字段

- `knowledge_refs.l1`：强烈建议写，但不强制。
- `fixture`：可省略，由默认规则推导。
- `profile`：可省略，由默认规则推导。
- `helpers`：可省略，默认空。
- `registered_suites`：可省略，默认空；后续 registry-driven all 只遍历 `status=active` 的 suite。

### 不放在 module.yaml 的内容

| 内容 | 所属层级 |
|---|---|
| `case_files` | `suite.yaml` |
| `case_ids` | `task.yaml` 或 CLI 参数 |
| `request_overrides` | suite profile |
| `case_flows` | suite profile |
| `case_bodies` | suite profile |
| `variables.cases` | suite profile |

## `suite.yaml` 边界

`suite.yaml` 只回答：

```text
这一批用例属于哪个 target/module，以及包含哪些 Markdown 用例文件。
```

它是用例批次入口，不负责模块能力，也不负责执行编排。

### 推荐结构

```yaml
target: sub2api
module: gateway_api
suite: quota_billing_v2

case_files:
  - quota_billing_business.md
  - quota_billing_boundary.md

profile: profile_quota_billing_v2_suite.md

knowledge_refs:
  l2:
    - test_workspace/knowledge/L2/quota_billing_v2.md
```

### 必填规则

`suite.yaml` 必填：

- `target`：被测系统。
- `module`：所属 L1 模块，用于找到 module fixture 和 module profile。
- `suite`：用例批次名，用于 generated 文件名、报告和 task 引用。
- `case_files`：本批用例包含的 Markdown 文件，不扫描目录猜测。

### 可选字段

- `profile`：可省略，默认推导。
- `knowledge_refs`：可省略，建议写 `l2` 方便 AI/review 追溯。

### profile 默认推导

如果不写 `profile`：

```text
优先读取 profile_{suite}_suite.md
如果不存在，再兼容 codegen_profile_{suite}_suite.md
```

如果显式写 `profile`，按显式路径读取。

### case_files 路径规则

`case_files` 相对 `suite.yaml` 所在目录解析。

```text
test_workspace/suites/sub2api/quota_billing_v2/
  suite.yaml
  business.md
  boundary.md
```

对应：

```yaml
case_files:
  - business.md
  - boundary.md
```

如果用例在外部项目，允许写绝对路径。

### 不放在 suite.yaml 的内容

| 内容 | 所属层级 |
|---|---|
| `fixture` / `helper` / `module_type` | `module.yaml` |
| `case_flows` / `case_bodies` | suite profile |
| `request_overrides` / `variables` | suite profile |
| `case_ids` / `include_manual` / `pytest_args` | `task.yaml` 或 CLI |
| `env_file` / `allow_risk` | `task.yaml` 或 CLI |

### 兼容策略

- `suite.yaml` 走新规则，必须显式写 `target/module/suite/case_files`，并拒绝生成细节和执行细节字段。
- `aitest_suite.yaml` 继续作为 legacy manifest 兼容读取。
- 无 manifest 的 `--cases <dir>` 继续短期兼容目录扫描，但不作为新项目推荐路径。

## `task.yaml` 边界

`task.yaml` 只回答：

```text
这一次要跑哪些测试单元，以及用什么执行参数跑。
```

它是执行计划，不是用例集合，也不是模块能力配置。

### 推荐结构

```yaml
schema_version: 1
name: sub2api_regression

description: Sub2API 回归任务

env_files:
  - /tmp/sub2api-test.env

defaults:
  include_manual: false
  pytest_args:
    - -q
  allow_risk: []

units:
  - name: quota_billing_v2
    suite_file: ../suites/sub2api/quota_billing_v2/suite.yaml

  - name: gateway_debug
    suite_file: ../suites/sub2api/gateway_smoke/suite.yaml
    case_ids:
      - TC-GW-001
      - TC-GW-002

  - name: sub2api_all
    target: sub2api
    all: true
```

### 必填规则

`task.yaml` 必填：

- `name`：任务名，用于报告路径、日志显示。兼容读取旧字段 `task`。
- `units`：执行单元列表。

每个 unit 必须二选一：

- `suite_file`
- `target + all: true`

### 当前实现范围

第一阶段实现：

- `schema_version: 1`
- `name`，兼容旧字段 `task`
- `env_files`
- `defaults.include_manual`
- `defaults.pytest_args`
- `defaults.allow_risk` 解析保留，不执行风险门禁
- `units[].name`
- `units[].suite_file`
- `units[].case_ids`
- `units[].include_manual`
- `units[].pytest_args`
- `units[].allow_risk` 解析保留，不执行风险门禁

暂不实现：

- `units[].target + all: true`

`target all` 需要基于 module registry 的 `registered_suites.status=active` 遍历，等 registry-driven all 阶段再做。

### env_files 规则

`env_files` 属于 task，不属于 suite。

原因：

```text
同一批用例可能在本地、CI、预发、正式影子环境运行，env 文件是执行环境输入。
```

路径相对 `task.yaml` 所在目录解析，允许绝对路径。

运行时只记录 env 文件路径和变量名，不记录变量值。

### case_ids 规则

`case_ids` 属于 task unit，不属于 suite。

它用于：

- 单 case debug
- CI rerun failed cases
- 局部回归某个 bug

当前实现用 pytest `-k` 做过滤。

### pytest_args / include_manual 规则

执行参数放在 task：

```yaml
defaults:
  include_manual: false
  pytest_args:
    - -q
```

unit 可以覆盖：

```yaml
units:
  - suite_file: xxx/suite.yaml
    include_manual: true
    pytest_args:
      - -q
      - -s
```

合并顺序：

```text
task.defaults
  -> unit override
  -> CLI extra pytest args
  -> case_ids filter
```

### 不放在 task.yaml 的内容

| 内容 | 所属层级 |
|---|---|
| `module_type` | `module.yaml` |
| `fixture` / `profile` / `helper` | `module.yaml` |
| `case_files` / `knowledge_refs` | `suite.yaml` |
| `case_flows` / `case_bodies` | suite profile |
| `request_overrides` / `variables` | suite profile |

## 推荐文件命名

### 总体原则

- 文件名表达语义，不表达实现历史。
- `manifest` 只作为通用概念，具体文件名要让人一眼知道用途。
- 不再用 `aitest_suite.yaml` 作为长期唯一标准名，后续可保留兼容。

### 建议命名

| 类型 | 推荐文件名 | 说明 |
|---|---|---|
| target 配置 | `target.yaml` | 一个 target 的入口配置 |
| module 注册 | `module.yaml` 或 `modules/{module}.yaml` | module 的稳定能力索引 |
| suite 声明 | `suite.yaml` | 单 suite 的用例和 profile 声明 |
| task 声明 | `task.yaml` 或 `tasks/{task}.yaml` | 一次执行计划 |
| module profile | `profile_{module}.md` | 长期稳定生成规则 |
| suite profile | `profile_{suite}_suite.md` | 本 suite 的生成规则 |

兼容期：

- 继续读取 `aitest_suite.yaml`。
- 继续读取 `codegen_profile_{module}.md`。
- 继续读取 `codegen_profile_{suite}_suite.md`。
- 新文档和新 skill 优先使用新命名。

是否立即重命名旧文件，由第二阶段配置梳理后决定。

## 目标目录结构草案

第一版目标结构：

```text
aitest_project/
  aitest_config/
    config.yaml
    project_config.yaml
    targets.yaml

  test_workspace/
    targets/
      sub2api/
        target.yaml
        modules/
          gateway_api.yaml
          management_auth_user.yaml
        fixtures/
          gateway_api.py
        helpers/
          http.py
        profiles/
          profile_gateway_api.md

      coupon_system/
        target.yaml
        modules/
          calibration.yaml
        fixtures/
        helpers/
        profiles/

    suites/
      sub2api/
        quota_billing_v2/
          suite.yaml
          business.md
          boundary.md
          profile_quota_billing_v2_suite.md

    tasks/
      sub2api_regression.yaml
      nightly_core.yaml

    generated/
      sub2api/
      coupon_system/

    reports/
      sub2api/
      coupon_system/
      latest/
```

是否保留现有：

```text
test_workspace/cases/
test_workspace/casesuites/
test_workspace/tests/fixtures/
test_workspace/tests/generated/
```

需要第三阶段单独评估，不在第一阶段直接删除。

## CLI 目标语义

### codegen

```bash
aitest codegen --target sub2api --all
aitest codegen --target sub2api --suite gateway_api/quota_billing_v2
aitest codegen --suite-file /path/to/suite.yaml
aitest codegen --task-file test_workspace/tasks/sub2api_regression.yaml
aitest codegen --target sub2api --suite gateway_api/quota_billing_v2 --case TC-GW-041
```

### run

```bash
aitest run --target sub2api --all
aitest run --target sub2api --suite gateway_api/quota_billing_v2
aitest run --suite-file /path/to/suite.yaml
aitest run --task-file test_workspace/tasks/sub2api_regression.yaml
aitest run --target sub2api --suite gateway_api/quota_billing_v2 --case TC-GW-041
```

### all 的新定义

```text
--all = 遍历 target/module registry 中 status=active 的 registered suites
```

禁止再定义为：

```text
扫描 test_workspace/cases/*
```

### suite 的新定义

```text
suite = 一个 target + module 下的一批用例
```

一个 suite 可以只包含一个 md；此时跑 suite 等价于跑这个 md 生成的 pytest，但执行单位仍叫 suite。

## Generated / Report 元数据

report 不应再从路径推断 suite/module/task。

generated pytest 应写入明确 metadata：

```python
__aitest_manifest__ = {
    "schema_version": 1,
    "target": "sub2api",
    "module": "gateway_api",
    "suite": "quota_billing_v2",
    "suite_file": "/path/to/suite.yaml",
    "case_files": ["/path/to/business.md"],
}
```

每条 case 元数据：

```python
__tc_meta__ = {
    "TC-GW-041": {
        "target": "sub2api",
        "module": "gateway_api",
        "suite": "quota_billing_v2",
        "case_file": "/path/to/business.md",
        "title": "...",
    }
}
```

task run 时可额外注入：

```python
"task": "sub2api_regression"
```

collector / renderer 以 metadata 为准，路径推断只作为兼容 fallback。

## 分阶段计划

这是大重构，必须拆阶段。每一阶段完成后都要做验证，并用子 Agent 或独立 review 流程检查改动质量。

### Phase 1：Target / Module / Suite / Task 架构重构方案

目标：

- 写清楚新概念和旧概念映射。
- 定义 target/module/suite/task 的数据结构。
- 定义配置继承和路径解析规则。
- 定义 legacy 兼容边界。
- 明确第一批代码要加哪些 loader/context，不急着改所有命令。

建议新增或改造：

- `aitest_kit/registry/target.py`
- `aitest_kit/registry/module.py`
- `aitest_kit/registry/suite.py`
- `aitest_kit/registry/task.py`
- 或者先集中在 `aitest_kit/config_registry.py`，第二轮再拆。

验收：

- 能加载 target/module/suite/task 配置。
- 能解析绝对路径、相对路径、`${ENV}`。
- 能把现有 coupon_system 映射为一个 target。
- 不破坏现有 module/suite 命令。

验证：

```bash
python3 -m pytest tests -q
python3 -m aitest_kit.cli doctor
python3 -m aitest_kit.cli codegen calibration --validate-profile
python3 -m aitest_kit.cli codegen calibration --check
```

必要时用 DragonCode 验证：

```bash
python3 -m aitest_kit.cli doctor --workspace /path/to/dragon/aitest_workspace
```

子 Agent review：

- 检查配置继承是否会造成歧义。
- 检查路径解析是否可能误读外部文件。
- 检查 legacy 行为是否被破坏。

### Phase 2：CLI 接入 registry loader

目标：

- 让新配置模型进入产品链路，但不迁移目录结构。
- `codegen` 支持直接读取 suite manifest 和 task manifest。
- `run` 支持直接读取 suite manifest 和 task manifest。
- 保持旧 `--cases`、module、legacy `--all` 行为不破坏。

新增入口：

```bash
aitest codegen --suite-file /path/to/suite.yaml
aitest codegen --task-file /path/to/task.yaml
aitest run --suite-file /path/to/suite.yaml
aitest run --task-file /path/to/task.yaml
```

第一版 task 范围：

- 支持 `units[].suite_file`。
- 支持 `units[].case_ids` 传递到 pytest `-k` 或等价过滤。
- 暂不支持 `units[].all`。
- 每个 task unit 复用 suite codegen/run 逻辑，避免重写主链路。
- task run 写入 task 级汇总报告：`test_workspace/reports/tasks/{task}/runs/{run_id}/`。

验收：

- `--suite-file` 可指向任意路径的 `suite.yaml` 或 legacy `aitest_suite.yaml`。
- `--task-file` 可逐个执行多个 suite unit，旧 `--task` 作为兼容别名。
- report 保留 task、unit、suite 来源，并生成 task 级汇总。
- 旧 `--cases` 测试继续通过。

验证：

```bash
python3 -m pytest tests/test_codegen_suite_profile.py tests/test_report_cli.py tests/test_registry_contexts.py -q
python3 -m aitest_kit.cli codegen calibration --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

子 Agent review：

- 检查 `--suite-file` 是否只是新入口，不改变旧 suite 语义。
- 检查 task 执行是否会意外混合不同 suite 的 generated 文件。
- 检查参数互斥规则是否清楚。

### Phase 3：配置项梳理与命名精简

目标：

- 梳理当前 `config.yaml`、`project_config.yaml`、profile、suite manifest 中的重复字段。
- 删除或降级没有实际消费方的字段。
- 明确哪些字段必填，哪些可由代码根据 target/module 推导。
- 改进文件命名，使其更符合语义。

重点问题：

- `knowledge_root` 是否保留：默认不保留，改为具体 `knowledge_refs`。
- `cases_dir` 是否仍是核心配置：新架构下应降级为 legacy 默认。
- `fixtures_dir` / `profile_dir` 是否可以由 target defaults 推导。
- module profile 文件名是否从 `codegen_profile_{module}.md` 迁移到 `profile_{module}.md`。
- suite manifest 是否从 `aitest_suite.yaml` 迁移到 `suite.yaml`。
- suite profile 是否从 `codegen_profile_{suite}_suite.md` 迁移到 `profile_{suite}_suite.md`。

验收：

- 配置项有明确消费方。
- 同一信息不要求人工重复写两次。
- 老文件名仍兼容。
- 新文件名有测试覆盖。

验证：

```bash
python3 -m pytest tests/test_codegen_suite_profile.py tests/test_doctor.py -q
python3 -m aitest_kit.cli codegen --cases test_workspace/casesuites/<coupon_suite> --validate-profile
python3 -m aitest_kit.cli codegen --cases test_workspace/casesuites/<coupon_suite> --check
```

子 Agent review：

- 检查新旧命名兼容。
- 检查文档示例是否和代码字段一致。
- 检查是否出现无消费方配置。

### Phase 4：项目目录结构精简

目标：

- 评估当前模板 workspace 的目录是否仍合理。
- 确定独立测试项目主结构。
- 设计 migration / upgrade 策略，避免直接破坏现有用户 workspace。

需要评估：

- `test_workspace/tests/fixtures/` 是否迁移到 `test_workspace/targets/{target}/fixtures/`。
- `test_workspace/tests/helpers/` 是否拆成 global helpers + target helpers。
- `test_workspace/tests/generated/` 是否迁移到 `test_workspace/generated/{target}/`。
- `test_workspace/cases/` 和 `test_workspace/casesuites/` 是否合并为 `test_workspace/suites/`。
- `test_workspace/knowledge/` 是否迁移到 `test_workspace/targets/{target}/knowledge/`。
- `reports/` 是否按 target 分目录。

约束：

- 不直接删除旧目录。
- 先兼容读取，再迁移模板。
- `upgrade` 不能覆盖用户已有 fixture/profile/cases。
- 需要备份策略，尤其是 generated、fixtures、profiles、skills。

第一刀状态：

- 已支持 target-aware suite runtime paths。
- 当 suite manifest 声明 `target` 且能加载到 `target.yaml` / `aitest_config/targets.yaml` 时：
  - module profile 从 target defaults 的 `profile_dir` 读取。
  - suite generated pytest 写入 target defaults 的 `generated_dir`。
  - suite run 从 target defaults 的 `generated_dir` 读取 pytest。
  - suite run 报告写入 target defaults 的 `reports_dir`。
- 当 target registry 不存在时，完全回退 legacy 路径：
  - `test_workspace/tests/fixtures`
  - `test_workspace/tests/generated`
  - `test_workspace/reports`
- 本阶段仍不迁移目录、不移动已有文件、不改变 generated 文件名格式。

第二刀状态：

- `aitest init` 模板已增加新布局锚点目录：
  - `test_workspace/targets/`
  - `test_workspace/suites/`
  - `test_workspace/generated/`
- 模板仍保留 legacy 目录，避免新旧工作流断裂：
  - `test_workspace/cases/`
  - `test_workspace/casesuites/`
  - `test_workspace/tests/fixtures/`
  - `test_workspace/tests/generated/`
- `aitest upgrade --check` 增加只读布局建议：
  - legacy fixture/profile 资产 → 建议迁移到 `test_workspace/targets/{target}/`
  - legacy generated pytest → 建议迁移到 `test_workspace/generated/{target}/`
  - legacy casesuite 资产 → 建议迁移到 `test_workspace/suites/{target}/{suite}/`
- `upgrade --check` 不移动文件、不创建 target 目录、不改写用户已有资产。
- `upgrade --apply` 仍只处理模板托管文件，不自动执行目录迁移。

第三刀状态：

- 已用真实 coupon `calibration` 模块建立最小 target/suite 试点：
  - target: `coupon_system`
  - module: `calibration`
  - suite: `calibration_smoke`
- 试点资产：
  - `test_workspace/targets/coupon_system/target.yaml`
  - `test_workspace/targets/coupon_system/modules/calibration.yaml`
  - `test_workspace/targets/coupon_system/profiles/profile_calibration.md`
  - `test_workspace/suites/coupon_system/calibration_smoke/suite.yaml`
  - `test_workspace/suites/coupon_system/calibration_smoke/profile_calibration_smoke_suite.md`
- `suite.yaml` 只引用现有 Markdown 用例文件，不复制用例：
  - `../../../cases/calibration/business.md`
- 已验证：
  - suite profile gate 通过。
  - suite dump-ir 能从 target module profile 读取 calibration 特有断言规则。
  - suite codegen 输出到 `test_workspace/generated/coupon_system/`。
  - suite `--check` freshness 通过。
  - generated pytest collect-only 收集 14 条用例。
  - `aitest run --suite-file ... -- --collect-only -q` 报告输出到 `test_workspace/reports/coupon_system/`。
- 试点暴露并修复了一个接线问题：
  - `run --suite-file` 的 freshness check 原来错误调用 `codegen --cases <suite.yaml>`。
  - 已改为调用 `codegen --suite-file <suite.yaml> --check`。
  - 已增加回归测试覆盖。
- target helper 第一版已接入：
  - `target.yaml.defaults.helper_dir` 指向 `test_workspace/targets/coupon_system/helpers`。
  - suite codegen 会在 target helper 文件存在时覆盖 `ProjectConfig.helper_import/grpc_helper_import`。
  - `calibration_smoke` generated pytest 已从 target helper 导入：
    - `from test_workspace.targets.coupon_system.helpers import http as http_helper`
- target fixture 第一版已迁移为 bridge：
  - `test_workspace/targets/coupon_system/fixtures/` 下已有当前 legacy fixture 的 target-local 入口。
  - `test_workspace/targets/coupon_system/helpers/` 下已有当前 legacy helper 的 target-local 入口。
  - legacy `test_workspace/tests/fixtures` 和 `test_workspace/tests/helpers` 暂时保留，服务旧 `--all` 和旧 generated 路径。

fixture discovery 问题已解决第一版：

- pytest 能识别 test module 中直接 import 进来的 `@pytest.fixture` 函数。
- suite 带 target 且存在 `module.yaml` 时，codegen 会从：
  - `module.yaml.fixture.file`
  - `module.yaml.fixture.default_fixture`
  自动推导 import：
  - `from test_workspace.targets.<target>.fixtures.<module> import <fixture>`
- 这个 import 会合并进 runtime profile 的 `extra_imports`，不要求 suite profile 或 module profile 重复配置。
- 已验证 `calibration_smoke` generated pytest 中出现：
  - `from test_workspace.targets.coupon_system.fixtures.calibration import setup_calibration`
- 已验证 `calibration_smoke` generated pytest 同时从 target helper 导入：
  - `from test_workspace.targets.coupon_system.helpers import http as http_helper`
- 当前 `coupon_system` 试点里的 target fixture/helper 先作为 bridge，重新导出现有 legacy fixture/helper。
- 后续如果真正迁移 fixture 实现，可以把 bridge 替换成完整 target-local fixture，不需要改 suite 用例和 generated 文件。

验收：

- 新 init workspace 使用新结构。
- 老 workspace 仍可运行。
- `aitest upgrade --check` 能提示结构迁移建议。
- coupon 示例能在新结构下跑通。

验证：

```bash
python3 -m pytest tests/test_workspace_template.py tests/test_upgrade_workspace.py -q
python3 -m aitest_kit.cli init --target /tmp/aitest-new-layout
python3 -m aitest_kit.cli doctor --workspace /tmp/aitest-new-layout
```

子 Agent review：

- 检查模板是否还有旧目录硬编码。
- 检查 README / AGENTS 模板是否和目录结构一致。
- 检查 generated import path 是否稳定。

### Phase 5：Skill 修改

目标：

- 让 skills 理解 target/module/suite/task。
- 不再默认建议把 workspace 注入被测项目。
- test-scaffold 生成 target/module 级 fixture/profile。
- test-codegen 优先按 suite/task 工作。
- test-maintain 能判断何时修改 module、suite、task。

影响 skills：

- `.codex/skills/knowledge-build`
- `.codex/skills/test-design`
- `.codex/skills/test-scaffold`
- `.codex/skills/test-codegen`
- `.codex/skills/test-maintain`
- `.codex/skills/emitter-build`

同步策略：

1. 先改 `.codex/skills/`。
2. 用户 review 后同步 `.claude/skills/` 和 `.agents/skills/`。
3. 同步后跑模板测试和 init 验证。

验收：

- skill 不再把 `aitest_workspace` 注入被测项目作为唯一主路径。
- skill 能解释 target 是被测系统，module 是测试能力边界，suite 是用例批次，task 是执行计划。
- skill 能根据 suite 的 target/module 找 L1/L2、fixture、profile。
- skill 对“新增用例但无 suite profile”“新增 module 但无 fixture”给出正确分流。

验证：

```bash
python3 -m pytest tests/test_workspace_template.py -q
python3 -m aitest_kit.cli init --target /tmp/aitest-skill-layout
find /tmp/aitest-skill-layout/.codex/skills -maxdepth 2 -type f | sort
```

子 Agent review：

- 检查 skill 是否仍引用旧 `--all` 主路径。
- 检查 skill 是否仍默认要求用例在 `test_workspace/cases/{module}`。
- 检查 skill 是否出现和新配置 schema 不一致的字段。

当前状态：

- 已完成第一版 skill 更新，并同步到 `.codex/skills`、`.claude/skills`、`.agents/skills`。
- 已更新：
  - `test-scaffold`：新 scaffold 默认产出 `target.yaml`、`module.yaml`、target fixture/helper、target module profile、`suite.yaml` 和 `profile_{suite}_suite.md`。
  - `test-codegen`：新增 suite 主路径说明，优先使用 `--suite-file <suite.yaml>`，legacy `--cases` 只作为回退。
  - `test-maintain`：影响面检查加入 target registry、target fixture/profile/helper、target generated。
  - `test-design`：明确 test-design 只产出 Markdown 用例，suite 接线交给 scaffold/codegen。
  - `emitter-build`：晋升分析支持 target/suite generated 与 profile 路径。
- 已验证三套 skill 目录 diff 一致。
- 已验证核心 suite 回归：
  - `python3 -m pytest tests/test_codegen_suite_target.py tests/test_codegen_suite_profile.py -q`

### Phase 6：文档修改

目标：

- README 仍保持 3 分钟上手。
- 新增或重写正式迁移指南。
- 更新 profile guide、quickstart、workflow guide。
- 删除或降级旧的 suite/module-only 说明。

文档策略：

- README 展示最短路径：创建独立测试项目、注册一个 target、生成 suite、run suite。
- Migration Guide 展示从旧注入模式迁移到独立测试项目。
- Workflow Guide 展示 target/module/suite/task 的完整心智模型。
- Code Reading Guide 只解释代码，不承载产品教程。

验收：

- 用户能从 README 知道：
  - AITest 是独立测试项目。
  - target 是被测系统。
  - module 维护 fixture/profile。
  - suite 放用例批次。
  - task 做执行编排。
- 文档中不再把 `--all` 解释为目录扫描。
- 文档中明确 suite 只有一个 md 时，跑 suite 等价于跑这个 md。

验证：

```bash
python3 -m pytest tests -q
python3 -m aitest_kit.cli doctor
python3 -m aitest_kit.cli codegen calibration --check
```

子 Agent review：

- 检查 README 是否能 3 分钟上手。
- 检查 Migration Guide 是否覆盖旧用户。
- 检查 docs/usebook 中是否有明显过时主路径。

当前状态：

- 已完成第一版文档同步：
  - `README.md`
  - `docs/usebook/aitest_quickstart.md`
  - `docs/usebook/aitest_migration_guide.md`
  - `docs/usebook/aitest_workflow_guide.md`
  - `docs/usebook/codegen_profile_guide.md`
  - `docs/usebook/codegen_troubleshooting.md`
- 文档主路径已切到：
  - `test_workspace/targets/{target}/`
  - `test_workspace/suites/{target}/{suite}/suite.yaml`
  - `test_workspace/generated/{target}/`
  - `aitest codegen --suite-file ...`
  - `aitest run --suite-file ...`
- legacy `--all` / module mode 只作为兼容说明保留。

## 备份与回滚

每个阶段开始前：

```bash
git status --short --branch -uall
```

涉及目录结构迁移前：

```text
test_workspace/backups/<timestamp>/
```

备份对象：

- `test_workspace/tests/fixtures/`
- `test_workspace/tests/helpers/`
- `test_workspace/tests/generated/`
- `test_workspace/cases/`
- `test_workspace/casesuites/`
- `aitest_config/`
- `.codex/skills/`

原则：

- 不备份运行产物 `reports/`，除非正在验证 report 重构。
- 不删除旧目录，先保留兼容。
- 不重写 generated 以外的用户文件，除非明确在 spec 当前阶段内。
- 大范围迁移前必须先在 coupon 示例上做 dry-run 或临时目录验证。

## 验证基线

每个阶段至少执行：

```bash
python3 -m pytest tests -q
python3 -m aitest_kit.cli doctor
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
```

说明：

- 在 `--all` 重构前，继续用当前命令做回归基线。
- 当 registry-driven all 完成后，把验证命令切换为新语义。

coupon 必跑：

```bash
python3 -m aitest_kit.cli codegen calibration --validate-profile
python3 -m aitest_kit.cli codegen calibration --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

必要时 DragonCode 验证：

```bash
python3 -m aitest_kit.cli doctor --workspace /Users/zmw/DragonCode-sub2api/aitest_workspace
python3 -m aitest_kit.cli codegen --workspace /Users/zmw/DragonCode-sub2api/aitest_workspace --all --validate-profile
python3 -m aitest_kit.cli codegen --workspace /Users/zmw/DragonCode-sub2api/aitest_workspace --all --check
```

DragonCode 只作为真实项目验证，不作为每次小改的强制门禁。

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 一次性重构过大 | 破坏 codegen/run/report 主链路 | 严格六阶段，阶段间提交 |
| 配置字段膨胀 | 用户难以理解 | Phase 3 专门做字段精简 |
| 新旧目录并存 | 文档和 skill 混乱 | 兼容期明确 legacy 标识 |
| 外部路径安全 | 误读或误写用户文件 | 只读外部 case/knowledge，generated/reports 默认写测试项目 |
| report 路径推断失效 | 报告归类错误 | metadata 驱动，路径推断只做 fallback |
| DragonCode 等真实项目断裂 | 发布风险 | 每阶段必要时做真实项目验证 |
| skill 与代码不同步 | AI 继续生成旧结构 | Phase 5 专门改 skill，先 `.codex` 后同步 |

## 非目标

本轮重构不做：

- 自动创建测试资源。
- 跨 workspace 联合报告。
- 多 target 独立虚拟环境管理。
- 自动启动/停止被测服务。
- 前端 UI 测试 IR。
- 自动应用 promotion patch。
- 直接删除所有 legacy 命令。

这些可以在 target/module/suite/task 主架构稳定后再设计。

## 第一阶段完成定义

Phase 1 完成时，应具备：

1. spec 被确认。
2. target/module/suite/task 数据结构和 loader 有测试覆盖。
3. coupon 能被映射成 target。
4. 现有 codegen/run/report 不被破坏。
5. 子 Agent 或独立 review 输出结构性问题清单。
6. 用户确认后再进入 Phase 2。
