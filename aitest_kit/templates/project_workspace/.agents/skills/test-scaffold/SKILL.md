---
name: test-scaffold
description: 构建模块级 fixture/module profile 或用例级 suite profile，把 Markdown 用例接入 test-codegen 管线
when_to_use: 当新模块缺少 fixture/module profile，或已有模块新增一批 Markdown 用例需要生成 suite profile 时
argument-hint: <target> <module> [scaffold-module|scaffold-suite|incremental] [suite_dir]
arguments: [target, module, mode, suite_dir]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash Agent
effort: high
---

# 测试脚手架构建

为 `$target` 下的 `$module` 模块构建 fixture/module profile，或为某个用例目录构建 suite profile，使其能进入 `test-codegen` 管线。

## 定位
```
test-design 产出 Markdown 用例
  ↓
  test-scaffold ← 本 skill
  ↓
test-codegen 消费 fixture + profile 生成 pytest
```

## 产出
| 文件 | 职责 |
|------|------|
| `test_workspace/targets/{target}/target.yaml` | 被测系统入口和默认目录 |
| `test_workspace/targets/{target}/modules/{module}.yaml` | module 归属、fixture/profile、registered_suites；手写 registered_suites 时推荐直接写 suite manifest 路径，需要 status 时再写 `{suite, manifest, status}` |
| `test_workspace/targets/{target}/fixtures/{module}.py` | Client 类 + setup/teardown fixture |
| `test_workspace/targets/{target}/helpers/` | target 专属 helper，通用 helper 不够时再新增 |
| `test_workspace/targets/{target}/profiles/profile_{module}.md` | module_type、共享 assertion_rules、默认 fixture/object、L1 稳定能力 |
| `{suite_dir}/suite.yaml` | 用例 suite 归属：target、module、suite、case_files、suite profile |
| `{suite_dir}/profile_{suite}_suite.md` | 本批用例的 variables、case_flows/case_bodies/request_overrides |
| `api_map_{module}.md` | API 面 + env 契约 + 可行性判定（scaffold 过程产物，保留供 review） |

模块级 fixture/profile/helper 归属于 `test_workspace/targets/{target}/`；suite 级文件跟随具体用例目录。

## 参考文档

详细格式模板和约束规则拆分到 `refs/` 目录，按需读取：
- `aitest_config/refs/config-files.md` — target/module/suite/profile/task/env 配置文件总手册，判断字段归属时优先读取
- `refs/formats.md` — API Map、variables/env 矩阵、状态影响表、profile YAML、fixture 代码、输出摘要的模板
- `refs/constraints.md` — fixture 硬约束、测试数据分类、注入一致性、case_flow 规则、路线映射、验证命令

## 哲学
AI 探索：理解 API 面、设计 Client、判断生成路线、写 case_flow。
Skill 保障：分步交互、结构化数据流、验证闭环。
用户 review 每一层设计决策，不面对黑盒最终产物。

## 代码阅读边界
默认不读待测系统源码。docs/、knowledge/、cases/ 不足时，列出缺口请求用户确认后读 API 声明层。

允许读取：路由/端点声明、请求/响应 schema、认证/中间件配置、启动配置。
禁止读取：handler body 业务逻辑、数据库模型/查询、内部服务调用、算法/策略。

读取过的 API 声明层文件记录到 `api_map_{module}.md`。

## Step 0：模式选择
确认：**target** + **模块名** + **模式**（scaffold-module / scaffold-suite / incremental）。如果用户只给模块名，先从 suite manifest、module registry 或现有目录推断 target；推断不到时询问。

### scaffold-module 模式
模块尚无 fixture 和 module profile。输入必须包含 L1/API 文档和一份最小冒烟用例 suite，用于锚定真实调用路径、认证方式、响应结构和基础断言。输出：

```text
test_workspace/targets/{target}/target.yaml
test_workspace/targets/{target}/modules/{module}.yaml
test_workspace/targets/{target}/fixtures/{module}.py
test_workspace/targets/{target}/profiles/profile_{module}.md
```

module profile 不索引所有 suite profile，不承载频繁变化的 L2 case_flow。
module profile 禁止放当前 suite 的 `case_flows/case_bodies/request_overrides/case_fixtures/variables.cases`；这些 TC-ID 绑定配置必须写入 suite profile，否则 profile gate 会报错。

### scaffold-suite 模式
已有 fixture 和 module profile，用户给出某个用例目录。输出：

```text
{suite_dir}/suite.yaml
{suite_dir}/profile_{suite}_suite.md
```

