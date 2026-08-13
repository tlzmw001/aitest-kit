# Module Harness Architecture Spec

## 状态

- 决策状态：已确认，进入实现。
- 变更类型：breaking architecture cleanup。
- 目标版本：后续开发版本，版本号在完整验证后决定。
- 实现分支：`codex/module-harness-architecture`。

## 背景

AITest 当前已经形成稳定的编译主线：

```text
Markdown cases
  + suite.yaml
  + module profile
  + suite profile
      -> profile gate
      -> Markdown parser
      -> Case IR planner
      -> pytest renderer
      -> generated pytest
      -> run / report
```

这条主线解决了测试意图、执行绑定和编译产物之间的职责分离，不在本次重构中推倒。

当前不稳定的是 module 运行能力层。框架同时向 profile 作者暴露了多种 fixture 使用方式：

- fixture 直接返回 Client。
- fixture 直接返回 Context。
- fixture 返回 factory，再由 `default_case_setup` 创建 case object。
- 单条 flow 覆盖 `fixture` / `object`。
- `case_fixtures` 为个别 case 改变 pytest 函数签名。

这些模式在 Python 中都能工作，但会迫使 AI 在每个新模块和 suite 中重新做架构选择。真实样例还出现了以下问题：

- fixture 按 `case_id` 分发测试数据或运行分支。
- fixture 文件同时承担协议 Client、业务动作、配置写入、断言计算和 cleanup。
- 未使用的依赖在 fixture setup 阶段被提前初始化，导致无关环境变量阻塞用例。
- module fixture 注册同时出现在 `module.yaml`、module profile 和 suite flow 中。

## 第一性原理决策

pytest fixture 的价值是依赖注入和生命周期管理，而不是为每条用例提供一套不同的编排语言。

AITest 对 profile/codegen 只公开一个稳定模型：

```text
一个 module
  -> 一个公开 pytest fixture: setup_{module}
  -> fixture 返回一个 {Module}Harness
  -> generated pytest 中固定命名为 harness
  -> case_flow 只编排 harness 能力和已生成的中间变量
```

Harness 不替代 pytest fixture。它是 module 测试能力的公开门面；内部仍可组合：

- session/module/function scope pytest fixture。
- `tmp_path`、`caplog`、`monkeypatch`、数据库事务和共享进程池。
- HTTP/gRPC Client。
- Redis、Nacos、消息队列和文件系统工具。
- `yield`、finalizer、context manager 和 `ExitStack` cleanup。
- 每 case 独立进程、mock server、临时文件或测试数据。

这些内部依赖不暴露给 suite profile。

## 保留的架构

本次保留：

- target / module / suite / task 概念。
- Markdown 作为测试意图源。
- module profile + suite profile 的运行时合并。
- profile gate、Case IR、renderer、freshness check。
- `requests`、profile variables、structured assertions。
- `case_flow` 的线性步骤模型。
- `case_body` 作为复杂运行器控制的逃生通道。
- framework helper 与 target 内已证实复用的技术 helper 按归属分层。
- generated pytest 是编译产物，不作为长期手写源文件。

## Canonical 目录

module 所有资产按所有权归到同一个目录：

```text
test_workspace/
├── targets/
│   └── {target}/
│       ├── target.yaml
│       ├── helpers/                      # target 内跨 module 已证实复用的纯技术适配，可选
│       └── modules/
│           └── {module}/
│               ├── __init__.py
│               ├── module.yaml
│               ├── profile.md
│               ├── fixture.py
│               ├── harness.py
│               ├── api.py               # 按需
│               ├── testdata.py          # 按需
│               ├── config_management.py # 按需
│               ├── assertions.py        # 按需
│               └── resources.py         # 按需
└── suites/
    └── {target}/
        └── {suite}/
            ├── suite.yaml
            ├── *.md
            └── profile_{suite}_suite.md
```

规则：

