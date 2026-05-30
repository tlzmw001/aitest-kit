---
name: test-maintain
description: 测试资产维护管家：根据需求变更、新增/修改/废弃用例、generated stale、fixture/profile 缺口等维护请求，识别影响面并路由到 test-design、test-fix、test-scaffold、test-codegen、emitter-build 或未来测试能力；本 skill 只编排和调用其他 skill，不直接修改文件。
when_to_use: 当用户提出需求变更后需要同步维护测试资产，新增/修改/删除/废弃测试用例，同步 Markdown/profile/generated pytest，处理 generated stale，或不确定该用 test-design/test-fix/test-scaffold/test-codegen 哪个入口时
argument-hint: <maintenance_request>
arguments: [maintenance_request]
user-invocable: true
allowed-tools: Read Glob Grep Bash
effort: high
---

# 测试资产维护管家

本 skill 是测试维护入口和 workflow router，不是新的 codegen 引擎，也不是直接编辑 generated pytest 的入口。

核心职责：

```text
理解用户维护意图
  -> 判断测试能力域
  -> 建立影响面清单
  -> 选择正确的底层 skill
  -> 调用或指导底层 skill 完成修改
  -> 验证测试资产一致性
  -> 输出维护摘要
```

## 硬边界

1. **只路由，不直接改文件**：本 skill 不使用 Write/Edit/apply_patch 修改任何文件；真正修改必须交给 `test-design`、`test-fix`、`test-scaffold`、`test-codegen` 等对应 skill。
2. **不直接编辑 generated pytest**：`test_workspace/generated/{target}/` 是编译产物。修改必须回到 Markdown 用例、profile、fixture、`aitest.yaml` 或 emitter。
3. **不绕过知识库**：需求变化可能影响业务规则时，先判断是否需要更新 knowledge，再进入用例维护。
4. **不自动大批删除**：删除或废弃 case 前必须列出影响面，默认优先 `retire`，用户明确要求后才 `delete`。
5. **不猜业务语义**：断言失败不自动判定为 SUT bug；报告只能做规则化初判，SUT bug 需要人工确认后记录到 `test_workspace/results/`。

## 能力注册表

当项目新增新的测试能力域、目录结构、用例格式、生成器或执行器时，必须同步更新本表、触发信号和验证命令。

| 能力域 | 触发信号 | 入口 skill | 关键产物 | 当前状态 |
|---|---|---|---|---|
| API 测试 | HTTP、gRPC、OpenAPI、proto、case_flow、fixture、profile、pytest | `test-design` / `test-scaffold` / `test-codegen` / `test-fix` | Markdown cases、fixture、profile、generated pytest、report | 支持 |
| E2E/API 编排 | 多模块、多服务、多步骤状态、端到端链路 | 当前优先走 API 能力；复杂能力缺口走 `test-scaffold incremental` | scenario suite、case_flow/case_body、fixture cleanup | 部分支持 |
| 前端测试 | 页面、按钮、表单、DOM、浏览器、截图、Playwright、视觉回归 | 未来 frontend-* skill | UI cases、page object、browser fixture、UI report | 未接入 |
| 契约测试 | OpenAPI/proto/schema 变更、兼容性、字段契约 | 未来 contract-* skill | contract cases、schema check | 未接入 |
| 数据/资源准备 | 测试账号、API key、余额、订阅、quota、测试数据生命周期 | 目前由 fixture + `require_env()` 显式声明；资源 provider 暂不内置 | env file、fixture helper、PRECONDITION_MISSING report | 轻量支持 |

遇到未知能力域时，停止在影响面分析阶段，说明缺少对应能力，并建议新增能力域或走人工流程。

## 意图分类

