# Profile Execution Binding Layer vNext Spec

## 背景

当前 codegen 的稳定路径是：

```text
Markdown suite + module profile + suite profile
  -> profile gate
  -> parser
  -> Case IR planner
  -> pytest renderer
```

Markdown 是人类 review 的测试意图源，pytest 是编译产物。profile 位于中间，负责把测试意图绑定到 fixture/helper、请求构造、断言规则和多步骤流程。

真实项目迁移时暴露出一个底层架构问题：请求构造目前没有成为独立的一等中间层。

当前事实：

- `request_overrides` 是顶层字段，主要服务 `default_http/default_grpc`。
- `case_flows` 一旦接管某条 case，`request_overrides` 不会自动生效。
- 迁移时 AI 容易在 `case_flow.kwargs` 里把 JSON 请求体作为字符串传入 fixture。
- 复杂请求变换、数组追加、字段删除、整段替换缺少标准表达。
- 集合断言、遍历断言容易退化为 raw assert 或 `case_bodies`。

因此，本 spec 不再把 Phase 1 定义为“新增 request_patches”，而是升级为：

```text
Unified Request Binding + JSON Patch
```

## 目标

1. 保持 Markdown 作为测试意图源，不把执行细节塞回 Markdown。
2. 将 profile 定位为 AI 生成、代码校验、人类可审查的 execution binding layer。
3. 建立统一请求绑定层，让 `default_http/default_grpc` 和 `case_flows` 共用同一套请求构造能力。
4. 使用结构化 YAML 表达请求差异，禁止把 JSON 对象伪装成字符串传入 profile。
5. 使用 JSON Patch 覆盖嵌套 dict/list、删除字段、数组追加、整段替换等复杂请求变换。
6. 引入结构化断言能力，减少常见集合断言对 raw Python assert 或 `case_bodies` 的依赖。
7. 保留 `case_bodies` 作为复杂控制流逃生通道，但让稳定重复模式有晋升路径。
8. 新架构不追求老 profile 字段长期兼容，但必须提供 `aitest upgrade` 迁移路径。

## 方案 A：Breaking Cleanup 决策

本轮按方案 A 一次性收敛断言层，不保留旧模板兼容。

1. `structured_assertions` 是唯一的结构化断言字段。
2. 试验字段 `assertion_templates` 不兼容、不读取、不自动降级；旧 workspace 通过 `aitest upgrade` 或人工改 profile。
3. `named_templates` 机制删除，不再由 `aitest.yaml.codegen.named_templates` 维护复杂断言宏。
4. `assertion_rules.template` 只表示直接渲染的 Python assert 模板字符串，不再引用命名模板。
5. 复杂公式、循环、条件、等待、跨响应业务计算不扩展 YAML 语言，沉淀到 fixture/helper 方法，再由 `case_flow.call` 调用。
6. `structured_assertions.target` 必须能在当前生成策略下解析为真实运行时变量：default 路线只允许 `resp`，case_flow 路线只能引用该 flow 产生的 `save_as`/`assign` 变量。
7. skills 按旧流程处理：先只改 `.codex`，用户 review 后再同步 `.claude`、`.agents` 和 init 模板 skills。

## 非目标

1. 不把全部 profile 都改成 JSON Patch。
2. 不在 YAML 中实现 `if` / `for` / `while` / `try` 等完整控制流。
3. 不删除 `case_bodies`。
4. 不长期兼容旧顶层 `request_overrides` 运行语义。
5. 不让用户主要手写 profile；人类主要 review Markdown、profile 摘要、Case IR 和关键绑定。
6. 不一次性重构所有历史文档和 lesson；只同步对用户工作流有实际影响的文档。

## Canonical Profile vNext

vNext profile 的核心字段：

```yaml
variables:
  defaults: {}
  cases: {}

requests:
  TC-DEMO-001:
    base: shared
    overrides:
      userId: u001
      pageSize: 20
    patches:
      - op: add
        path: /items/-
        value:
          sku: A001
          count: 2

case_flows:
  TC-DEMO-001:
    fixture: setup_demo_api
    object: client
    steps:
      - call: client.create_order
        kwargs:
          body: {request_ref: self}
        save_as: resp

structured_assertions:
  TC-DEMO-001:
    - type: jsonpath_equals
      target: resp
      path: $.code
      equals: 0
```

旧字段处理原则：

