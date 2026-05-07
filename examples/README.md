# AITest Examples

本目录是示例层索引，用来把“学习参考”和“新项目模板”分开。

当前阶段不移动现有示例源码和测试资产，避免一次性改动大量路径。示例仍保留在仓库现有位置，本目录只记录它们的边界、入口和可对照内容。

## 示例清单

| 示例 | 说明 | 当前位置 |
|---|---|---|
| coupon_system | AIAutoTest 主示例待测系统，覆盖推荐、校准、发放、AB、限流等模块 | `coupon_system/`、`ab_experiment_sdk/`、根 `test_workspace/` |
| discount_policy | 伪新项目迁移演练产物，验证新项目从公开文档到 generated pytest 的接入流程 | `docs/discount_system/`、`test_workspace/cases/discount_policy/`、`test_workspace/tests/fixtures/discount_policy.py` |

## 使用约定

- 新项目不要复制根 `test_workspace/`，应使用 `aitest init` 或 `templates/project_workspace/`。
- 示例里的业务规则、Redis key、端口、fixture 只作为学习参考。
- 如果未来要物理移动示例资产，应先完成 workspace 参数稳定性验证，再按独立 spec 迁移路径和导入。
