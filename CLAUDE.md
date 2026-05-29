# AIAutoTest

AI 驱动的自动化测试工具，基于 Claude Code Skill 编排"文档 → 知识库 → 用例 → 执行"全流程。

## 项目结构

```
coupon_system/          # 待测系统：智能优惠券推荐策略服务（FastAPI + gRPC + Redis）
docs/                   # 开发文档输入目录（skill 的输入源）
test_workspace/         # AI 生成内容的工作目录
  knowledge/            #   测试知识库（L0/L1/L2 + TEST_SPEC）
  cases/                #   测试用例（Markdown，按模块分目录）
  casesuites/           #   可选：按 L2/迭代批次组织的独立用例 suite
  tests/                #   pytest 测试代码
    conftest.py         #     全局 session fixtures
    fixtures/           #     模块 fixture（每模块一个 .py + codegen_profile.md）
    helpers/            #     HTTP/Redis 等测试工具函数
    generated/          #     codegen 生成的 pytest 文件（编译产物）
  reports/              #   测试执行报告（运行产物，不入库）
  results/              #   待测系统 bug 记录
  plans/                #   方案文档
aitest_kit/             # Python 测试工具库
  templates/            #   包内唯一 project_workspace 模板
  codegen/              #   codegen 引擎
    parser.py           #     Markdown → ParseResult
    planner.py          #     ParseResult → Case IR（策略规划）
    ir.py               #     Case IR 数据结构
    ir_renderer.py      #     Case IR → pytest 文本
    emitter.py          #     编排入口（装载 + 诊断 + 落盘）
    profile.py          #     profile YAML 读取 + 轻量校验
    profile_validator.py#     profile JSON Schema + 语义校验
    promotion.py        #     case_bodies 晋升候选分析
    health.py           #     模块成熟度报告
    cli.py              #     codegen 子命令
    render_utils.py     #     断言解析 + 格式工具
    project_config.py   #     aitest.yaml codegen 配置加载
aitest_config/          # 项目级配置
  aitest.yaml           #   workspace 路径 + codegen 默认规则
  schemas/              #   JSON Schema
    codegen_profile.schema.json  # profile 结构契约
.claude/skills/         # Claude Code Skill 定义
  doc-gen/              #   设计文档生成（从源码）
  doc-review/           #   设计文档审查
  knowledge-build/      #   测试知识库构建/更新
  test-design/          #   测试用例设计
  test-scaffold/        #   构建模块 fixture + codegen profile（test-design → test-codegen 桥梁）
  test-codegen/         #   Markdown → pytest 代码生成（emitter + AI 补全）
  test-fix/             #   用例修正 + 经验沉淀
  emitter-build/        #   从已验证 .py 提取确定性模板
```

## 常用命令

```bash
# 安装依赖
pip install -e ".[dev,server]"

# 启动待测系统
python -m coupon_system.main

# 运行单测
pytest tests/

# 执行 generated 测试并生成结构化报告
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest report

# 初始化并操作独立新项目 workspace
aitest init --target /path/to/your_project
aitest codegen --workspace /path/to/your_project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest run --workspace /path/to/your_project --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

## 技术栈

- Python 3.9+
- FastAPI + gRPC（待测系统）
- httpx + grpcio（测试客户端）
- Redis（数据层）

## 测试飞轮工作流

八个 skill 构成一条闭环流水线，分为**设计阶段**和**执行阶段**：

```
── 设计阶段 ──

docs/（开发文档）
  ↓
doc-review  ── 审查文档完整性，输出缺口清单
  ↓
doc-gen     ── 从源码补全缺失的设计文档（可选，文档不足时用）
  ↓
knowledge-build ── 从文档构建/更新测试知识库（L0/L1/L2）
  ↓
test-design ── 基于知识库 + TEST_SPEC 生成测试用例（Markdown）
  ↓
人工评审用例
  ↓
test-fix    ── 修正用例错误，沉淀经验到 TEST_SPEC 和相关 skill

── 脚手架阶段 ──

test-scaffold ── 从用例 + API 文档构建 fixture + codegen profile
  ↓
