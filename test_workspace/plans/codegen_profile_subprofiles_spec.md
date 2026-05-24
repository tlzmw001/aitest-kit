# Codegen Module Profile + Case Suite Profile Spec

## 背景

正式项目里，测试知识库通常分两层：

- L1：模块级长期知识，例如接口面、认证方式、通用错误格式、共享状态准备能力。
- L2：需求变更或测试批次，例如一次计费改造、一次登录流程调整、一次模型路由策略变更。

当前 codegen 默认把模块、用例目录、profile 绑定在一起：

```text
test_workspace/cases/{module}/business.md
test_workspace/tests/fixtures/codegen_profile_{module}.md
  -> test_workspace/tests/generated/test_{module}_business.py
```

这个模型在简单项目里够用，但在真实项目里会让 profile 膨胀，也会让 case 和 codegen 过度耦合。理想模型应当是：

```text
L1 module profile 是稳定资产；
case suite 是流动资产；
suite profile 跟着用例走；
codegen 运行时临时合并 module profile + suite profile。
```

因此，本 spec 将前一版 “master profile 索引 sub_profiles” 升级为 “module profile + case suite profile”。后者解耦性更好：新增一批用例时，不需要修改 L1 module profile。

## 目标

1. 先基于 L1 知识生成模块级 fixture 和 module profile。
2. 任意目录下的一批 Markdown 用例可以声明自己属于哪个 L1 module。
3. test-scaffold 基于这批用例生成跟随用例的 suite profile。
4. codegen 运行时合并 module profile + suite profile，生成对应 pytest。
5. generated pytest 文件名由模块名和用例文件名决定：`test_{module}_{case_file_stem}.py`。
6. 是否把 100 条用例拆成多个 pytest 文件，由用户先拆多个 Markdown 文件决定；codegen 不负责理解“每 20 条拆分”的语义。

## 非目标

1. 不让 module profile 反向索引所有 suite profile。
2. 不要求所有用例必须放在 `test_workspace/cases/{module}`。
3. 不让 codegen 自动决定如何拆分用例文件。
4. 不改变 Markdown 用例本身的基础格式。
5. 不自动应用 promotion patch。
6. 不把 suite profile 做成新的编程语言；复杂控制流仍下沉 fixture/helper 或保留 case_body。

## 核心概念

| 名称 | 含义 |
|---|---|
| module | L1 模块，例如 `gateway_api` |
| case suite | 一批相关 Markdown 用例，通常来自某个 L2 或某个临时测试批次 |
| module fixture | `test_workspace/tests/fixtures/{module}.py`，模块级 Client/helper/cleanup |
| module profile | `test_workspace/tests/fixtures/codegen_profile_{module}.md`，模块级 codegen 能力 |
| suite profile | 跟随用例目录的 `codegen_profile_{suite}_suite.md` |
| suite manifest | 跟随用例目录的 `aitest_suite.yaml`，说明这批用例属于哪个 module |
| runtime profile | codegen 运行时合并 module profile + suite profile 得到的内存结构 |

依赖方向：

```text
case suite -> suite manifest -> module profile
case suite -> suite profile -> module profile
```

不是：

```text
module profile -> sub profiles
```

## 推荐目录形态

模块级稳定资产：

```text
test_workspace/knowledge/L1/gateway_api.md
test_workspace/tests/fixtures/gateway_api.py
test_workspace/tests/fixtures/codegen_profile_gateway_api.md
```

一批 L2 用例可以放在 workspace 内：

```text
test_workspace/casesuites/quota_billing_v2/
  aitest_suite.yaml
  business.md
  boundary.md
  codegen_profile_quota_billing_v2_suite.md
```

也可以放在用户指定的任意目录：

```text
/path/to/customer_cases/quota_billing_v2/
  aitest_suite.yaml
  business.md
  boundary.md
  codegen_profile_quota_billing_v2_suite.md
```

多个 pytest 文件来自多个 Markdown 文件：

```text
test_workspace/casesuites/quota_billing_v2/
  billing_business.md
  billing_boundary.md
  billing_state.md
```

生成：

```text
test_workspace/tests/generated/test_gateway_api_billing_business.py
test_workspace/tests/generated/test_gateway_api_billing_boundary.py
test_workspace/tests/generated/test_gateway_api_billing_state.py
```

## suite manifest

`aitest_suite.yaml` 是用例目录的轻量入口。它只描述归属和输出，不承载生成细节。