- `modules/{module}/module.yaml` 是唯一 module registry 文件。
- `modules/{module}/profile.md` 是唯一 module profile。
- `modules/{module}/fixture.py` 是唯一公开 fixture 模块。
- 公开 fixture 符号固定为 `setup_{module}`。
- Harness 类推荐命名为 `{ModulePascalCase}Harness`。
- suite profile 继续跟随 suite，不移入 module。
- 不预先创建空的 `api.py`、`testdata.py` 等文件；职责出现后再创建。
- 避免宽泛的 `actions.py`、`utils.py` 和 `common.py`。
- 不再建立 `test_workspace/helpers/`。当前没有跨 target 共享的用户工具，未来若出现真实复用需求再单独设计。
- target helper 不承载业务动作、测试数据或断言；这些能力必须归入对应 module package。

## Helper 作用域

工具代码放到能够覆盖所有实际调用者的最小作用域：

```text
aitest_kit.helpers
  跨 workspace 稳定的框架内置能力

test_workspace/targets/{target}/helpers
  同一 target 内已经被多个 module 使用的 proto、认证或协议适配

test_workspace/targets/{target}/modules/{module}/*.py
  只属于一个 module 的业务测试能力
```

目录按需存在，不要求每个项目建立全部层级。target helper 只有在第二个 module 出现真实调用后才抽取；首次出现的工具先留在 module 内。`aitest_kit.helpers` 是框架发布包内部能力，不是用户 workspace 的自由扩展目录。

## Module Manifest

`module.yaml` 只保留模块事实和聚合索引：

```yaml
target: coupon_system
module: calibration
module_type: multi_endpoint

knowledge_refs:
  l1:
    - test_workspace/knowledge/L1/calibration.md

registered_suites:
  - suite: calibration_smoke
    manifest: test_workspace/suites/coupon_system/calibration_smoke/suite.yaml
    status: active
```

删除以下配置选择：

```yaml
fixture:
  file: ...
  default_fixture: ...
helpers: [...]
profile: ...
```

fixture、profile 和 module package 路径全部由 canonical 目录推导。helper 不需要注册；普通 Python import 是事实来源。

## Harness Contract

每个 module 的 `fixture.py` 只公开一个 fixture：

```python
import pytest

from .harness import CalibrationHarness


@pytest.fixture
def setup_calibration(...) -> CalibrationHarness:
    harness = CalibrationHarness(...)
    try:
        yield harness
    finally:
        harness.close()
```

允许 `setup_calibration` 依赖 private/shared pytest fixtures：

```python
@pytest.fixture(scope="session")
def _service_pool():
    ...


@pytest.fixture
def setup_calibration(_service_pool, tmp_path) -> CalibrationHarness:
    ...
```

约束：

- `setup_{module}` 必须返回或 yield Harness，不得返回 factory。
- 额外 module-local fixture 必须以 `_` 开头，仅作为实现细节。
- 不按 TC-ID 新建 fixture。
- fixture 不读取未被 Harness 实际使用的业务 env。
- fixture 不按 `case_id` 选择账号、请求、配置或业务分支。
- Harness 使用资源栈记录已创建资源，`close()` 只清理实际初始化的资源。
- Harness capability 优先按需初始化，避免无关依赖阻塞当前 case。

## Harness 内部组织

Harness 是薄门面和资源所有者，不是新的大文件：

```python
class CalibrationHarness:
    @cached_property
    def api(self) -> CalibrationApi:
        return CalibrationApi.from_env()

    @cached_property
    def config(self) -> CalibrationConfig:
        return CalibrationConfig(self.resources)

    @cached_property
    def assertions(self) -> CalibrationAssertions:
        return CalibrationAssertions()

    def close(self) -> None:
        self.resources.close()
```

环境变量由实际使用它的 capability 读取：

```text
harness.api.recommend()
  -> 读取 API base URL

harness.grpc.recommend()
  -> 读取 gRPC target

harness.nacos.publish()
  -> 读取 Nacos 连接信息
```

只调用 HTTP 的 case 不应因缺少 gRPC/Nacos/Redis 环境变量失败。

## Canonical Case Flow

suite profile 不再选择 fixture 或 object。generated pytest 的对象名固定为 `harness`：

```yaml
case_flows:
  TC-CAL-001:
    steps:
      - call: harness.config.write_linear_rules
        kwargs:
          rules: [...]
      - call: harness.api.recommend
        kwargs:
          body: {request_ref: self}
        save_as: resp
      - call: harness.assertions.matches_linear
        args:
          - {ref: resp}
        kwargs:
          k: 1.2
          b: 0.1
        save_as: matched
      - assert: "assert matched"
```