验证：validate-profile / dump-ir / codegen --check / collect

── 执行阶段 ──

test-codegen ── Markdown 用例 → pytest 代码
  ↓
aitest run / pytest 执行
  ↓
result.json + report.md
  ↓
失败时分流：
  ├─ 用例问题 → test-fix → 重新 codegen
  └─ fixture/codegen 问题 → 更新 codegen_profile + fixture → 重新 codegen
  ↓
测试全部通过
  ↓
emitter-build ── 从已验证的 .py 提取确定性模板到 emitter
```

### test-codegen 流程细节

生成链路：`parser → Case IR planner → emitter/IR renderer → pytest`

1. **parser 解析** — `python3 -m aitest_kit.codegen.parser` 确定性提取 Markdown 结构
   - 如果 JSON 块解析失败，parser 输出诊断信息（E001），不静默返回 None
2. **profile 硬门禁** — 普通生成、`--check`、`--dump-ir`、`--explain`、promotion 分析都先通过 profile gate；有 ERROR 直接阻断
3. **Case IR planner** — 结合 ParseResult + `aitest.yaml` + runtime profile 生成可解释的生成计划
   - 策略优先级：`skipped > custom_case_body > structured_case_flow > manual > default_grpc > default_http`
   - 每个决策记录 source_trace（来自 Markdown / `aitest.yaml` / profile 的哪个字段）
4. **emitter/IR renderer 生成** — 确定性生成 .py
   - 断言匹配优先级：profile assertion_rules > `aitest.yaml` builtin_assertion_rules > named_templates
   - module_type 校验：module.yaml/profile 声明的模块类型必须满足 `aitest.yaml` 中该类型的 requires 字段
5. **生成后验证** — `ast.parse` + `pytest --collect-only`
6. **AI 补写 UNPARSED** — emitter 输出的 `# UNPARSED ASSERTION:` 由 AI 翻译为可执行断言（UNPARSED 为 0 时跳过）
7. **端到端验证** — `aitest run --suite-file <suite.yaml>`
8. **经验沉淀** — 调试经验写入 profile，调用 `/emitter-build` 提取新规则

### codegen CLI 常用命令

```bash
# 日常收口顺序
aitest codegen --suite-file <suite.yaml> --validate-profile
aitest codegen --suite-file <suite.yaml> --dump-ir
aitest codegen --suite-file <suite.yaml> --check
aitest codegen --suite-file <suite.yaml>
aitest run --suite-file <suite.yaml> -- --collect-only -q

# 生成（含 profile 硬门禁）
aitest codegen --suite-file <suite.yaml>

# 一致性校验（generated 是否与 Markdown/profile 同步）
aitest codegen --suite-file <suite.yaml> --check

# Case IR 观测
aitest codegen --suite-file <suite.yaml> --dump-ir
aitest codegen --suite-file <suite.yaml> --explain TC-CAL-001

# profile 体检
aitest codegen --suite-file <suite.yaml> --validate-profile --write-report

# 健康报告（成熟度、strategy/assertion 统计）
aitest codegen --suite-file <suite.yaml> --health-report --write-report

# 晋升分析
aitest codegen --suite-file <suite.yaml> --analyze-promotion --write-report
aitest codegen --suite-file <suite.yaml> --suggest-promotion-patch
```

### 使用指引

- **首次接入新项目**：`aitest init --target <project_dir>` → `/doc-review` → `/doc-gen`（按需）→ `/knowledge-build` → `/test-design` → `/test-scaffold` → `/test-codegen`
- **需求迭代**：新文档放入 `docs/` → `/knowledge-build`（增量更新）→ `/test-design`（增量生成）
- **新模块缺 fixture/profile**：`/test-scaffold`（构建 target/module fixture + module profile，再接 suite profile）
- **用例出错**：`/test-fix`（修用例 + 记 TEST_SPEC 陷阱 + 更新 skill）
- **生成 pytest**：`/test-codegen --suite-file <suite.yaml>`
- **执行并报告**：`aitest run --suite-file <suite.yaml>`，默认排除 manual；需要时加 `--include-manual`
- **只想看文档质量**：`/doc-review`