```yaml
module: gateway_api
suite: quota_billing_v2
knowledge_refs:
  l1: test_workspace/knowledge/L1/gateway_api.md
  l2: test_workspace/knowledge/L2/quota_billing_v2.md
case_files:
  - business.md
  - boundary.md
profile: codegen_profile_quota_billing_v2_suite.md
```

规则：

1. `module` 必填，用于定位 module fixture 和 module profile。
2. `suite` 必填，用于报告、临时输出和错误定位。
3. `case_files` 可选；省略时 codegen 扫描当前目录下所有 `.md` 用例文件，排除非用例文档。
4. `profile` 可选；默认按 `codegen_profile_{suite}_suite.md` 查找。
5. `knowledge_refs` 可选但推荐，帮助 AI 修复时回到 L1/L2 来源。

## module profile

module profile 是 L1 级能力，不应随着每批用例变化。

```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.tests.fixtures.gateway_api import setup_gateway_api"

assertion_rules:
  - name: "gateway standard error"
    pattern: "..."
    template: "..."

default_fixture: setup_gateway_api
default_object: client
```

职责：

1. 声明 module_type。
2. 提供模块级 imports。
3. 提供共享 assertion_rules。
4. 记录默认 fixture/object 约定。
5. 不索引 suite profile。
6. 不承载频繁变化的 L2 case_flow，除非是少量历史兼容用例。

## suite profile

suite profile 跟随用例目录，文件名必须带 `_suite`：

```text
codegen_profile_quota_billing_v2_suite.md
```

YAML 示例：

```yaml
profile_scope: case_suite
parent_module: gateway_api
parent_profile: test_workspace/tests/fixtures/codegen_profile_gateway_api.md
suite: quota_billing_v2
knowledge_refs:
  l1: test_workspace/knowledge/L1/gateway_api.md
  l2: test_workspace/knowledge/L2/quota_billing_v2.md

case_flows:
  TC-GW-041:
    fixture: setup_gateway_api
    object: client
    steps:
      - call: client.create_api_key
        kwargs:
          quota: 0
        save_as: http_resp
      - assign: resp
        expr: http_resp.json()
      - assert: 'assert http_resp.status_code == 400'
      - assert: 'assert resp["error"] == "QUOTA_INVALID"'
```

允许字段：

| 字段 | 说明 |
|---|---|
| `profile_scope` | 必须为 `case_suite` |
| `parent_module` | 必须等于 suite manifest 的 `module` |
| `parent_profile` | 可选，默认由 module 推导 |
| `suite` | 必须等于 suite manifest 的 `suite` |
| `knowledge_refs` | 可选但推荐 |
| `extra_imports` | suite 专用 import，少量使用 |
| `request_overrides` | suite 内 case 级请求覆盖 |
| `case_fixtures` | suite 内 case 级 fixture 签名 |
| `case_bodies` | suite 内 case 级自定义 Python body |
| `case_flows` | suite 内 case 级结构化流程 |

不推荐字段：

| 字段 | 规则 |
|---|---|
| `module_type` | 由 module profile 声明；suite profile 不覆盖 |
| `assertion_rules` | 第一版只放 module profile；避免 suite 间规则冲突 |

## runtime merge 规则

codegen 根据命令输入确定 case source，再合并 profile。

```text
module profile + suite profile -> runtime profile
```

合并规则：

| 字段 | 规则 |
|---|---|
| `module_type` | 只从 module profile 读取 |
| `extra_imports` | module + suite 顺序合并去重 |
| `assertion_rules` | 第一版只从 module profile 读取 |
| `request_overrides` | suite 覆盖范围内按 case_id 使用；与 module 同 case_id 重复时报 ERROR |
| `case_fixtures` | 按 case_id 合并；重复时报 ERROR |
| `case_bodies` | 按 case_id 合并；重复时报 ERROR |
| `case_flows` | 按 case_id 合并；重复时报 ERROR |

冲突必须报 ERROR：

1. suite manifest 缺少 `module` 或 `suite`。
2. module profile 不存在。
3. suite profile 不存在且用例无法走默认模板。
4. suite profile 的 `parent_module` 与 manifest `module` 不一致。
5. 同一个 case_id 同时存在于 `case_bodies` 和 `case_flows`。
6. suite profile 引用了当前 case suite 不存在的 case_id。
7. 当前 case suite 有不可默认生成的 case，但 suite profile 未覆盖。

## CLI 形态

保留当前模块级命令：

```bash
python3 -m aitest_kit.cli codegen gateway_api
```