| 用户意图 | 判断信号 | 路由 |
|---|---|---|
| 新增测试点 | “新增用例/补测试/覆盖新规则/新增字段测试” | 先判断 fixture 能力：够用走 `test-design` + `test-codegen`；不够走 `test-scaffold incremental` |
| 修改已有测试 | “需求改了/预期变了/字段改名/规则调整” | 建影响面；单条 case 错误走 `test-fix`；需求级修改走 `knowledge-build`/`test-design`/`test-codegen` |
| 废弃或删除测试 | “接口废弃/这批 case 不要了/删除相关测试” | 先列 retire/delete 清单；用户确认后路由到底层 skill 修改源文件并重新 codegen |
| generated stale | “--check stale/generated 过期/pytest 和 case 不一致” | 走 `test-codegen`；若 stale 源于 fixture/profile 缺口，转 `test-scaffold incremental` |
| fixture/profile 缺口 | “没有 fixture/缺方法/缺认证/header/env/cleanup/上传/流式/mock” | 走 `test-scaffold incremental` |
| suite 注册到聚合入口 | “把这个 suite 加到 module/target/all”“注册 suite”“让模块跑到这个 suite” | 先确认 target/module/suite.yaml，再调用 `aitest registry register-suite` |
| 创建 task | “创建 task/任务/回归集，包含这些 suite” | 先确认 task 名称和 suite_file 清单，再调用 `aitest task create` |
| 单条用例错误 | “TC-XXX-001 写错/预期错/前置不可行” | 走 `test-fix` |
| 已验证模式沉淀 | “重复 case_flow/case_body/想沉淀规则” | 走 `emitter-build` |
| 不确定入口 | 用户只说“帮我维护测试/同步测试” | 本 skill 建影响面后给出路由选择，不直接改 |

简化判断：

```text
需求变化不明确 -> 先影响面分析
只是新增/修改用例表达 -> test-design/test-fix/test-codegen
需要新增测试调用能力 -> test-scaffold incremental
只是 generated 不一致 -> test-codegen
只是把 suite 纳入 module/target/all 聚合 -> aitest registry register-suite
只是创建 task manifest -> aitest task create
重复模式稳定后 -> emitter-build
```

## 工作流程

### Step 1：读取维护请求

提取：

- 目标模块、suite、case_id 或需求名称
- 变更类型：add / update / retire / delete / sync / diagnose
- 用户是否要求只分析、不修改
- 是否涉及新能力域（API/UI/E2E/Contract/Data）

如果用户请求包含删除、发布、修改 `.env` 或改待测系统代码，必须先停下确认。

### Step 2：建立影响面清单

只读检查，优先使用 `rg`：

- knowledge：`test_workspace/knowledge/L1/`、`test_workspace/knowledge/L2/`、`TEST_SPEC.md`
- suites：`test_workspace/suites/`
- target registry：`test_workspace/targets/{target}/target.yaml`、`modules/{module}.yaml`
- fixture/profile/helper：`test_workspace/targets/{target}/fixtures/`、`profiles/`、`helpers/`
- generated：`test_workspace/generated/{target}/`
- reports/results：`test_workspace/reports/latest/`、`test_workspace/results/`

输出格式：

```markdown
## 影响面

能力域：API / UI / E2E / Contract / Data / Unknown
维护类型：add / update / retire / delete / sync / diagnose

### 受影响知识库
- ...

### 受影响用例
- TC-...

### 受影响 profile / fixture
- ...

### 预计 generated
- ...

### 建议路由
- 下一步使用：test-...
- 原因：...
```

### Step 3：选择维护路径

#### add：新增测试

1. 如果需求规则未进入知识库，建议先用 `knowledge-build`。
2. 如果只是补 Markdown 用例，路由 `test-design`。
3. 如果已有 target/module fixture/profile 能力足够，路由 `test-codegen` 生成或补 suite profile。
4. 如果缺少 target/module registry、fixture、helper、module profile，或需要新增端点、认证、header、case-scoped env、cleanup、文件上传、流式响应、mock、复杂生命周期，路由 `test-scaffold incremental`。

#### update：修改测试

1. 定位 case_id、suite 或需求对应的 Markdown 源文件。
2. 判断是单条用例错误还是需求级规则变化。
3. 单条用例错误路由 `test-fix`。
4. 需求级变化先建议更新 knowledge，再路由 `test-design` / `test-codegen`。

#### retire/delete：废弃或删除测试

默认建议 `retire`：

- 保留历史记录
- 标注不再自动执行或移动到维护说明
- 避免丢失需求追踪

