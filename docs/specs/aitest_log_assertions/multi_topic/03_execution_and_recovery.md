# 分片 03 · 多来源日志的后台执行与恢复

**交付结果**　一条业务调用可以登记多个日志来源。pytest 执行一次 Harness 调用并继续跑用例。父进程分批询问日志平台，每个来源收齐后立即取证。一个来源的等待、快照或断言失败都能定位到对应来源。用例仍只结算一次。[总体评审稿](../multi_topic_review.md)

## 1. 接入现有运行链

| 现有代码 | 本片改动 |
|---|---|
| `log_assertions/discovery.py`、`pytest_plugin.py` | 保留静态发现和选中用例的 collection 预检。按步骤实际需要的来源汇总 read、按 `on_success` 汇总 cleanup。记录预期的步骤和来源，用于发现漏执行。 |
| `log_assertions/scope.py`、`runtime.py`、`store.py` | 将一次登记、绑定、冻结和异常关闭应用到同一步的全部来源。持久化每个来源的独立状态。 |
| `log_assertions/coordinator.py`、`run.py` | 复用父 CLI 的一个事件循环、一个平台客户端与选中的运行配置。负责状态调度、快照取证、终态写入和恢复。 |
| `log_assertions/cleanup.py`、`projection.py` | 按整例决定清理资格，把同一步不同来源的结果投影到同一条用例。报告字段及验收见[分片 04](04_reports_and_acceptance.md)。 |

以上路径相对于 `aitest_kit/`。当前 `RunStore` 有两项唯一约束 `(attempt,step)` 和 `(source,correlation)`，`plan_sources()` 只读 wrapper 的 `source_id`，`Coordinator.poll()` 每批挑一个 source，`expire_waiting()` 将到期统一记为 ERROR。这四处都影响完整运行链。保留无日志且未显式配置并发的 pytest 快路径。

## 2. 一个步骤登记多个来源

以步骤 `reply` 为例，三组断言的原始 `group_index` 为 0、1、2，分别绑定 main、perf、main。落库两行，main 保存组 0 和 2，perf 保存组 1。两行引用同一 attempt、step、截止时间和 Harness 提交的关联值，各自保有规则、输入、版本、领取标识和结果。仅选择 perf 时只产生 perf 行。先按本步骤列表的位置逐项配对规则和输入，再按实际来源分组。报告保留 flow 的原始 `group_index`，多步骤交错声明时这些下标可能不连续。

1. **发现计划。** [分片 02](02_profiles_and_binding.md) 的 wrapper 继续传模块默认 `source_id` 作为 Harness 绑定锚点。如果任一组显式选择了 `source`，该步骤所有 compiled rules 均含已解析的 `source_id`，按实际值分组。原 0.7 形状的 rules 全部没有该字段，全部归 wrapper 的来源并保留旧的超时分类。仅显式选择单个别名的步骤也启用新分类。半数规则带字段、字段类型错误等损坏的计划须报错。收集、执行与报告复用同一份分组结果。
2. **登记。** 保留 recorder 的 register/bind/freeze/fail 调用形态，handle 可持有多个内部 request 行 ID。进入 scope 一次计算 `deadline = 当前时间 + request_timeout_seconds`。在同一个短写事务内按去重后的来源数检查 `active + 新增行数 <= pending_request_limit`，登记全部 PREPARED 再调用 Harness。预算不足时零新增行、零业务调用。两次同时申请最后一个名额不能突破上限。一个来源内多组不重复收费。
3. **绑定。** `bind_log_request(source_id, correlation_value)` 校验当前 scope、线程、默认锚点和非空关联值，在一笔事务将该值绑定到所有行。scope 有效期间重复同值返回成功，改值报绑定错误。跨来源相同 reqId 合法；同一实际来源和 ID 已属于另一业务调用时，拒绝本次整步绑定，记录冲突原所有者，禁止对有歧义的精确目标新提交清理。多项同时冲突须记录全部。冲突登记需能随正常提交持久化，返回异常不能把标记一并回滚。保留已有受理回执。
4. **冻结。** 汇总并校验响应指针、变量及安全 JSON 大小，然后在一笔事务将已配对的冻结输入分发到对应来源行。若任一必需输入缺失，整步记录 `LOG_INPUT_ERROR`。未绑定或绑定失败使用 `LOG_BINDING_ERROR`。已绑定、全部期望都是静态值时，业务异常仍可关闭 scope 并让后台取证，原 pytest 异常保留。重复 freeze、已关闭句柄、源行状态不相符均不可覆盖已提交结果。绑定和冻结的并发读者只见提交前或提交后的整步状态。
5. **交还 pytest。** fixture 释放业务资源，pytest 继续下一步。后台可在已绑定 PREPARED 时提前查询状态并保存观测；看到 COMPLETE 后等待冻结，复用该版本进入 READY。遇到平台终态也保留观测，完成冻结后再按下表裁决。等待绑定或输入的责任仍由 scope 及回收逻辑承担。

