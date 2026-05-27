# AITest Workspace

这是一个目标系统的 AITest 测试工作区。它不是业务源码目录的一部分，而是用于管理测试知识库、Markdown 用例、fixture/profile、generated pytest 和测试报告的独立 workspace。

核心流程：

```text
docs -> knowledge -> cases -> fixture/profile -> generated pytest -> report
```

## 3 分钟开始

### 1. 体检

```bash
aitest doctor
```

刚初始化时没有模块是正常的。下一步需要把目标系统文档放进 `docs/`，再让 AI 生成知识库、用例和脚手架。

### 2. 放入目标系统文档

建议至少提供一份公开行为文档，例如：

```text
docs/public_api.md
docs/openapi.yaml
docs/protos/
docs/config_schema.md
```

第一轮只选择一个小模块或一条主链路，不要一开始覆盖整个系统。

### 3. 让 AI 生成测试资产

在本目录下启动 AI 编程工具，然后可以这样提问：

```text
请基于 docs/ 下的公开 API 文档，先用 doc-review 检查文档缺口；
如果足够，再用 knowledge-build 构建测试知识库；
然后为 <模块名> 设计 Markdown 用例；
最后用 test-scaffold 生成 fixture 和 codegen profile。
```

生成后再执行：

```bash
aitest codegen <module> --validate-profile
aitest codegen <module> --dump-ir
aitest codegen <module>
aitest codegen <module> --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

运行测试：

```bash
aitest run <module>
```

## 目录结构

```text
docs/                         # 公开 API 文档、设计文档、OpenAPI/proto 等
aitest_config/                 # 项目配置、codegen 配置、schema、refs
test_workspace/
  knowledge/                   # L0/L1/L2 + TEST_SPEC
  cases/                       # 模块级 Markdown 用例
  casesuites/                  # 可选：按 L2/迭代组织的独立 suite
  tests/
    fixtures/                  # fixture 动作库 + module profile
    generated/                 # codegen 生成的 pytest
    helpers/                   # HTTP/gRPC/Redis helpers
  reports/                     # aitest run 生成的报告
  results/                     # 已确认待测系统 bug 记录
.codex/skills/                 # Codex skills
.claude/skills/                # Claude Code skills
.agents/skills/                # agents workflow skills
AGENTS.md / CLAUDE.md          # AI 协作说明
```

## 关键产物

| 产物 | 说明 |
|---|---|
| `docs/` | 测试规则来源，优先放公开 API/设计文档 |
| `test_workspace/knowledge/` | 测试知识库，记录当前系统可测试契约 |
| `test_workspace/cases/` | Markdown 用例，是测试设计源文件 |
| `test_workspace/casesuites/` | 可选，用于需求、迭代、临时批次 |
| `test_workspace/tests/fixtures/{module}.py` | 模块 fixture，封装公开 API 调用和测试动作 |
| `test_workspace/tests/fixtures/codegen_profile_{module}.md` | 模块 profile，配置稳定生成规则 |
| `codegen_profile_{suite}_suite.md` | suite profile，跟随某批用例 |
| `test_workspace/tests/generated/` | generated pytest，视为编译产物 |
| `test_workspace/reports/` | 执行报告 |
| `test_workspace/results/` | 已确认的待测系统 bug |

## 什么时候用哪个 skill

| 场景 | 推荐入口 |
|---|---|
| 文档是否足够做测试不确定 | `doc-review` |
| 需要建立或更新测试知识库 | `knowledge-build` |
| 需要生成 Markdown 用例 | `test-design` |
| 新模块缺 fixture/profile | `test-scaffold` |
| 现有模块新增用例且 fixture 足够 | `test-codegen` |
| 测试失败需要分流 | `aitest run` + `test-fix` |
| 稳定模式需要沉淀 | `emitter-build` |

## 模块和 suite

模块级用例放在：

```text
test_workspace/cases/<module>/business.md
test_workspace/cases/<module>/boundary.md
test_workspace/tests/fixtures/<module>.py
test_workspace/tests/fixtures/codegen_profile_<module>.md
```

suite 用例适合按 L2 需求、迭代或临时批次组织：

```text
test_workspace/casesuites/<suite>/aitest_suite.yaml
test_workspace/casesuites/<suite>/business.md
test_workspace/casesuites/<suite>/codegen_profile_<suite>_suite.md
```

suite profile 跟随用例目录，module profile 保留模块级稳定能力。

## 常用命令

```bash
aitest doctor

aitest codegen --all --validate-profile
aitest codegen --all --dump-ir
aitest codegen --all
aitest codegen --all --check

aitest codegen --cases test_workspace/casesuites/<suite> --validate-profile
aitest codegen --cases test_workspace/casesuites/<suite>

aitest run <module>
aitest report
```

运行真实接口测试时，可以通过本地不提交的 env 文件提供服务地址、账号、token 和 API key：

```bash
AITEST_ENV_FILE=/tmp/your-system-test.env aitest run <module>
```

`aitest run` 会把 env 文件注入 pytest 子进程；报告只记录变量名，不记录变量值。真实 shell 环境变量优先于 env 文件。

从本目录外执行时，追加：

```bash
--workspace /path/to/aitest_workspace
```

## 升级 workspace

```bash
python3 -m pip install -U aitest-kit
aitest upgrade --workspace /path/to/aitest_workspace --check
aitest upgrade --workspace /path/to/aitest_workspace --apply
```

`pip install -U` 只更新 CLI 和 Python 包。`aitest upgrade` 用来同步通过 `aitest init` 复制到本 workspace 的模板资产，例如 skills、schema、refs、helpers 和说明文档。

不要用 `aitest init --force` 升级已有 workspace。

## 信息源边界

新项目迁移默认以公开设计文档、API 定义、配置 schema、示例请求/响应和可执行 API 行为作为规则来源。

不要从目标系统源码、已有测试或内部实现文档推断业务规则，除非项目明确切换到已文档化的灰盒阶段。

## 安全注意事项

- 不要提交 `.env`、服务凭证、访问 token、生产账号或真实用户数据。
- 服务地址、账号、token 和 API key 通过环境变量或本地不提交配置传入 fixture。
- profile 的 `variables.env` 只写环境变量名，不写变量值。
- `test_workspace/reports/` 可能包含请求、响应和错误详情；对外共享前需要脱敏。
- AITest Kit 不自动创建账号、充值、生成真实 API key 或调用高风险付费资源。

## 稳定性说明

v0.1.x 稳定维护：

- `aitest init/codegen/run/report/doctor/upgrade`
- workspace 目录结构
- Markdown 用例格式
- module/suite profile schema
- Case IR 到 pytest 的主链路
- generated freshness check
- 结构化报告格式

仍在演进：

- health/promotion report 口径
- `case_flows` step 词汇表
- 内部 Python API
- 未来前端、契约测试和更多 emitter 类型
