# coupon_system Example

`coupon_system` 是本仓库的主示例待测系统，用来持续验证 AITest 框架能力。

## 示例边界

- 待测系统源码：`coupon_system/`
- 依赖服务与 SDK：`ab_experiment_sdk/`
- 示例测试资产：根目录 `docs/`、`aitest_config/`、`test_workspace/`

这些内容不是新项目初始化模板。用户接入自己的系统时，应从 `aitest init --target /path/to/project` 开始。

## 参考价值

- 多模块 Markdown 用例组织方式。
- `codegen_profile_{module}.md` 中 assertion rules、request overrides、case_flows、case_bodies 的使用方式。
- generated freshness check、profile gate、health report、promotion report 的完整链路。
- 待测系统 bug 记录与测试报告分流方式。

## 不在本阶段移动的原因

物理移动会影响大量测试路径、文档链接、fixture 导入和现有验证命令。本阶段先用 `examples/` 建立示例索引，等 `aitest init` 与 `--workspace` 路线稳定后，再评估是否迁移到真正的 `examples/coupon_system/` 工作区。
