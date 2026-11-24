# 日志断言候选验收记录

候选为 `aitest-kit 0.7.0rc1`，从 AIAutoTest `729a8d1` 上的本地改动构建。旧工作区验收使用已发布的 Kit `0.6.0`。候选 wheel SHA-256、依赖版本、命令、退出码和用例明细由 `scripts/verify_log_assertions_wheel.py` 写入 `acceptance.json`。同一目录保存 JUnit、脱敏后的示例报告和 Agent 候选工具链锁。

| 验收项 | 状态 | 证据与环境 |
| --- | --- | --- |
| wheel 与 sdist 分发 | 通过 | macOS ARM64 上安装候选到独立 Python 3.12 环境，核对样例、Schema、说明和 neutral skills，运行 `pip check`、`init`、`doctor` |
| 旧工作区升级 | 通过 | 原版 0.6.0 init、生成和运行后使用候选执行 upgrade、freshness、旧报告重渲染及再次运行。保留用户改过的 Schema、自定义 Harness 和历史 JSON |
| 后台并发、报告和清理 | 通过 | loopback 观察 1/1、4/2 及跨单元并发上限，核对通过、日志失败、清理 403、幂等重试、恢复与报告 |
| 多请求和分页 | 通过 | 从 wheel 提取双请求示例，验证不同 reqId、两页快照、版本冲突后从第一页重读、大整数、false、null 和响应派生值 |
| AI 可发现资料和诊断命令 | 通过 | 安装包成员检查和候选 CLI 实跑 validate-profile、dump-ir、explain、freshness，非法后台引用被 E534 拒绝 |
| Agent 报告预检及依赖 | 通过 | 在沿用 Agent 已锁版本的候选环境生成真实 pytest XML，再执行 Agent 源码中的 collector 和 renderer 预检；Agent 本地测试 50 项通过 |
| Windows 与 Linux | 待验 | 已接入三平台 CI 安装矩阵，实际通过状态由 CI 执行者填报。当前本地验收在 macOS，Docker daemon 未连接 |
| 真实模型独立编写用例 | 待验 | Agent 验收人员在已配置模型的隔离工作区，仅提供安装后的样例和指南，并记录初次生成、修正和最终结果 |
| Worker 崩溃与进程信号的跨平台验证 | 待验 | 当前覆盖临时 SQLite 的退出窗口和恢复、取消结算回归。仍需在目标环境主动终止验收 worker 并核对进程退出与业务调用次数 |
| 同源 Agent 多平台 wheel、候选 bundle 与云端 Runner | 待验 | Agent 发布人员提供同源四平台 wheel，使用候选工具链锁构包，再用批准的 Runner 环境验证模板、项目虚拟环境和报告下载 |
| 真实 Kafka、隧道和清理 | 待验 | 目标环境提供专用来源、测试服务和鉴权变量，按分片 4 的真实平台场景执行并保存脱敏证据 |

[验收规格](04_acceptance_and_agent.md) · [用户指南](../../usebook/aitest_log_assertions.md)
