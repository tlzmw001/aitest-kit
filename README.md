# AIAutoTest

AI 驱动的自动化测试工具，基于 Claude Code Skill 编排 **文档 → 知识库 → 用例 → 代码 → 执行** 全流程。

本项目探索一种新的测试生产模式：用 AI Skill 流水线将开发文档转化为可执行的 pytest 测试代码，做到"测试用例即编译产物"——Markdown 是唯一数据源，pytest 代码由 codegen 管线确定性生成。

## 快速开始

### 环境要求

- Python 3.9+
- Redis（待测系统的数据层）
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI（运行 Skill 流水线）

### 安装

```bash
# 安装项目及依赖
pip install -e ".[dev,server]"
```

### 新项目接入

当前仓库同时包含 AITest 框架代码、示例待测系统和本仓库自己的测试资产。给一个全新的项目设计测试时，不要直接复用根目录下已有的 `test_workspace/`。

新项目应从干净模板开始：

```bash
aitest init --target /path/to/your_project
```

源码开发场景也可以手工复制 `templates/project_workspace/`。然后在新项目目录内放入开发文档，重建 `aitest_config/`、`test_workspace/knowledge/`、Markdown 用例、fixture 和 codegen profile。完整迁移步骤见 `docs/usebook/codegen_new_project_migration_playbook.md`。

如果不想切换目录，核心命令支持 workspace 参数：

```bash
aitest codegen <module> --workspace /path/to/your_project --validate-profile
aitest run <module> --workspace /path/to/your_project
aitest report --workspace /path/to/your_project
```

### 启动待测系统

```bash
# 启动智能优惠券推荐服务（FastAPI + gRPC）
python -m coupon_system.main
```

### 运行测试

```bash
# 运行单元测试
pytest tests/

# 运行 codegen 生成的集成测试
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

## 项目结构

```
AIAutoTest/
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
├── docs/                       # 开发文档输入（Skill 的原始输入源）
├── pyproject.toml              # 项目元数据 + 依赖声明
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
