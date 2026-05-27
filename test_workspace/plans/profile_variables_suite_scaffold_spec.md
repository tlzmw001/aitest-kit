# Profile Variables And Suite Scaffold Spec

## 背景

DragonCode 真实项目试点暴露出一个比 Runtime Preconditions 更基础的问题：

同一个模块、同一个 fixture/driver 下，不同用例经常需要传入不同变量，例如：

- 登录成功用普通账号密码。
- 管理端操作用管理员账号或管理员 token。
- 网关调用用不同 API key。
- 401/403 用例故意不传 token 或传错误 token。
- 边界用例要覆盖不同 URL、header、query、请求字段。

当前 scaffold 主要把环境变量理解成 fixture 需要的模块级配置，容易退化成“一套 env 支撑整个模块”。这对简单模块可用，但对真实商用系统不够：

- 某些用例不需要 admin token，却可能被模块级 fixture 初始化拖死。
- 某些用例故意测试无 token，却可能被统一 env check 提前拦截。
- 账号、密码、API key、请求字段等数据散落在 fixture 或 case_flow 里，不方便人 review。
- suite profile 已经实现，但还没有充分发挥“用例目录和 generated pytest 解耦”的价值。

本 spec 的目标是用轻量方式补齐“变量面板”和 suite scaffold 的心智模型，而不是立即建设完整测试资源系统。

## 第一性原理

AITest Kit 可以类比为 AI 驱动的低代码自动化测试平台：

| 低代码自动化平台 | AITest Kit 对应物 | 职责 |
|---|---|---|
| 操作节点 / 可拖拽模块 | Driver/Client action 方法 | 登录、创建 key、调用接口、查询 Redis |
| 变量面板 | profile variables | base_url、username、password、token、请求字段 |
| 流程编排 | case_flow | call / assign / assert / comment |
| 平台执行计划 | Case IR | 解析后的结构化执行计划 |
| 导出的脚本 | generated pytest | 编译产物 |
| 执行报告 | aitest run/report | 结果、分类、反哺 |

更准确的术语边界：

- pytest fixture：依赖注入和生命周期管理，负责创建 driver/client、准备和清理资源。
- Driver/Client action：测试动作库，负责调用公开 API 或测试可观测接口，例如 `login()`、`create_api_key()`、`query_redis()`。
- helper：底层通用工具，例如 HTTP/Redis/gRPC 封装、JSONPath、轮询、通用断言。
- profile variables：用例变量面板，说明这批用例或这条用例使用什么数据。
- case_flow：动作编排，说明调用哪些 action、传哪些变量、保存哪些中间变量、执行哪些断言。

核心边界：

```text
fixture 注入 driver
driver 暴露 action
variables 提供数据
case_flow 编排 action
Case IR 解释执行计划
pytest 只是编译产物
```

## 目标

1. 让一份 case suite 可以独立携带自己的 suite profile，并生成对应 pytest。
2. 让 suite profile 可以声明本 suite 和每条 case 的变量。
3. 让 case_flow 可以通过 `{var: name}` 引用变量，而不是把 env 名或值散落在步骤里。
4. 让 fixture/driver 专注动作能力，不按 case_id 分发，不决定某条用例该用哪个账号。
5. 保持目录和模块低耦合：fixture/action 属于模块，variables/case_flow 属于 suite。
6. 强化 test-scaffold 的人类 review 交互，先 review action/variables/route 样例，再全量生成。

## 非目标

本期不做：

- 不在 `case_flow` 里引入 `if` / `loop` / `try` 等控制结构。
- 不建设完整 Test Resources 生命周期系统。
- 不自动注册用户、创建真实 API key、充值、消耗额度或调用高风险上游。
- 不自动修改 `.env`。
- 不读取或打印 env 变量值。
- 不把 project-specific 规则写进框架，例如 `SUB2API_ADMIN_TOKEN`、`low_balance_api_key` 这类项目专名。
- 不让 module profile 维护 suite profile 索引。
- 不让 fixture 感知 suite 名或 case_id。
- 不把 test-design 的测试维度 review 流程塞进 test-scaffold。

后续可做但不在本期：

- Runtime Preconditions 的结构化异常和报告分类。
- `resources` provider，如 `active_user`、`active_api_key`。
- 自动创建且可 cleanup 的低风险临时资源。
- 高风险资源的 sandbox/mock 策略。
- case_flow 级 named flow template。
- 更丰富的变量 provider，如 secret manager、文件、表达式、上一步输出到变量面板。

## Profile Variables 设计

### 数据来源

第一版只支持两种变量来源：

```yaml
env: ENV_NAME
value: literal
```

含义：

