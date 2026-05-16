# AITest Quickstart

本文面向第一次把 `aitest-kit` 接入新项目的用户。目标不是一次性完成完整迁移，而是先跑通最小闭环：

```text
init workspace -> 写一个 Markdown 用例 -> 写一个 codegen_profile -> codegen -> pytest collect
```

## 1. 安装

在你的 Python 环境中安装工具包：

```bash
pip install aitest-kit
```

本仓开发态可使用：

```bash
pip install -e ".[dev]"
```

发布状态说明：

- v0.1 面向本地试用和新项目迁移演练。
- 稳定入口是 `aitest init/codegen/run/report`、workspace layout、Markdown 用例格式和 profile schema。
- health/promotion report、promotion patch 和内部 Python API 仍按实验能力看待。

## 2. 初始化项目 workspace

不要直接复用 AIAutoTest 仓库里的 `test_workspace/`。在你的目标项目目录，或一个独立目录中初始化：

```bash
aitest init --target /path/to/your_project
```

初始化后会生成：

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

这些文件是新项目测试工作区的一部分。后续命令如果不在 `/path/to/your_project` 内执行，统一加 `--workspace /path/to/your_project`。

安全提醒：

- 不要把 `.env`、生产凭证、token 或真实用户数据放入 workspace 并提交。
- 生成报告可能包含请求、响应和错误详情，对外共享前需要脱敏。
- 外部服务地址优先通过环境变量传入 fixture；缺失时让 fixture 明确失败。

## 3. 空 workspace 体检

先确认 CLI 能识别 workspace：

```bash
aitest codegen --workspace /path/to/your_project --all --validate-profile
```

如果还没有任何模块，会看到类似提示：

```text
No modules found under the configured cases directory.
Next step: create test_workspace/cases/<module>/business.md and a matching codegen profile under test_workspace/tests/fixtures.

Profile validation summary: modules=0, errors=0, warnings=0
```

这不是失败，而是告诉你下一步要创建模块用例和 profile。

## 4. 创建最小模块

以 `demo` 模块为例，创建：

```text
test_workspace/cases/demo/business.md
test_workspace/tests/fixtures/codegen_profile_demo.md
```

`business.md`：

~~~markdown
# demo 业务测试用例

---

## 共享配置

**接口**：`POST /api/v1/demo`

**基础请求体（HTTP）**：

```json
{
  "request_id": "req_default",
  "user_id": "user_default",
  "value": 1
}
```

**标准前置**：
- 服务已启动

**通用断言**：`response.code == 0`

**变量定义**：
- 无

---

## 一、基础成功场景

### TC-DEMO-001：默认请求返回成功
- **优先级**：P1
- **场景变量**：请求覆盖：`{"request_id": "req_demo_001", "user_id": "u_demo_001"}`
- **断言**：`response.code == 0`
~~~

`codegen_profile_demo.md`：

~~~markdown
# demo codegen profile

```yaml
module_type: standard_http
request_overrides:
  TC-DEMO-001:
    user_id: "u_demo_001"
    request_id: "req_demo_001"
```
~~~

说明：Markdown 里的“场景变量/请求覆盖”用于人类 review 和 trace；当前确定性 codegen 的请求体差异以 profile 的 `request_overrides` 为准。

## 5. 生成前门禁

```bash
aitest codegen --workspace /path/to/your_project demo --validate-profile
aitest codegen --workspace /path/to/your_project demo --dump-ir
```

期望：

- `--validate-profile` 输出 `Status: OK`
- `--dump-ir` 能看到每条用例的 `strategy`、`request`、`assertions` 和 `source_trace`

如果这里失败，先看 [codegen_troubleshooting.md](./codegen_troubleshooting.md)。

## 6. 生成 pytest

```bash
aitest codegen --workspace /path/to/your_project demo
aitest codegen --workspace /path/to/your_project demo --check
```

期望：

- 第一次生成 `test_workspace/tests/generated/test_demo_business.py`
- 再跑 `--check` 输出 `All generated files are up to date.`

## 7. 收集 generated 测试

推荐在 workspace 根目录执行：

```bash
cd /path/to/your_project
python -m pytest test_workspace/tests/generated --collect-only -q
```

如果你从其他目录执行，需要确保 Python 能找到该 workspace 下的 `test_workspace` 包，例如设置 `PYTHONPATH=/path/to/your_project`。

## 8. 下一步

最小链路跑通后，再进入正式迁移：

1. 把公开设计文档放入 `docs/`。
2. 用 `knowledge-build` 构建知识库。
3. 用 `test-design` 生成模块 Markdown 用例。
4. 为模块补充 fixture 和 `codegen_profile_{module}.md`。
5. 按门禁顺序执行：

```bash
aitest codegen --workspace /path/to/your_project --all --validate-profile
aitest codegen --workspace /path/to/your_project --all --dump-ir
aitest codegen --workspace /path/to/your_project --all --check
aitest codegen --workspace /path/to/your_project --all
python -m pytest /path/to/your_project/test_workspace/tests/generated --collect-only -q
```

更完整的新项目迁移流程见 [AITest 新项目迁移指南](./aitest_migration_guide.md)。
