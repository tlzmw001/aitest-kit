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
test_workspace/         # 知识库、用例、fixture、profile、generated pytest、报告
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
| 脚手架 | 为模块补 fixture、helper、profile | `/test-scaffold` |
| 代码生成 | Markdown + profile → pytest | `aitest codegen` |
| 执行报告 | freshness check → pytest → 结构化报告 | `aitest run` |
| 沉淀 | 重复模式提取为规则和模板 | `/emitter-build` |

## CLI 速查

```bash
aitest init --target <dir>                                   # 初始化 workspace
aitest doctor                                                # 体检
aitest codegen --suite-file <suite.yaml> --validate-profile  # profile 门禁
aitest codegen --suite-file <suite.yaml>                     # 生成 pytest
aitest codegen --suite-file <suite.yaml> --check             # 检查 generated 是否过期
aitest run --suite-file <suite.yaml>                         # 执行一个 suite
aitest run --target <target> [--module <module>]             # 按 target/module 回归
aitest run --all                                             # 全量回归
aitest report --suite-file/--target/--all ...                # 重渲染报告
```

运行真实接口测试时通过 env 文件提供凭据：

```bash
AITEST_ENV_FILE=/tmp/test.env aitest run --suite-file <suite.yaml>
```

报告只记录变量名，不记录变量值。完整选项见 `aitest --help`。

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
| `test-design` | 从知识库生成 Markdown 用例 |
| `test-scaffold` | 为新模块或 suite 补 fixture/profile |
| `test-codegen` | 从 Markdown/profile 生成 pytest |
| `test-fix` | 修正错误用例并沉淀经验 |
| `test-maintain` | 诊断 workspace 状态，路由到对应 skill |
| `emitter-build` | 从已验证测试中提取可沉淀规则 |

## Codegen 路线

| 路线 | profile 配置 | 适用场景 |
|---|---|---|
| 默认 HTTP/gRPC | `request_overrides` | 单接口、请求结构稳定 |
| 断言规则 | `assertion_rules` | 调用标准，断言需模板化 |
| 结构化流程 | `case_flows` | 线性多步骤 |
| 自定义代码 | `case_bodies` | 并发、mock、进程等复杂场景 |

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
│   ├── targets/                  # fixture、helper、module profile
│   ├── generated/                # generated pytest（编译产物）
│   ├── reports/                  # 运行报告
│   └── results/                  # 待测系统 bug 记录
├── skills/                       # agent-neutral AI skills
├── AGENTS.md
└── CLAUDE.md
```

## 安全与隐私

- 不提交 `.env`、token、密码或生产账号。
- profile `variables.env` 只写变量名，不写值；报告可能含请求/响应详情，对外共享前需脱敏。
- 不自动创建账号、充值或调用付费资源。

## 当前稳定边界

v0.2.x 稳定：`aitest init/codegen/run/report/doctor/upgrade`、workspace layout、Markdown 用例格式、profile schema、Case IR → pytest 主链路、freshness check、结构化报告。

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
- [CHANGELOG](CHANGELOG.md) — 版本变更记录

## License

[MIT](./LICENSE)
