---
name: test-scaffold
description: 构建或增量维护 canonical Module Harness、module registry/profile 和 suite profile，把 Markdown 用例接入 test-codegen 管线
when_to_use: 当新模块缺少 Module Harness，或现有模块新增用例需要补动作能力、资源生命周期或 suite profile 时
argument-hint: <target> <module> [scaffold-module|scaffold-suite|incremental] [suite_dir]
arguments: [target, module, mode, suite_dir]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash Agent
effort: high
---

# 测试脚手架构建

为一个 target/module 建立唯一 Module Harness，或把新 suite 接入现有 Harness。

```text
test-design -> Markdown suite
                 |
                 v
          test-scaffold
                 |
                 v
            test-codegen
```

## Canonical 产物

```text
test_workspace/targets/{target}/
  target.yaml
  helpers/                              # 同一 target 内已有多个 module 复用时才存在
  modules/{module}/
    __init__.py
    module.yaml
    profile.md
    fixture.py
    harness.py
    <responsibility>.py                 # 按需，如 api.py/resources.py

{suite_dir}/
  suite.yaml
  *.md
  profile_{suite}_suite.md
```

固定运行契约：

```text
setup_{module} -> {Module}Harness -> generated variable: harness
```

- `module.yaml`：target/module/module_type、knowledge refs、registered suites。
- `profile.md`：模块级稳定 `assertion_rules` 和 `variables.defaults`。
- `fixture.py`：只公开 `setup_{module}`，负责 pytest 生命周期和 Harness 装配。
- `harness.py`：模块测试能力门面和资源所有者。
- suite profile：TC-ID 绑定的 variables、requests、structured assertions、case flows/bodies。
- 不建立 `test_workspace/helpers/`。单模块能力留在 module package；target helper 必须已有至少两个 module 真实复用。

## 必读参考

- `aitest_config/refs/config-files.md`：配置字段和目录归属。
- `refs/constraints.md`：Harness contract、flow 边界和验证门禁。
- `refs/formats.md`：API Map、profile、Harness 和输出模板。

## 读写边界

默认只读 docs、knowledge、Markdown cases、公开 API/schema/路由声明、启动配置、现有测试资产和 `aitest.yaml`。文档不足时先列缺口，再请求用户确认是否读取更多声明层文件。

禁止：

- 修改待测系统、generated pytest、`.env` 或凭证文件。
- import 待测系统内部实现来伪造测试状态。
- 生成按 `case_id` 分发请求、账号、配置或断言的 fixture/Harness。
- 为 suite 新建第二个公开 pytest fixture。
- 在 suite profile 配置 fixture/object/extra imports。

## Step 0：选择模式

从 suite manifest、module registry 和目录推导 target/module；无法唯一确定才询问。

- `scaffold-module`：新模块。必须有 L1/API 输入和一份最小冒烟 suite。
- `scaffold-suite`：Harness 已满足需求，只需补 suite manifest/profile。
- `incremental`：新用例暴露了 Harness 能力、env、setup 或 cleanup 缺口。

只是新增参数、断言组合或调用已有 capability 时，留在 `test-codegen`；需要新端点、认证、环境依赖、资源准备或 cleanup 时，进入 incremental。

## Step 1：建立 API Map

分析公开接口和用例，输出 `test_workspace/targets/{target}/api_maps/api_map_{module}.md`：

- 端点、协议、认证和请求体。
- env 分层与 case variables/env 矩阵。
- 状态副作用、cleanup 和可行性判定。
- 信息缺口、manual/skipped 候选。

向用户分两段 review：先端点/认证，再 env/状态/可行性。格式见 `refs/formats.md`。

## Step 2：设计 Harness 能力

先给出能力签名表，不直接写完整代码：

```text
class GatewayHarness
  login(username, password) -> httpx.Response
  create_key(name) -> dict
  delete_key(key_id) -> None
  assert_key_active(payload) -> bool
  close() -> None
```

每个 capability 标明：协议、认证、状态变更、env、cleanup。优先表达可复用业务动作，不写 `run_case(case_id)` 或每条用例一个方法。

复杂循环、条件、等待、临时文件和 mock 可以封装为 capability；fixture 仍只负责装配与生命周期。用户确认能力粒度后再实现。

## Step 3：生成 module package

生成 canonical 五个文件，必要时再按职责拆文件：

1. `module.yaml` 不配置 fixture/helper/profile 路径。
2. `harness.py` 定义 `{Module}Harness`。
3. `fixture.py` 只公开 `setup_{module}`，直接 return/yield Harness。
4. `profile.md` 不放 TC-ID 绑定内容，也不重复 `module_type`。
5. 使用 `require_env()`/`require_envs()`；未调用的 capability 不应提前读取自己的可选 env。

先运行 Harness contract 和 compileall，再进入 profile。

## Step 4：确认 profile 路线

选择 1-2 条代表 case 展示完整片段并让用户 review：

- 默认 HTTP 是否足够。
- 是否需要 `requests.patches`、structured assertions 或 `case_flow`。
- flow 是否只调用 `harness.*` 和前序变量。
- 复杂控制是否已封装为 capability，或确实需要 `case_body`。

`case_flow` 只支持 `call`、`assign`、`assert`、`comment`。profile 不选择 fixture/object，生成器从 module registry 绑定 `setup_{module}` 和 `harness`。

## Step 5：生成 suite profile

- module profile 只放跨 suite 稳定规则/defaults。
- suite profile 放具体 TC-ID 的 variables、requests、structured assertions、case flows/bodies。
- pure manual 不写可执行 profile entry；半自动 manual 可写 flow/body 并保留 marker。
- 可行性存疑保持 skipped，不用 comment-only flow 冒充执行。
- `case_body` 只通过 `harness` 获取能力。

展示路线分布、manual/skipped 清单和保留 case_body 的原因。

## Step 6：验证闭环

严格执行 `refs/constraints.md#验证命令与预期`：

1. `aitest doctor`
2. `--validate-profile`
3. `--dump-ir` / 代表 case `--explain`
4. 正式 codegen
5. `--check`
6. compileall + suite collect
7. 已注册 suite 的 module selector 检查

scaffold 完成表示测试资产能稳定进入 codegen，不代表真实服务断言已经通过。

## 跨模块 review

第二个模块起检查真实复用：

- 同一 target 已有两个 module 使用的纯协议/认证适配，可提取到 target helpers。
- 只属于当前 module 的业务动作、测试数据和断言继续留在 module package。
- 跨项目稳定能力才考虑进入 `aitest_kit.helpers`。
- 重复 flow/body 仅标记为 `emitter-build` 候选，不自动晋升。

## 完成标准

1. canonical module package 完整，`doctor` 的 Harness contract 无错误。
2. 只有一个公开 `setup_{module}` fixture，并直接返回/yield Harness。
3. fixture/Harness 不按 case_id 隐式分发；用例差异在 suite profile 显式表达。
4. module/suite profile 归属正确，profile gate 无 ERROR。
5. Case IR 的 structured flow 固定使用 `setup_{module}` 和 `harness`。
6. codegen、freshness、compileall 和 collect 全部通过。
7. module selector 能发现已注册 suite。

输出格式见 `refs/formats.md#输出摘要模板`。