## 3. SQLite 格式与迁移

新库采用 `PRAGMA user_version=2`。每行 request 的业务键改为 `UNIQUE(attempt,step,source)`，保留 `UNIQUE(source,correlation)`，其中未绑定的 correlation 仍可为空。保留按调度状态、下次查询时间、截止时间取队列的索引。

| 需要持久化的事实 | 用途 |
|---|---|
| 每行的计划语义版本 | 旧单来源步骤用旧分类，新格式步骤用本片分类。恢复读取已保存的计划。 |
| 每个来源预检时协商的 `evidence_view` | 在登记时保存其视图或引用同事务可见的持久预检记录；v1 历史来源为 `single_partition`。恢复检查原视图与新发现一致，变化时报告来源能力错误。 |
| 每个选中 nodeid 所声明的 `(step,source)` | 即时阶段全通过但某个应执行的来源从未登记时，产生 `LOG_INPUT_STEP_NOT_EXECUTED` 并禁止清理。v1 原有仅记 step 的声明仍用原匹配规则。 |
| 最近一次通过协议校验的状态 `last_observation` | 包含 kit 收到响应的 `observed_at`、`result`、`capture_state`、`availability`、`version`、`event_count`、`expected_event_count`。时间对外用 UTC RFC3339。NOT_FOUND 的 Request 字段均为空，旧平台未提供的字段为空。尚无成功响应则整项为空。 |
| 最近未恢复的轮询错误 `last_poll_error` | 只含受控错误码 `code` 和时间 `at`。下一次有效状态响应清空该错误。计数和错误用于诊断，完成判定只使用平台的状态与可用性。 |

在 `LogRun.open(resume=True)` 取得原 run 的进程锁并核对身份之后、开放 worker 或协调器之前，识别当前库版本。迁移 v1 时在单一 SQLite 事务重建 request 约束，逐列拷贝原主键，新列赋旧语义及空观测，再重建索引并补齐声明记录结构。保留旧 request ID、关联值、期限、规则、冻结输入、状态、run/attempt、epoch、result、冲突标记、清理幂等键及已有回执。不回读 workspace 猜测旧声明的来源。

需要暂关外键建表时，在事务外只对专用迁移连接切换 `foreign_keys`，在提交前执行 `foreign_key_check`、比对行数及子表引用，恢复开启检查。避免 `executescript` 的隐式提交拆散迁移事务。迁移事务内更新库版本并递增 owner epoch，旧 worker 在锁释放后写入会被 epoch 校验拒绝。异常回滚后仍能以 v1 重试。v2 重开不重建表；未知版本拒绝写入。历史报告已发布的返回码及输出不因升级改变。

## 4. 预检、轮询与快照

预检沿用 `GET /v1/sources` 和 `GET /v1/ui-settings`。取选中用例实际需要的 source_id，逐个检查 enabled、read、可用快照能力以及显式要求的 cleanup 授权。新 `partitioned` 视图即使 `completion_supported=false` 也可用；旧来源无 `evidence_view` 时由原单分区能力判定。无完成契约来源在业务调用前报前置错误。显式只测 perf 时无需有 main 的读取授权。

