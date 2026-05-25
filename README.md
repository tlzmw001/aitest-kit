# aitest-kit

> **把开发文档逐步转成知识库、Markdown 用例、pytest 代码和结构化测试报告。**

[English](README.en.md)

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

AITest Kit 是一套 AI 辅助的自动化测试工具链。CLI 与 workspace 模板负责稳定、可重复的生成和执行；本地 AI skills 负责文档理解、用例设计、问题修正和规则沉淀。

## 亮点

- **文档驱动** — 从开发文档出发，逐步构建知识库、用例和测试代码，不跳步
- **确定性 codegen** — Markdown 用例 + profile 配置编译为 pytest，相同输入相同输出
- **三层可移植** — 框架层换项目不改，项目配置层重写 YAML，模块配置层每模块一份
- **防御层内置** — profile gate、parser 诊断、module_type 校验，静默失败在生成前拦截
- **AI 做探索，规则做沉淀** — AI 先手写探索未知，稳定模式沉淀为可验证的配置和生成规则
- **结构化报告** — `result.json` + `report.md` + `junit.xml`，失败自动分流到用例 / fixture / 环境 / 系统 bug
- **零硬编码** — 端口、URL、凭证全部走环境变量或配置文件

## 快速开始

### 1. 安装

```bash
pip install aitest-kit
```

### 2. 初始化新项目 workspace

```bash
aitest init --target /path/to/your_project
```

### 3. 跑第一个 codegen

```bash
cd /path/to/your_project

# 校验 → 观察 → 生成 → 检查
aitest codegen --all --validate-profile
aitest codegen --all --dump-ir
aitest codegen --all
aitest codegen --all --check

# 收集测试
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

从 workspace 外部操作时追加 `--workspace /path/to/your_project`。

## 给人类用户

日常使用主路径：

```bash
aitest codegen <module>              # 生成单个模块的 pytest
aitest codegen --all                 # 生成全部模块
aitest codegen --cases <suite_dir>   # 生成一批独立 case suite 的 pytest
aitest codegen --all --check         # 校验 generated 是否与 Markdown/profile 同步
aitest run <module>                  # 执行测试 + 生成结构化报告
aitest report                        # 重新渲染报告
aitest doctor                        # 检查 workspace、profile、generated 和 collect 状态
aitest upgrade --check               # 检查已初始化 workspace 是否需要同步新版模板资产
aitest upgrade --apply               # 安全应用可自动合并的模板资产升级
```

### 升级已有 workspace

升级分两步：

```bash
python3 -m pip install -U aitest-kit
aitest upgrade --workspace /path/to/your_project --check
aitest upgrade --workspace /path/to/your_project --apply
```

`pip install -U` 只升级 CLI、codegen、doctor、run/report 等 Python 程序；`aitest upgrade` 才会检查已经复制进项目的 workspace 资产，例如 skills、schema、refs、helpers 和协作说明。

不要用 `aitest init --force` 升级已有 workspace。`upgrade` 会根据 `.aitest/workspace.json` 判断文件是否仍是旧模板：未被本地修改的模板文件可安全更新，疑似用户修改过的文件默认跳过并提示人工 review。

### 观测与诊断

```bash
aitest codegen <module> --validate-profile          # profile 门禁校验
aitest codegen <module> --dump-ir                    # 查看每条用例的生成策略
aitest codegen <module> --explain TC-XXX             # 解释单条用例为什么这么生成
aitest codegen --all --health-report --write-report  # 模块成熟度报告
aitest codegen <module> --analyze-promotion          # 晋升候选分析
aitest doctor --module <module>                      # 诊断单个模块
```

## 给 AI Agent

AITest Kit 内置 8 个本地 skills，安装到 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)、Codex 或其他 AI 编程环境后，形成闭环测试流水线：

```
── 设计阶段 ──

docs/（开发文档）
  ↓  /doc-review      审查文档完整性，输出缺口清单
  ↓  /doc-gen         从源码补全缺失的设计文档（可选）
  ↓  /knowledge-build  构建/更新测试知识库（L0/L1/L2）
  ↓  /test-design      基于知识库 + TEST_SPEC 设计测试用例
  ↓  人工评审
  ↓  /test-fix         修正用例 + 沉淀经验到 TEST_SPEC

