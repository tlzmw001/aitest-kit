# Test Spec

本文件记录当前项目的测试设计红线、共享约定和已经踩过的坑。

## 通用规则

- Markdown 用例是测试设计源文件。
- generated pytest 是编译产物，优先修改 Markdown/profile/fixture/config 后重新生成。
- HTTP JSON 基础请求体必须是合法 JSON，不允许 `{{var}}` 占位符。
- 用例差异优先写入 profile 的 `request_overrides`。
- 不用弱断言凑自动化；断言必须对应真实业务契约。
- 测试失败先分流：用例问题、profile/codegen 问题、fixture/helper 问题、环境问题、待测系统 bug。
- 确认为待测系统 bug 时，记录到 `test_workspace/results/`。

## 项目约定

- 待补充：服务启动方式、环境变量、依赖服务、数据隔离策略。
- 待补充：模块缩写表和 TC ID 规则。
- 待补充：通用错误码和异常响应格式。
