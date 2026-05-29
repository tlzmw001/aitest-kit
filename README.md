# aitest-kit

> 把开发文档、API 契约和 AI 设计出来的测试想法，沉淀成可审查、可重复生成、可运行报告的自动化测试资产。

[English](README.en.md)

[![PyPI version](https://img.shields.io/pypi/v/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aitest-kit.svg?style=flat-square)](https://pypi.org/project/aitest-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://github.com/tlzmw001/aitest-kit/blob/main/LICENSE)

AITest Kit 是一套 AI 辅助的自动化测试工具链，适合把一个新的后端服务、API 网关、业务系统或已有测试项目逐步接入自动化测试。

它的核心原则很简单：

```text
AI 负责探索未知，代码负责稳定重复。
```

AI 用来读文档、理解新系统、设计初版用例、判断失败原因和沉淀规则；`aitest-kit` 用代码负责 Markdown 解析、profile 校验、Case IR 规划、pytest 生成、freshness check、测试执行和报告输出。

## 3 分钟上手

### 1. 安装

```bash
python3 -m pip install -U aitest-kit
```

如果安装后找不到 `aitest` 命令，可以先用模块入口：

```bash
python3 -m aitest_kit.cli --help
```

### 2. 初始化一个测试工作区

推荐把 AITest workspace 放在目标项目下的独立目录：

```bash
cd /path/to/your_project
aitest init --target ./aitest_workspace
cd ./aitest_workspace
```

初始化后会得到：

```text
docs/                 # 放公开 API 文档、设计文档、OpenAPI/proto 等
aitest_config/         # 项目配置、codegen 配置、schema
test_workspace/        # 知识库、Markdown 用例、fixture、profile、generated pytest、报告
.codex/.claude/.agents # AI skills
AGENTS.md / CLAUDE.md  # AI 协作说明
```

### 3. 体检

```bash
aitest doctor
```

刚初始化时没有模块是正常的。下一步把目标系统的公开文档放到 `docs/`，然后让 AI 按 workspace 内的 skills 走完整流程：

```text
doc-review -> knowledge-build -> test-design -> test-scaffold -> test-codegen -> aitest run
```

如果你已经有 Markdown 用例和 profile，可以直接跑：

```bash
aitest codegen --all --validate-profile
aitest codegen --all
aitest codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

## 适合解决什么问题

- 新项目没有自动化测试，但有开发文档、API 文档或接口定义。
- 你希望 AI 帮忙设计测试，但不希望每次都重新生成一堆不可维护的 pytest。
- 你想把测试设计、测试代码和执行报告分开管理。
- 你需要把失败先分流成文档问题、用例问题、fixture/profile 问题、环境问题、codegen 问题或待测系统 bug。
- 你希望一个项目越测越稳定：初期 AI 多探索，后期规则和代码多沉淀。

不适合：

- 只想一次性生成临时 pytest，不关心后续维护。
- 没有可执行接口，也没有可观测结果。
- 希望工具自动创建生产账号、真实 token、付费 API key 或高风险测试资源。

## 完整工作流

AITest Kit 的主路径是一条测试飞轮：

```text
公开文档 / API 契约
  -> 测试知识库 L0/L1/L2
  -> Markdown 测试用例
  -> fixture + codegen profile
  -> Case IR
  -> generated pytest
  -> aitest run / report
  -> 失败修正与规则沉淀
```

### 1. 文档和知识库

把公开文档放入 `docs/`：

```text
docs/public_api.md
docs/openapi.yaml
docs/protos/
docs/config_schema.md
```

使用 AI skills 构建测试知识库：

```text
/doc-review       检查文档缺口
/doc-gen          必要时从源码补测试设计文档
/knowledge-build  生成 L0 系统索引、L1 模块契约、L2 需求变更
```

知识库是测试设计的主输入。文档没写清楚的行为标 `[?]`，不要猜。

### 2. Markdown 用例

用例是人类可 review 的测试设计源文件：

```text
test_workspace/cases/{module}/business.md
test_workspace/cases/{module}/boundary.md
```

也可以按需求批次组织独立 suite：

```text
test_workspace/casesuites/{suite}/aitest_suite.yaml
test_workspace/casesuites/{suite}/business.md
test_workspace/casesuites/{suite}/codegen_profile_{suite}_suite.md
```

用例由 `/test-design` 生成或修订，人工 review 后进入 codegen。

### 3. Fixture 和 profile

fixture 是测试动作库，profile 是 codegen 配置。

```text
test_workspace/tests/fixtures/{module}.py
test_workspace/tests/fixtures/codegen_profile_{module}.md
```

fixture 负责：

- 读取服务地址、token 等运行时输入。
- 调用公开 HTTP/gRPC API。
- 准备和清理测试状态。
- 封装可复用的 client/action 方法。

profile 负责：

- 声明 `module_type`。
- 配置 `request_overrides`、`variables`、`assertion_rules`。
- 用 `case_flows` 描述稳定多步骤流程。
- 用 `case_bodies` 保留复杂逃生通道。

### 4. Codegen

日常门禁顺序：

```bash
aitest codegen --all --validate-profile
aitest codegen --all --dump-ir
aitest codegen --all
aitest codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

常用单模块命令：

```bash
aitest codegen <module> --validate-profile
aitest codegen <module> --dump-ir
aitest codegen <module> --explain TC-XXX-001
aitest codegen <module>
aitest codegen <module> --check
```

从 workspace 外部执行时加：

```bash
--workspace /path/to/aitest_workspace
```

### 5. 执行和报告

```bash
aitest run <module>
aitest report
```

`aitest run` 会先检查 generated pytest 是否过期。如果 Markdown/profile 和 generated pytest 不一致，会生成 `BLOCKED_RUN` 报告并停止，避免执行旧代码。

报告输出：

```text
test_workspace/reports/latest/
test_workspace/reports/runs/{run_id}/
```

核心文件：

- `junit.xml`
- `result.json`
- `report.md`

## CLI 命令速查

| 命令 | 作用 |
|---|---|
| `aitest init --target <dir>` | 初始化干净 workspace |
| `aitest upgrade --workspace <dir> --check` | 检查已初始化 workspace 是否需要同步新版模板 |
| `aitest upgrade --workspace <dir> --apply` | 安全应用可自动合并的模板升级 |
| `aitest doctor` | 检查 workspace、profile、generated、collect 和环境变量提示 |
| `aitest codegen <module>` | 生成单个模块 pytest |
| `aitest codegen --all` | 生成所有模块 pytest |
| `aitest codegen --cases <suite_dir>` | 生成独立 case suite pytest |
| `aitest codegen --all --check` | 检查 generated 是否过期 |
| `aitest run <module>` | 执行 generated pytest 并生成结构化报告 |
| `aitest report` | 从已有 `result.json` 重新渲染报告 |

运行真实接口测试时，可以通过 env 文件提供服务地址、账号、token 和 API key：

```bash
AITEST_ENV_FILE=/tmp/your-system-test.env aitest run <module>
```

`aitest run` 会把 env 文件注入 pytest 子进程；报告只记录变量名，不记录变量值。真实 shell 环境变量优先于 env 文件。

## AI Skills 速查

AITest workspace 会内置 `.codex`、`.claude`、`.agents` 三套 skills，适配不同 AI 编程环境。

| Skill | 什么时候用 |
|---|---|
| `doc-review` | 检查开发文档是否足够生成测试 |
| `doc-gen` | 从源码或现有文档补测试设计输入 |
| `knowledge-build` | 构建/更新 L0/L1/L2 测试知识库 |
| `test-design` | 从知识库生成 Markdown 用例 |
| `test-scaffold` | 为新模块或新 suite 补 fixture/profile |
| `test-codegen` | 从 Markdown/profile 生成 pytest 并验证 |
| `test-fix` | 修正错误用例并沉淀经验 |
| `emitter-build` | 从已验证测试中提取可沉淀规则 |

判断入口：

| 场景 | 用哪个 |
|---|---|
| 新项目第一次接入 | `doc-review -> knowledge-build -> test-design -> test-scaffold -> test-codegen` |
| 新增模块 | `test-scaffold` |
| 现有模块新增用例，已有 fixture/action 足够 | `test-codegen` |
| 新增用例时发现 fixture 缺动作 | 回到 `test-scaffold` 增量补 fixture/profile |
| 测试失败但不知道归因 | `aitest run` 看报告，再用 `test-fix` 或修 fixture/profile |

## Codegen 路线

| 路线 | profile 配置 | 适用场景 |
|---|---|---|
| 默认 HTTP/gRPC | `request_overrides` | 单接口、请求结构稳定 |
| 断言规则 | `assertion_rules` | 调用流程标准，但断言需要模板化 |
| 结构化流程 | `case_flows` | 线性多步骤：call / assign / assert / comment |
| 自定义代码 | `case_bodies` | 并发、mock、进程、文件生命周期等复杂场景 |

推荐演进方向：

```text
case_bodies -> case_flows -> assertion_rules / 默认模板
```

## Workspace 结构

```text
aitest_workspace/
├── docs/                         # 公开文档和迁移输入
├── aitest_config/
│   ├── config.yaml               # 项目路径、服务、协议等配置
│   ├── project_config.yaml       # codegen 项目配置
│   ├── schemas/                  # profile JSON Schema
│   └── refs/                     # 用例格式、断言策略等参考
├── test_workspace/
│   ├── knowledge/                # L0/L1/L2 + TEST_SPEC
│   ├── cases/                    # 模块级 Markdown 用例
│   ├── casesuites/               # 可选：按需求/迭代组织的 suite
│   ├── tests/
│   │   ├── fixtures/             # fixture + codegen profile
│   │   ├── generated/            # 生成的 pytest，视为编译产物
│   │   └── helpers/              # HTTP/gRPC/Redis helpers
│   ├── reports/                  # 运行报告
│   └── results/                  # 已确认待测系统 bug 记录
├── .codex/skills/
├── .claude/skills/
├── .agents/skills/
├── AGENTS.md
└── CLAUDE.md
```

## 安全与隐私

- 不要提交 `.env`、token、密码、生产账号或真实用户数据。
- profile 的 `variables.env` 只写环境变量名，不写值。
- `.env` 只作为本地运行输入；报告和错误信息只显示变量名。
- `test_workspace/reports/` 可能包含请求、响应、错误详情；对外共享前需要脱敏。
- AITest Kit 不自动创建账号、充值、生成真实 API key 或调用高风险付费资源。

## 当前稳定边界

v0.1.x 稳定维护：

- `aitest init/codegen/run/report/doctor/upgrade`
- workspace layout
- Markdown 用例格式
- module/suite profile schema
- Case IR -> pytest 主链路
- freshness check
- 结构化报告格式

仍在演进：

- health/promotion report 口径
- `case_flows` step 词汇表
- 内部 Python API
- 未来前端、契约测试、更多 emitter 类型

## 开发本仓

```bash
git clone https://github.com/tlzmw001/aitest-kit.git
cd aitest-kit
python3 -m pip install -e ".[dev,server]"

python3 -m pytest tests -q
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli doctor
```

本仓内置 `coupon_system/` 作为真实回归资产，用来验证 codegen、报告、fixture/profile 和迁移能力。

## 文档

- [Quickstart](docs/usebook/aitest_quickstart.md) — 跑通最小闭环
- [Migration Guide](docs/usebook/aitest_migration_guide.md) — 新项目迁移指南
- [Workflow Guide](docs/usebook/aitest_workflow_guide.md) — 长期协作模型、skill 分工和测试资产维护路线
- [Profile Guide](docs/usebook/codegen_profile_guide.md) — 编写 module/suite profile
- [Troubleshooting](docs/usebook/codegen_troubleshooting.md) — codegen 常见问题
- [Coupon System Full Example](docs/usebook/coupon_system_full_example.md) — 本仓回归资产示例
- [Roadmap](ROADMAP.md) — 当前边界和演进方向
- [Contributing](CONTRIBUTING.md) — 贡献指南
- [CHANGELOG](CHANGELOG.md) — 版本变更记录

## License

[MIT](./LICENSE)
