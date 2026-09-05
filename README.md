# aitest-kit

> 把开发文档、API 契约和 AI 设计出来的测试想法，沉淀成可审查、可重复生成、可运行报告的自动化测试资产。

[English](README.en.md)

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

```text
AI 负责探索未知，代码负责稳定重复。
```

## 为什么用 aitest-kit

- **测试设计和测试代码分离** — Markdown 用例是人可 review 的设计源文件；pytest 是编译产物，从 Markdown + profile 确定性生成，不需要人工维护。
- **失败不只是红绿灯** — 每次失败自动分流：文档问题、用例问题、fixture 问题、环境问题、codegen 问题或待测系统 bug。不用人工猜归因。
- **越测越稳定** — 初期 AI 读文档、探索系统、设计用例；反复验证的模式沉淀进 profile 和 assertion_rules，AI 参与逐步减少，确定性逐步增加。
- **9 个 AI skill 覆盖全流程** — 从文档审查、知识库构建、用例设计到 fixture 脚手架、codegen、失败修复和规则沉淀，skill 约束 AI 行为，人工 review 把关质量。

不适合：一次性 pytest、没有可执行接口、需要自动创建生产账号或付费资源。

## 3 分钟上手

### 1. 安装

```bash
python3 -m pip install -U aitest-kit
```

找不到 `aitest` 命令时用 `python3 -m aitest_kit.cli --help`。

### 2. 初始化工作区

```bash
cd /path/to/your_project
aitest init --target ./aitest_workspace
cd ./aitest_workspace
```

初始化后会得到：

```text
docs/                  # 公开 API 文档、设计文档、OpenAPI/proto
aitest_config/          # 项目配置、codegen 配置、schema、参考手册
test_workspace/         # 知识库、suite、Module Harness、generated pytest、报告
skills/                 # agent-neutral AI skills，按需复制到 .codex/.claude/.agents
AGENTS.md / CLAUDE.md   # AI 协作说明
```

配置文件写法见 `aitest_config/refs/config-files.md`。

### 3. 体检并开始

```bash
aitest doctor
```

刚初始化时没有模块是正常的。把文档放入 `docs/`，让 AI 按 skills 走完整流程：

```text
doc-review → knowledge-build → test-design → test-scaffold → test-codegen → aitest run
```

已有 Markdown 用例和 profile 时直接验证和生成：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

详细迁移步骤和长期维护见 [Getting Started](docs/usebook/aitest_getting_started.md)。

## 工作流

```text
公开文档 / API 契约
  → 测试知识库 L0/L1/L2
  → Markdown 测试用例
  → fixture + codegen profile
  → Case IR → generated pytest
  → aitest run / report
  → 失败修正与规则沉淀
```

| 阶段 | 做什么 | 主要工具 |
|---|---|---|
| 文档和知识 | 公开文档放入 `docs/`，构建可测试契约 | `/doc-review` `/knowledge-build` |
| 用例设计 | 从知识库生成 Markdown 用例，人工 review | `/test-design` |
| 脚手架 | 为模块构建 Module Harness 和 profile | `/test-scaffold` |
| 代码生成 | Markdown + profile → pytest | `aitest codegen` |
| 执行报告 | freshness check → pytest → 结构化报告 | `aitest run` |
| 沉淀 | 重复模式提取为规则和模板 | `/emitter-build` |

## CLI 速查

```bash
aitest init --target <dir>                                   # 初始化 workspace
aitest doctor                                                # 体检
aitest agent setup                                           # 安装当前用户的 Pi Runtime
aitest agent doctor                                          # 检查本地 Pi Runtime
aitest codegen --suite-file <suite.yaml> --validate-profile  # profile 门禁
aitest codegen --suite-file <suite.yaml>                     # 生成 pytest
aitest codegen --suite-file <suite.yaml> --check             # 检查 generated 是否过期
aitest run --suite-file <suite.yaml>                         # 执行一个 suite
aitest run --suite-file <suite.yaml> --capture               # 执行并写入 capture.jsonl
aitest run --target <target> [--module <module>]             # 按 target/module 回归
aitest run --all                                             # 全量回归
aitest report --suite-file/--target/--all ...                # 重渲染报告
```

### 本地 Console

本地 Console 使用 Vue 3 + AITest FastAPI，仅监听 loopback 地址。正式 wheel 自带编译后的
前端资源，因此安装用户不需要 Node.js，也不需要进入 AITest 源码目录：

```bash
python3 -m pip install "aitest-kit[server]"
AITEST_CONSOLE_PORT=<本地端口> aitest console --workspace /path/to/aitest_workspace
```

源码开发者使用 Node.js 22.18+；修改 Vue 后运行 `npm --prefix console_web run build`，构建结果写入
`aitest_kit/console/web/` 并随 wheel 分发。`--workspace` 可以指向任意已初始化目录；未初始化
目录不会在“打开”时被自动修改，只有用户在界面明确点击“初始化并打开”才调用安全的非 force
初始化，模板冲突会停止并保留原文件。
省略 `--workspace` 时会先打开 Console 空态，再从界面选择或初始化目录。

