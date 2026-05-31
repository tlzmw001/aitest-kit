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
| `test_workspace/targets/{target}/modules/{module}.yaml` | module 归属、fixture、registered_suites；手写 registered_suites 时推荐直接写 suite manifest 路径，需要 status 时再写 `{suite, manifest, status}` |
| `test_workspace/targets/{target}/fixtures/{module}.py` | Client 类 + setup/teardown fixture |
| `test_workspace/targets/{target}/helpers/` | target 专属 helper，通用 helper 不够时再新增 |
| `test_workspace/targets/{target}/profiles/profile_{module}.md` | module_type、共享 assertion_rules、默认 fixture/object、L1 稳定能力 |
| `{suite_dir}/suite.yaml` | 用例 suite 归属：target、module、suite、case_files；suite profile 走约定路径 |
| `{suite_dir}/profile_{suite}_suite.md` | 本批用例的 variables、case_flows/case_bodies/request_overrides |
| `test_workspace/targets/{target}/api_maps/api_map_{module}.md` | API 面 + env 契约 + 可行性判定（scaffold 过程产物，保留供 review） |

模块级 fixture/profile/helper 归属于 `test_workspace/targets/{target}/`；suite 级文件跟随具体用例目录。

## 参考文档

详细格式模板和约束规则拆分到 `refs/` 目录，按需读取：
- `aitest_config/refs/config-files.md` — target/module/suite/profile/task/env 配置文件总手册，判断字段归属时优先读取
- `refs/formats.md` — API Map、variables/env 矩阵、状态影响表、profile YAML、fixture 代码、输出摘要的模板
- `refs/constraints.md` — fixture 硬约束、测试数据分类、注入一致性、case_flow 规则、路线映射、验证命令

## 哲学
AI 探索：理解 API 面、设计 Client、判断生成路线、写 case_flow。
Skill 保障：分步交互、结构化数据流、验证闭环。
用户 review 设计决策，机械产物呈现后自动推进。

## 读写边界

默认不读待测系统源码。docs/、knowledge/、cases/ 不足时，列出缺口请求用户确认后读 API 声明层。

允许读取：路由/端点声明、请求/响应 schema、认证/中间件配置、启动配置、其他模块 fixture/profile、`aitest.yaml`。
允许写入：target 下的 fixture/profile/helper/module.yaml、api_map、suite 目录下的 suite.yaml 和 suite profile。
禁止：读业务逻辑（handler body/DB 模型/内部调用/算法）、改 generated/、改 .env、硬编码凭证、编造 API 行为、import 待测系统、改待测系统代码、生成 case_id 分发表。

读取过的 API 声明层文件记录到 api_map。

## Step 0：模式选择
确认：**target** + **模块名** + **模式**（scaffold-module / scaffold-suite / incremental）。如果用户只给模块名，先从 suite manifest、module registry 或现有目录推断 target；推断不到时询问。

### scaffold-module 模式
模块尚无 fixture 和 module profile。输入必须包含 L1/API 文档和一份最小冒烟用例 suite，用于锚定真实调用路径、认证方式、响应结构和基础断言。没有可用冒烟用例时，不编造 Markdown case；先回到 `test-design` 或请用户提供最小 case。产出见上方产出表。

module profile 禁止放当前 suite 的 `case_flows/case_bodies/request_overrides/case_fixtures/variables.cases`；这些 TC-ID 绑定配置必须写入 suite profile，否则 profile gate 会报错。
最小 suite 必须注册到 `module.yaml.registered_suites`，用于验证 module/target/all selector 能发现该模块。

### scaffold-suite 模式
已有 fixture 和 module profile，用户给出某个用例目录。产出 `suite.yaml` + `profile_{suite}_suite.md`。suite profile 文件名必须以 `_suite.md` 结尾，只覆盖该目录下的 case_id。

### incremental 模式
从 `test-codegen` 接手"fixture 能力不足"的问题，不是重做整个模块。

1. 读取失败信号，判断缺口类型：只缺 suite profile → 退回 `test-codegen`
2. 缺测试调用能力 → 按 Step 1 补 api_map 增量，按 Step 2 追加 Client 方法（最小追加，不重写已有）
3. 按 Step 5 追加 profile 条目，不重写已有
4. Step 6 验证后回到 `test-codegen`

## Step 1：API Map 全量分析（子 Agent）

单个子 Agent 一次完成 API 面提取、variables/env 矩阵、状态影响和可行性判定。

子 Agent 输入：cases/ + docs/knowledge + 代码 API 声明层（需用户先确认可读范围）。
子 Agent 产出：完整 `api_map_{module}.md`，格式参考 `refs/formats.md`。包含：
- 端点列表 + 认证模式 + 请求体参考
- 环境变量分层（连接/认证/资源/业务）
- case → variables/env 矩阵（分类规则参考 `refs/formats.md#case-variablesenv-矩阵`）
- 状态影响表 + 可行性判定 + skip_list

主 Agent 分段呈现给用户确认：
- **段 1**：端点列表、认证模式、信息缺口
- **段 2**：env 分层、variables 矩阵、状态影响、可行性判定（用户可将可行性存疑的 case 移入可执行或确认 skipped）

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

