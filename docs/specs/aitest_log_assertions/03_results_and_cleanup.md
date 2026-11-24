# 分片 3 · 用例最终结果、报告与日志清理

依赖 [用例与客户端](01_profile_and_client.md) 和 [执行与恢复](02_execution_and_recovery.md)。本片决定用户看到的用例结论、整轮退出码，以及 Kit 何时可以申请删除日志。实现基线为 Kit v0.6.0。

## 1. 验收目标与输入

同一次 run 中，A 的 HTTP 断言通过、日志断言失败，B 全部通过并声明成功后清理。应在 B 完成时保存其结论并申请清理；A 的日志保留到平台 TTL。命令退出时，JSON、Markdown、JUnit、Console 均能定位 A 的具体失败，汇总为一条通过、一条失败，退出码为 1。

使用分片 2 的同一个 SQLite。运行器提供运行范围、已选择及实际启动的用例、完整 nodeid、尝试序号、pytest 各阶段及中断事实。验证器提供请求步骤、来源与关联值、采集与读取状态、快照版本、规则检查结果、冻结期望及有界实际值。将这些事实按 `run_id + unit_index + nodeid + attempt` 关联，按 `request_step` 归入一次请求。TC-ID 用于展示和筛选。由唯一持有 run 写权限的协调器负责结算、清理和发布报告。

当前 [collector](../../../aitest_kit/report/collector.py) 通过 JUnit 映射静态元数据时会去除参数化后缀。接入新链路后，以 pytest 插件捕获的完整实例键连接结果，复用 collector 的标题、suite、module、分类和手工用例元数据。集合级失败或无法映射的实例要保留诊断。避免按用例名称近似匹配后写错结论或清理另一请求。

## 2. 一条用例怎样结算

同一逻辑实例（unit 与完整 nodeid）在最终汇总中占一行。若运行中产生多次尝试，保留各次事实，最终计数采用框架认可的最后一次有效尝试。重试使用新的请求关联值，失败尝试的证据照常留存。在重试决定或所需 pytest 阶段结果尚未确定时不得提交清理。短 TTL 下，日志证据可先验证并保存。

| 已知事实 | 对外 outcome | 原因与处置 |
| --- | --- | --- |
| 即时阶段、收尾或已声明规则仍在执行 | `pending` | 在当前进度中单独计数。即时已失败但仍须收尾时保留原因，优先显示该原因 |
| pytest 判为跳过且无执行失败 | `pytest_skipped` | 包括 pytest 已认可的预期失败。若已发请求，停止未完成检查并保留日志 |
| pytest 即时检查或收尾已失败 | 沿用即时结果的 `failed/error` | 复用原有 failure 及分类；保存已经得到的日志诊断。尚未执行的步骤标为未执行 |
| 即时通过，完整、可读快照上某条 `assert` 结果为假 | `failed` | `failure.phase=log_assertion`，`classification=failure_type=ASSERTION_FAILURE` |
| 即时通过，证据到期、缺失、采集不完整、HTTP 故障或鉴权失败 | `error` | `phase=log_evidence`。分类为 ENVIRONMENT_ERROR；运行前已知缺 Token 或来源缺完整性能力时用 PRECONDITION_MISSING |
| 即时通过，步骤未绑定、动态 expected 无法冻结、索引或类型等求值异常 | `error` | `phase=log_rule`，分类 TEST_SCAFFOLD_ERROR，写入具体步骤、规则位置和异常。结构或语法错误应在 profile gate 被拦下 |
| 即时通过，全部已声明规则通过 | `passed` | 持久化结果后按策略生成清理意图。此例其他请求任一失败，整例都不申请清理 |
| 用户取消、worker 丢失，或恢复时缺少终态证明 | 受影响且已启动的实例为 `error` | 写明取消、中断或即时结论未知。明确取消结束运行；崩溃后仅在仍有可复核证据时依分片 2 继续 |

同一实例有多项日志问题时，保留各组结果，主原因按“证据或求值错误、断言失败、通过”优先级选取；同一优先级按 profile 声明顺序选第一项。即时失败为主因时继续显示即时失败。已取消/即时失败的用例可以终止仍在等待的日志任务，标注未执行原因，排除自动清理。已选择但从未启动的单元记录在运行中断信息内，避免虚增通过数。