suite profile 文件名必须以 `_suite.md` 结尾，只覆盖该目录下的 case_id。验证命令：

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --check
```

### incremental 模式
用于已有模块新增用例时，从 `test-codegen` 接手"fixture 能力不足"的问题；不是重做整个模块。

1. 读取 `test-codegen` 的失败信号：缺少 fixture 方法、新认证/header、case-scoped env、cleanup、流式/文件/WebSocket/mock 等新交互能力
2. 读取现有 target/module registry、fixture、module profile、suite profile、helpers 和新增 cases
3. 判断缺口类型：只缺 suite profile 则退回 `test-codegen`；缺测试调用能力才继续 incremental scaffold
4. 对新增 case 执行 Step 3 + Step 4，更新 variables/env 矩阵、状态影响和可行性判定
5. 如需新端点方法或 helper，回到 Step 2 扩展 Client，只追加最小方法，不重写已有方法
6. 如需新 env，按连接/认证/资源/业务分层，并优先 case-scoped lazy lookup，避免一个 case 的 secret 缺失拖垮整个模块
7. Step 6 → Step 7 追加 suite profile 条目或必要的 module profile 稳定能力，不重写已有条目
8. Step 8 验证闭环；通过后回到 `test-codegen` 重新生成或 check

## Step 1：提取 API Map

**子 Agent 适用**：读大量源材料，产出紧凑文档。

提取来源优先级：cases/ 共享配置 → docs/knowledge → 代码 API 声明层（需用户确认）。

产出 `api_map_{module}.md`，格式参考 `refs/formats.md#api-map-模板`。环境变量必须分层（连接/认证/资源/业务），分层在此步完成，后续步骤继承。

**用户确认**：端点列表、认证模式、env 分层、信息缺口。

## Step 2：设计 fixture Client

基于已确认的 API Map 设计方法签名。交付物是签名表，不是完整代码：

```
class {Module}Client:
    __init__(base_url, auth_token)     # auth_token: required, 缺失时 fail
    post_messages(model, messages)     → httpx.Response  [HTTP, auth: yes]
    get_public_models()                → httpx.Response  [HTTP, auth: no]
    recommend(request)                 → RecommendReply  [gRPC, auth: no]
    create_api_key(name)               → httpx.Response  [HTTP, auth: yes, 状态变更: 创建]
    delete_api_key(key_id)             → httpx.Response  [HTTP, auth: yes, 状态变更: 删除]
```

每个方法标注 **auth 需求**（yes/no）和 **状态变更**（创建/修改/删除，有则标，无则省略）。

设计原则：每个端点一个方法，HTTP 返回 `httpx.Response`，gRPC 返回 protobuf message，env 驱动不硬编码。首次创建前读其他模块 fixture 参考项目惯例。

**用户确认**：方法粒度、命名、auth 标注。

## Step 3：Profile Variables 与环境变量契约

**子 Agent 适用**。可与 Step 2 并行。

输入：api_map 的分层 env 定义 + cases/ 全部文件。
产出：case → variables/env 矩阵，**追加写入 api_map_{module}.md**。格式和分类规则参考 `refs/formats.md#case-variablesenv-矩阵`。

矩阵写入 api_map 后，Step 5 只处理 fixture/driver 必需的模块级 env；case-scoped 的账号、密码、token、URL path、非法字段等优先写入 suite profile `variables`，由 case_flow 通过 `{var: name}` 引用。

**用户确认**：哪些变量是真实凭证、CI 中能否自动获取。

## Step 4：状态影响与可行性判定

**子 Agent 适用**。可与 Step 3 并行。

产出两部分，**追加写入 api_map_{module}.md**。格式参考 `refs/formats.md#状态影响表` 和 `refs/formats.md#可行性判定`。

非幂等且无 cleanup API 的 case 默认标为可行性存疑。可行性判定是 Step 7 的显式输入——skip_list 中的 case 不生成 case_flow/case_body。`[manual]` case 要单独判断：纯人工不生成 profile entry；能自动触发动作或稳定断言的半自动 manual 才生成 case_flow/case_body，并保留 manual marker。

**用户确认**：非幂等 case 是否可接受、cleanup 策略、是否需要测试专用资源。用户可以将可行性存疑的 case 移入可执行或确认保持 skipped。

## Step 5：生成 fixture + registry 接线

基于已确认的 Step 2（Client 签名 + auth 标注）和 api_map 中的 variables/env 矩阵生成 `test_workspace/targets/{target}/fixtures/{module}.py`。

数据流：
- `__init__` 参数和 fail-fast 逻辑 → 从 Step 2 auth 标注 + api_map env 分层
- cleanup 方法 → 从 Step 4 状态影响表
- env check 粒度 → 从 Step 3 矩阵中筛出 fixture/driver 必需的模块级 env；case-scoped 变量不写进 fixture 初始化
- 必需 env 读取统一用 `from aitest_kit.runtime_variables import require_env`；不要手写 `os.environ.get(...)` + `pytest.fail(...)`，这样报告才能稳定归类为 `PRECONDITION_MISSING`

