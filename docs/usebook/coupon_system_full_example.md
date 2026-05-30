# coupon_system 完整示例

`coupon_system` 是本仓库内置的真实回归资产，用来展示 AITest Kit 在复杂 API 测试项目中的组织方式。它不是使用 AITest 的前置条件，也不是新项目必须复制的业务系统。

它适合回答这个问题：

```text
一个包含 HTTP、gRPC、Redis、AB 服务、多模块用例、generated pytest 和结构化报告的真实项目，如何使用 AITest Kit 组织测试资产？
```

## 一、这个示例展示什么

`coupon_system` 覆盖：

- FastAPI HTTP 服务。
- gRPC 服务。
- Redis 状态。
- AB 实验服务。
- 内部 gRPC 打分服务。
- 外部 HTTP 打分服务。
- Markdown 用例。
- codegen profile。
- module fixture。
- generated pytest。
- `aitest run` 结构化报告。

它主要用于展示完整能力和做仓库回归，不建议作为陌生用户第一次试跑的唯一入口。第一次迁移自己的系统时，仍然建议从 [AITest 新项目迁移指南](./aitest_migration_guide.md) 开始。

## 二、关键目录

```text
coupon_system/                         # 待测优惠券推荐系统
ab_experiment_sdk/                     # AB 实验服务和 SDK
docs/                                  # 开发文档和使用说明
test_workspace/knowledge/              # 测试知识库
test_workspace/suites/coupon_system/   # suite Markdown 用例和 suite profile
test_workspace/targets/coupon_system/  # 模块 fixture、helper 和 module profile
test_workspace/generated/coupon_system/# generated pytest
test_workspace/reports/                # aitest run 输出
test_workspace/results/                # 已确认的待测系统 bug 记录
```

## 三、服务依赖

完整执行 generated 集成测试前，需要启动这些本地服务：

| 服务 | 默认地址 | 作用 |
|---|---|---|
| Redis | `127.0.0.1:6379` | 库存、领取记录、用户特征、限流计数 |
| AB 实验服务 | `127.0.0.1:8100` | 实验评估、实验管理、白名单管理 |
| 内部 gRPC 打分服务 | `127.0.0.1:50052` | 主服务 `external=0` 时调用 |
| 外部 HTTP 打分服务 | `127.0.0.1:50053` | 主服务 `external=1` 时调用 |
| 待测 HTTP 服务 | `127.0.0.1:8000` | 推荐 HTTP API |
| 待测 gRPC 服务 | `127.0.0.1:50051` | 推荐 gRPC API |

详细启动命令见 [服务启动说明](./service_startup.md)。

## 四、启动顺序

推荐按依赖顺序启动：

1. Redis
2. AB 实验服务
3. 内部 gRPC 打分服务
4. 外部 HTTP 打分服务
5. 待测主服务

主服务建议显式使用远程 AB 服务，并绕过本机代理：

```bash
env AB_SERVICE_URL=http://127.0.0.1:8100 \
  NO_PROXY=localhost,127.0.0.1 \
  no_proxy=localhost,127.0.0.1 \
  python3 -m coupon_system.main
```

如果只做 codegen、profile gate、generated freshness 或 pytest collect，可以不启动服务。真实 pytest 执行才需要服务可达。

## 五、codegen 验证

在仓库根目录执行：

```bash
python3 -m aitest_kit.cli codegen --target coupon_system --validate-profile
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --dump-ir
python3 -m aitest_kit.cli codegen --target coupon_system --check
python3 -m aitest_kit.cli run --target coupon_system -- --collect-only -q
```

这些命令分别验证：

- profile schema 和语义是否通过。
- 每条用例走哪条生成策略。
- generated pytest 是否与 Markdown/profile/config 同步。
- generated pytest 是否可导入和收集。

## 六、运行测试和报告

服务启动后，可以按 suite、模块、target 或全量运行：

```bash
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --case-id TC-CAL-001
python3 -m aitest_kit.cli run --target coupon_system --module calibration
python3 -m aitest_kit.cli run --target coupon_system
python3 -m aitest_kit.cli run --all
```

