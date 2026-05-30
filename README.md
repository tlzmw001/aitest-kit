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

推荐创建一个独立的 AITest workspace。它可以放在目标项目下，也可以单独建一个测试仓库；对接多个服务时，更推荐单独维护测试项目。

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
skills/                # agent-neutral AI skills，按需复制到 .codex/.claude/.agents
AGENTS.md / CLAUDE.md  # AI 协作说明
```

配置文件的完整写法见 `aitest_config/refs/config-files.md`。新建 target、module、suite、profile 或 task 时，优先按这份手册判断字段归属。

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
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

常用执行维度也可以直接走 registry：

```bash
aitest codegen --target <target> --module <module> --check
aitest run --target <target> --module <module>
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --case-id TC-XXX-001
aitest run --target <target>
aitest run --all
```

多个 suite 组成一次回归任务时，用 task 文件编排：

```bash
aitest codegen --task-file test_workspace/tasks/<task>.yaml --check
aitest run --task-file test_workspace/tasks/<task>.yaml
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
test_workspace/suites/{target}/{suite}/suite.yaml
test_workspace/suites/{target}/{suite}/business.md
test_workspace/suites/{target}/{suite}/profile_{suite}_suite.md
```

用例由 `/test-design` 生成或修订，人工 review 后进入 codegen。

### 3. Fixture 和 profile

fixture 是测试动作库，profile 是 codegen 配置。

```text
test_workspace/targets/{target}/target.yaml
test_workspace/targets/{target}/modules/{module}.yaml
test_workspace/targets/{target}/fixtures/{module}.py
test_workspace/targets/{target}/helpers/
test_workspace/targets/{target}/profiles/profile_{module}.md
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

配置边界：`profile_{module}.md` 只放 L1 级稳定能力；`profile_{suite}_suite.md` 放具体 TC-ID 绑定的 `variables.cases/case_flows/case_bodies/request_overrides/case_fixtures`。详细示例见 `aitest_config/refs/config-files.md`。

### 4. Codegen

日常门禁顺序：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

codegen 模式说明：

| 命令 | 是否需要 profile gate | 是否写 generated | 用途 |
|---|---:|---:|---|
| `--dry-run` | 否 | 否 | 只解析 Markdown，用于 scaffold/profile 完成前检查用例格式 |
| `--validate-profile` | 自身就是校验 | 否 | 校验 profile JSON Schema、case_id 对齐、case_flow/case_body 语义 |
| `--check` | 是 | 否 | 临时重新生成到 tmpdir，与已有 generated pytest 做 diff |
| `--dump-ir` | 是 | 否 | 输出 suite 的 Case IR JSON，定位 strategy、fixture、request、assertion 来源 |
| `--explain <TC-ID>` | 是 | 否 | 输出单条 case 的 IR 解释 |
| `--health-report` | 是 | 否，除非加 `--write-report` | 输出 codegen 健康度、成熟度和待沉淀信号 |
| `--analyze-promotion` | 是 | 否，除非加 `--write-report` | 分析当前 suite profile 中 `case_bodies` 的晋升机会 |
| 无特殊参数 | 是 | 是 | 正式生成 pytest |

诊断入口的粒度不同：`--dump-ir`、`--explain` 只支持 `--suite-file`，用于精确排查单个 suite 或单条 case；`--health-report`、`--analyze-promotion` 支持 `--suite-file`、`--target <target> --module <module>` 和 `--target <target>`，用于聚合查看模块或目标系统的生成健康度和晋升候选。`--suggest-promotion-patch` 仍只支持 `--suite-file`，避免批量生成难以 review 的 patch 草案。

可以按不同粒度执行：

```bash
# 一个 suite
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check

# 一个 suite 中的单个 case（run/report 支持；codegen 仍以 suite 为生成单位）
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --case-id TC-XXX-001

# 一个模块下注册的 active suites
aitest codegen --target <target> --module <module> --check
aitest run --target <target> --module <module>
aitest report --target <target> --module <module>

# 一个 target 下全部 active suites
aitest codegen --target <target> --check
aitest run --target <target>
aitest report --target <target>

# registry 中全部 active suites
aitest codegen --all --check
aitest run --all
aitest report --all
```

从 workspace 外部执行时加：

```bash
--workspace /path/to/aitest_workspace
```

suite 可以直接通过 `--suite-file` 运行；只有注册到 `module.yaml.registered_suites`
后，才会进入 `--module`、`--target`、`--all` 聚合入口。注册使用：