硬约束、代码结构和测试数据分类参考 `refs/constraints.md#fixture-硬约束` 和 `refs/formats.md#fixture-代码结构`。

registry 接线（原子步骤）：生成 fixture 文件后，立即检查 `test_workspace/targets/{target}/modules/{module}.yaml` 是否声明 `fixture.file/default_fixture`。suite generated pytest 会从 module.yaml 自动注入 fixture import。

**用户确认**：fixture 代码。

## Step 6：Profile 模式确认

auto_fields 判断和 module_type → 路线映射参考 `refs/constraints.md#auto_fields-判断` 和 `refs/constraints.md#module_type--路线映射`。

逐条 case 从简到繁评估路线，参考 `refs/constraints.md#逐条-case-路线评估`。api_map 中标为 skipped 的 case 不参与路线评估。

从可执行 case 中挑 1-2 条最有代表性的（标准是代表性，不是路线覆盖），展示完整 profile 片段：路线理由、fixture/object、steps、断言。说明选择原因。

Profile YAML 结构参考 `refs/formats.md#profile-yaml-结构`，注入一致性和 case_flow 规则参考 `refs/constraints.md`。

**用户确认**：路线选择、step 结构、断言充分性。

## Step 7：生成全量 profile

**子 Agent 适用**。

子 Agent 输入（全部为已确认的结构化文档）：
- Step 6 确认的 profile 模式样本
- cases/ 全部文件
- Client 方法签名（Step 2）
- api_map 中的 variables/env 矩阵（Step 3）
- **api_map 中的 skip_list（Step 4）**— skip_list 中的 case 不生成 case_flow/case_body

输出：scaffold-module 模式生成完整 `profile_{module}.md`；scaffold-suite 模式生成 `{suite_dir}/profile_{suite}_suite.md`。suite profile 优先承载 `variables` 和本批 case 的 `case_flows/case_bodies/request_overrides`。纯人工 manual 不写入 suite profile；半自动 manual 写入可执行 flow/body。路线选择记录附在 profile 末尾或输出摘要中。

**用户确认**：路线分布统计 + 特殊标注的 case。

## Step 8：验证闭环

验证命令和预期结果参考 `refs/constraints.md#验证命令与预期`。

collect 预期数量 = 总 case - skipped - manual，不追求最大化。

## Step 9：跨模块 review（第 2+ 模块时）

检查跨模块可复用模式，只标记和建议，不自动提取：
- Client 重复模式（auth header）→ helpers/ 或 base Client
- 相同 assertion 模式 → `aitest.yaml.codegen.builtin_assertion_rules`
- 相似 case_flow 结构 → named flow template 候选

## 子 Agent 策略

| 步骤 | 任务 | 输入 | 输出 |
|------|------|------|------|
| Step 1 | 提取 API Map | cases/、docs/、代码 API 层 | api_map（~1 页） |
| Step 3 | 扫描 variables/env | cases/、api_map env 分层 | case variables/env 矩阵（追加到 api_map） |
| Step 4 | 扫描状态影响 | cases/、api_map | 状态影响表 + skip_list（追加到 api_map） |
| Step 7 | 生成全量 profile | cases/、确认的模式、签名、skip_list | profile 文件 |

并行：Step 1 确认后，Step 2（主 Agent）与 Step 3 + 4（子 Agent）可并行。
case < 10 条时主 Agent 直接处理也可。

api_map 是全流程的结构化中间文档。Step 3、Step 4 的产出追加写入 api_map，后续步骤从 api_map 读取，不依赖 AI 跨步骤记忆。

## 边界

允许：读 docs/knowledge/cases/、经确认读 API 声明层、读其他模块 fixture/profile、读 `aitest.yaml`、创建/修改 target 下的 fixture/profile/helper/module.yaml 和 api_map、运行验证命令。

禁止：读业务逻辑、改 generated/、改 .env、硬编码凭证、编造 API 行为、import 待测系统、改待测系统代码、生成 case_id 分发表。

## 完成标准

1. `test_workspace/targets/{target}/fixtures/{module}.py` 存在且 `compileall` 通过
2. `test_workspace/targets/{target}/profiles/profile_{module}.md` 存在且 `--validate-profile` 无 ERROR
3. `--dump-ir` 中每条 case 的 strategy 符合预期
4. `codegen --check` 通过
5. `module.yaml` 已声明 fixture/profile，`pytest --collect-only` 收集数 = 可执行 case 数
6. api_map 包含 env 分层 + case variables/env 矩阵 + 可行性判定
7. 可行性存疑 case 已经用户确认处理方式

scaffold 完成意味着"能进入 codegen 管线"，不意味着"测试通过"。真正连服务跑测试是 `aitest run` 的职责。

## 输出摘要

格式参考 `refs/formats.md#输出摘要模板`。