Console 可以浏览和编辑 Markdown、Profile、YAML、Harness/helper，执行 profile validation、
codegen、生成同步检查和 run，并读取 `result.json` / `report.md` 历史。generated 与报告保持
只读。用户可以显式编辑已授权的 `.env`、`AITEST_ENV_FILE` 和 task `env_files`；env 值不会
进入普通文件接口；任务输出会对 Console 已知的敏感值做脱敏，测试资产仍不得主动打印凭证。

在 Console 的“设置 → 模型连接”中，用户只需填写连接名称、接口类型、Base URL、模型名和
API Key，无需查询 Pi Provider。连接测试会通过 Pi Worker 发起一次不调用工具的真实模型请求；
非敏感配置写入 workspace，API Key 只保存在当前 Console 进程内存，重启 Console 或切换
workspace 后需要重新输入。

Pi Agent Runtime 通过 Console 的 Runtime 卡片或 `aitest agent setup` 显式安装到当前用户目录；
不会修改 workspace，也不会读取模型 API Key。安装就绪后，主导航的“Agent”可以创建 approval
或 full_trust 本地 session。页面通过可恢复的 SSE 事件流展示对话、工具时间线和审批卡；write/edit 可展开
Monaco Diff，已验证的 workspace 路径和 AITest run/report 工具事件可以跳转到编辑器或报告页。
approval 模式支持允许一次、本会话允许和拒绝；递归 `grep`、write/edit、Shell 和外部目录访问需要审批。
直接读取敏感路径默认拒绝，但批准 grep/Shell 后仍可能读取敏感内容；审批不是逐文件隔离或沙箱。
full_trust 每次创建或重新激活 session 都必须针对当前 workspace 明确确认。
会话历史保存在当前用户的 workspace-scoped session 目录，支持多历史会话、单 active Worker。
重启后可查看历史并显式继续；未完成的运行标记为 interrupted，不自动重试工具或重放审批。

运行真实接口测试时通过 env 文件提供凭据：

```bash
AITEST_ENV_FILE=/tmp/test.env aitest run --suite-file <suite.yaml>
```

报告只记录变量名，不记录变量值。完整选项见 `aitest --help`。

排查失败时可加 `--capture`，运行目录下会生成一个 `capture.jsonl`。框架只自动捕获默认 HTTP 用例；自定义 fixture、gRPC 或 SDK 调用可以手动调用 `aitest_kit.helpers.capture.capture_io()`。在 generated 测试函数体内调用时，`capture_io()` 可自动归因到当前 case；显式传入 `case_id` 仍然有效。pytest fixture setup/teardown 阶段不在该 context 内。capture 不自动脱敏，敏感字段应在用户 fixture 中处理后再写入。

### 本地 Pi Agent Runtime

Python wheel 携带锁定的 Pi Worker 安装种子，不携带体积较大的 `node_modules`。用户先安装
Node.js（最低 `22.19.0`，推荐 Node.js 24 LTS），再显式安装用户级 Runtime：

```bash
aitest agent setup
aitest agent doctor --workspace /path/to/aitest_workspace
```

默认安装到 `~/.aitest/runtimes/pi-worker/<bundle-hash>/`，可以用 `AITEST_RUNTIME_HOME` 覆盖根目录。
setup 使用 wheel 内的精确 lockfile，不安装 Node、不写 workspace、不修改 Python `site-packages`，
也不会读取模型凭证。源码开发仍可运行 `npm ci --prefix agent_runtime/pi_worker`；resolver 会优先
使用依赖完整的源码 Worker，再使用当前 bundle 对应的用户级 Runtime。

在 workspace 的 `aitest_config/aitest.yaml` 中只配置模型引用和环境变量名，不保存 Key 值：

```yaml
agent:
  runtime: pi
  connection_name: Anthropic
  model:
    protocol: anthropic_messages
    provider: anthropic
    name: claude-sonnet-4-5
    api_key_env: ANTHROPIC_API_KEY
    base_url: null
    base_url_env: null
```

Key 由当前 shell 提供。审批模式是默认值；完全信任模式必须逐次明确确认，它会让原生
read/write/edit/grep/find/ls/bash 继承当前本机用户权限，不是 Sandbox：

```bash
export ANTHROPIC_API_KEY=<your-key>
aitest agent run --workspace /path/to/aitest_workspace \
  --skill-path /path/to/skill \
  --prompt "检查当前测试资产，并运行 profile validation"

aitest agent run --workspace /path/to/aitest_workspace \
  --mode full_trust \
  --prompt "执行已确认的测试维护任务"
```

协议和日志只传环境变量名，不传 Key。审批模式下 workspace 内 read/search 默认允许，
write/edit/bash/外部目录需批准，`.env`、私钥等敏感路径默认拒绝。