## Step 3：生成 fixture + registry 接线（子 Agent，呈现不阻塞）

子 Agent 输入：确认的 Client 签名 + api_map（env 分层、cleanup 策略）。
子 Agent 产出：`fixtures/{module}.py` + registry 接线检查结果。

必需 env 统一用 `require_env()`，硬约束和代码结构参考 `refs/constraints.md` 和 `refs/formats.md#fixture-代码结构`。

registry 接线：生成 fixture 后立即检查 `module.yaml` 声明 `fixture.file/default_fixture`，且 `default_fixture` 符号可 import。

主 Agent 呈现 fixture 代码和接线结果，自动推进到 Step 4；用户有异议可打断修改。

## Step 4：Profile 模式确认

auto_fields 判断、module_type → 路线映射、逐条 case 路线评估参考 `refs/constraints.md`。api_map 中标为 skipped 的 case 不参与路线评估。

从可执行 case 中挑 1-2 条最有代表性的，展示完整 profile 片段：路线理由、fixture/object、steps、断言。

注入模型和 case_flow 规则参考 `refs/constraints.md#fixture-注入一致性` 和 `refs/constraints.md#case_flow-规则`。Profile YAML 结构参考 `refs/formats.md#profile-yaml-结构`。

**用户确认**：路线选择、step 结构、断言充分性。

## Step 5：生成全量 profile（子 Agent，呈现不阻塞）

子 Agent 输入（全部为已确认的结构化文档）：
- Step 4 确认的 profile 模式样本
- cases/ 全部文件
- Client 方法签名（Step 2）
- api_map（env 矩阵 + skip_list）

子 Agent 产出：scaffold-module 模式生成 `profile_{module}.md` + `profile_{suite}_suite.md`；scaffold-suite 模式只生成 suite profile。module profile 只放 L1 稳定能力；suite profile 承载 `variables` 和 TC-ID 绑定的 `case_flows/case_bodies/request_overrides/case_fixtures`。纯人工 manual 不写入；半自动 manual 写入可执行 flow/body 并保留 manual marker。

主 Agent 呈现路线分布统计 + skipped/manual 清单 + case_body 保留原因，自动推进到 Step 6；用户有异议可打断。

## Step 6：验证闭环（子 Agent）

子 Agent 按 `refs/constraints.md#验证命令与预期` 依次执行全部验证命令，产出 pass/fail 摘要表。

collect 预期数量 = 总 case - skipped - pure manual。已注册 suite 追加 module selector 级验证。

验证通过 → 输出摘要，scaffold 完成。
验证失败 → 主 Agent 呈现失败项 + 修复建议，用户确认后修复并重新验证。

## Step 7：跨模块 review（第 2+ 模块时）

检查跨模块可复用模式，只标记和建议，不自动提取：
- Client 重复模式（auth header）→ helpers/ 或 base Client
- 相同 assertion 模式 → `aitest.yaml.codegen.builtin_assertion_rules`
- 相似 case_flow 结构 → `emitter-build` 候选

## 子 Agent 策略

| 步骤 | 任务 | 输入 | 输出 | 确认方式 |
|------|------|------|------|----------|
| Step 1 | API Map 全量分析 | cases/、docs/、API 声明层 | 完整 api_map | 阻塞：分段确认（端点+认证 → env+可行性） |
| Step 3 | 生成 fixture + 接线 | Client 签名、api_map | fixture .py + 接线检查 | 呈现不阻塞 |
| Step 5 | 生成全量 profile | 确认的模式、cases/、api_map | profile 文件 + 路线分布 | 呈现不阻塞 |
| Step 6 | 验证闭环 | 生成产物、验证命令表 | pass/fail 摘要 | 失败时阻塞 |

case < 10 条时主 Agent 可直接处理不委托子 Agent。

api_map 是全流程的结构化中间文档，后续步骤从 api_map 读取，不依赖 AI 跨步骤记忆。

## 完成标准

1. api_map 存在，包含 API Map、env 分层、case variables/env 矩阵、状态影响表、可行性判定和 skip_list
2. `fixtures/{module}.py` 和相关 helpers 存在且 `compileall` 通过
3. `module.yaml` 已声明 `fixture.file/default_fixture/module_type/registered_suites`，module profile 位于约定路径
4. `default_fixture` 符号真实可 import
5. module profile 只放 L1 稳定能力；suite profile 放 TC-ID 绑定内容
6. `--validate-profile` 无 ERROR；WARNING 已列出并确认处理方式
7. `--dump-ir` 中每条 case 的 strategy 符合 Step 4 路线
8. `codegen` 后 `codegen --check` 通过
9. `aitest run --suite-file <suite.yaml> -- --collect-only -q` 通过；已注册 suite 还要通过 module selector 的 `--check` 和 collect

scaffold 完成意味着"能进入 codegen 管线"，不意味着"测试通过"。真正连服务跑测试是 `aitest run` 的职责。

## 输出摘要

格式参考 `refs/formats.md#输出摘要模板`。
