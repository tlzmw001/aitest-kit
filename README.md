# aitest-kit

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

AI 驱动的自动化测试工具包，围绕 **文档 → 知识库 → Markdown 用例 → codegen → pytest 执行 → 报告反哺** 构建测试生产流程。

CLI 与 workspace 模板负责稳定、可重复的生成和执行；本地 AI skills 负责文档理解、用例设计、问题修正和规则沉淀。项目目标是让 AI 先探索未知，再把稳定模式沉淀为可验证、可复用的配置和代码生成规则。

## 快速开始

### 环境要求

- Python 3.9+
- pytest
- 目标系统所需的本地依赖或外部服务，例如 HTTP 服务、gRPC 服务、Redis、数据库等
- 可选：[Claude Code](https://docs.anthropic.com/en/docs/claude-code)、Codex 或其他 AI 编程环境，用于运行本地 skills 工作流

### 安装

```bash
# 从 PyPI 安装
pip install aitest-kit

# 从本地 release wheel 安装（用于发布前验收或内部分发）
pip install dist/aitest_kit-0.1.1-py3-none-any.whl

# 本仓开发和回归验证
pip install -e ".[dev,server]"
```

### 接入新项目

本仓保持单仓架构：`aitest_kit`、schema、workspace 模板和本仓回归资产同仓维护，但真实用户项目使用独立 workspace。不要直接复用本仓的 `test_workspace/` 作为新项目工作区。

```bash
# 在目标目录创建干净 workspace
aitest init --target /path/to/your_project

# 从任意目录操作该 workspace
aitest codegen --workspace /path/to/your_project --all --validate-profile
aitest codegen --workspace /path/to/your_project --all
aitest run --workspace /path/to/your_project <module>
aitest report --workspace /path/to/your_project
```

workspace 模板只有一个来源：`aitest_kit/templates/project_workspace/`。项目根目录不再维护第二份 `templates/project_workspace/`。
模板会同时初始化 `AGENTS.md`、`CLAUDE.md` 和 `.codex/.claude/.agents` 三套 skills；这些是新项目 AI 协作流程的一部分，不需要用户手工从本仓复制。

新项目从零接入建议先读：

- [AITest Quickstart](docs/usebook/aitest_quickstart.md)：跑通 `init -> codegen -> pytest collect` 最小闭环
- [Codegen Profile Guide](docs/usebook/codegen_profile_guide.md)：编写 `codegen_profile_{module}.md`
- [Codegen Troubleshooting](docs/usebook/codegen_troubleshooting.md)：排查 profile gate、stale generated、fixture 等常见问题
- [Codegen 新项目迁移 Playbook](docs/usebook/codegen_new_project_migration_playbook.md)：完整迁移 SOP
- [CHANGELOG](CHANGELOG.md)：当前 release 支持范围、实验能力和不支持项

### 本仓开发与示例回归

本仓内置 `coupon_system/` 和 `ab_experiment_sdk/` 作为回归资产，用于验证 aitest-kit 自身的 codegen、报告和迁移能力。它们不是新项目接入时必须复制的模板。

```bash
# 启动本仓示例待测系统（FastAPI + gRPC）
python -m coupon_system.main

# 运行本仓单元测试
pytest tests/

# 运行本仓 generated 集成测试
pytest test_workspace/tests/generated/ -v

# 执行 generated 测试并生成结构化报告
aitest run calibration              # 默认跳过 manual 用例
aitest run calibration --include-manual
aitest report                       # 从 latest/result.json 重新渲染 report.md

# 用 codegen CLI 生成/校验测试代码
aitest codegen --all --validate-profile  # profile 硬门禁：JSON Schema + 语义校验
aitest codegen calibration          # 生成单个模块
aitest codegen --all                # 生成全部模块
aitest codegen --all --check        # 校验模式：检查生成结果是否一致
aitest codegen --all --health-report --write-report
```

### 发布状态与稳定性

v0.1 的稳定边界是本地 CLI、workspace layout、Markdown 用例格式、profile JSON Schema、profile gate、Case IR 到 generated pytest 的主链路，以及 `aitest run/report` 的报告格式。

仍处于演进状态的能力包括：health/promotion report 的成熟度口径、promotion patch 的人工应用流程、`case_flows` 的 step 词汇表，以及 `aitest_kit.codegen` 下的内部 Python API。新项目迁移仍需要人工 review 文档、用例、profile 和 fixture；工具不会自动修改待测系统业务代码。

### 安全与隐私

- 不要把 `.env`、服务凭证、访问 token、生产数据库地址或真实用户数据提交到 AITest workspace。
- fixture 需要外部服务地址时，优先从环境变量读取；缺失时应明确失败，不要写死 URL 或静默跳过。
- `test_workspace/reports/` 可能包含请求 ID、响应体、断言错误、服务错误详情和 JUnit XML；对外共享前需要按项目规则脱敏。
- `test_workspace/results/` 用于记录确认过的待测系统 bug，也可能包含复现数据；同样按测试证据管理。
- v0.1 不会自动清洗待测系统响应，敏感字段需要在 fixture、helper 或报告发布流程中自行控制。

## 项目结构

```
aitest-kit/
├── coupon_system/              # 待测系统：智能优惠券推荐服务
│   ├── http_app.py             #   FastAPI HTTP 入口
│   ├── main.py                 #   服务启动入口
│   ├── services/               #   业务服务层
│   ├── calibration/            #   分数校准模块
│   ├── scoring_server/         #   gRPC 打分服务
│   ├── config/                 #   服务配置
│   └── protos/                 #   protobuf 定义
│
├── ab_experiment_sdk/          # AB 实验 SDK（待测系统依赖）
│
├── test_workspace/             # AI 生成的测试工作区
│   ├── knowledge/              #   测试知识库（L0 架构 / L1 模块 / L2 接口）
│   ├── cases/                  #   测试用例 Markdown（按模块分目录）
│   ├── tests/
│   │   ├── conftest.py         #     全局 session fixtures
│   │   ├── fixtures/           #     模块 fixture + codegen profile
│   │   ├── helpers/            #     HTTP / gRPC / Redis 测试工具
│   │   └── generated/          #     codegen 生成的 pytest 文件（编译产物）
│   ├── results/                #   待测系统 bug 记录
│   ├── reports/                #   测试执行报告（运行产物，不入库）
│   └── plans/                  #   方案文档
│
├── aitest_kit/                 # Python 工具库
│   ├── cli.py                  #   命令行入口（aitest 命令）
│   ├── templates/              #   包内唯一 project_workspace 模板
│   ├── codegen/                #   代码生成引擎
│   │   ├── parser.py           #     Markdown → 结构化数据
│   │   ├── planner.py          #     ParseResult → Case IR
│   │   ├── ir.py               #     Case IR 数据结构
│   │   ├── ir_renderer.py      #     Case IR → pytest 文本
│   │   ├── emitter.py          #     装载、诊断、落盘编排
│   │   ├── project_config.py   #     项目配置加载器
│   │   ├── profile.py          #     模块 profile 加载器
│   │   ├── profile_validator.py #     profile 结构和语义门禁
│   │   ├── promotion.py        #     case_body 晋升候选分析
│   │   ├── health.py           #     codegen 健康报告
│   │   └── render_utils.py     #     代码渲染工具
│   └── report/                 #   测试结果采集与 Markdown 报告
│
├── aitest_config/              # 项目级配置（详见下方"配置文件"章节）
│   ├── config.yaml             #   项目路径 / 服务 / 协议 / 已知限制
│   ├── project_config.yaml     #   codegen 引擎配置
│   ├── schemas/                #   JSON Schema（profile 结构契约）
│   └── refs/                   #   共享引用文档（断言策略、用例格式模板等）
│
├── .claude/skills/             # Claude Code Skill 定义（详见下方"Skill 流水线"章节）
├── .codex/skills/              # Codex Skill 定义
├── .agents/skills/             # agents 工作流 Skill 定义
├── docs/                       # 开发文档输入（Skill 的原始输入源）
├── pyproject.toml              # 项目元数据 + 依赖声明
├── AGENTS.md                   # AI 协作总入口
└── CLAUDE.md                   # Claude Code 项目指令
```

## Skill 流水线

七个 Skill 构成一条闭环测试流水线，分为设计阶段和执行阶段：

```
── 设计阶段 ──

docs/（开发文档）
  ↓  /doc-review     审查文档完整性，输出缺口清单
  ↓  /doc-gen        从源码补全缺失的设计文档（可选）
  ↓  /knowledge-build 构建/更新测试知识库（L0/L1/L2）
  ↓  /test-design    基于知识库 + TEST_SPEC 设计测试用例
  ↓  人工评审
  ↓  /test-fix       修正用例 + 沉淀经验到 TEST_SPEC

── 执行阶段 ──

  ↓  /test-codegen   Markdown 用例 → pytest 代码
  ↓  aitest run / pytest 执行
  ↓  result.json + report.md
  ↓  失败分流 → /test-fix 或更新 fixture/profile/emitter
  ↓  测试全部通过
  ↓  /emitter-build  从已验证 .py 提取确定性模板
```

### Skill 速查

| Skill | 用途 | 调用示例 |
|-------|------|---------|
| `/doc-review` | 审查开发文档完整性 | `/doc-review` |
| `/doc-gen` | 从源码生成设计文档 | `/doc-gen calibration` |
| `/knowledge-build` | 构建/更新测试知识库 | `/knowledge-build calibration` |
| `/test-design` | 设计测试用例（Markdown） | `/test-design calibration` |
| `/test-fix` | 修正用例 + 沉淀经验 | `/test-fix calibration` |
| `/test-codegen` | Markdown → pytest 代码 | `/test-codegen calibration` |
| `/emitter-build` | 提取确定性生成模板 | `/emitter-build calibration` |

### 使用场景

- **首次接入新项目**：`/doc-review` → `/doc-gen`（按需）→ `/knowledge-build` → `/test-design`
- **需求迭代**：新文档放入 `docs/` → `/knowledge-build`（增量）→ `/test-design`（增量）
- **用例出错**：`/test-fix`（修用例 + 更新 TEST_SPEC 陷阱）
- **生成 pytest**：`/test-codegen <模块名>`
- **模板固化**：测试全部通过后 `/emitter-build <模块名>`

## Codegen 管线

codegen 是本项目的核心——将 Markdown 测试用例确定性地编译为 pytest 代码。

### 工作流程

```
Markdown 用例 + codegen_profile
  → profile gate（JSON Schema + 语义校验）
  → parser（结构化提取）
  → Case IR planner（生成策略与 source_trace）
  → emitter / IR renderer（确定性生成 pytest）
  → AI 补写少量 UNPARSED
  → pytest collect/run
```

1. **profile gate** 是硬门禁：普通生成、`--check`、`--dump-ir`、`--explain` 和 promotion 分析都会先校验 profile，ERROR 直接阻断。
2. **parser** 确定性地将 Markdown 解析为 `SharedConfig` + `TestCase` 列表，不读取 profile，也不做业务推理。
3. **Case IR planner** 结合 Markdown、`project_config.yaml` 和 `codegen_profile_{module}.md` 决定每条用例走 `default_http`、`default_grpc`、`structured_case_flow`、`custom_case_body`、`manual` 或 `skipped`。
4. **emitter / IR renderer** 把 Case IR 确定性渲染为 `.py`；无法模板匹配的断言输出为 `# UNPARSED ASSERTION:`，由 AI 补写。
5. **health / promotion report** 写入 `test_workspace/reports/codegen/latest/`，用于观察成熟度和判断下一轮规则沉淀。

### 三层可移植架构

codegen 管线分三层，换项目时只改配置层，不改框架层：

| 层级 | 内容 | 换项目时 |
|------|------|---------|
| **框架层** | parser / Case IR / emitter / profile validator / promotion / health / CLI / helpers / SKILL.md | 不改 |
| **项目配置层** | `aitest_config/config.yaml` + `project_config.yaml` | 重写 |
| **模块配置层** | `codegen_profile_{module}.md` + `fixtures/{module}.py` | 每模块一份 |

### 防御层

codegen 管线内置分层防御，拦截常见的静默失败：

| 错误码 | 触发条件 | 行为 |
|--------|---------|------|
| E001 | parser JSON 解析失败 | 输出诊断信息，不静默返回 None |
| E002 | 无基础请求体且无 case_bodies/case_flows 覆盖 | 拒绝生成 |
| E003 | codegen_profile 声明未知 module_type | 拒绝生成 |
| E004 | module_type 缺少 requires 字段 | 拒绝生成 |
| E501-E511 | profile 结构、case_id、case_flow、module_type 校验失败 | profile gate 阻断 |

## 配置文件清单

### `aitest_config/config.yaml` — 项目配置

供 Skill 读取的项目级配置，定义路径映射、服务地址等。换项目时修改此文件。

| 配置段 | 内容 |
|--------|------|
| `paths` | 知识库、用例、文档等目录路径 |
| `service` | 待测服务语言、框架、端点地址、路由模式 |
| `data` | 测试数据存储（Redis 等）连接信息 |
| `protocols` | 协议偏好（HTTP / gRPC）|
| `known_limitations` | 待测系统的已知限制，影响用例可行性判断 |

### `aitest_config/project_config.yaml` — codegen 引擎配置

emitter / parser 生成 pytest 代码时读取。换项目时修改此文件。

| 配置段 | 内容 |
|--------|------|
| `helper_import` / `helper_call` | 生成代码的 import 语句和请求调用方式 |
| `api_path` | 默认 API 路径 |
| `var_map` | 断言变量简写 → 完整表达式映射 |
| `module_abbrevs` | 模块名 → TC ID 缩写映射 |
| `named_templates` | 复杂断言的 Python 命名模板列表 |
| `module_types` | 模块类型定义及必需字段 |
| `modules` | 模块注册表（类型 + 特殊说明）|
| `builtin_assertion_rules` | 内置断言规则（正则 → 模板映射）|

### `aitest_config/refs/` — 共享引用文档

跨 Skill 共用的格式定义和模板：

| 文件 | 内容 |
|------|------|
| `assertion-strategy.md` | 断言策略（结构断言 / 关系断言 / manual）|
| `case-format.md` | 用例 Markdown 格式规范 |
| `l1-template.md` | L1 知识库文档模板 |
| `l2-template.md` | L2 知识库文档模板 |
| `mismatch-format.md` | mismatch 记录格式 |

### `pyproject.toml` — 项目元数据

标准 Python 项目配置，定义依赖、入口命令（`aitest`）、pytest 配置等。

### `test_workspace/tests/conftest.py` — 全局 Fixture

提供 session 级 fixture：`http_base_url`、`grpc_target`、`ab_base_url`、`redis_url`、`redis_tracker`。通过环境变量覆盖默认地址。

### 模块配置文件（每模块一份）

| 文件 | 内容 |
|------|------|
| `tests/fixtures/codegen_profile_{module}.md` | 模块的 codegen 配置：module_type、断言规则、请求模板、setup 映射、调试经验 |
| `tests/fixtures/{module}.py` | 模块的 pytest fixture：setup/teardown 逻辑、`_CASE_CONFIGS` 数据 |

## 测试报告

`aitest run` 会先执行 generated freshness check，确认 Markdown/profile 与 generated pytest 一致；检查失败时生成 `BLOCKED_RUN` 报告并停止，不执行过期测试。

报告产物默认写入 `test_workspace/reports/`：

```
test_workspace/reports/
├── latest/
│   ├── junit.xml
│   ├── result.json
│   └── report.md
└── runs/{run_id}/
    ├── junit.xml
    ├── result.json
    └── report.md
```

`manual` 用例默认不执行，报告会单独统计 `manual_total`、`manual_executed`、`manual_not_run`。如需执行 manual 用例，使用 `aitest run --include-manual`。

## 待测系统

当前待测系统是一个**智能优惠券推荐策略服务**（`coupon_system/`），技术栈：

- **FastAPI** — HTTP 接口（`/api/v1/recommend`）
- **gRPC** — 打分服务
- **Redis** — 库存、场景路由表、实验配置缓存

> 测试代码作为独立进程通过 HTTP/gRPC 调用待测服务，不 import 服务内部模块。

## 技术栈

| 组件 | 技术 |
|------|------|
| 待测系统 | Python / FastAPI / gRPC / Redis |
| 测试客户端 | httpx / grpcio |
| 测试框架 | pytest |
| 代码生成 | aitest_kit（parser → Case IR planner → emitter / IR renderer）|
| AI 编排 | Claude Code Skill |
| 配置格式 | YAML |

## License

MIT
