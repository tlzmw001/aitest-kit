# AITest Quickstart

本文面向第一次把 `aitest-kit` 接入新项目的用户。目标是 3 分钟内完成安装、初始化和第一轮体检，并知道接下来该让 AI 做什么。

核心心智模型：

```text
公开文档 -> 知识库 -> Markdown 用例 suite -> target fixture/profile -> generated pytest -> report
```

`aitest-kit` 不要求你一开始就写完所有自动化。正确做法是：先接入一个最小模块，跑通闭环，再逐步扩展。

## 1. 安装

```bash
python3 -m pip install -U aitest-kit
```

如果安装后找不到 `aitest` 命令，通常是 Python 脚本目录不在 `PATH`。可以先用模块入口验证：

```bash
python3 -m aitest_kit.cli --help
```

## 2. 初始化 workspace

推荐创建一个独立的 AITest workspace。它可以放在目标项目下，也可以是单独的测试仓库：

```bash
cd /path/to/your_project
aitest init --target ./aitest_workspace
cd ./aitest_workspace
```

初始化后会生成：

```text
docs/                  # 放公开 API 文档、设计文档、OpenAPI/proto 等
aitest_config/          # 项目配置、codegen 配置、schema、refs
test_workspace/         # 知识库、用例、fixture、profile、generated、报告
.codex/.claude/.agents  # AI skills
AGENTS.md / CLAUDE.md   # AI 协作说明
```

从 workspace 外执行 CLI 时，加 `--workspace`：

```bash
aitest doctor --workspace /path/to/your_project/aitest_workspace
```

## 3. 第一轮体检

```bash
aitest doctor
```

刚初始化时没有模块是正常的。你会看到类似提示：

```text
No modules found under the configured cases directory.
```

这不是失败，只表示还没有 `test_workspace/cases/<module>/` 和对应 profile。

## 4. 放入文档

把目标系统的公开行为资料放入 `docs/`，例如：

```text
docs/public_api.md
docs/openapi.yaml
docs/protos/
docs/config_schema.md
```

建议第一轮只选一个小模块或一条主链路，例如：

- 用户登录
- API key 创建和查询
- 订单创建
- 网关转发
- 账单扣费查询

不要一开始覆盖整个系统。先跑通一条闭环更重要。

## 5. 让 AI 生成测试资产

在 `aitest_workspace` 下启动 Codex、Claude Code 或其他 AI 编程工具，然后按顺序使用 workspace 内置 skills。

你可以直接这样提问：

```text
请基于 docs/ 下的公开 API 文档，先用 doc-review 检查文档缺口；
如果足够，再用 knowledge-build 构建测试知识库；
然后为 <模块名> 设计一批 Markdown 用例；
最后用 test-scaffold 生成 fixture 和 codegen profile。
```

产物应该出现在：

```text
test_workspace/knowledge/                 # L0/L1/L2
test_workspace/suites/<target>/<suite>/   # Markdown 用例 + suite.yaml + suite profile
test_workspace/targets/<target>/          # target/module registry、fixture、helper、module profile
```

典型 suite 结构：

```text
test_workspace/suites/<target>/<suite>/suite.yaml
test_workspace/suites/<target>/<suite>/business.md
test_workspace/suites/<target>/<suite>/profile_<suite>_suite.md
```

## 6. 生成 pytest

target/suite 用例：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- --collect-only -q
```

如果要把多个 suite 作为一次回归或冒烟任务执行，创建 `test_workspace/tasks/<task>.yaml`，然后运行：

```bash
aitest codegen --task-file test_workspace/tasks/<task>.yaml --check
aitest run --task-file test_workspace/tasks/<task>.yaml
```

legacy 模块模式仍兼容 `aitest codegen <module>` 和 `test_workspace/tests/generated/`，但新项目建议从 `suite.yaml` 开始。

判断结果：

- `--validate-profile` 必须 `errors=0`。
- `--dump-ir` 用来看每条用例最终走 `default_http`、`case_flows`、`case_bodies` 还是 `skipped`。
- `--check` 必须显示 generated 文件没有过期。
- `pytest --collect-only` 必须能收集到测试函数。

## 7. 运行测试并看报告

先准备 fixture 需要的环境变量，例如：

```bash
cat > /tmp/your-system-test.env <<'EOF'
YOUR_SYSTEM_BASE_URL=http://127.0.0.1:8080
YOUR_SYSTEM_ADMIN_TOKEN=...
EOF
```

然后运行：

```bash
AITEST_ENV_FILE=/tmp/your-system-test.env aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
```

报告位置：

```text
test_workspace/reports/latest/report.md
test_workspace/reports/latest/result.json
test_workspace/reports/latest/junit.xml
```

`aitest run` 会先做 generated freshness check。如果 Markdown/profile 已经变了但 pytest 没重新生成，会写出 `BLOCKED_RUN` 报告并停止，避免执行旧测试。

## 8. 什么时候用哪个 skill

| 场景 | 推荐入口 |
|---|---|
| 文档是否足够做测试不确定 | `doc-review` |
| 需要从公开文档建立测试知识库 | `knowledge-build` |
| 需要设计 Markdown 用例 | `test-design` |
| 新模块还没有 fixture/profile | `test-scaffold` |
| 现有模块新增用例，fixture 动作已经足够 | `test-codegen` |
| 新增用例时发现 fixture 缺动作 | 回到 `test-scaffold` 增量补 fixture/profile |
| 测试失败，需要判断是环境、用例、脚手架还是系统 bug | `aitest run` + `test-fix` |
| 测试稳定后想沉淀重复规则 | `emitter-build` |

## 9. 升级已有 workspace

升级分两层：

```bash
python3 -m pip install -U aitest-kit
aitest upgrade --workspace /path/to/aitest_workspace --check
aitest upgrade --workspace /path/to/aitest_workspace --apply
```

`pip install -U` 更新 CLI 和 Python 代码。`aitest upgrade` 同步 `aitest init` 复制进项目的模板资产，例如 skills、schema、refs、helpers 和 workspace 说明。

不要用 `aitest init --force` 升级已有 workspace。`upgrade` 只自动覆盖仍等于旧模板的文件；本地改过的文件会跳过并提示人工 review。

## 10. 常见问题

### 找不到 `aitest`

使用模块入口：

```bash
python3 -m aitest_kit.cli --help
```

或把 Python 用户脚本目录加入 `PATH`。

### `doctor` 提示没有模块

刚初始化时正常。创建 `test_workspace/targets/<target>/modules/<module>.yaml`、`test_workspace/targets/<target>/profiles/profile_<module>.md` 和至少一个 `test_workspace/suites/<target>/<suite>/suite.yaml` 后再跑。

### profile 校验失败

先修 profile，不要直接生成 pytest。profile gate 是硬门禁，格式错误时不进入 Case IR 和 emitter。

### generated 过期

运行：

```bash
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check
```

### 运行测试缺环境变量

fixture 应该明确报出缺少的环境变量名，但不要打印变量值。把变量设置在 shell、CI secret、本地不提交的 `.env`，或通过 `AITEST_ENV_FILE=/path/to/test.env aitest run --suite-file <suite.yaml>` 指定的 env 文件中。

## 下一步

- 新项目完整迁移：见 [AITest Migration Guide](./aitest_migration_guide.md)
- 长期协作模型、skill 分工和测试资产维护：见 [AITest Workflow Guide](./aitest_workflow_guide.md)
- profile 编写：见 [Profile Guide](./codegen_profile_guide.md)
- codegen 排错：见 [Troubleshooting](./codegen_troubleshooting.md)