报告输出：

```text
test_workspace/reports/latest/result.json
test_workspace/reports/latest/report.md
test_workspace/reports/latest/junit.xml
test_workspace/reports/tasks/<task_or_selector>/latest/report.md
```

如果 generated pytest 过期，`aitest run` 会生成 `BLOCKED_RUN` 报告并停止，避免执行旧测试。

## 七、典型模块

### calibration：默认模板 + 断言规则

`calibration` 代表标准推荐接口模块。它主要走默认 HTTP/gRPC 模板，复杂点在断言公式。

相关文件：

```text
test_workspace/suites/coupon_system/calibration_smoke/
test_workspace/targets/coupon_system/profiles/profile_calibration.md
test_workspace/targets/coupon_system/fixtures/calibration.py
test_workspace/generated/coupon_system/test_calibration_calibration_smoke_business.py
```

它展示：

- 单接口请求如何走默认模板。
- `response.code == 0` 如何被内置规则翻译。
- 分段校准公式如何通过 profile `assertion_rules` 和 named template 生成可执行断言。

### ab_service：case_flow + case_body 混合

`ab_service` 是多端点服务模块，默认 `/api/v1/recommend` 模板不适用。

它展示：

- 运行中 HTTP API CRUD 适合 `case_flows`。
- 文件持久化、Remote SDK 生命周期、mock、subprocess 等复杂场景适合保留 `case_bodies`。
- `case_body` 不是失败，但要有明确保留理由。

### issuance：状态副作用验证

`issuance` 展示推荐后副作用验证：

- 发放结果。
- Redis 库存。
- 用户券查询。
- HTTP/gRPC 查询路径。
- 并发库存场景。

它说明多步骤状态验证应优先通过 fixture/helper 封装能力，再由 `case_flow` 或必要的 `case_body` 调用。

### logging：隔离服务和日志捕获

`logging` 涉及隔离服务、日志采集和人工可观测性判断。它展示了为什么有些场景不适合强行塞进 `case_flow`。

## 八、如何解读 health report

```bash
python3 -m aitest_kit.cli codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml --health-report --write-report
```

关注：

- profile errors 是否为 0。
- `UNPARSED` 是否为 0。
- 各模块 `default_http` / `structured_case_flow` / `custom_case_body` 占比。
- `case_body` 是否有明确保留理由。
- skipped/manual 是否来自真实不可自动化边界，而不是为了隐藏失败。

health report 是治理工具，不是为了把所有模块都强行推到同一种策略。

## 九、常见失败分流

| 现象 | 优先判断 | 处理方式 |
|---|---|---|
| `Connection refused` | 服务未启动或端口不对 | 按 `service_startup.md` 启动依赖 |
| generated stale | Markdown/profile/config 改了但未重新生成 | 运行 `aitest codegen --suite-file <suite.yaml>` 或 `aitest codegen --target <target>` |
| profile gate failed | profile 格式或 case_id 引用错误 | 修 profile，不进入 renderer |
| `UNPARSED ASSERTION` | 断言无法确定性翻译 | 先分流：Markdown 表达、用例问题、缺规则、不可观测 |
| `assert isinstance(resp, dict)` | 弱断言 | 补业务断言或改成 `case_flow` |
| 待测行为不符合公开契约 | 系统 bug | 记录到 `test_workspace/results/` |

## 十、迁移到自己项目时怎么借鉴

不要复制 `coupon_system` 的业务规则。应该借鉴它的组织方式：

- 文档先进入知识库。
- Markdown 用例作为可 review 的测试设计。
- fixture 封装公开 API 和测试状态能力。
- profile 表达模块生成规则。
- generated pytest 只作为编译产物。
- report 反哺用例、fixture、profile 或系统 bug。

如果你的项目是多端点状态流，可以重点参考 `ab_service` 和 `issuance`。如果你的项目是标准单接口，可以重点参考 `calibration`。
