# discount_policy Migration Example

`discount_policy` 是伪新项目迁移演练示例，用来验证 AITest 能否只依赖公开行为文档完成新模块接入。

## 示例边界

- 公开文档副本：`docs/discount_system/public_api_doc.md`
- 知识库：`test_workspace/knowledge/L1/discount_policy.md`、`test_workspace/knowledge/L2/discount_system_initial_public_api.md`
- Markdown 用例：`test_workspace/cases/discount_policy/`
- fixture/profile：`test_workspace/tests/fixtures/discount_policy.py`、`test_workspace/tests/fixtures/codegen_profile_discount_policy.md`
- generated pytest：`test_workspace/tests/generated/test_discount_policy_*.py`

## 参考价值

- 从公开 API 文档构建 L1/L2。
- 将多端点 HTTP 服务沉淀为 `structured_case_flow`。
- 使用项目专属环境变量 `DISCOUNT_SYSTEM_BASE_URL` fail fast。
- 通过 profile gate、dump IR、codegen check、pytest collect/run 验证迁移结果。

## 使用提醒

这个示例已经进入根 `test_workspace/`，用于和现有 codegen 全量门禁一起验证。它不是模板内容；新项目仍应使用 `aitest init` 生成干净工作区。