- `request_overrides` 不再作为 vNext 推荐字段。
- `request_patches` 不作为独立顶层推荐字段。
- `aitest upgrade --apply` 负责把旧字段迁移到 `requests.<case_id>.overrides/patches`。
- codegen vNext 可以拒绝旧字段，提示用户先运行 `aitest upgrade`。

## 核心设计

profile 分为五层：

```text
profile execution binding
├── variables
│   └── 运行变量和值来源
├── requests
│   └── 统一请求绑定：base + overrides + patches
├── case_flows
│   └── 线性动作编排，可通过 request_ref 引用 requests
├── assertion_rules / structured_assertions
│   └── 结构化断言和自然语言/表达式断言映射
└── case_bodies
    └── 复杂控制流逃生通道，稳定后由 emitter-build 评估晋升
```

### 统一请求绑定层

`requests` 是一等中间层。它不属于 default_http，也不属于 case_flow，而是两者都可以引用。

请求构造顺序固定：

```text
shared_config.base_request_http
  -> project default_request.auto_fields
  -> profile requests.<case_id>.overrides
  -> profile requests.<case_id>.patches
  -> RequestBindingIR
  -> generated pytest request object
```

`requests.<case_id>` 字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `base` | string | 否 | 第一版只支持 `shared`，默认 `shared` |
| `overrides` | object | 否 | 普通结构化覆盖 |
| `patches` | list | 否 | JSON Patch 操作 |

示例：

```yaml
requests:
  TC-ORDER-001:
    overrides:
      user_id: u001
      scene: checkout
    patches:
      - op: replace
        path: /filters/0/status
        value: active
      - op: add
        path: /items/-
        value:
          id: item_002
          count: 1
      - op: remove
        path: /debug
```

JSON Patch 约束：

- 第一阶段支持 `add`、`replace`、`remove`。
- `path` 使用 JSON Pointer。
- `add` / `replace` 必须有 `value`。
- `remove` 不允许有 `value`。
- `move`、`copy`、`test` 第一阶段不暴露。
- patch 只作用于最终请求体，不作用于 profile 自身。

### default_http/default_grpc 与 requests

default 路线不再直接读取旧 `request_overrides`，而是默认读取：

```text
requests[self]
```

也就是：

```text
TC-DEMO-001 default_http
  -> build_request("TC-DEMO-001")
  -> http_helper.post(..., json=body)
```

如果某条 default case 没有 `requests.<case_id>`，仍可以使用共享基础请求体 + auto_fields。

### case_flow 与 requests

`case_flow` 通过 `request_ref` 引用统一请求绑定：

```yaml
case_flows:
  TC-ORDER-001:
    fixture: setup_order_api
    object: client
    steps:
      - call: client.create_order
        kwargs:
          body: {request_ref: self}
        save_as: resp
```

`request_ref` 规则：

| 写法 | 含义 |
|---|---|
| `{request_ref: self}` | 引用当前 case_id 的 request binding |
| `{request_ref: TC-ORDER-001}` | 引用指定 case_id 的 request binding |

渲染目标：

```python
__request = build_request("TC-ORDER-001")
resp = client.create_order(body=__request)
```

约束：

- `request_ref` 必须引用存在的 `requests.<case_id>`，或当前 case 可从 shared base 生成 request。
- `case_flow.kwargs` 中看起来像 JSON 对象/数组的字符串，应产生 validator warning 或 error。
- 如果确实需要 raw string body，必须使用明确命名，例如 `raw_body`，避免误把 JSON 字符串当结构化请求。

### RequestBindingIR

新增或重构 IR：

```python
RequestBindingIR
  case_id: str
  base_source: str
  auto_fields: dict
  overrides: dict
  patches: list[RequestPatchIR]
  source_trace: dict
```

`CaseIR` 应持有：

```python
request_binding: RequestBindingIR | None
```

不论 case 使用 default 路线还是 `case_flow`，只要它需要请求体，都应能关联同一套 `RequestBindingIR`。

### 断言层

新增结构化断言，不通过 YAML 控制流表达循环。

第一批 `structured_assertions` 类型：

```yaml
structured_assertions:
  TC-DEMO-001:
    - type: jsonpath_equals
      target: resp
      path: $.code
      equals: 0
    - type: jsonpath_all_equals
      target: resp
      path: $.data.items[*].publishStatus
      equals: 0
    - type: jsonpath_len_gte
      target: resp
      path: $.data.items
      value: 1
    - type: jsonpath_field_in_set
      target: resp
      path: $.data.items[*].status
      values: [active, pending]
```

第一阶段支持：