── 脚手架阶段 ──

  ↓  /test-scaffold    从用例 + API 文档构建 fixture + codegen profile
  ↓  验证：validate-profile / dump-ir / codegen --check / collect

── 执行阶段 ──

  ↓  /test-codegen     Markdown 用例 → pytest 代码
  ↓  aitest run / pytest 执行
  ↓  result.json + report.md
  ↓  失败分流 → /test-fix 或更新 fixture/profile/emitter
  ↓  测试全部通过
  ↓  /emitter-build    从已验证 .py 提取确定性模板
```

### Skill 速查

| Skill | 用途 | 调用示例 |
|-------|------|---------|
| `/doc-review` | 审查开发文档完整性 | `/doc-review docs/` |
| `/doc-gen` | 从源码生成设计文档 | `/doc-gen src/ docs/` |
| `/knowledge-build` | 构建/更新测试知识库 | `/knowledge-build docs/` |
| `/test-design` | 设计测试用例（Markdown） | `/test-design <module>` |
| `/test-fix` | 修正用例 + 沉淀经验 | `/test-fix TC-XXX "error desc"` |
| `/test-scaffold` | 构建模块 fixture + profile | `/test-scaffold <module>` |
| `/test-codegen` | Markdown → pytest 代码 | `/test-codegen <module>` |
| `/emitter-build` | 提取确定性生成模板 | `/emitter-build <module>` |

### 使用场景

| 场景 | 路径 |
|------|------|
| 首次接入新项目 | `/doc-review` → `/doc-gen`（按需）→ `/knowledge-build` → `/test-design` → `/test-scaffold` → `/test-codegen` |
| 需求迭代 | 新文档 → `/knowledge-build`（增量）→ `/test-design`（增量） |
| 新模块缺 fixture | `/test-scaffold <module>`（构建 fixture + profile） |
| 用例出错 | `/test-fix`（修用例 + 更新 TEST_SPEC 陷阱） |
| 生成 pytest | `/test-codegen <module>` |
| 模板固化 | 测试全部通过后 `/emitter-build <module>` |

## Codegen 管线

将 Markdown 测试用例确定性编译为 pytest 代码：

```
Markdown 用例 + codegen_profile
  → profile gate（JSON Schema + 语义校验）
  → parser（结构化提取）
  → Case IR planner（生成策略与 source_trace）
  → emitter / IR renderer（确定性生成 pytest）
  → AI 补写少量 UNPARSED
  → pytest collect/run
