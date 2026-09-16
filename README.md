# aitest-kit

> 把开发文档、API 契约和 AI 设计出来的测试想法，沉淀成可审查、可重复生成、可运行报告的自动化测试资产。

一个本地优先的测试研发工作台：用浏览器管理测试资产，用内置 Pi Agent 辅助设计和维护，
用确定性的 CLI 完成校验、生成、执行与报告。文件保存在你的 workspace，模型服务和 API Key 由你选择（BYOK）。

[English](README.en.md)

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

```text
AI 负责探索未知，代码负责稳定重复。
```

## 为什么用 aitest-kit

- **测试设计和测试代码分离** — Markdown 用例是人可 review 的设计源文件；pytest 是编译产物，从 Markdown + profile 确定性生成，不需要人工维护。
- **失败不只是红绿灯** — 结构化报告区分前置条件、环境、脚手架、codegen 和断言等问题，辅助定位；断言失败仍需结合契约人工确认，不能自动判为待测系统 bug。
- **越测越稳定** — 初期 AI 读文档、探索系统、设计用例；反复验证的模式沉淀进 profile 和 assertion_rules，AI 参与逐步减少，确定性逐步增加。
- **9 个 AI skill 覆盖全流程** — 从文档审查、知识库构建、用例设计到 fixture 脚手架、codegen、失败修复和规则沉淀，skill 约束 AI 行为，人工 review 把关质量。
- **同一套文件，界面和 CLI 都能用** — 浏览目录打开 workspace，用 Monaco 多标签编辑用例和配置，在界面执行校验、生成和测试，再查看结构化报告。
- **Agent 可以动手，权限由你决定** — Pi Agent 可以读取文档、按 skill 生成或修改测试资产、运行命令；审批模式逐项确认，也支持显式开启完全信任模式。

不适合：一次性 pytest、没有可执行接口、需要自动创建生产账号或付费资源。

## 3 分钟上手

### 1. 安装