| 运行条件 | 调度动作 |
|---|---|
| 平台声明 `readiness_batch_supported=true` | 同一客户端、凭证下将到轮询时间的唯一 `(source_id,reqId)` 混合提交到 `POST /v1/requests/readiness`。每批最多 `min(200,batch_reqids_max)` 对，逐项验证顺序与双键，缺项、重复、错序或内外来源不符均视为整批协议错误；完整响应通过校验后才应用各项。 |
| 能力缺省或为 false | 对有兼容完成状态与快照能力的来源使用既有 `POST /v1/requests/status`，同一来源多个 ID 一批。已经宣告新接口而返回 404、403、坏响应时直接报告错误。 |
| 待查多于一个批次 | 全 run 最多一个状态 HTTP 在途，循环发后续到期批。优先临近截止并轮转来源，保证低流量来源也进入批次。422 TOO_MANY_TARGETS 附更小合法上限时按新上限拆批；无有效降幅时终止该次错误。短暂的 408、429、5xx 和连接故障按剩余期限与 Retry-After 有界重试。 |
| 一项 COMPLETE + AVAILABLE 且输入已冻结 | 该项退出常规轮询，按有效截止时间领取 READY。带 `source_id,reqId,expected_version` 读取这一来源全部页，每页含 data。按协商视图取单分区或跨分区快照，完成后执行此来源全部组一次。409 换版时丢弃所有旧页、退回待查，保留原截止时间；其他项独立推进。 |

跨分区的排序、协议校验与完整页集见[客户端分片](01_platform_client.md)及[平台交接稿](../../log_capture_platform_delivery/07_observed_topic_handoff.md)。只能使用单个完整版本。已有 `snapshot_max_bytes/events/pages` 限制适用于每份完整快照，事件正文仅在内存中用于规则求值。并发限制仍全 run 共享，`case_concurrency` 限制 pytest，`log_concurrency` 限制取证及规则任务，状态轮询单独占一个 HTTP 名额。轮询查询只读调度所需字段，领取验证任务时才读取规则和冻结输入。批查 HTTP、分页、规则子进程均在 SQLite 写事务外运行。

以 30 个不同 reqId 同时各等 3 个来源为例，B=200 时一个新接口调用可查 90 对；旧接口用三个同源批次。若其中两类均已 COMPLETE，下一轮只含尚待查的 30 对。状态 HTTP 不返回正文。正文请求数取决于每个来源各自的页数。

## 5. 期限、故障与结果

所有来源共用步骤登记时的绝对截止时间。查询、翻页及重试使用剩余时间；单次 HTTP 不超过配置上限和所选项最短剩余预算。有期限临近的项造成批查询中止时，仅已到期项结算，其余按自己的期限重新调度。发现 `expires_at` 后，按它与业务截止时间中更早者限制取证。已在期限内取得完整快照时，规则计算服从现有独立的 `check_timeout_seconds`。

| 新语义步骤在该来源上的事实 | 该来源结论 |
|---|---|
| 有效响应为 NOT_FOUND 或 COLLECTING + AVAILABLE；到业务截止仍未收齐，最近状态之后无未恢复轮询故障 | `FAILED / LOG_READINESS_TIMEOUT`，阶段 `log_evidence`、分类 `ASSERTION_FAILURE`。平台明确返回 TIMED_OUT + AVAILABLE 时立即作相同裁决。 |
| 截止前始终未得到有效响应，或最后一次未齐后持续断网、限流或服务出错 | `ERROR`，在 `log_evidence` 暴露最后已知错误或证据超时。保留最后有效观测与时间；无观测时显示未知。 |
| 先遇 TTL、DELETE_PENDING、DELETED、EXPIRED、已知缺口 INCOMPLETE、意外 OBSERVED、不可解析响应、鉴权失败 | 证据/权限/协议 `ERROR`。同时有可用性和采集错误时优先解释证据不可用。 |
| 平台已报 COMPLETE，但验证槽排队、分页、版本争用或读取故障耗尽预算 | 取证 `ERROR`。要保留已收齐来源的观测。规则表达式求值为假为业务断言 `FAILED`，规则运行异常为 `ERROR`。 |