- `env`：运行时先从 `os.environ` 读取，缺失时读取 dotenv 文件；默认读取当前工作目录 `.env`，若设置 `AITEST_ENV_FILE` 则读取该指定文件。缺失时应失败，并且不能打印变量值。
- `value`：profile 中的字面量，适合错误密码、固定请求字段、非法枚举、固定 URL path 片段等。

暂不支持：

- `ref`
- `resource`
- `expr`
- secret manager
- 数据库或远端配置读取

### 推荐结构

变量应优先放在 suite profile：

```yaml
profile_scope: case_suite
parent_module: management_auth_user
suite: login_smoke

variables:
  defaults:
    base_url:
      env: SUB2API_BASE_URL

  cases:
    TC-LOGIN-001:
      username:
        env: SUB2API_NORMAL_USER_EMAIL
      password:
        env: SUB2API_NORMAL_USER_PASSWORD

    TC-LOGIN-002:
      username:
        env: SUB2API_ADMIN_USER_EMAIL
      password:
        env: SUB2API_ADMIN_USER_PASSWORD

    TC-LOGIN-003:
      username:
        env: SUB2API_NORMAL_USER_EMAIL
      password:
        value: wrong-password
```

解析规则：

```text
case variables = variables.defaults + variables.cases[case_id]
case 级变量覆盖 default 同名变量
```

第一版不做 suite/module 多级复杂继承。module profile 可以不放 variables，避免职责混乱。

### case_flow 引用变量

case_flow 的 `args` / `kwargs` 支持 `{var: name}`：

```yaml
case_flows:
  TC-LOGIN-001:
    fixture: setup_management_auth_user
    object: auth
    steps:
      - call: auth.login
        kwargs:
          username:
            var: username
          password:
            var: password
        save_as: resp
      - assert: assert resp.status_code == 200
```

渲染语义：

```python
__tc_vars__ = resolve_case_variables(__tc_meta__)
resp = auth.login(
    username=__tc_vars__["username"],
    password=__tc_vars__["password"],
)
```

变量缺失或 env 未设置时，后续 Runtime Preconditions 方案会提供结构化错误；本 spec 先定义数据模型和 scaffold/codegen 接线方向。

## case_flow 默认 setup 设计

真实模块里经常出现同一类重复前置动作，例如每条用例都需要先从 fixture 注入的 factory 创建带 `case_id` 的 case client：

```yaml
default_fixture: setup_validation_ratelimit
default_object: client_factory
default_case_setup:
  call: client_factory
  kwargs:
    case_id: "{case_id}"
  save_as: case
```

语义：

- `default_fixture` 给未显式声明 `fixture` 的 `case_flows` 补 pytest fixture。
- `default_object` 给 fixture 注入对象起别名，例如 generated pytest 中先生成 `client_factory = setup_validation_ratelimit`。
- `default_case_setup` 自动插入到每条 `case_flow.steps` 前面，`{case_id}` 替换为当前用例 ID。
- 单条 `case_flow` 可以显式声明 `fixture` / `object` 覆盖默认值。
- 如果某条 `case_flow` 已经手写了完全相同的第一步，codegen 不重复插入，便于老 profile 渐进迁移。

目标不是引入复杂继承，而是把“每条 flow 都重复的 factory setup”上收到 profile 顶层，降低 profile 膨胀。

## Suite Profile 解耦模型

### 三层职责

| 层 | 生命周期 | 职责 |
|---|---|---|
| fixture `{module}.py` | 随模块能力变化 | Driver/Client、action、cleanup |
| module profile `codegen_profile_{module}.md` | 随 L1 模块稳定能力变化 | module_type、extra_imports、default fixture/object、通用 assertion_rules |
| suite profile `codegen_profile_{suite}_suite.md` | 随某批用例变化 | variables、case_flows、case_bodies、request_overrides |

规则：

- 新增一批用例时，优先新增 suite profile。
- 只有 fixture/action 能力不足时，才回到 `test-scaffold incremental` 修改 fixture/module profile。
- module profile 不维护 `sub_profiles` 索引。
- suite profile 跟着用例目录走。

### suite manifest

每个用例 suite 目录通过 `aitest_suite.yaml` 声明归属：

```yaml
module: management_auth_user
suite: login_smoke
case_files:
  - business.md
  - boundary.md
profile: codegen_profile_login_smoke_suite.md
```

执行入口：

```bash
python3 -m aitest_kit.cli codegen --cases test_workspace/casesuites/login_smoke
python3 -m aitest_kit.cli codegen --cases test_workspace/casesuites/login_smoke --check
```

目标效果：

```text
用户提供一份 case suite
  -> scaffold-suite 生成 suite profile
  -> codegen --cases 生成对应 pytest
  -> run/report 按 suite 输出
```

### pytest 文件命名

对于 suite 目录下的 case 文件，生成文件建议包含 module + suite + case file stem：

