# AITest Workspace Template Spec

## 背景

当前仓库同时承担框架开发、示例回归和新项目接入说明三种职责。用户接入新项目时，不应该直接复用本仓的 `test_workspace/`，否则会把 coupon/AB 示例资产、历史报告和项目配置一起带过去。

本 spec 的目标是把真实用户工作区从本仓示例资产中隔离出来，同时保留 `aitest_kit` 与 workspace 协议同仓维护，避免拆仓带来的版本漂移。

## 决策

采用单仓、单模板源方案：

- 不拆分 `aitest_kit` 与 workspace 协议仓库。
- 不保留顶层 `templates/project_workspace/`。
- `aitest_kit/templates/project_workspace/` 是唯一 workspace 模板源。
- `aitest init --target <dir>` 从包内模板复制干净工作区。
- `codegen`、`run`、`report` 通过 `--workspace <dir>` 在目标工作区内执行。

这样源码态和安装态都读取同一份模板，不存在“源码模板”和“包内镜像”两份副本的同步问题。

## 影响范围

- 新增 `aitest init` 命令。
- 新增 workspace 上下文切换工具。
- `codegen` 支持 `--workspace`。
- `run` / `report` 支持 `--workspace`。
- 包内模板目录纳入 Python package data。
- `AGENTS.md` / `CLAUDE.md` 和三套本地 skills 纳入模板，保证新项目初始化后具备完整 AI 协作入口。
- 文档统一为“包内唯一模板源”口径。

## 非目标

- 不拆仓。
- 不移动本仓现有 `test_workspace/` 示例与回归资产。
- 不把当前 coupon/AB 项目的知识库、用例或 generated pytest 放入模板。
- 不改变 codegen IR、parser 或 emitter 的核心生成语义。

## 模板内容

模板只包含新项目启动所需的干净骨架：

```text
AGENTS.md
CLAUDE.md
.agents/
.claude/
.codex/
docs/
aitest_config/
  config.yaml
  project_config.yaml
  refs/
  schemas/
test_workspace/
  cases/
  knowledge/
  plans/
  reports/
  results/
  tests/
```

其中：

- `AGENTS.md` / `CLAUDE.md` 是新项目通用协作入口，不复制本仓 coupon/AB 示例项目的专属说明。
- `.codex/skills/`、`.claude/skills/`、`.agents/skills/` 带入同一套测试飞轮 SOP，适配 Codex、Claude Code 和 agents 工作流。
- `docs/` 是新项目公开设计文档入口，避免用户初始化后第一步还要手工创建目录。
- `aitest_config/config.yaml` 定义标准路径。
- `aitest_config/project_config.yaml` 提供通用默认 codegen 配置，用户接入新系统时必须按项目改写。
- `test_workspace/tests/helpers/http.py` 提供最小 HTTP helper。
- `test_workspace/tests/conftest.py` 提供通用 `http_base_url` / `grpc_target` fixture。

## 验收标准

1. `aitest init --target <dir>` 能创建干净 workspace。
2. 默认不覆盖已有文件；`--force` 只覆盖模板管理的文件。
3. 仓库根目录不存在顶层 `templates/project_workspace/`。
4. 新 workspace 包含 `AGENTS.md`、`CLAUDE.md`、`.codex/skills/`、`.claude/skills/`、`.agents/skills/`。
5. `codegen --workspace <dir>` 在目标 workspace 读取 cases/profile/config，并把 generated 写回目标 workspace。
6. `run --workspace <dir>` 和 `report --workspace <dir>` 使用目标 workspace 的报告目录。
7. `python3 -m pytest tests -q` 通过。