- `jsonpath_equals`
- `jsonpath_exists`
- `jsonpath_not_exists`
- `jsonpath_all_equals`
- `jsonpath_any_equals`
- `jsonpath_len_equals`
- `jsonpath_len_gte`
- `jsonpath_field_in_set`

约束：

- 结构化断言生成确定性 Python assert。
- 结构化断言必须出现在 Case IR 中，`--dump-ir` / `--explain` 可审查。
- 复杂业务计算沉淀到 fixture/helper assertion 方法，不扩展 YAML 运算语言。

### case_flow 边界

`case_flows` 继续表达线性动作编排：

```yaml
case_flows:
  TC-DEMO-001:
    fixture: setup_demo_api
    object: client
    steps:
      - call: client.create_resource
        kwargs:
          body: {request_ref: self}
        save_as: create_resp
      - call: client.query_resource
        args:
          - {ref: create_resp["id"]}
        save_as: query_resp
```

边界：

- 允许 `call`、`assign`、`assert`、`comment`。
- 不新增 YAML `for` / `if` / `while`。
- 需要循环、条件、等待、重试时，应封装到 fixture/helper 方法里，由 `case_flow.call` 调用。

### case_body 边界

`case_bodies` 保留为逃生通道，适合：

- 并发
- mock server 生命周期
- 文件上传下载
- WebSocket
- 异步任务轮询
- 复杂 cleanup
- 第三方上游模拟
- profile/fixture/helper 尚未沉淀的探索性复杂逻辑

约束：

- `case_bodies` 不是默认路线。
- 已稳定且重复出现的 body 应进入 `emitter-build` 分析。
- 晋升方向优先级：fixture/helper -> structured_assertions -> case_flows -> builtin emitter。

## Upgrade 策略

不做长期前向兼容，但必须提供 workspace upgrade。

### upgrade 输入

旧 profile 可能包含：

```yaml
request_overrides:
  TC-DEMO-001:
    user_id: u001
```

未来如果已有旧试验字段，也可能包含：

```yaml
request_patches:
  TC-DEMO-001:
    - op: add
      path: /items/-
      value: {id: item_001}
```

### upgrade 输出

统一迁移为：

```yaml
requests:
  TC-DEMO-001:
    overrides:
      user_id: u001
    patches:
      - op: add
        path: /items/-
        value: {id: item_001}
```

### upgrade 规则

1. `request_overrides.<case_id>` -> `requests.<case_id>.overrides`。
2. `request_patches.<case_id>` -> `requests.<case_id>.patches`。
3. 如果 `requests.<case_id>` 已存在，upgrade 合并后输出 diff，遇到冲突时停止并要求人工确认。
4. `case_flow.kwargs` 中 JSON 字符串不自动迁移，只输出 warning 和定位路径。
5. upgrade 不改 Markdown 用例语义。
6. upgrade 不修改 generated pytest；用户需要重新 codegen。

### upgrade 验证

```bash
aitest upgrade --check --workspace <workspace>
aitest upgrade --apply --workspace <workspace>
aitest codegen --suite-file <suite.yaml> --validate-profile
aitest codegen --suite-file <suite.yaml> --check
```

## 受影响文件

### 代码

| 文件 | 影响 |
|---|---|
| `aitest_config/schemas/codegen_profile.schema.json` | 新增 canonical `requests`、`structured_assertions`；移除或禁止旧 `request_overrides` |
| `aitest_kit/codegen/profile_validator.py` | 校验 `requests`、`request_ref`、patch op/path/value、JSON 字符串 body warning |
| `aitest_kit/codegen/profile.py` | 加载 `requests`、`structured_assertions` |
| `aitest_kit/codegen/profile_merge.py` | 合并 module profile + suite profile 中的 `requests`、`structured_assertions` |
| `aitest_kit/codegen/planner.py` | 构造 RequestBindingIR；default 和 case_flow 都读取统一 request binding |
| `aitest_kit/codegen/case_flow_planner.py` | 支持 `{request_ref: self|TC-ID}` |
| `aitest_kit/codegen/ir.py` | 增加 RequestBindingIR、RequestPatchIR，结构化断言复用或扩展现有 AssertionIR |
| `aitest_kit/codegen/ir_renderer.py` | 渲染统一 request builder、request_ref、structured assertion |
| `aitest_kit/codegen/render_utils.py` | JSON Pointer/JSONPath 渲染辅助函数 |
| `aitest_kit/codegen/suite_runner.py` | `--dump-ir`、`--explain`、`--check` 展示新增 IR |
| `aitest_kit/codegen/profile_validation_report.py` | 展示 requests/structured_assertions 诊断摘要 |
| `aitest_kit/upgrade/` 或现有 upgrade 模块 | 迁移旧 profile 字段到 canonical `requests` |