```text
casesuites/login_smoke/business.md
  -> test_management_auth_user_login_smoke_business.py

casesuites/login_smoke/boundary.md
  -> test_management_auth_user_login_smoke_boundary.py
```

原因：

- 避免和模块传统 `business.md` / `boundary.md` 冲突。
- 让 report 和文件名都能直观看到 suite 来源。
- 不要求用户为了拆 pytest 文件而理解框架内部拆分规则；用户拆 case 文件即可自然拆 generated pytest。

## 复杂逻辑承载原则

第一版 `case_flow` 不支持 `if` / `loop` / `try`。

复杂逻辑按以下路线承载：

| 场景 | 承载位置 |
|---|---|
| 不同账号、token、URL、请求字段 | profile variables |
| 多步骤调用和中间变量 | case_flow |
| 分页、等待、轮询、重试 | Driver action/helper |
| 并发、mock、复杂控制流 | case_body |
| 稳定重复的复杂控制逻辑 | 晋升为 action/helper 或 named template |
| 单次特殊逻辑 | 保留 case_body，并记录原因 |

不把 `case_flow` 做成完整脚本语言。否则会引入新的调试和解释成本，违背“代码负责稳定重复”的初衷。

## test-design 与 test-scaffold 边界

测试维度拆分、按点分节、复杂用例推导、全部用例标题 review 属于 `test-design`。

`test-scaffold` 不负责设计测试维度，不从零生成测试用例。

边界：

```text
test-design:
  设计测试维度
  给出每节复杂用例推导
  生成人类可 review 的 Markdown case

test-scaffold:
  读取已有 case
  设计 fixture/driver action
  设计 variables matrix
  选择 case_flow/case_body 路线
  生成 module profile 或 suite profile

test-codegen:
  编译 case + profile 为 pytest
```

## test-scaffold Review 交互

`test-scaffold` 应采用分阶段 review，减少返工。

### scaffold-module 模式

模块还没有 fixture/module profile 时：

1. 输出 API/action 候选表。
2. 输出 Driver/Client 方法签名表。
3. 输出变量候选表，只做变量面板，不做资源系统。
4. 输出 1-2 条代表性 case_flow 样例。
5. 用户确认后再写 fixture/module profile。

示例 review 表：

```markdown
## Driver Actions

| action | 参数 | 返回 | 说明 |
|---|---|---|---|
| login | username, password | httpx.Response | 调登录接口 |
| get_profile | token | httpx.Response | 查询当前用户 |
| create_api_key | admin_token, name | httpx.Response | 管理端创建 key |

## Variables

| variable | source | scope | 用途 |
|---|---|---|---|
| base_url | env: SUB2API_BASE_URL | default | 服务地址 |
| username | case env/value | case | 登录用户名 |
| password | case env/value | case | 登录密码 |
| admin_token | case env | case | 管理接口认证 |
```

### scaffold-suite 模式

已有 fixture/module profile，用户提供 case suite 时：

1. 读取 suite case 文件和 module action 能力。
2. 输出 variables matrix。
3. 输出路线分布：default/case_flow/case_body/skipped/manual。
4. 展示 1-2 条复杂 case 的完整 suite profile 片段。
5. 用户确认后生成 `aitest_suite.yaml` 和 suite profile。

不在此阶段重新设计测试维度。

### incremental 模式

当 test-codegen 发现现有 fixture/action 不足时：

1. 只分析新增能力缺口。
2. 追加最小 action/helper。
3. 更新对应 suite profile，不重写已有 profile。
4. 重新运行 codegen/check/collect。

## 子 Agent 使用策略

可用子 Agent 提升效率，但主 Agent 保留架构判断。

适合子 Agent：

- 从 docs/knowledge/cases 提取 API/action 候选。
- 从 case suite 扫描变量需求，生成 variables matrix 草稿。
- 扫描状态影响和 cleanup 风险。
- 根据已确认样例生成全量 case_flow 草稿。

主 Agent 必须负责：

- 统一 action/variable 命名。
- 删除过度设计。
- 检查 fixture、module profile、suite profile 的边界。
- 挑选代表性 case 给用户 review。
- 最终写文件和跑验证。

子 Agent 只降低上下文负担，不替代主 Agent 对质量的判断。

## 对现有实现的影响

### 仅更新 scaffold skill 的影响

如果本阶段只强化 scaffold 说明，不实现 profile variables：

修改文件：

```text
.codex/skills/test-scaffold/SKILL.md
.codex/skills/test-scaffold/refs/formats.md
.codex/skills/test-scaffold/refs/constraints.md
.claude/skills/test-scaffold/...
.agents/skills/test-scaffold/...
aitest_kit/templates/project_workspace/.codex/skills/test-scaffold/...
aitest_kit/templates/project_workspace/.claude/skills/test-scaffold/...
aitest_kit/templates/project_workspace/.agents/skills/test-scaffold/...
```