体验本文的 Console 和 Agent 能力，推荐从当前 `main` 安装。需要 Python 3.9+；
仅使用界面和 CLI 不需要 Node.js，使用 Agent 另外需要 Node.js 22.19.0+ 和 npm。

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[server]"
```

Windows PowerShell 使用 `.venv\Scripts\Activate.ps1` 激活环境，并按本机安装使用 `python` 替代 `python3`。
仓库已包含构建好的前端，不需要先执行 npm 构建。偏好已发布版本时可安装
`python3 -m pip install -U "aitest-kit[server]"`，但 PyPI 版本可能落后于当前 `main`。

后续命令使用同一个 Python 环境。找不到 `aitest` 时，先确认已激活环境，或将命令前缀替换为
`python3 -m aitest_kit.cli`，例如 `python3 -m aitest_kit.cli console --port 8123`。

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

### 3. 打开界面并开始

```bash
aitest doctor
aitest console --workspace . --port 8123
```

`8123` 是示例端口，可换成空闲端口。浏览器会自动打开带本地会话凭证的页面。
先在“工作台”查看资产，再到“用例”编辑、“运行”执行、“报告”看结果。
想让 Agent 帮忙创建或维护测试资产，继续阅读下方 [Agent 配置与使用](#agent-配置与使用)。

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
aitest console --workspace <dir> --port <port>                # 启动本地界面
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

## 本地 Console：浏览、编辑、执行、看报告

本地 Console 使用 Vue 3 + FastAPI，源码编辑器使用 Monaco（VS Code 的编辑器组件）。
服务只监听本机回环地址，不是需要部署到服务器的多人 SaaS。界面与 CLI 使用同一份 workspace 文件。

| 页面 | 可以做什么 |
|---|---|
| 工作台 | 浏览目录、打开或初始化 workspace；浏览 target、module、suite、case 和 task，创建测试资产、删除 suite |
| 用例 | 多标签编辑 Markdown、YAML、Python 和 profile；Markdown 安全预览、校验结果、保存冲突处理；设置中调整编辑器主题和标签行为 |
| 运行 | 选择 case、suite、module 或 task；执行 profile validation、codegen、freshness check 和测试 |
| 报告 | 查看历史执行、`result.json` 和 `report.md`；JSON 只读查看 |
| 诊断 | 查看失败分类并跳转相关源文件；区分配置、脚手架、环境、生成和断言问题，断言失败不自动等于待测系统 bug |
| 环境 | 显式创建或编辑已授权 env 文件，敏感值默认隐藏，外部 env 文件逐文件授权 |
| Agent | 与模型协作、查看工具调用和写入 Diff、处理审批、继续历史会话、查看请求诊断 |

suite 是界面增删管理的最小用例单位。修改或删除 suite 内的单个 case，请直接编辑对应 Markdown 并保存；
不提供 case 级新增／删除表单。generated pytest 和报告保持只读，Harness、helper、profile 使用代码编辑器，不提供复杂低代码表单。

### 从任意目录启动

安装完成且环境已激活后，不需要回到 AITest 源码目录。可指定 workspace，或先打开空工作台再浏览目录：

```bash
aitest console --workspace /path/to/aitest_workspace --port 8123
# 也可以先不打开 workspace
aitest console --port 8123
```

端口也可通过 `AITEST_CONSOLE_PORT` 提供。默认会自动打开浏览器；若没有自动打开，追加 `--no-open`
重新启动，并复制终端输出的完整 `Session URL`。不要只打开裸地址或分享会话地址；Console 重启后旧凭证失效。

选择未初始化目录时不会自动写文件。只有点击“初始化并打开”才调用非 force 初始化，
模板冲突会停止并保留原文件。打开 workspace 不会自动运行测试。

### 一次常用操作流程

1. 在“工作台”打开 workspace，选择或创建 target、module、suite。
2. 在“用例”编辑 Markdown；按需维护 module/suite profile、Harness 和 helper。
3. 到“运行”先做 profile validation，再 codegen，再做 freshness check（确认生成的 pytest 与源用例和配置一致，不是执行测试）。
4. 在“环境”准备运行所需变量，选择范围运行测试。
5. 在“报告”看本次和历史结果，有问题到“诊断”定位并回到源文件修正，再生成和运行。

环境页支持 `.env`、`AITEST_ENV_FILE` 和 task `env_files`；env 值不进入普通文件接口或 localStorage。
任务输出会对 Console 已知的敏感值做脱敏，但测试资产仍不得主动打印凭证。

## Agent 配置与使用

内置 Agent 通过 Pi SDK 运行，可以读取文档和测试知识库、遵循 workspace skills 生成 Markdown 用例、
补充 Harness/profile、执行校验和 codegen、分析失败并修改测试资产。AI 负责判断与编辑，
稳定的校验、生成和执行仍交给 AITest CLI；不是让模型绕过 profile gate 直接维护 generated pytest。

### 1. 准备 Runtime 和模型连接

1. 安装 Node.js 22.19.0+ 和 npm，再打开“设置 → 模型连接”。
2. 在 Runtime 卡片确认安装，或在终端执行 `aitest agent setup`。它按锁定依赖安装到当前用户目录，不修改 workspace。
3. 填写连接名称、接口类型、Base URL、模型名和 API Key，无需查找 Pi Provider。
   支持 OpenAI Responses、OpenAI Chat Completions、Anthropic Messages；OpenAI 兼容模型的“自动检测”优先 Responses，仅在明确协议不兼容时尝试 Chat Completions。Claude 模型名自动选择 Anthropic Messages。
4. 点击“测试连接”，确认成功后保存。测试会发送真实、无工具的模型请求，可能产生服务商费用；自动检测回退时可能多于一次。

Base URL 和模型名以你的服务商提供的信息为准。非敏感配置保存在 workspace；界面输入的 Key 仅保存在当前
Console 进程内存，重启或切换 workspace 后需要重新输入。也可在启动 Console 前通过所配置的环境变量提供 Key。
本地优先不等于模型离线：Agent 读取的内容可能发送给所配置的模型服务，使用外部源码和知识库前需确认数据使用权限。

### 2. 创建会话，按 skill 工作

打开“Agent”，建议先创建审批模式会话。Console 会将当前 workspace 的 `.codex/skills/`、
`.agents/skills/`、`skills/` 作为 skill 输入；新 workspace 自带的 `skills/` 可直接使用，不必额外安装一套全局 Pi 配置。
AITest 使用隔离的 Agent 配置目录，不自动加载用户全局 Pi 配置和第三方扩展。

可以从这些具体指令开始（把模块和路径换成自己的）：

```text
使用 test-maintain 检查当前 workspace，告诉我下一步该做什么，先不要改文件。
使用 test-design，基于已有知识库为指定模块设计一个 suite，写完后停下来等我 review。
使用 test-scaffold 补齐已确认 suite 的 Harness 和 profile，然后使用 test-codegen 校验并生成测试。
读取这次执行的 result.json，区分环境、脚手架和断言问题，先提出修复建议。
```

审批卡展示待执行工具与参数，支持“允许一次”“本会话允许”“拒绝”；write/edit 可查看 Monaco Diff。
外部目录、递归 grep、写文件和 Shell 需要审批；直接读取敏感路径默认拒绝。
**审批不是沙箱**：批准 grep/Shell 后仍可能访问敏感内容。完全信任模式会使用本机进程权限，
每次创建或重新激活都需针对当前 workspace 确认，只应在信任任务、文件和模型时使用。

### 3. 历史恢复与长等待排查

支持多个持久历史会话，同一 Console 同时只有一个活跃 Worker，不能并行运行多个 Agent 会话。
重启后可查看历史并显式继续；未完成任务标记为 `interrupted`，不自动重试工具或恢复旧审批授权，
应先核对最后一次工具是否已产生效果。历史保存在用户级、按 workspace 隔离的目录，不是额外的跨会话语义记忆库。

输入区上方展示请求阶段和审批状态，展开“请求诊断”可看 HTTP、首字、完成耗时及自动重试。
遇到长等待，可在发送前勾选“仅下一条消息采集详细流诊断”；目前仅 OpenAI Responses 支持详细 SSE 统计。
诊断不记录请求／响应正文、思考内容、header 或凭证，也不改变原有权限和重试策略。

### CLI、Runtime 与运行凭据

运行真实接口测试时通过 env 文件提供凭据：

```bash
AITEST_ENV_FILE=/tmp/test.env aitest run --suite-file <suite.yaml>
```

报告的环境来源信息只记录变量名，不记录变量值；请求／响应和测试输出仍需避免泄露敏感内容。完整选项见 `aitest --help`。

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

协议和日志只传环境变量名，不传 Key。审批模式下 workspace 内 read/find/ls 默认允许，
grep/write/edit/bash/外部目录需批准，`.env`、私钥等敏感路径默认拒绝。

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
- 不应让 Agent 未经确认创建真实账号、充值或变更生产资源；模型连接测试和 Agent 对话会调用你配置的服务，可能产生费用。

## 当前稳定边界

核心链路：`aitest init/codegen/run/report/doctor/upgrade`、workspace layout、Markdown 用例格式、profile schema、request bindings、structured assertions、Case IR → pytest、freshness check、结构化报告。

当前 `main` 还提供本地 Console、Monaco 编辑、Pi Agent 审批与持久会话、请求诊断；不包含多人服务、沙箱或多 Agent 会话并行执行。
仍在演进：Console/Agent 交互、health/promotion report 口径、`case_flows` step 词汇表、内部 Python API 和契约测试方向。

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

修改前端才需要 Node.js 和前端构建。源码开发建议统一使用满足 Worker 要求的 Node.js 22.19.0+：

```bash
npm ci --prefix console_web
npm run build --prefix console_web
```

构建产物写入 `aitest_kit/console/web/`。重新启动 Console 并使用新打开的会话页面查看效果；
只重启 Python 不会自动编译 Vue 源码。Worker 源码开发和用户级 Runtime 安装方式见上文。

## 文档

- [Getting Started](docs/usebook/aitest_getting_started.md) — 安装、初始化、首个模块迁移到长期维护
- [Profile Guide](docs/usebook/codegen_profile_guide.md) — 编写 module/suite profile
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md) — codegen 常见问题
- [Contributing](CONTRIBUTING.md) — 贡献指南
- [Console / Pi 交付验收](docs/usebook/console_delivery_verification.md) — 三平台安装 CI、视觉基线和持久化测量
- [CHANGELOG](CHANGELOG.md) — 版本变更记录

## License

[MIT](./LICENSE)