用户明确要求删除时，先列出：

```text
case_id
Markdown 源文件
suite profile 条目
module profile 条目
generated pytest 函数
删除原因
回滚方式
```

确认后路由到底层 skill 修改源文件并重新 codegen。

#### sync：同步 generated

1. 路由 `test-codegen`。
2. 若 `--validate-profile` 或 `--dump-ir` 发现 fixture/profile 缺口，转 `test-scaffold incremental`。
3. 不允许直接修改 generated pytest 来消除 stale。

#### diagnose：诊断维护入口

如果用户只是问“下一步用哪个 skill”，只输出影响面和路由建议，不进入修改。

### Step 4：调用底层 skill

本 skill 只负责决定调用哪个 skill。调用时必须把上下文压缩成底层 skill 需要的输入：

- `test-design`：模块/suite、关联 knowledge、需要新增或覆盖的测试维度
- `test-fix`：case_id、错误描述、期望修正方向
- `test-scaffold`：target、模块、模式（scaffold-module/scaffold-suite/incremental）、suite_dir、fixture/profile/helper 缺口
- `test-codegen`：模块、`--suite-file <suite_dir>/suite.yaml` 或 `--task-file <task.yaml>`、是否 check/dump-ir
- `emitter-build`：已验证 pytest、profile、可沉淀模式
- `aitest registry register-suite`：target、module、suite.yaml、status；用于把 suite 接入 module/target/all 聚合入口
- `aitest task create`：task name、明确的 suite.yaml 清单、description/output；用于创建 task manifest

不要把本 skill 的完整分析原文原样塞给底层 skill；只传决策所需的最小上下文。

维护 CLI 只用于确定性接线，不生成业务测试资产。新建 target/module/suite、补 fixture/helper/profile、判断 case_flow/case_body 仍然路由 `test-scaffold`。

### Step 5：验证维护结果

底层 skill 修改后，按能力域选择验证。

API suite 模式：

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml>
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --check
python3 -m aitest_kit.cli run --suite-file <suite.yaml> -- --collect-only -q
```

API suite 模式：

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --check
python3 -m aitest_kit.cli run --suite-file <suite_dir>/suite.yaml -- --collect-only -q
```

API task 模式：

```bash
python3 -m aitest_kit.cli codegen --task-file <task.yaml> --check
python3 -m aitest_kit.cli run --task-file <task.yaml> -- --collect-only -q
```

如果真实服务和前置 env 已准备好，再运行：

```bash
aitest run <module>
```

或 `aitest run --suite-file <suite_dir>/suite.yaml`。

### Step 6：维护摘要

输出：

```markdown
## 测试维护摘要

维护类型：add / update / retire / delete / sync / diagnose
能力域：API / UI / E2E / Contract / Data / Unknown

### 路由结果
- 使用 skill：
- 原因：

### 资产变化
- knowledge：
- cases：
- fixture/profile：
- generated：
- reports/results：

### 验证
- 命令：
- 结果：

### 后续
- 需要人工确认：
- 需要新增能力域：
- 可沉淀模式：
```

## 自我迭代规则

当仓库新增以下任一内容时，必须同步更新本 skill：

- 新测试能力域，如前端、契约、数据资源、移动端、性能测试
- 新用例格式或目录结构
- 新 target/module/suite/task 配置字段
- 新 profile 类型或生成器
- 新执行入口或报告分类
- 新底层 skill

更新内容至少包括：

1. 能力注册表
2. 意图分类表
3. 路由规则
4. 影响面清单
5. 验证命令

如果本 skill 无法识别某类新请求，输出 `Unknown capability` 并建议新增能力域，不要强行套用 API 测试流程。

## 禁止项

- 禁止直接使用 Write/Edit/apply_patch 修改测试资产
- 禁止直接编辑 generated pytest
- 禁止直接删除 case/profile/generated
- 禁止修改待测系统业务代码
- 禁止修改 `.env` 或写入密钥
- 禁止为通过测试而放宽断言、skip 失败用例或伪造响应
- 禁止把 `ASSERTION_FAILURE` 自动判定为 `SUT_BUG`