## 3. 结果格式与报告发布

沿用 `result.json`、`report.md`、`junit.xml` 及已有 bucket 和单位目录。启用新链路的 JSON 保留 `run_id/status/summary/modules/cases` 和已有 `failure` 字段。新增以下字段，历史数据缺少它们时按 v0.6.0 的读取方式处理。

| 字段 | 契约 |
| --- | --- |
| `log_validation`（run 级） | `schema_version: 1`、`revision`（本轮单调递增）、`final`、`case_concurrency`、`log_concurrency`、`exit_code`（终态前 null）、`issues[]`。运行级问题写 `kind/unit_index/source_id/request_step/reason/message` 等适用字段 |
| `summary.pending` | 未有最终结论的已启动用例数。在最终报告中为 0。原有 passed/failed/error/pytest_skipped 各按最终实例计一次，run 级问题单列 |
| `cases[].log_validation` | 该用例启用日志规则时含 `unit_index`、`attempt`、`immediate_outcome`、`requests[]`。原有 `cases[].nodeid` 保留完整参数化后缀 |
| `requests[]` | `request_step/source_id/reqId`、`capture_state/availability/version`、`rules[]`、`cleanup`。尚无法取得的值为 null |
| `rules[]` | 规则在 profile 中的路径、阶段、结果、原因；失败项附表达式、期望与实际摘要，以及可定位的 event_id/offset。运行过程中可以为等待状态 |
| `cleanup` | `policy`、`state`、`job_id`、`reason`。状态含 `retain/queued/accepted/failed/unknown`。未返回受理回执时 job_id 为 null |

以下是失败用例的字段节选。事件 ID 与业务值仅供测试夹具使用。

```json
{
  "tc_id": "TC-DEMO-001",
  "nodeid": "test_demo.py::TestScene::test_query[mobile]",
  "outcome": "failed",
  "failure": {
    "phase": "log_assertion",
    "classification": "ASSERTION_FAILURE",
    "failure_type": "ASSERTION_FAILURE",
    "exception_type": "AssertionError",
    "message": "reply 的 SCENE_HIT 事件数期望 1，实际 0"
  },
  "log_validation": {
    "unit_index": 1, "attempt": 1, "immediate_outcome": "passed",
    "requests": [{
      "request_step": "reply", "source_id": "demo", "reqId": "at-example-01",
      "capture_state": "COMPLETE", "availability": "AVAILABLE", "version": 8,
      "rules": [{"path": "case_flows.TC-DEMO-001.log_assertions[0].checks[0]",
                 "phase": "log_assertion", "result": "failed", "expression": "assert len(events) == 1",
                 "expected_summary": "1", "actual_summary": "0"}],
      "cleanup": {"policy": "on_success", "state": "retain", "job_id": null, "reason": "case_failed"}
    }]
  }
}
```

支持取值的断言记录实际操作数；复杂表达式记录已知筛选条件、匹配数及首个相关事件。取值时沿用 `report/sanitizer.py` 的敏感字段和摘要限制，先对字段名和值递归脱敏再截断，Token、鉴权头、完整响应、原始事件正文、SQLite/WAL 不进入报告。请求 ID 及普通业务定位信息按平台授权使用。等待、错误与跳过均须有可读原因。

**汇总和发布时序**