```bash
aitest registry register-suite \
  --target <target> \
  --module <module> \
  --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

如果手写 `module.yaml`，`registered_suites` 推荐使用 suite manifest 路径简写：

```yaml
registered_suites:
  - test_workspace/suites/<target>/<suite>/suite.yaml
```

需要声明非 active 状态时再使用完整格式：

```yaml
registered_suites:
  - suite: <suite>
    manifest: test_workspace/suites/<target>/<suite>/suite.yaml
    status: paused
```

如果要创建一个显式任务清单：

```bash
aitest task create \
  --name nightly_gateway \
  --suite-file test_workspace/suites/<target>/<suite1>/suite.yaml \
  --suite-file test_workspace/suites/<target>/<suite2>/suite.yaml
```

### 5. 执行和报告

```bash
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest report --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

`aitest run` 会先检查 generated pytest 是否过期。如果 Markdown/profile 和 generated pytest 不一致，会生成 `BLOCKED_RUN` 报告并停止，避免执行旧代码。

报告输出：

```text
test_workspace/reports/<target>/<module>/suites/<suite>/latest/
test_workspace/reports/<target>/<module>/cases/<case_id>/latest/
test_workspace/reports/<target>/<module>/module/latest/
test_workspace/reports/<target>/target/latest/
test_workspace/reports/tasks/<task_name>/latest/
```

每个报告 bucket 都保留 `runs/{run_id}/` 历史记录和 `latest/` 最近一次结果。task、target、module 等聚合执行会把 suite 明细放到同一个 run_id 下的 `units/` 目录，避免一次命令产生多个难以关联的顶层 run_id。

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
| `aitest registry register-suite --target <target> --module <module> --suite-file <suite.yaml>` | 把 suite 安全注册到 module 聚合入口 |
| `aitest task create --name <task> --suite-file <suite.yaml>...` | 从明确 suite 清单创建 task manifest |
| `aitest codegen --suite-file <suite.yaml>` | 生成 target-aware case suite pytest |
| `aitest codegen --task-file <task.yaml>` | 按 task 中的 suite 列表生成或检查 pytest |
| `aitest codegen --target <target> [--module <module>]` | 按 target 或 target/module registry 生成或检查 pytest |
| `aitest codegen --all` | 遍历 registry 中全部 active suites |
| `aitest run --suite-file <suite.yaml>` | 执行一个 suite 并生成结构化报告 |
| `aitest run --suite-file <suite.yaml> --case-id <TC-ID>` | 只执行一个 suite 中指定 case |
| `aitest run --task-file <task.yaml>` | 执行一个 task 并生成 task 级汇总报告 |
| `aitest run --target <target> [--module <module>]` | 执行 target 或 target/module 下注册的 active suites |
| `aitest run --all` | 执行 registry 中全部 active suites |
| `aitest report --suite-file/--task-file/--target/--all ...` | 从已有 `result.json` 重新渲染对应维度报告 |

运行真实接口测试时，可以通过 env 文件提供服务地址、账号、token 和 API key：

```bash
AITEST_ENV_FILE=/tmp/your-system-test.env aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

`aitest run` 会把 env 文件注入 pytest 子进程；报告只记录变量名，不记录变量值。真实 shell 环境变量优先于 env 文件。

## AI Skills 速查

AITest workspace 会内置一份 agent-neutral 的 `skills/` 目录。根据当前 AI 编程环境复制到对应目录：

```bash
# Codex
mkdir -p .codex/skills && cp -R skills/. .codex/skills/

# Claude Code
mkdir -p .claude/skills && cp -R skills/. .claude/skills/

# agents workflow
mkdir -p .agents/skills && cp -R skills/. .agents/skills/
```

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
│   ├── aitest.yaml               # 推荐统一入口：workspace 路径 + codegen 默认规则
│   ├── schemas/                  # profile JSON Schema
│   └── refs/                     # 用例格式、断言策略等参考
├── test_workspace/
│   ├── knowledge/                # L0/L1/L2 + TEST_SPEC
│   ├── suites/                   # 按 target/suite 组织 Markdown 用例
│   ├── targets/                  # target/module fixture、helper、profile
│   ├── generated/                # 按 target 分桶的 generated pytest
│   ├── reports/                  # 运行报告
│   └── results/                  # 已确认待测系统 bug 记录
├── skills/                       # agent-neutral AITest skills
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

v0.2.x 稳定维护：

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
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --check
python3 -m aitest_kit.cli codegen --target coupon_system --module calibration --check
python3 -m aitest_kit.cli run --target coupon_system --module calibration -- --collect-only -q
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