### 关键约定

- 测试知识库是用例设计的唯一输入源，不绕过知识库直接写用例
- Markdown 用例是唯一数据源，test-codegen 生成 pytest 代码执行
- TEST_SPEC 是所有 skill 的行为准则，经验教训统一沉淀在此
- 用例存放在 suite 目录，用 `suite.yaml` 绑定 target/module
- 模块 fixture 按 target/module 拆分到 `test_workspace/targets/{target}/fixtures/{module}.py`
- module profile 存放在 `test_workspace/targets/{target}/profiles/profile_{module}.md`；suite profile 跟随用例目录，命名为 `profile_{suite}_suite.md`
- 测试执行报告写入 `test_workspace/reports/`，属于运行产物，不提交；待测系统 bug 仍记录到 `test_workspace/results/`
- 项目结构或流程发生变更时，检查是否需要同步更新 `CLAUDE.md` 和 `README.md`，并询问用户是否需要更新 `docs/usebook/` 下的文档

### test-report 流程细节

1. **freshness check** — `aitest run` 默认先检查 generated pytest 是否与 Markdown/profile 一致；失败时生成 `BLOCKED_RUN` 报告并停止。
2. **pytest 执行** — 默认追加 `-m "not manual"`；`--include-manual` 才执行 manual 用例。
3. **metadata join** — generated pytest 中的 `__tc_meta__` 连接 JUnit XML 结果；`__codegen_skipped__` 记录未生成 pytest 函数的可行性存疑用例。
4. **结果落盘** — 输出 `junit.xml`、`result.json`、`report.md` 到 `test_workspace/reports/runs/{run_id}/`，并同步到 `latest/`。
5. **反哺清单** — 报告按环境、fixture/codegen、断言失败、未知问题生成下一步处理建议。

## 测试执行注意事项

### 部署拓扑先行

设计 fixture 前必须确认服务的实际部署模式：
- 确认 `AB_SERVICE_URL`、`REDIS_URL`、`HTTP_BASE_URL` 等环境变量的实际值
- 确认服务间调用关系（本地 SDK vs 远程服务）
- 优先用运行时 API 操作（如 AB 白名单 CRUD），而非启动时环境变量注入

### httpx 系统代理

httpx 0.28+ 会自动读取 macOS 系统代理，`proxy=None` 无效。测试 helper 中必须用显式 transport：
```python
httpx.Client(transport=httpx.HTTPTransport())
```

### 测试角色边界

AI 的角色是测试工程师，不是被测系统的开发者：
- `coupon_system/`、`ab_experiment_sdk/` 下的源码和配置文件不得修改
- 只改测试资产、测试工具和协作流程：`test_workspace/`、`aitest_kit/`、`aitest_config/`、`.claude/skills/`、`.codex/skills/`、`.agents/skills/`
- 通过被测系统已有的 API、环境变量、磁盘数据文件来构造测试条件
- 现有接口无法满足测试需求时，记录为"测试基础设施需求"让用户决定

## codegen 可移植架构

codegen 管线分三层，换项目时只改配置层，不改框架层：

```
┌─────────────────────────────────────────────────────┐
│  框架层（换项目不改）                                  │
│  - parser engine (parser.py)                        │
│  - Case IR planner (planner.py, ir.py)              │
│  - IR renderer (ir_renderer.py)                     │
│  - emitter orchestrator (emitter.py)                │
│  - CLI (cli.py)                                     │
│  - profile validator (profile_validator.py)         │
│  - promotion analyzer (promotion.py)               │
│  - health reporter (health.py)                     │
│  - 通用 helpers (http.py, redis_ops.py)              │
│  - skill 框架模板 (SKILL.md)                         │
│  - JSON Schema (codegen_profile.schema.json)        │
├─────────────────────────────────────────────────────┤
│  项目配置层（换项目重写，YAML 格式）                    │
│  - aitest_config/aitest.yaml                        │
│  - target/module registry                           │
│  - grpc_ops.py（项目专属 protobuf 封装）              │
├─────────────────────────────────────────────────────┤
│  模块配置层（每模块一份）                              │
│  - profile_{module}.md                              │
│  - targets/{target}/fixtures/{module}.py            │
├─────────────────────────────────────────────────────┤
│  用例批次层（按 L2/迭代批次，可选）                    │
│  - suite.yaml                                       │
│  - profile_{suite}_suite.md                         │
└─────────────────────────────────────────────────────┘
```