### 测试

| 文件 | 影响 |
|---|---|
| `tests/test_codegen_ir.py` | default 和 case_flow 共用 RequestBindingIR 的主路径 |
| `tests/test_codegen_profile_validator.py` | schema/语义校验、错误诊断、JSON 字符串 warning |
| `tests/test_codegen_suite_runner.py` | dump-ir/check/explain 包含 request binding |
| `tests/test_codegen_profile_merge.py` | module/suite profile 合并 `requests` |
| `tests/test_upgrade.py` 或相关 upgrade 测试 | 旧字段迁移到 `requests` |

### 文档

| 文件 | 影响 |
|---|---|
| `docs/usebook/codegen_profile_guide.md` | 增加 execution binding、requests、request_ref、structured_assertions |
| `docs/usebook/codegen_troubleshooting.md` | 增加 request_ref、patch path、JSON 字符串 body 错误排查 |
| `docs/usebook/aitest_getting_started.md` | 简短说明 profile 是 execution binding，不是手写 pytest 替代品 |
| `README.md` / `README.en.md` | 更新 profile 能力和路线说明 |
| `aitest_config/refs/config-files.md` | 更新 profile 字段手册 |
| `aitest_kit/templates/project_workspace/aitest_config/refs/config-files.md` | init 模板同步 |

### Skills

skills 修改必须单独 review 后再改，不在 Phase 1 直接批量同步。

| 文件 | 影响 |
|---|---|
| `.codex/skills/test-scaffold/SKILL.md` | 生成 suite profile 时优先使用 `requests`、`request_ref`、`structured_assertions` |
| `.codex/skills/test-codegen/SKILL.md` | 解释新字段、dump-ir/check 验证路径 |
| `.codex/skills/emitter-build/SKILL.md` | 从 case_body/raw assert 晋升到 structured_assertions 或 helper |
| `.claude/skills/...` | 待 `.codex` review 通过后同步 |
| `.agents/skills/...` | 待 `.codex` review 通过后同步 |
| `aitest_kit/templates/project_workspace/skills/...` | 待运行中 skill review 通过后同步模板 |

## 分阶段实现

### Phase 1：Unified Request Binding

目标：统一 default 和 case_flow 的请求构造能力。

实现项：

1. schema 增加 canonical `requests`。
2. validator 校验：
   - 顶层旧 `request_overrides` 在 vNext schema 中报错，并提示运行 upgrade。
   - `requests.<case_id>` 必须引用 suite 内存在的 case。
   - `base` 第一版只允许 `shared`。
   - `overrides` 必须是 mapping。
   - `patches` 必须是 patch list。
   - patch op 仅支持 `add`、`replace`、`remove`。
   - `request_ref` 必须引用存在 request binding 或当前 case 可生成 shared request。
   - `case_flow.kwargs` 中 JSON 字符串 body 产生 warning 或 error。
3. profile merge：
   - module/suite 都配置同一 case 的 `requests` 时，suite 覆盖或扩展 module。
   - `overrides` 使用深合并。
   - `patches` 按顺序拼接，module patches 在前，suite patches 在后。
4. planner：
   - 新增 RequestBindingIR。
   - default_http/default_grpc 使用 RequestBindingIR。
   - structured_case_flow 如果有 `request_ref`，同样关联 RequestBindingIR。
5. renderer：
   - 生成统一 request builder。
   - default 路线调用 builder。
   - case_flow 渲染 `{request_ref: ...}` 为结构化 request object。
6. upgrade：
   - `request_overrides` -> `requests.*.overrides`。
   - `request_patches` -> `requests.*.patches`。
   - JSON 字符串 kwargs 只给 warning，不自动改。
7. tests：
   - default_http 使用 `requests`。
   - case_flow 使用 `{request_ref: self}`。
   - case_flow 引用其他 case 的 request。
   - patch add/replace/remove。
   - 旧 `request_overrides` 被 validator 拒绝。
   - upgrade 迁移旧字段。

验收：

```bash
python3 -m pytest tests/test_codegen_ir.py tests/test_codegen_profile_validator.py -q
python3 -m pytest tests/test_upgrade.py -q
python3 -m pytest tests -q
python3 -m compileall aitest_kit
```

### Phase 2：Structured Assertions

目标：减少集合断言、JSONPath 断言对 raw assert/case_body 的依赖。