`call` 根对象规则：

- 第一个根对象只能是固定的 `harness`，或前序 `save_as` / `assign` 生成的变量。
- 不允许直接调用 pytest fixture 名。
- 不允许 suite profile 用 `extra_imports` 绕过 Harness。
- 复杂循环、条件、等待和重试写入 Harness capability 的普通 Python 函数。
- `case_flow` 继续只支持 `call`、`assign`、`assert`、`comment`。

## Profile 收敛

从可编写 profile schema 删除：

- `default_fixture`
- `default_object`
- `default_case_setup`
- `case_fixtures`
- `case_flows.*.fixture`
- `case_flows.*.object`

module profile 只保留跨 suite 稳定的生成能力：

- `assertion_rules`
- `variables.defaults`
- 必要且稳定的 module-level imports；后续评估是否继续收敛。

suite profile 继续承载：

- `variables`
- `requests`
- `structured_assertions`
- `case_flows`
- `case_bodies`

`module_type` 的唯一事实来源是 `module.yaml`，不再重复写入 module profile。

## Case Body 规则

`case_body` 保留，但 generated pytest 只注入 canonical Harness：

```python
def test_complex_case(self, setup_demo):
    harness = setup_demo
    # custom body
```

不再通过 `case_fixtures` 改变函数签名。case body 需要的临时目录、mock、进程或数据库事务也必须通过 Harness 访问。

## Runtime Binding 和 Case IR

module fixture binding 不再伪装成 profile 作者字段。

`SuiteContext` / `RuntimeProfile` 应携带独立的 module binding：

```text
ModuleBinding
  target
  module
  fixture_module
  fixture_import
  fixture_name = setup_{module}
  object_name = harness
```

renderer 使用 `pytest_plugins = [fixture_module]` 注册整个 module fixture 模块，而不是只 import `setup_{module}` 符号。这样 `setup_{module}` 才能依赖同文件的 private fixture；`fixture_import` 继续用于解释、诊断和静态检查。

Planner 对不同策略使用固定绑定：

```text
default_http
  fixtures = [http_base_url]

structured_case_flow
  fixtures = [setup_{module}]
  object = harness

custom_case_body
  fixtures = [setup_{module}]
  object = harness

manual / skipped
  fixtures = []
```

Case IR 继续记录已解析的 fixture 和 object，保证 `--dump-ir` / `--explain` 可见；但它们来自 module registry binding，不来自 profile 选择。

## Validator 和 Doctor

profile gate 必须阻断：

- 已删除的 fixture/object/default setup 字段。
- `case_flow.call` 使用未知根对象。
- suite profile 使用 `extra_imports`。
- 非 manual flow 只有 comment。
- request/variable/save_as 的非法引用。

doctor 必须检查：

- canonical module 目录完整。
- `module.yaml` 的 target/module 与目录一致。
- `fixture.py` 存在。
- `setup_{module}` 可 import，且确实是 pytest fixture。
- fixture 返回注解或 yield 路径符合 Harness contract。
- `harness.py` 和 Harness 类型存在。
- 除 `setup_{module}` 外没有额外公开 module fixture。
- module profile 和所有 active suite profile 通过 gate。
- generated freshness 和 collect 通过。

可静态识别但不适合硬阻断的模式使用 warning：

- fixture/Harness 按 `case_id` 分发。
- Harness 构造阶段集中读取多个可选依赖 env。
- Harness 或 fixture 文件超过约定规模。
- capability 方法包含无法追踪的 cleanup。

## Upgrade

本项目尚未商用，本次不维持旧 profile 运行兼容层，但 `aitest upgrade` 必须提供迁移辅助：

1. `--check` 识别旧 module 目录、fixture 配置和旧 profile 注入字段。
2. `--apply` 只执行可机械完成的目录移动、字段删除和 import 更新，并先备份。
3. factory fixture、`case_id` 分发和 `case_fixtures` 需要语义重写时，生成明确 blocker，不自动猜测。
4. upgrade 后必须重新运行 scaffold/codegen review，不承诺 generated pytest 字节级不变。
5. 不静默保留 legacy loader fallback。

## 实现阶段

### Phase 1：框架 contract