### 首次接入新项目的 codegen 配置

1. 先执行 `aitest init --target <project_dir>` 创建独立 workspace，不直接复用本仓 `test_workspace/`
2. 修改 `<project_dir>/aitest_config/aitest.yaml`：声明 workspace 路径、codegen 默认规则和 module_type 集合
3. 每个 target 创建 `target.yaml`，每个模块创建 `modules/{module}.yaml`
4. 每个模块创建 `profile_{module}.md`：声明 module_type、assertion_rules、request_overrides 等
5. 每个模块创建 `fixtures/{module}.py`：实现 setup/teardown 逻辑

workspace 模板只有一个来源：`aitest_kit/templates/project_workspace/`。模板同时初始化 `AGENTS.md`、`CLAUDE.md` 和 `.codex/.claude/.agents` 三套 skills；不要维护顶层 `templates/project_workspace/` 镜像。

### module_type 分类

codegen_profile 头部必须声明 module_type，emitter 根据类型校验必需字段：

| module_type | 适用场景 | 必需字段 |
|-------------|---------|---------|
| `standard_recommend` | 标准推荐接口模块 | 无额外要求 |
| `multi_endpoint` | 多端点服务模块 | case_bodies 或 case_flows |
| `subprocess_capture` | 需要隔离进程捕获输出 | case_bodies 或 case_flows |
| `isolated_service` | 需要隔离服务实例 | case_bodies 或 case_flows |

### 四条生成路线

| 路线 | profile 配置 | 适用场景 |
|------|-------------|---------|
| 默认模板 | `request_overrides` | 标准推荐接口，只需覆盖请求字段 |
| 断言规则 | `assertion_rules` | 标准接口但断言需要模板化（如分段校准） |
| `case_flows` | `case_flows` YAML | 稳定多步骤流程（调用 → 保存 → 断言） |
| `case_bodies` | `case_bodies` 原始代码 | 复杂场景逃生通道（并发、进程、mock、文件） |

晋升方向：case_bodies → case_flows → assertion_rules / 默认模板。同一 case_id 不允许同时出现在 `case_bodies` 和 `case_flows`。

### 诊断分层

| 代码 | 层 | 含义 |
|------|----|------|
| E001 | parser | Markdown JSON 解析失败 |
| E002 | emitter | 缺少基础请求体且未被 profile 覆盖 |
| E003-E004 | emitter | module_type 校验失败 |
| E201-E203 | planner | 策略/请求体/断言解析问题 |
| E301 | renderer | IR 渲染不支持 |
| E501-E511 | profile validator | profile 结构/引用/格式问题 |

### Markdown 用例格式规范

Markdown 用例的共享配置格式是框架标准，所有项目统一使用以下 section 名（不可自定义）：

```markdown
## 共享配置
**接口**：`POST /api/v1/xxx`
**基础请求体（HTTP）**：
```json
{合法 JSON，不允许 {{var}} 占位符}
```
**基础请求体（gRPC）**：
```text
{protobuf 文本格式}
```
**标准前置**：
- 前置条件列表
**通用断言**：`response.code == 0`
**变量定义**：
- `var_name` = 定义
```

**关键规则**：
- `json` 代码块必须是严格合法 JSON，`json.loads` 必须能解析
- 变化字段用合法默认值填充（如 `"external": 0`），case 级差异通过 codegen_profile 的 request_overrides 声明
- 禁止 `{{var}}` 模板占位符出现在 JSON 块中

### 待测系统 bug 记录

测试发现的待测系统 bug 记录到 `test_workspace/results/`，不跳过、不放宽断言、不伪造成功响应。等待系统修复后重新执行验证。