实现项：

1. schema 增加 `structured_assertions`。
2. validator 校验：
   - case_id 必须存在。
   - `type` 必须是支持集合。
   - `target` 必须是变量名或支持的响应对象引用。
   - JSONPath 字段必须是非空字符串。
   - 不同 type 的必填字段明确。
3. planner：
   - 将 `structured_assertions` 转为 `AssertionIR(kind=structured_assertion)`。
   - `resolved_by` 使用 `profile.structured_assertions.<case_id>`。
4. renderer：
   - 生成 deterministic assert。
   - 使用 `jsonpath_ng` 或包内 helper。
5. tests：
   - `jsonpath_all_equals` 覆盖 `items[*].publishStatus == 0`。
   - `jsonpath_len_gte`。
   - path 不匹配时生成可读失败信息。

验收：

```bash
python3 -m pytest tests/test_codegen_ir.py tests/test_codegen_profile_validator.py -q
python3 -m pytest tests -q
python3 -m compileall aitest_kit
```

### Phase 3：Profile Review Surface

目标：让人类 review 中间层摘要，而不是逐行读 YAML。

实现项：

1. `--dump-ir` 展示 request binding 和 structured assertions。
2. `--explain TC-ID` 输出：
   - base request 来源
   - auto fields
   - request overrides
   - request patches
   - request_ref 使用点
   - case_flow steps
   - structured assertions
   - final strategy
3. `--health-report` 增加：
   - raw assert 数量
   - structured_assertions 数量
   - case_bodies 数量
   - JSON string kwargs warning 数量
   - 可晋升候选提示

### Phase 4：Skills 与文档同步

目标：让 AI 新增 suite profile 时使用 canonical 中间层。

执行纪律：

1. 先改 `.codex` 版本并给用户 review。
2. review 通过后同步 `.claude`、`.agents`。
3. 最后同步 init 模板 `skills/`。

实现项：

1. `test-scaffold`：
   - 简单字段变化写 `requests.<case_id>.overrides`。
   - 深层 list/dict 删除/追加/整段替换写 `requests.<case_id>.patches`。
   - case_flow 调用请求体时使用 `{request_ref: self}`。
   - 集合断言写 `structured_assertions`。
   - 循环/条件/等待封装到 helper，不在 profile 造控制流。
2. `test-codegen`：
   - 新增 profile 字段排查说明。
   - UNPARSED 断言优先回写 structured_assertions/assertion_rules。
3. `emitter-build`：
   - raw assert / case_body 可晋升到 structured_assertions 或 helper。
4. 文档：
   - profile 是 execution binding layer。
   - 人类主要 review Markdown、profile 摘要、Case IR，不默认手写整份 profile。

## 后续统一架构 Backlog

本 spec 的 Phase 1 只直接处理请求构造层。除此之外，当前项目还有几个需要记录但不在 Phase 1 一次性解决的统一点。

记录原则：

- 只记录会影响长期架构清晰度的点。
- 不把所有问题塞进本次实现，避免重构范围失控。
- 每个后续点都必须能被未来独立 spec 接走。

### 1. 断言绑定层

现状：

- Markdown 断言可能是自然语言、表达式、raw Python assert。
- profile 有 `assertion_rules`。
- case_flow 里也能写 raw assert。

问题：

- 断言入口分散，AI 容易直接写 raw assert。
- 集合断言、JSONPath 断言、字段存在性断言缺少统一结构化表达。
- 人类 review 时难判断断言是业务意图、profile 映射还是 Python 逃生。

建议：

- Phase 2 先引入 `structured_assertions`。
- 后续把“自然语言/表达式 -> assertion rule -> template -> Python assert”链路统一到一个 assertion planner。
- raw assert 作为逃生，不作为推荐格式。

触发独立 spec 的条件：

- 真实项目中 raw assert 持续增加。
- `items[*].field`、列表长度、字段存在性、排序、范围断言重复出现 3 次以上。

### 2. 变量与资源层

现状：

- `variables.defaults/cases` 已存在。
- runtime env、fixture 内部 env、case 级变量、测试资源 alias 还没有完全统一。

问题：

- env、case variable、fixture 内部常量、测试账号/API key 等来源分散。
- 缺变量时能报告 `PRECONDITION_MISSING`，但“需要什么测试资源”还不是一等模型。
- 不同用例需要不同账号/key 时，容易在 fixture/profile 里硬写变量名。

建议：

- 短期维持 `variables`。
- 后续再设计 `resources`，但不在本 spec 实现。
- 不把资源自动创建做进 Phase 1，避免系统过重。