新增 case suite 模式：

```bash
python3 -m aitest_kit.cli codegen --cases /path/to/quota_billing_v2
```

如果没有 `aitest_suite.yaml`，允许显式指定 module：

```bash
python3 -m aitest_kit.cli codegen --module gateway_api --cases /path/to/quota_billing_v2
```

推荐验证顺序：

```bash
python3 -m aitest_kit.cli codegen --cases /path/to/quota_billing_v2 --validate-profile
python3 -m aitest_kit.cli codegen --cases /path/to/quota_billing_v2 --dump-ir
python3 -m aitest_kit.cli codegen --cases /path/to/quota_billing_v2
python3 -m aitest_kit.cli codegen --cases /path/to/quota_billing_v2 --check
```

## 生成文件命名

输入文件：

```text
/path/to/quota_billing_v2/business.md
/path/to/quota_billing_v2/boundary.md
/path/to/quota_billing_v2/state.md
```

生成文件：

```text
test_workspace/tests/generated/test_gateway_api_business.py
test_workspace/tests/generated/test_gateway_api_boundary.py
test_workspace/tests/generated/test_gateway_api_state.py
```

如果不同 suite 中存在同名用例文件，会冲突。因此正式项目推荐用户给用例文件带语义前缀：

```text
quota_billing_business.md
quota_billing_boundary.md
auth_refresh_business.md
```

生成：

```text
test_gateway_api_quota_billing_business.py
test_gateway_api_quota_billing_boundary.py
test_gateway_api_auth_refresh_business.py
```

codegen 不负责按 20 条拆文件。需要多个 pytest 文件时，用户先拆多个 Markdown 用例文件。

若目标 generated 文件已存在，但记录的 source case file 与当前 suite 不一致，codegen 必须报冲突错误，不允许静默覆盖。后续可增加 `--output-dir` 支持临时输出目录，但默认正式产物仍写入 `test_workspace/tests/generated/`。

## test-scaffold 分工

### scaffold-module

输入：

1. L1 知识库和公开 API 文档。
2. 一份最小冒烟 case suite，用于锚定真实调用路径、认证方式、响应结构和基础断言。

输出：

```text
test_workspace/tests/fixtures/{module}.py
test_workspace/tests/fixtures/codegen_profile_{module}.md
```

```text
smoke/
  aitest_suite.yaml
  smoke.md
```

1. 至少覆盖一个最基础成功路径。
2. 至少覆盖一个认证或基础错误路径；若模块无认证，则覆盖一个参数校验错误。
3. 只断言公开契约中稳定字段，不断言未定义实现细节。
4. 数据准备必须可重复，不能依赖一次性人工状态。

scaffold-module 的定位是“基于 L1 + 冒烟用例建立模块基础测试能力”，不是一次性覆盖所有 L2 场景。

它的完成标准是：

1. 能从 L1/API 文档识别端点、认证、环境变量、通用错误格式。
2. 生成 Client 方法签名和基础实现。
3. 生成 module profile 的 module_type、extra_imports、共享 assertion_rules、默认 fixture/object。
4. 通过 `compileall`。
5. 通过 `aitest doctor` 的 fixture/profile 静态检查。
6. 冒烟 case suite 的 `--validate-profile`、`--dump-ir`、`codegen --cases ... --check` 和 collect-only 通过。

后续 L2 迭代如果发现 fixture 缺少端点方法、cleanup、env 分层或 helper，再通过 scaffold-suite/test-fix 修改 module fixture 和 suite profile。fixture 是随项目测试深度逐步扩展的稳定资产，不要求第一天覆盖全部未来用例。

### scaffold-suite

输入：case suite 目录 + module profile + fixture。

输出：

```text
{cases_dir}/aitest_suite.yaml
{cases_dir}/codegen_profile_{suite}_suite.md
```

完成标准：

1. suite profile 覆盖所有默认模板无法稳定生成的 case。
2. `--validate-profile` 无 ERROR。
3. `--dump-ir` strategy 符合预期。
4. `codegen --cases ... --check` 通过。
5. collect-only 通过。

也就是说，真正判断“测试生成是否完成”的地方在 scaffold-suite，不在 scaffold-module。

## 受影响范围