1. pytest 原始 JUnit 写入私有 run 状态区。已选日志用例的阶段事实在 pytest 运行中即可写入，后台任务以已保存事实更新本轮用例结论。发布进度快照时使用 `status=RUNNING`（控制器失联待恢复可显示 INTERRUPTED）、`final=false`、`exit_code=null`。
2. 终态由用例逐层重算 unit、module、task、target、all 的计数，保留 manual、codegen_skipped 等既有统计。在对应 run 目录以临时文件、flush 和原子替换发布。先更新 unit 产物，再写父报告；Markdown 和 JUnit 先完成，最后替换父 `result.json` 作为该 revision 的发布标志。写入异常返回非零，恢复时按持久事实可重复生成同一结论。
3. 为 bucket 中完成发布的同一代报告维护 `latest`。在 bucket 写锁下暂存并替换，保留原有目录形状；读者按受保护的当前版本读。在锁内比较启动次序，恢复旧 run 仅在没有更新 run 占用该指针时更新 latest。使用同一 bucket 的普通 run 发布也遵守此规则。临时文件与数据库留在私有位置。
4. `aitest report` 继续从选定的 JSON 离线重渲染。读取历史报告或刷新 Console 不能触发网络、清理、恢复、补发请求或重写其他 run。对于进行中的报告，输出须标注进度并绑定读取到的 revision；若选择将 Markdown 写回，使用与发布共享的锁并复核 revision 后再替换。

**退出码与 JUnit**

- 已有 env/freshness 门禁沿用 10，pytest 的中断、用法、内部错误和无测试等原始非零码优先保留。单元聚合沿用既有非零码次序处理这些上游状态，再合并本片新增的错误。仅含原有用例时执行旧路径。
- 已到终态且业务实例或运行收尾有失败/错误时返回 1。显式取消返回 2。仅有正常通过或既有合法跳过，且所有声明的清理已受理时返回 0。发布本身失败也返回非零。接入新链路时，正常结论使用 COMPLETED，有失败或运行级问题使用 FAILED_RUN，主动取消使用 CANCELLED，前置门禁保留 BLOCKED_RUN。
- 每个业务实例产生一个 JUnit testcase。业务断言失败写 failure，证据或规则错误写 error，跳过写 skipped。参数化 ID、弃用尝试及附带诊断可放 name/properties/诊断摘要，XML 由标准序列化器编码。仅清理失败时业务 testcase 仍通过，在独立的 `aitest.infrastructure` testsuite 中每个未获受理的清理意图生成一个 error，并使根节点统计和进程退出码反映错误。其他无业务实例归属的致命运行错误采用同样方式。JSON 的业务用例数和基础设施问题数分别展示。
- 对于聚合 run，根 JUnit 收集最终 unit 结果和不重复的基础设施问题。供发布的最终 XML 由持久结果生成。原始 pytest XML 与旧报告都无需经由新的规则求值器再次判断。

## 4. 清理意图、请求与失败恢复

清理策略取分片 1 的组字段 `cleanup: retain | on_success`。同一请求步骤上的显式策略应一致，全未声明时使用 retain。一次用例通过并且明确登记 on_success 后，Kit 可立即为对应请求提交清理。服务端负责实际批量删除。首版每个来源内的单个精确 ID 对应一个清理意图和一个幂等键，便于按用例释放与恢复。

1. 协调器在一个事务内保存用例最终结果，并为每个符合条件的请求插入唯一的清理意图，记录 `source_id/reqId`、UUID 幂等键、固定的提交截止时间和状态。提交事务成功后才可发 HTTP。不同规则引用同一次调用只生成一个意图。关联身份的唯一性是来源接入合同。遇到已知重复绑定时拒绝新绑定，阻止仍可拦截的清理，已受理的任务保留原回执并报告冲突。
2. 使用原 Token 主体调用 `POST /v1/cleanup`，body 为 `{"source_id":"demo","reqIds":["at-example-01"]}`，header 为 `Idempotency-Key`。核对 202、来源、非空 job_id 与目标数后保存 accepted 和回执。run 到此可结束本意图。人工或 Agent 稍后可凭回执查询物理删除状态。[平台精确清理](../log_capture_platform_delivery/02_http.md)
3. 网络断开、响应丢失、可重试服务错误，用同一键、主体和请求体重试。在 `aitest_config/log_assertions.yaml` 的 `cleanup` 段读取 `submit_timeout_seconds`（默认 15）、`retry_initial_seconds`（0.5）、`retry_max_seconds`（3）；各为有限正数，初始值不大于最大值。排队预算从意图入库开始，默认 120 秒，由 `queue_timeout_seconds` 配置。提交预算从首次领取并准备发送时起算，独立于证据读取截止时间。按指数退避，服务端 Retry-After 较长时从其指示，超出剩余预算即结束。鉴权失败、幂等冲突或请求不合法写 failed。若明确从未受理，提交到期记 failed；连接断开等情形无法确认受理状态则记 unknown。两者均计入 run 级问题。恢复只能在平台承诺的幂等有效期内使用原键，意图已过提交期限或无法确认原主体时保留原因供查证。
4. 如果在 202 和本地落盘之间崩溃，恢复使用原键重取回执。若已超过本地期限且未持有回执，则保留 unknown。业务结论先前已持久化，不随 HTTP 重试次数改变。明确 retain、业务失败、取消、共享身份冲突均不提交清理。