触发独立 spec 的条件：

- 同一 suite 内出现多个测试账号/API key/resource alias。
- 报告中 PRECONDITION_MISSING 无法解释“缺的是哪类资源”。
- 用户明确需要运行前资源准备、清理或风险门禁。

### 3. profile review surface

现状：

- 人类容易被迫读 YAML。
- `--dump-ir` / `--explain` 已存在，但不是 profile review 的主界面。

问题：

- profile 是中间层，不应该要求人逐行审 YAML。
- 当前 review 粒度更偏底层字段，缺少“这条 case 最终怎么构造请求、怎么调用、怎么断言”的摘要。

建议：

- Phase 3 强化 `--explain`，让 review 关注“这条 case 最终如何构造请求、如何调用、如何断言”。

触发独立 spec 的条件：

- `requests` / `request_ref` / `structured_assertions` 上线后，profile YAML 复杂度继续上升。
- 人工 review 主要卡在“看不懂这条 case 会生成什么 pytest”。

### 4. generated helper 复用

现状：

- renderer 可能在 generated pytest 中生成辅助函数。
- 随着 request builder、json patch、jsonpath assertion 增加，generated 文件可能膨胀。

问题：

- 如果每个 generated 文件都内联 request builder / JSON Patch / JSONPath helper，生成文件会越来越吵。
- generated pytest 是编译产物，应该尽量薄，稳定逻辑应放包内 helper。

建议：

- 请求构造、JSON Patch、JSONPath assertion 尽量放到包内 helper。
- generated pytest 只调用稳定 helper。

触发独立 spec 的条件：

- Phase 1/2 后 generated pytest 出现明显 helper 重复。
- lint/compile/阅读成本因 generated helper 增加。

### 5. upgrade 与 schema 演进

现状：

- `aitest upgrade` 已存在，但 profile schema 演进还需要更明确的迁移责任。

问题：

- 如果 schema breaking change 没有 upgrade，用户 workspace 会在升级后直接不可用。
- 如果 codegen 静默兼容旧字段，架构会长期背负多套语义。

建议：

- breaking schema change 必须配套 upgrade。
- 新版本 codegen 遇到旧字段时，明确提示 upgrade，而不是静默兼容。

触发独立 spec 的条件：

- 每次新增/删除 profile 顶层字段。
- 每次 target/module/suite/task 配置语义出现 breaking change。

### 6. profile ownership 与生成责任

现状：

- profile 是 codegen 输入，但通常由 AI 根据 Markdown、fixture、知识库生成。
- 文档里仍容易让用户误解成“人类需要手写整份 profile”。

问题：

- 如果用户大量手写 profile，AITest 会退化成换格式写 pytest。
- 如果 profile 完全不可审，又会变成黑盒中间产物。

建议：

- profile 定位为 AI 生成、代码校验、人类 review 摘要和 IR 的 execution binding。
- skills 应指导 AI 产出 profile，同时给人类展示 route table / request binding / assertion binding 摘要。

触发独立 spec 的条件：

- Phase 3 review surface 完成后，仍发现用户主要在直接编辑 YAML。

## 风险和约束

1. JSON Patch path 错误会导致运行时失败。profile gate 能检查格式，但在没有实际 base request 时不能保证所有 path 存在。
2. 如果结构化断言类型过多，会演变成 DSL 膨胀。第一阶段只做高频类型。
3. 如果把循环/条件下放到 profile，会破坏可维护性。复杂控制流必须留在 fixture/helper 或 `case_bodies`。
4. 不做老字段长期兼容会影响已有 workspace，因此 upgrade 必须先实现并测试。
5. 现有 generated pytest 不应手工迁移。能力上线后按 suite 重新 codegen。

## 推荐实施顺序

1. Phase 1：Unified Request Binding。
2. 用 coupon 或 discount 类小项目验证 default 和 case_flow 共用 request binding。
3. 用真实迁移场景验证 JSON 字符串 kwargs warning 和 upgrade。
4. Phase 2：Structured Assertions。
5. Phase 3：Profile Review Surface。
6. Phase 4：skills 与文档同步，先 `.codex` review，再同步其他目录。

## 回滚策略

- schema breaking change 必须配套 upgrade；回滚时恢复旧 profile 文件或重新运行旧版本 codegen。
- 新 generated pytest 是编译产物，可删除后用旧版本重新生成。
- 不修改 Markdown 用例语义，不强制迁移历史 suite 的业务描述。
