# AITest 项目工作区

本目录是一个目标系统的测试工作区。

## 目录结构

- `aitest_config/`：项目级路径配置、codegen 配置、schema 和共享格式参考。
- `AGENTS.md` / `CLAUDE.md`：本工作区的 AI 协作入口。
- `.codex/skills/`、`.claude/skills/`、`.agents/skills/`：本地测试工作流 skill。
- `docs/`：目标系统的公开设计文档，供知识库构建流程使用。
- `test_workspace/knowledge/`：L0/L1/L2 测试知识库和 `TEST_SPEC.md`。
- `test_workspace/cases/`：Markdown 测试用例，按模块组织。
- `test_workspace/tests/fixtures/`：模块 fixture 和 `codegen_profile_{module}.md`。
- `test_workspace/tests/generated/`：codegen 生成的 pytest 文件。
- `test_workspace/reports/`：测试执行报告。
- `test_workspace/results/`：已确认的待测系统 bug 记录。

## 快速开始

1. 将目标系统的公开设计文档放入项目的 docs 目录。
2. 构建或更新测试知识库。
3. 在 `test_workspace/cases/{module}/` 下创建 Markdown 用例。
4. 在 `test_workspace/tests/fixtures/` 下添加 fixture 和 `codegen_profile_{module}.md`。
5. 生成并运行测试：

```bash
aitest codegen --all --validate-profile
aitest codegen --all
aitest run <module>
```

从工作区外部执行时，追加 `--workspace /path/to/workspace`。

## 信息源边界

新项目迁移默认按黑盒测试工作流执行。以公开设计文档、API 定义、配置 schema、示例请求/响应和可执行的 API 行为作为规则来源。

不要从目标系统源码、已有测试或内部实现文档推断业务规则，除非项目明确切换到已文档化的灰盒阶段。

## 安全注意事项

- 不要提交 `.env` 文件、服务凭证、访问 token 或生产数据。
- 目标服务 URL 通过环境变量或不提交的本地配置传递。
- `test_workspace/reports/` 下的报告可能包含请求 ID、响应内容、断言错误和服务错误详情。
- 在团队外部分享报告和 bug 记录前，请先审查或脱敏。

## 稳定性说明

v0.1 的稳定接口包括 `aitest` CLI、本工作区目录结构、Markdown 用例文件、`codegen_profile_{module}.md` 和生成的 pytest 输出。

健康报告、晋升报告、晋升补丁和内部 Python API 属于辅助工具，可能会演进。