清理调度使用独立的提交名额，默认 4 个，由 `cleanup_concurrency` 配置。每个已保存的意图单独提交，退避中的意图不占用 HTTP 名额。状态查询、读证据、执行业务用例均可继续。截止前无法排队发出的意图记 failed。关闭时只汇合本轮已授权的清理意图。

## 5. Console、改动位置与验收

| 实现入口 | 责任与兼容要求 |
| --- | --- |
| `aitest_kit/report/collector.py`、`classifier.py`、`renderer.py` | 保留 `collect_result()`、`render_markdown()` 原有调用。抽出持久结果到 JSON/JUnit 的最终投影，保留旧字段及类型 |
| `aitest_kit/report/cli.py`、`task_runner.py`、`paths.py` | 接入同一结算规则、私有原始 XML 和发布顺序。按文件职责拆分新增逻辑，避免继续扩写大入口 |
| `aitest_kit/console/workspace.py`、`console/jobs.py` | 既有报告列表、详情透出生效的 revision、是否终态和清理问题数。关联活动进程与 run。进程异常消失且没有终态时显示中断/可恢复 |
| `console_web/src/views/RunView.vue`、`ReportsView.vue`、`DiagnosticsView.vue` 及其类型 | 沿用现有刷新机制。显示待验证数、失败表达式和清理回执。运行中用中性状态，取消单列。失败详情读取 `tc_id/failure.classification/failure.message`，兼容旧记录 |
| SQLite 清理意图与分片 1 HTTP client | 用分片 2 同库、同一 run 所有权。Kit 只提交精确请求。权限由日志服务在每次 HTTP 调用中校验 |

实现后至少添加以下定向回归。使用真实临时 SQLite、临时报告目录、确定性 HTTP 替身与事件同步；接口细节见 [第四片端到端验收](04_acceptance_and_agent.md)。

| 场景 | 必须看到的结果 |
| --- | --- |
| A 即时通过/日志失败，B 全通过 | 中间态无假通过，最终各层计数一致；只清理声明 on_success 的 B；A 的表达式、数量、来源可定位 |
| 纯证据错误、求值错误、teardown 失败、跳过或取消 | 同名 TC-ID、参数化和不同 unit 仍能区分；有界摘要与归因正确，不删除失败用例日志 |
| 同请求两组检查，另一请求失败 | 成功前不清理；后一请求失败时，两请求都留存 |
| 模拟受理后丢响应、收到回执前重启 | 同键同目标，平台仅创建一个 job；最终报告记录回执 |
| 所有业务检查通过，清理 403 或提交到期 | 业务计数保持 passed，run issues、Markdown、基础设施 JUnit 错误和 CLI 退出 1 对齐 |
| A 晚于 B 恢复发布、聚合中途崩溃 | 最新报告仍指向较新的 B；A 原目录可重建；离线 report 的内容能复现持久结果 |
| 旧报告、旧 Console、Agent 预检入口 | 原字段、分类、文件名和 Python 调用均可读，干净环境不要求日志平台凭证 |

从 Kit 仓库根运行。下列 `test_log_results.py` 和 `test_log_cleanup.py` 为本片应建立的验证文件。

```bash
python -m pytest -q tests/test_log_results.py tests/test_log_cleanup.py tests/test_report_cli.py tests/test_collector.py tests/test_renderer.py tests/console/test_console_jobs.py
npm --prefix console_web run test -- src/views/ReportsView.test.ts src/views/DiagnosticsView.test.ts src/views/RunView.test.ts
npm --prefix console_web run build
```
