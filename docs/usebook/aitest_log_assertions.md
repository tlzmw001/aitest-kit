# 日志断言与恢复

安装候选 wheel 后，在独立工作区初始化样例。需要并行业务用例时安装 wheel 的 `parallel` extra。

```bash
python -m pip install "${KIT_WHEEL}[parallel]"
aitest init --target "$ACCEPTANCE_WORKSPACE"
cd "$ACCEPTANCE_WORKSPACE"
cp -R examples/log_assertions/test_workspace/. test_workspace/
```

业务地址由 `AITEST_LOG_DEMO_URL` 提供。日志平台连接使用 `AITEST_LOG_BASE_URL` 和 `AITEST_LOG_TOKEN`。样例事件来源为 `demo`。项目接入时，在 module registry 中填写实际来源，由 Harness 根据业务接口约定决定如何启用采集和绑定请求 ID。

```bash
suite=test_workspace/suites/demo/log_assertions/suite.yaml
aitest codegen --suite-file "$suite" --validate-profile
aitest codegen --suite-file "$suite" --explain TC-DEMO-001
aitest codegen --suite-file "$suite"
aitest codegen --suite-file "$suite" --check
aitest run --suite-file "$suite" --case-concurrency 4 --log-concurrency 2
aitest report --suite-file "$suite"
```

`log_assertions` 按业务步骤绑定日志。用例的即时检查可以引用业务响应，后台检查通过 `expected` 读取冻结的响应派生值。初始化后的 `log_multi_request` 样例覆盖同一用例两次请求、各自的日志筛选和多页事件。语法和清理策略见工作区包内的 `aitest_config/refs/log-assertions.md`。

运行 ID 会出现在终端。进程中断后，在原工作区恢复该运行。

```bash
aitest run --resume "$RUN_ID"
```

恢复继续处理剩余日志断言和可安全重试的清理请求。业务请求只在初始测试执行中发送。查看 `result.json`、`report.md`、`junit.xml` 或 Console 核对最终结论。清理回执表示平台已受理精确请求；清理异常会影响整轮退出码。

## 验证候选包

```bash
python -m build
python scripts/verify_log_assertions_wheel.py --wheel-dir dist --baseline-wheel "$BASELINE_WHEEL" --output "$EVIDENCE_DIR"
```

`BASELINE_WHEEL` 指向原版 Kit 0.6.0 wheel。使用 `--agent-root "$AGENT_ROOT"` 可同时执行 Agent 报告预检并产出候选工具链锁。验收结果和报告保存在 `EVIDENCE_DIR`。可在 CI 安装矩阵查看 Windows、Linux 和 macOS 的结果。真实日志平台验收需使用目标来源、业务服务及授权的日志平台连接。