- 新增 `ModuleBinding`。
- registry loader 切换 canonical module 目录。
- suite runtime profile 携带 module binding。
- planner/renderer 固定注入 `setup_{module}` 和 `harness`。
- schema 删除多注入字段。
- validator 增加固定根对象和 profile scope 校验。
- 更新单元测试，建立 breaking contract。

### Phase 2：诊断和迁移

- doctor 增加 Harness contract 检查。
- upgrade 增加旧 module/fixture/profile 迁移诊断和可机械迁移步骤。
- CLI help 和错误信息指向 canonical module 结构。

### Phase 3：内置样例迁移

- 迁移 `discount_system`。
- 迁移 `coupon_system` 全部 module。
- 删除 factory fixture 和 `case_id` 分发表。
- 将 module 专属能力按职责拆分。
- 删除任何 workspace 顶层 helper。
- 已被多个 module 复用的 target 纯技术 helper 保持 target 级；其余能力迁入 module package。
- suite profile 全部改为 `harness.*` 调用。

### Phase 4：skills、模板和文档

- 核心代码和样例验证完成后，先修改 `.codex` skill 供用户 review。
- 用户确认后再同步 `.claude`、`.agents` 和 init 模板 skills。
- 更新配置手册、profile guide、troubleshooting、README 和 getting started。
- init 模板只生成 canonical module 布局说明，不生成虚假示例数据。

## 验收标准

1. profile schema 不再允许 fixture/object/factory 选择字段。
2. 每个可执行 module 只有一个公开 `setup_{module}` fixture。
3. 所有 structured case flow 的生成对象名都是 `harness`。
4. suite profile 不需要知道 pytest 内部 fixture。
5. default HTTP 不隐式执行 module Harness。
6. case body 只通过 Harness 获取运行能力。
7. 未使用的 capability 不读取 env、不建立连接。
8. 所有 module/suite profile gate 通过。
9. 所有 generated pytest freshness check 通过。
10. 全量 pytest collect 通过。
11. coupon 和 discount 真实服务测试通过；无法启动的外部依赖必须明确记录。
12. `doctor` 能识别破坏 Harness contract 的模块。
13. upgrade 能识别旧 workspace 并给出可执行迁移结果或明确 blocker。
14. workspace 中不存在 `test_workspace/helpers/`；module 专属能力不再散落于 target 级目录。

## Review 修复项

首轮实现 review 后，以下问题纳入本 spec 的完成范围：

1. `setup_{module}` 只装配轻量 Harness；HTTP、gRPC、Redis、AB、配置文件和隔离服务环境变量由实际使用它们的 capability 按需解析。
2. registry loader 硬校验 module 调用名、module package 目录名、`module.yaml.module` 三者一致，并校验每个 registered suite 的 target/module 归属。
3. `case_flow` 的 call path、kwargs、`save_as` 和 `assign` 必须是合法且非 Python keyword 的标识符；禁止覆盖 `harness` 等框架保留绑定。
4. `assertion_rules` 只允许写在 module profile；suite profile 出现该字段必须由 profile gate 明确阻断，不能静默丢弃。
5. Harness teardown 中关键共享状态恢复不得被次要资源清理失败阻断；清理错误必须可见。
6. `.codex` 的 scaffold/emitter 示例必须分别展示 `harness.py` 与 `fixture.py`，且 assertion rule 不得引用默认策略中不存在的 `harness` 变量。

本轮明确不修改 module promotion 的跨 suite 聚合算法，该事项保持独立决策。

## 主要验证命令

```bash
python3 -m pytest tests -q
python3 -m aitest_kit.cli doctor
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m compileall aitest_kit test_workspace/targets test_workspace/generated
python3 -m pytest test_workspace/generated --collect-only -q
```

真实服务验证按 target 的公开启动方式和 env contract 单独执行，不修改被测系统实现来迁就测试。

## 明确不做

- 不新增 Case Spec 层。
- 不新增 capability name registry。
- 不把 YAML 扩展为 `if/for/while/try` 编程语言。
- 不删除 Case IR。
- 不合并 Markdown 与 profile。
- 不把 target 专属 proto/helper 提升为框架内置 helper。
- 不允许 AI 为新增 suite 或 case 新建第二个公开 fixture。