## AI Skills

workspace 内置 agent-neutral 的 `skills/`，按环境复制到对应目录：

```bash
mkdir -p .claude/skills && cp -R skills/. .claude/skills/   # Claude Code
mkdir -p .codex/skills && cp -R skills/. .codex/skills/     # Codex
```

| Skill | 什么时候用 |
|---|---|
| `doc-review` | 检查文档是否足够生成测试 |
| `doc-gen` | 从源码或现有文档补测试设计输入 |
| `knowledge-build` | 构建/更新 L0/L1/L2 测试知识库 |
| `case-migrate` | 可选能力，仅用于把外部/历史用例迁移为 AITest Markdown 用例 |
| `test-design` | 从知识库生成 Markdown 用例 |
| `test-scaffold` | 为新模块构建 Harness，或为 suite 补 profile |
| `test-codegen` | 从 Markdown/profile 生成 pytest |
| `test-fix` | 修正错误用例并沉淀经验 |
| `test-maintain` | 诊断 workspace 状态，路由到对应 skill |
| `emitter-build` | 从已验证测试中提取可沉淀规则 |

## Codegen 路线

| 路线 | profile 配置 | 适用场景 |
|---|---|---|
| 默认 HTTP/gRPC | `requests` | 单接口、请求结构稳定 |
| 断言规则 | `assertion_rules` | 调用标准，断言需模板化 |
| 结构化流程 | `case_flows` | 线性多步骤 |
| 自定义代码 | `case_bodies` | 并发、mock、进程等复杂场景 |

`case_flows` 只做流程编排，根对象固定为 `harness`；临时文件、日志捕获、mock、循环、条件和 cleanup 等运行细节封装为 Module Harness capability。详见 [Profile Guide](docs/usebook/codegen_profile_guide.md)。

推荐演进：`case_bodies → case_flows → assertion_rules / 默认模板`。详见 [Profile Guide](docs/usebook/codegen_profile_guide.md)。

## Workspace 结构

```text
aitest_workspace/
├── docs/                         # 公开文档输入
├── aitest_config/
│   ├── aitest.yaml               # workspace 配置 + codegen 默认规则
│   ├── schemas/                  # profile JSON Schema
│   └── refs/                     # 用例格式、配置写法参考
├── test_workspace/
│   ├── knowledge/                # L0/L1/L2 + TEST_SPEC
│   ├── suites/                   # Markdown 用例 + suite profile
│   ├── targets/                  # target registry + modules/{module}/{module.yaml,profile.md,fixture.py,harness.py}
│   ├── generated/                # generated pytest（编译产物）
│   ├── reports/                  # 运行报告
│   └── results/                  # 待测系统 bug 记录
├── skills/                       # agent-neutral AI skills
├── AGENTS.md
└── CLAUDE.md
```

Module 运行能力只有一种公开形态：`setup_{module}` fixture 直接返回 `{Module}Harness`，generated pytest 中统一命名为 `harness`。单模块能力留在 module package；只有同一 target 内已被多个 module 实际复用的纯技术适配才进入 `targets/{target}/helpers/`，不建立 workspace 顶层 helpers。

## 安全与隐私

- 不提交 `.env`、token、密码或生产账号。
- profile `variables.env` 只写变量名，不写值；报告可能含请求/响应详情，对外共享前需脱敏。
- 不自动创建账号、充值或调用付费资源。

## 当前稳定边界

v0.3.x 稳定：`aitest init/codegen/run/report/doctor/upgrade`、workspace layout、Markdown 用例格式、profile schema、request bindings、structured assertions、Case IR → pytest 主链路、freshness check、结构化报告。

仍在演进：health/promotion report 口径、`case_flows` step 词汇表、内部 Python API、前端和契约测试方向。

## 开发本仓

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
python3 -m pip install -e ".[dev,server]"

python3 -m pytest tests -q
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --check
python3 -m aitest_kit.cli codegen --target coupon_system --module calibration --check
python3 -m aitest_kit.cli run --target coupon_system --module calibration -- --collect-only -q
python3 -m aitest_kit.cli doctor
```

本仓内置 `coupon_system/` 作为真实回归资产。详见 [Coupon System Full Example](docs/usebook/coupon_system_full_example.md)。

## 文档

- [Getting Started](docs/usebook/aitest_getting_started.md) — 安装、初始化、首个模块迁移到长期维护
- [Profile Guide](docs/usebook/codegen_profile_guide.md) — 编写 module/suite profile
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md) — codegen 常见问题
- [Contributing](CONTRIBUTING.md) — 贡献指南
- [Console / Pi 交付验收](docs/usebook/console_delivery_verification.md) — 三平台安装 CI、视觉基线和持久化测量
- [CHANGELOG](CHANGELOG.md) — 版本变更记录

## License

[MIT](./LICENSE)