0.7 形状的规则和迁入的 v1 行继续走现有超时/不可用分类。在线轮询和 `--resume` 的到期收尾使用相同判据。超时裁决先检查持久化状态、观测、最近故障及实际到期原因，通过一笔带条件的写事务结束该行。过期响应、已取消任务或旧 claim 不能覆盖终态；未开始断言的规则不能显示为 passed。

## 6. 恢复、结算与清理

- **恢复。** `aitest run --resume RUN_ID` 读取原库的计划/规则版本、绝对期限、环境文件引用和平台身份绑定；继续使用原 run 的有效地址。地址身份不符时拒绝访问。Token 变化时按既有策略重新验证读取授权，原清理主体无法确认时置 unknown。待处理项重新协商能力，使用同一入口的隧道，业务调用数保持不变。
- **恢复断点。** 对已绑定但未冻结的 PREPARED 行按步骤整体关闭。全部所需期望为静态时可继续，否则缺少响应值标输入错误。未绑定标绑定错误。READY/RUNNING 依既有 owner epoch 和 claim 机制回到待查并重新验证版本；已落库终态保持。进程退出前已确定 COMPLETE、之后错过取证期仍报取证 ERROR。显式取消保留 CANCELLED，缺少即时阶段事实的 attempt 保留中断。先结算可能产生的 outbox，再判断是否要加载凭证；重复恢复不会重发已受理清理。
- **整例结算。** `settle()` 核对已关闭的最后一次 attempt、pytest setup/call/teardown、每个声明的 `(step,source)` 及全部来源终态。沿用即时阶段既有优先级；即时通过时，来源中有 ERROR 则用例 error，否则有 FAILED 则 failed，全通过才 passed。迟到的另一来源仍在期限内独立收尾，保留其诊断。过往 attempt 仅供历史查看。JSON、Markdown、JUnit 对每个用例计数一次。
- **清理。** 仅整例 passed 后，在结算事务为显式 `on_success` 的每个实际 `(source_id,reqId)` 写一次 outbox。同源多组共用意图，未声明来源、冲突目标、整例失败/超时/跳过/中断均无新提交。服务端受理及重放沿用原幂等键和重试期限；一个源清理受理不影响另一个同名 ID。未提交、受理失败、回执不明的结果沿用原报告语义。

## 7. 本片验收

| 测试组 | 可观察的通过条件 |
|---|---|
| 绑定与容量 | 三组 main/perf/main 登记两行且原组序号无损。纯 perf 只有一行。重复同值绑定成功；冲突、容量不足、模拟第二个来源写入失败都不能留下半步绑定或部分冻结。用两个独立连接竞争名额与关联值。 |
| 调度与并发 | 记录每轮端点、组合、事件页及在途数，验证同批跨源、拆批、旧接口降级、403 无降级、同源组共用快照。main 先完成时 perf 仍轮询；在 perf 放行前另一个 pytest 用例已完成即时阶段。 |
| 超时分流 | 注入时间并分别返回 NOT_FOUND、COLLECTING、TIMED_OUT、INCOMPLETE、410、持续断网、先 COLLECTING 再持续断网、COMPLETE 后读取超时。逐项核对来源结果、原因、观测时间、用例退出码及零清理。旧规则重跑保持 0.7 分类。 |
| 迁移与恢复 | 用真实 v1 结构造含未完成请求、终态结果、冲突和已入队清理的库。验证行 ID、外键、原 deadline、结果、幂等键；注入建表或数据拷贝中断可重试。验证 v2 新建及重开、未知版本拒绝写、旧 epoch/claim 无法补写。 |
| 结算与清理 | 同一步一源通过一源超时，报告仅一条 failed 用例、显示两源结果，清理提交数为零；整例通过按声明源提交，默认保留。模拟绑定后、冻结后、分页中、结算与提交之间崩溃并恢复，业务总调用一次。 |

在现有 `tests/test_log_assertion_binding.py`、`tests/log_assertions/` 中补充对应回归，优先使用可控时钟、事件屏障和环回 HTTP 记录器。实现后的分片验证入口如下。

```bash
python3 -m pytest -q tests/test_log_assertion_binding.py tests/test_log_platform_client.py tests/log_assertions
```