| 文件/模块 | 影响 |
|---|---|
| `aitest_kit/codegen/cli.py` | 增加 `--cases`、可选 `--module`、suite manifest 解析 |
| `aitest_kit/codegen/profile.py` | 支持加载 module profile + suite profile 并 merge |
| `aitest_kit/codegen/profile_validator.py` | 支持 suite profile schema、case_id 与当前 suite 对齐校验 |
| `aitest_config/schemas/codegen_profile.schema.json` | 增加 `profile_scope`、`parent_module`、`suite`、`knowledge_refs` |
| `aitest_kit/codegen/parser.py` | 支持任意 case file stem，不再只限 `business/boundary` |
| `aitest_kit/codegen/emitter.py` | 输出文件名改为 `test_{module}_{case_file_stem}.py` |
| `aitest_kit/codegen/planner.py` | 应只消费 runtime profile，不关心 suite 来源 |
| `aitest_kit/codegen/health.py` | 未来可按 suite 统计成熟度 |
| `aitest_kit/doctor.py` | 检查 module profile、suite manifest、suite profile 是否一致 |
| `aitest_kit/run.py` 或报告链路 | 后续支持按 suite run/report |

## 技能影响

| skill | 修改方向 |
|---|---|
| `knowledge-build` | 不需要关心 suite profile |
| `test-design` | 可以输出到任意 case suite 目录；不负责拆 pytest |
| `test-scaffold` | 拆成 module scaffold 和 suite scaffold 两个阶段 |
| `test-codegen` | 增加 `--cases` 流程说明 |
| `test-fix` | 修用例时优先改 case suite 目录下的 md 和 `_suite` profile |
| `emitter-build` | promotion 写回 suite profile，不默认写 module profile |

## 单 case 预览相邻能力

单 case 生成不应修改正式 generated 文件。

推荐模式：

```bash
python3 -m aitest_kit.cli codegen --cases /path/to/suite --case TC-GW-041 --preview
python3 -m aitest_kit.cli codegen --cases /path/to/suite --case TC-GW-041 --scratch-file /tmp/test_tc_gw_041.py
```

用途：

1. 调试某条 case 的生成结果。
2. scaffold-suite 时聚焦新用例。
3. test-fix 时减少 diff 噪音。

它和 suite profile 是相邻能力，但建议单独实现，不与第一版 suite codegen 混在一个 PR。

## 实现阶段

### Phase 1：spec 和 schema 草案

1. 定义 `aitest_suite.yaml`。
2. 定义 suite profile 字段。
3. 明确 module profile 与 suite profile merge 规则。

### Phase 2：suite codegen 最小能力

1. CLI 支持 `--cases`。
2. 任意 `.md` 用例文件可生成 `test_{module}_{case_file_stem}.py`。
3. 支持 module profile + suite profile merge。
4. 支持 `--validate-profile`、`--dump-ir`、`--check`。

### Phase 3：test-scaffold 拆分

1. `scaffold-module`：生成 L1 fixture + module profile。
2. `scaffold-suite`：基于具体用例生成 `_suite` profile。
3. 更新 `.codex/skills/test-scaffold/SKILL.md`，review 后同步其他 skill 目录和模板。

### Phase 4：run/report suite 化

1. `aitest run --cases` 或 `aitest run --suite`。
2. report 中记录 `module`、`suite`、`case_files`、`knowledge_refs`。
3. 失败反哺定位到 suite profile。

## 验收标准

代码能力完成后必须通过：

```bash
python3 -m compileall aitest_kit
python3 -m pytest tests -q
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli doctor
```

新增测试至少覆盖：

1. 旧模块级 `codegen {module}` 行为不变。
2. `codegen --cases <dir>` 能从 `aitest_suite.yaml` 找到 module。
3. 显式 `--module <module> --cases <dir>` 在无 manifest 时可工作。
4. suite profile 文件名必须带 `_suite`。
5. 任意用例文件名 `quota_billing_business.md` 生成 `test_{module}_quota_billing_business.py`。
6. suite profile 中的 `case_flows` 能进入 Case IR。
7. suite profile 引用不存在 case_id 报 ERROR。
8. 同 case_id 同时出现在 case_body/case_flow 报 ERROR。
9. `--check` 能识别 suite generated 文件 stale。
10. 不同 suite 生成同名 `test_{module}_{case_file_stem}.py` 时必须报冲突，不静默覆盖。

## 结论

主推荐方案应从：

```text
module profile -> indexes sub_profiles
```

调整为：

```text
case suite -> owns suite profile -> references module profile
```

这样 codegen 的稳定能力留在 L1，具体用例生成策略跟着用例走。用户想拆分测试代码时，先拆分 Markdown 用例文件；codegen 只负责把每个用例文件确定性编译成对应 pytest 文件。