```

### 四条生成路线

| 路线 | profile 配置 | 适用场景 |
|------|-------------|---------|
| 默认模板 | `request_overrides` | 标准单接口，只需覆盖请求字段 |
| 断言规则 | `assertion_rules` | 标准接口但断言需要模板化 |
| `case_flows` | YAML 多步骤流程 | 稳定的调用 → 保存 → 断言流程 |
| `case_bodies` | 原始 Python 代码 | 复杂场景逃生通道（并发、mock、进程等） |

晋升方向：`case_bodies` → `case_flows` → `assertion_rules` / 默认模板。

### 防御层

| 错误码 | 触发条件 | 行为 |
|--------|---------|------|
| E001 | parser JSON 解析失败 | 输出诊断，不静默返回 None |
| E002 | 无基础请求体且无 profile 覆盖 | 拒绝生成 |
| E003-E004 | module_type 校验失败 | 拒绝生成 |
| E501-E511 | profile 结构/引用/格式校验失败 | profile gate 阻断 |

### 三层可移植架构

| 层级 | 内容 | 换项目时 |
|------|------|---------|
| **框架层** | parser / Case IR / emitter / validator / CLI / helpers / skills | 不改 |
| **项目配置层** | `config.yaml` + `project_config.yaml` | 重写 |
| **模块配置层** | `codegen_profile_{module}.md` + `fixtures/{module}.py` | 每模块一份 |
| **用例批次层** | `aitest_suite.yaml` + `codegen_profile_{suite}_suite.md` | 按 L2/测试批次跟随用例目录 |

## Workspace 结构

`aitest init` 创建的目录：

```
your_project/
├── aitest_config/
│   ├── config.yaml              # 项目路径 / 服务 / 协议
│   ├── project_config.yaml      # codegen 引擎配置
│   ├── schemas/                 # JSON Schema（profile 结构契约）
│   └── refs/                    # 共享引用文档（断言策略、用例格式等）
├── test_workspace/
│   ├── knowledge/               # 测试知识库（L0/L1/L2 + TEST_SPEC）
│   ├── cases/                   # Markdown 测试用例（按模块分目录）
│   ├── casesuites/              # 可选：独立 case suite（按 L2/测试批次分目录）
│   ├── tests/
│   │   ├── fixtures/            # 模块 fixture + codegen profile
│   │   ├── generated/           # codegen 生成的 pytest（编译产物）
│   │   └── helpers/             # HTTP / gRPC 测试工具
│   ├── reports/                 # 测试执行报告
│   └── results/                 # 待测系统 bug 记录
├── .claude/skills/              # Claude Code skills
├── .codex/skills/               # Codex skills
└── .agents/skills/              # agents skills
```

## 配置文件

### `aitest_config/config.yaml` — 项目配置

| 配置段 | 内容 |
|--------|------|
| `paths` | 知识库、用例、文档等目录路径 |
| `service` | 待测服务语言、框架、端点地址 |
| `protocols` | 协议偏好（HTTP / gRPC） |
| `known_limitations` | 待测系统已知限制 |

### `aitest_config/project_config.yaml` — codegen 引擎配置

| 配置段 | 内容 |
|--------|------|
| `helper_import` / `helper_call` | 生成代码的 import 和请求调用 |
| `api_path` | 默认 API 路径 |
| `var_map` | 断言变量简写映射 |
| `module_abbrevs` | 模块名 → TC ID 缩写 |
| `default_request.auto_fields` | default_http/default_grpc 自动注入的请求字段；新项目默认空 |
| `builtin_assertion_rules` | 内置断言规则（正则 → 模板） |
| `module_types` | 模块类型定义及必需字段 |

### 模块配置（每模块一份）

| 文件 | 内容 |
|------|------|
| `codegen_profile_{module}.md` | module_type、断言规则、请求模板、case_flows / case_bodies |
| `fixtures/{module}.py` | setup / teardown、`_CASE_CONFIGS` |

## 测试报告

`aitest run` 执行前先检查 generated 是否与 Markdown/profile 同步；不同步时生成 `BLOCKED_RUN` 报告并停止。

```
test_workspace/reports/
├── latest/
│   ├── junit.xml
│   ├── result.json
│   └── report.md
└── runs/{run_id}/
```

`manual` 用例默认不执行，`--include-manual` 时执行。

## 安全与隐私

- 不要把 `.env`、凭证、token 或生产数据提交到 workspace
- fixture 需要服务地址时从环境变量读取，缺失时明确失败
- `test_workspace/reports/` 可能包含请求/响应详情，共享前需脱敏
- v0.1 不自动清洗待测系统响应

## 发布状态

**v0.1 稳定边界**：CLI、workspace layout、Markdown 用例格式、profile JSON Schema、Case IR → pytest 主链路、`aitest run/report` 报告格式。

**演进中**：health/promotion report 口径、`case_flows` step 词汇表、`aitest_kit.codegen` 内部 Python API。

## 开发

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
pip install -e ".[dev,server]"

# 单元测试
pytest tests/

# codegen 回归
aitest codegen --all --validate-profile
aitest codegen --all --check
```

本仓内置 `coupon_system/` 作为回归资产，用于验证 codegen、报告和迁移能力。

## 文档

- [Quickstart](docs/usebook/aitest_quickstart.md) — 跑通最小闭环
- [Migration Guide](docs/usebook/aitest_migration_guide.md) — 新项目迁移指南
- [Coupon System Full Example](docs/usebook/coupon_system_full_example.md) — 本仓真实回归资产示例
- [Profile Guide](docs/usebook/codegen_profile_guide.md) — 编写 codegen profile
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md) — 常见问题排查
- [Roadmap](ROADMAP.md) — 当前边界和演进方向
- [Contributing](CONTRIBUTING.md) — 贡献指南
- [CHANGELOG](CHANGELOG.md) — 版本变更记录

## License

[MIT](./LICENSE)