效果：

- 不改变 CLI 行为。
- 不改变 profile schema。
- 不改变 generated pytest。
- 只改善 AI scaffold 的产物结构和 review 交互。

### 实现 profile variables 的影响

需要修改：

```text
aitest_config/schemas/codegen_profile.schema.json
aitest_kit/templates/project_workspace/aitest_config/schemas/codegen_profile.schema.json
aitest_kit/codegen/profile.py
aitest_kit/codegen/profile_validator.py
aitest_kit/codegen/ir.py
aitest_kit/codegen/planner.py
aitest_kit/codegen/ir_renderer.py
aitest_kit/codegen/render_utils.py
tests/test_codegen_*.py
docs/usebook 或 codegen profile guide
```

可能新增：

```text
aitest_kit/runtime_variables.py
```

职责：

- 解析 `env` / `value`。
- 不泄露 env 值。
- 为后续 `PreconditionMissing` 和 report 分类打基础。

### 后续 report/precondition 的影响

如果要把缺 env 分类成结构化报告，还会涉及：

```text
aitest_kit/report/classifier.py
aitest_kit/report/collector.py
aitest_kit/report/renderer.py
tests/test_classifier.py
tests/test_report_*.py
```

这属于后续 Runtime Preconditions 阶段，不是本 spec 第一优先实现项。

## 验收标准

### scaffold 文档层

1. `test-scaffold` 明确区分 fixture、driver action、helper、variables、case_flow。
2. `test-scaffold` 不包含 test-design 的测试维度生成流程。
3. `refs/formats.md` 包含 variables matrix 和 suite profile variables 示例。
4. `refs/constraints.md` 包含复杂逻辑承载规则和 fixture/action 边界。
5. 三套 skill 和 workspace template 保持同步。

### profile variables 实现层

1. Profile schema 支持 `variables.defaults` 和 `variables.cases`。
2. 变量 item 只支持 `env` 或 `value`，且二者互斥。
3. `case_flow` 的 `args` / `kwargs` 支持 `{var: name}`。
4. `--validate-profile` 能发现：
   - 未定义变量引用。
   - 非法变量结构。
   - `env` / `value` 同时出现。
   - case_id 不存在。
5. `--dump-ir` 能看到每条 case resolved variables 的来源。
6. generated pytest 不包含 env 值，只在运行时读取。
7. 缺 env 时测试失败，错误信息包含 env 名，不包含 env 值。
8. `codegen --cases <suite_dir> --check` 能稳定判断 suite generated pytest 是否过期。

### suite 解耦层

1. 用户提供一个独立 case suite 目录即可生成 suite profile 和 pytest。
2. module profile 不需要修改来登记新 suite。
3. fixture 不感知 suite 名。
4. generated pytest 文件名包含 module + suite + case file stem。
5. report metadata 能保留 suite 信息。

## 推荐实施顺序

### Phase 1：先改 scaffold 说明，不改 codegen

- 修改 `test-scaffold` 和 refs。
- 明确 variables matrix、action review、suite profile review。
- 在 DragonCode 试点中重新 review 一个 suite，验证人类 review 是否更顺畅。

### Phase 2：实现 profile variables MVP

- 支持 `variables.defaults` / `variables.cases`。
- 支持 `env` / `value`。
- 支持 `{var: name}` 在 case_flow args/kwargs 中引用。
- 扩展 schema、validator、IR、renderer、测试。
- 运行时支持 `.env` / `AITEST_ENV_FILE` 作为 env 变量兜底来源。

### Phase 3：补 report/precondition 分类

- 增加统一缺 env 错误。
- report 输出 `PRECONDITION_MISSING`。
- 不自动 skip。

### Phase 4：设计 test resources

- 引入资源 provider。
- 只从低风险、可 cleanup 资源开始。
- 高风险资源保持 env/manual。

## 关键设计结论

1. `fixture 是动作库`不是严谨术语；应表述为：fixture 注入 driver，driver 暴露 actions。
2. `variables` 是比 `env groups` 更轻、更贴近当前痛点的模型。
3. suite profile 是 variables 和 case_flow 的首选归属地，因为它跟着用例走。
4. module profile 只承载模块稳定能力，不索引 suite，不承载 L2 迭代用例的大量 case_flow。
5. case_flow 不扩展为脚本语言，复杂控制逻辑放到 action/helper/case_body。
6. scaffold 负责接线和变量/action review，不负责测试维度设计。
7. 子 Agent 可以参与提取和草稿生成，但主 Agent 必须负责边界、命名和质量判断。
