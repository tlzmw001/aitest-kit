# Codegen 新项目迁移 Playbook

## 核心原则

AIAutoTest 当前不拆分 `aitest_kit` 与 workspace 协议仓库。框架代码、schema、模板和示例回归资产同仓维护；真实用户项目通过独立 workspace 隔离。

workspace 模板只有一个来源：

```text
aitest_kit/templates/project_workspace/
```

不要新增或维护顶层 `templates/project_workspace/`。这样源码运行和安装后运行都读取同一份模板，避免双模板同步问题。

## 零、信息边界

新项目迁移先按黑盒测试方式建立最小闭环：只使用公开设计文档、接口定义、配置 schema、示例请求响应和可执行 API 行为作为规则来源。不要读取目标系统源码、已有测试或内部实现文档来推断业务规则。

如果项目后续明确进入灰盒补文档阶段，需要把边界切换写清楚：哪些源码或配置可以读、读它们是为了补全文档还是为了修复测试基础设施。不要把源码推断出的规则直接混进首轮黑盒用例。

## 一、初始化工作区

在新项目目录外执行：

```bash
aitest init --target /path/to/your_project
```

初始化后，新项目目录中会出现：

```text
AGENTS.md
CLAUDE.md
.agents/
.claude/
.codex/
docs/
aitest_config/
test_workspace/
```

其中 `AGENTS.md` / `CLAUDE.md` 是新项目通用协作入口，三套 hidden skills 分别服务 agents、Claude Code 和 Codex，`docs/` 用来放公开设计文档。它们和 `aitest_config/`、`test_workspace/` 一样属于初始化资产，不需要用户手工从 AIAutoTest 根目录复制。

后续如果不在该目录内执行命令，统一加 `--workspace`：

```bash
aitest codegen --workspace /path/to/your_project --all --validate-profile
aitest codegen --workspace /path/to/your_project --all
aitest run --workspace /path/to/your_project <module>
aitest report --workspace /path/to/your_project
```

第一次使用建议先按 [AITest Quickstart](./aitest_quickstart.md) 跑通最小 demo 模块，再迁移真实业务模块。

## 二、重写项目配置

优先修改：

- `aitest_config/config.yaml`
- `aitest_config/project_config.yaml`

其中 `project_config.yaml` 是迁移的核心。它决定：

- generated pytest 的 helper import
- 默认 API 路径
- HTTP/gRPC 调用函数
- 断言变量映射
- 模块缩写
- module_type
- 内置断言规则

换项目时不要改 parser/emitter engine；先通过配置、profile、fixture/helper 适配。

## 三、建立模块资产

每个模块至少准备：

```text
test_workspace/cases/{module}/business.md
test_workspace/cases/{module}/boundary.md
test_workspace/tests/fixtures/{module}.py
test_workspace/tests/fixtures/codegen_profile_{module}.md
```

优先路线：

1. 默认 HTTP/gRPC 模板：适合单请求、规则稳定的模块。
2. `assertion_rules`：适合请求流程标准但断言可模板化的模块。
3. `case_flows`：适合稳定多步骤流程。
4. `case_bodies`：保留给并发、进程、mock、文件生命周期等复杂场景。

## 四、门禁顺序

每轮迁移按这个顺序验证：

```bash
aitest codegen --workspace /path/to/your_project --all --validate-profile
aitest codegen --workspace /path/to/your_project --all --dump-ir
aitest codegen --workspace /path/to/your_project --all --check
aitest codegen --workspace /path/to/your_project --all
python3 -m pytest /path/to/your_project/test_workspace/tests/generated --collect-only -q
```

`--check` 在 generated 文件还没生成时会提示 stale，这是正常状态；生成后再次执行应为 up to date。

pytest collect 推荐在 workspace 根目录执行：

```bash
cd /path/to/your_project
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

如果必须从其他目录执行，需要显式设置 `PYTHONPATH=/path/to/your_project`，否则可能出现 `ModuleNotFoundError: No module named 'test_workspace'`。

## 五、分流规则

- 文档不清楚：补知识库 `[?]` 或找产品确认。
- 用例不可测：修改 Markdown，或记录为测试基础设施需求。
- profile 格式错误：先修 profile gate。
- fixture/codegen 问题：修改 fixture/profile/helper/project_config，不直接长期手写 generated。
- 待测系统 bug：记录到 `test_workspace/results/`，不 skip、不放宽断言。

相关文档：

- [Codegen Profile Guide](./codegen_profile_guide.md)
- [Codegen Troubleshooting](./codegen_troubleshooting.md)
