# 分片二 · 并发执行、持久状态与恢复

2026-11-19 · 开发规格。实现基线为 Kit v0.6.0。依赖第一片的 LogAssertionGroupIR、规则执行器和日志客户端，向第三片提供可恢复的阶段事实与检查结果。详细业务判定、报告投影和清理 outbox 由第三片定义。本片完成后仍须在真实日志平台联调。

## 1. 当前入口与本片交付

v0.6.0 的 `report/cli.py` 在 `subprocess.run(pytest_cmd)` 返回后收集 JUnit，`report/task_runner.py` 逐单元执行 suite。Kit 基础依赖含 pytest，尚无 xdist。实施保留 selector 的解析、freshness check、env 加载和 suite 启动顺序，在整轮运行边界增加一个后台协调器。先按原 selector 与 TC-ID 选择解析 suite，freshness 通过后从 gate/IR 的可选 log_assertions 得到候选计划。pytest 完成 `-k/-m` 等 collection 过滤后上报实际实例，在本单元首条业务用例 setup 前完成所选来源的凭证与能力预检。每个 worker 在 collection 完成时上报过滤后的 nodeid，经父协调器确认后才能进入 setup。单元无日志规则时可直接放行。仅有旧用例或有效选择内没有日志规则时不读取 Token、不连接日志平台。

| 影响位置 | 本片职责 |
| --- | --- |
| `aitest_kit/report/cli.py` | 增加两类并发参数和恢复入口，建立父运行上下文，启动/收敛协调器与 pytest，向结果层交接 |
| `aitest_kit/report/task_runner.py` | task/module/target/all 的全部单元复用父运行上下文，suite 即时阶段结束后启动下一单元 |
| `aitest_kit/log_assertions/config.py` | 解析本片配置、优先级和组合校验 |
| `aitest_kit/log_assertions/runtime.py` | 实现第一片的请求步骤上下文、关联绑定和响应输入冻结 |
| `aitest_kit/log_assertions/pytest_plugin.py` | 建立真实用例实例身份，持久化 setup/call/teardown 事实 |
| `aitest_kit/log_assertions/store.py` | SQLite 事务、版本、运行排他、claim 与恢复 |
| `aitest_kit/log_assertions/coordinator.py` | 状态批查、就绪调度、期限、取消及结果交接 |
| `pyproject.toml` 与模板 | 增加 parallel 可选依赖，分发可选配置说明与运行目录忽略规则 |

按职责拆文件，单文件遵循仓库 500 行限制。第三片与本片共用同一个状态库。既有 `collect_result()`、`render_markdown()` 对外签名通过新增调用层适配。

## 2. 两类并发与 pytest 调度

| 参数 | 默认 | 精确定义 |
| --- | ---: | --- |
| `case_concurrency` | 1 | 全 run 同时执行 setup、call、teardown 的 pytest 用例实例上限，用例即时阶段结束即释放 |
| `log_concurrency` | 1 | 全 run 同时对已就绪请求读取一致快照并执行其全部日志规则的上限 |

两者为正整数，拒绝 bool、零和负数。`1 / 1` 表示两阶段各自串行。A 已结束即时阶段但仍等待日志时，B 可以执行。COLLECTING 或 NOT_FOUND 请求等待下次查询时不占日志验证名额。相同请求的多组规则共用一次有界快照。

当前 suite 内允许最多 N 个独立用例执行，后一个 suite 在前一个 pytest 进程退出后启动。前一个 suite 的日志验证可以继续。每个来源、每个 suite、每个 xdist worker 共用父 run 的日志额度。多个独立 CLI run 各有自己的额度，报告记录本轮生效值。

**调度方案。** `case_concurrency=1` 使用普通 pytest 执行。大于 1 时采用 pytest-xdist 的进程调度，参数为 `-n N --dist load --max-worker-restart 0`。固定 suite 内各用例原有步骤顺序。自动 worker 重启关闭后，worker 崩溃产生执行错误，已登记的请求仍按自身状态收尾。Kit 的恢复入口仅恢复日志检查和清理。

parallel extra 首版采用 `pytest-xdist==3.8.0`，该版本声明 Python ≥ 3.9、pytest ≥ 7 和 execnet ≥ 2.1。实施在 Python 3.9 的兼容 pytest 8 组合和 Agent 实际 Python/pytest 组合分别验证并锁定测试环境。目标解释器缺插件时在执行业务前报前置条件错误，提示安装 `aitest-kit[parallel]`。[发布元数据](https://pypi.org/pypi/pytest-xdist/3.8.0/json)

pytest 使用启动 Kit 的同一个 `sys.executable`。Agent 若选择项目 .venv，必须在该解释器中验证 Kit、pytest、xdist 版本，不能依赖机器上另一环境恰好装过插件。日志规则即使只并发 1，也需加载本次升级的 Kit 插件。

**配置冲突。** 新能力生效时 Kit 拥有用例并发配置。检查 CLI 透传、task 默认/unit 的 pytest_args、PYTEST_ADDOPTS 和 pytest 实际加载的 addopts 中的 `-n/--numprocesses`、分发模式、远程 worker 与重启参数。重复指定并发或分发参数应在 collection/fixture 前报错误并列出参数来源，统一改用 Kit 配置。插件在 pytest 配置阶段再次核对实际 worker 数和模式，防止绕过全 run 上限。旧 workspace 未使用日志能力、未显式配置 Kit 并发时继续走原参数透传路径。

**资源隔离。** 开启用例并发的 suite 必须使用可并行的账号、临时数据、业务配置和清理目标。function fixture 创建独立 Python 对象，外部同名资源仍由 Harness 自己隔离。xdist 的 session fixture 会在各 worker 分别执行，共享一次初始化需要明确的业务协调。首版以独立用例并发为验收对象。[xdist fixture 生命周期](https://pytest-xdist.readthedocs.io/en/stable/how-to.html#making-session-scoped-fixtures-execute-only-once)

## 3. 配置与 CLI

可选工作区文件为 `aitest_config/log_assertions.yaml`。进入新增日志或 Kit 并发路径时读取。旧用例无需日志平台配置。下表参数属于一次 run，单元和请求不能分别扩张全局额度。

```yaml
schema_version: 1
platform:
  base_url_env: AITEST_LOG_BASE_URL
  token_env: AITEST_LOG_TOKEN
execution:
  case_concurrency: 1
  log_concurrency: 1
  request_timeout_seconds: 120
  poll_interval_seconds: 1
  http_timeout_seconds: 5
  pending_request_limit: 5000
  snapshot_max_bytes: 8000000
  snapshot_max_events: 10000
  snapshot_max_pages: 1000
  check_timeout_seconds: 2
  cancel_grace_seconds: 5
cleanup:
  submit_timeout_seconds: 15
  retry_initial_seconds: 0.5
  retry_max_seconds: 3
state:
  directory: .aitest/runs
  retention_seconds: 86400
```

platform 的环境变量名可配置，实际值使用既有 env 文件/运行环境加载规则。base_url、Token 在该 run 首次需要日志检查时解析。凭证不写入库或报告，URL 使用 http/https 合法绝对地址。请求发送超时和连接超时均受 `http_timeout_seconds` 限制，且不得超过当前任务剩余期限。

CLI 覆盖顺序为 `--case-concurrency/--log-concurrency` → 工作区文件 → 默认值。未知键报错。超时、轮询、保留期必须是有限正数，字节上限及数量上限为正整数。snapshot 三项最多为示例默认值，允许向下调，首版读取硬上限与第一片相同。运行配置生效值、配置版本和环境变量名写入运行元数据。首版检查组沿用 run 的请求期限，两项并发额度在全 run 内共享。cleanup 的固定截止时间、退避与退出结论见第三片。

```bash
aitest run --suite-file test_workspace/suites/demo/smoke/suite.yaml --case-concurrency 4 --log-concurrency 2
aitest run --task-file test_workspace/tasks/regression.yaml --log-concurrency 2
aitest run --workspace "$ACCEPTANCE_WORKSPACE" --resume "$ACCEPTANCE_RUN_ID"
```

`--resume` 与所有新运行 selector、case 过滤、pytest 参数和并发覆盖互斥，可与 `--workspace` 使用。恢复采用库内保存的规则和运行参数，按保存的环境变量名称重新取得凭证。原 run 内的日志来源不能自动改绑另一日志服务。

首次解析时对规范化 base URL 和当前 Token 分别记录私有运行绑定指纹。Token 指纹采用带每 run 随机盐的 HMAC，盐与指纹仅存私有状态区，报告只记环境变量名。原文凭证、URL userinfo 及带凭证的 query 均禁止入库。恢复比较 URL 绑定，发生变化时拒绝向新目标发送原请求的查询或清理。Token 指纹变化时可以在现凭证重新校验读权限后取证，原 Token 主体无法确认的清理意图交第三片记 unknown，避免重发另一个主体的幂等操作。

## 4. 本地状态与运行所有权

默认状态路径为 `<workspace>/.aitest/runs/<run_id>/log-assertions.sqlite3`，独立于 reports 和 latest。可配置的 state.directory 必须解析到工作区内的本地文件系统目录，校验路径和符号链接。新运行先原子分配目录，run_id 在该工作区状态根内唯一。task 各单元复用父 run_id 和同一库，并保存各自报告路径。恢复通过唯一 run_id 定位，无需从多个 report bucket 猜测。

| 记录 | 标识与必须持久化的内容 |
| --- | --- |
| run | run_id、workspace 身份、selector、各单元和输出路径、Kit/状态格式/规则执行器版本、配置快照、控制状态、owner_epoch、开始/截止/结束信息 |
| case_attempt | `run_id + unit_index + 完整 pytest nodeid + attempt` 派生 case_instance_id。unit_index 采用本轮计划的稳定单元序号，单 suite 固定为 0。保存各 pytest 阶段结果、执行 worker 身份及已知结束事实 |
| request_check | 内部 request_id、case_instance_id、request_step、规则 hash/执行器版本、source_id、关联值、绑定与输入冻结状态、期限、next_poll_at、平台版本和 expires_at、验证状态及 claim |
| check_result | request_id、rule_index、check_index、失败表达式、结论、经脱敏的有限实际值/期望值、证据定位、完成时间 |
| 清理及投影 | 第三片定义的 outbox、幂等键、受理回执、结果投影版本，复用上述事务边界 |

SQLite 开启 foreign_keys、WAL、busy_timeout，连接按进程和使用线程创建，使用参数化 SQL。协调器用一个有界单线程 executor 提交短事务，pytest worker 使用各自同步连接。默认 busy_timeout 为 1000 ms，忙重试服从本地操作/任务期限。写事务只处理本地状态，HTTP、pytest 执行、事件解析和规则运算在事务外完成。输入落库失败时，prepare 阻止对应业务调用继续。已发请求后的状态写入失败需显式报运行错误并保留此前事实。[sqlite3 连接规则](https://docs.python.org/3.9/library/sqlite3.html)

父协调器持有整个 run 的 OS 进程锁。Unix 使用 flock，Windows 使用对应文件锁，持有锁的句柄持续到该次协调结束。第二个同 run 协调器启动失败，不靠“心跳超时”强行抢活。取得锁后事务内增加 owner_epoch。pytest 子进程写入携带本轮 epoch，旧 epoch 的登记、绑定及阶段回执被拒绝，防止父进程退出后遗留 worker 写入新恢复轮次。

每项 READY 任务通过短事务按期望状态与 epoch 条件更新为 RUNNING，附带唯一 claim_token。只有相同 epoch、token 能提交结果。进程重启取得独占权后回收旧 RUNNING claim。终态结果以 request/rule/check 身份唯一约束保存，同一输入重复取证不会重复累计通过数或创建第二个清理意图。

状态目录由 workspace 忽略规则排除。终态状态库保留 86400 秒以供查询/恢复补偿，按 finished_at 起算。每次新 run 启动时对该状态根执行有界维护，只处理 Kit 创建的运行目录，获取其独占锁后再次核验已过保留期、控制状态 FINISHED/CANCELLED、结果已发布且没有待提交清理，再关闭连接并回收该目录。INTERRUPTED、活跃及仍有可恢复清理的目录保留，故障记录后留待下一次维护。内部状态回收与报告产物保留分别执行。

## 5. pytest 阶段与请求登记

新运行通过 `-p aitest_kit.log_assertions.pytest_plugin` 显式启用插件。父进程传入受校验的状态路径、run_id、unit_index 和 epoch。每个真实执行 worker 在 setup 前建立 case_attempt 并分配递增 attempt，以完整 nodeid 保留参数化后缀。使用 pytest 阶段钩子记录 setup/call/teardown。xdist controller 负责子进程完成或崩溃收敛，正常阶段事实由实际执行 worker 写入，重复回执幂等处理。[pytest 阶段钩子](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_makereport)

与第一片的接口接线如下。

1. 生成代码进入 `log_request_step(request_step=..., rules=..., expected_inputs=...)`。scope 在业务调用前同步提交 request_check、静态期望和检查期限，设置 ContextVar。规则与身份完整且待办数量有预算时才进入业务调用。第一片的 `log_capture_requested()` 只在当前有效 scope 返回 true，使共享 Harness 能按此次调用决定是否设置采集参数。
2. Harness 调用 `bind_log_request(source_id, correlation_value)`。来源须与 module 声明一致，关联值为非空字符串，精确保存。重复相同绑定可安全返回，改绑报错误。一个来源内同一关联值已被本轮另一个业务请求身份使用时拒绝，避免重试或并发请求串用。
3. 业务调用返回后，scope.freeze_response(reply) 按 IR 提取并冻结所需响应值。规则仅持有显式的安全 JSON 输入。context 退出时清除，后续线程/异步任务不能冒用已经结束的 scope。
4. 同时具备来源、关联值及全部 required expected 的请求从 PREPARED 转 WAITING。有绑定且静态期望已足够的请求，在业务调用抛错时仍可完成日志验证，所属用例保留即时失败。scope 异常关闭时，未绑定记 LOG_BINDING_ERROR，缺少 required 响应派生期望记 LOG_INPUT_ERROR。
5. 已绑定但尚未冻结响应输入的 PREPARED 项可批查状态以取得 expires_at，验证必须等输入完整。协调器仅使用库内冻结数据。fixture 关闭客户端或业务清理不触发日志删除。

用户显式重试用例时创建新 attempt 和新的内部 request_id。业务协议需要 Harness 为新调用生成新的关联值。后台恢复保留原 attempt。插件或 worker 崩溃导致缺少阶段结果时记录即时阶段中断，不根据日志成功反推业务调用或 teardown 成功。

## 6. 后台调度、期限和取消

父 run 在第一条业务调用前启动后台协调器。协调线程运行自己的事件循环，pytest 使用可取消的 Popen 及有界等待，主线程持续检查取消与后台致命错误。pytest 子进程设置受跟踪的进程组和启动身份，标准输出持续转发，避免 PIPE 堵塞。平台预检只读一次 `get_limits()`，从 `GET /v1/ui-settings` 取得 page_size_max 和 batch_reqids_max，分别取 min(100, page_size_max) 与 min(200, batch_reqids_max)。首版所有日志状态批查串行调度，按同一平台、凭证和 source 聚合。平台返回更低的结构化 limit 时缩批，拒绝循环重发同一超限批次。巡检按来源轮转，优先考虑最早截止时间，空队列使用可中断等待。

新客户端使用 httpx.AsyncClient 与显式 AsyncHTTPTransport，各方法接受关键字 deadline。整个批查或全部分页读操作通过 asyncio.wait_for 受剩余绝对期限约束，响应流在 finally 关闭。连接/读取的单次超时和慢速分块传输均受此总期限约束。客户端取消信号继续向上抛出，协调器不得把主动取消排回重试队列。规则子进程运算和 SQLite 短事务也不在事件循环中执行阻塞等待。

| 验证状态 | 可执行动作与退出条件 |
| --- | --- |
| PREPARED | 意图已保存，尚待绑定或输入冻结。scope 关闭仍缺必需信息时 ERROR |
| WAITING | 批查 NOT_FOUND/COLLECTING，更新 next_poll_at。正常 COMPLETE 且 AVAILABLE 时进入 READY |
| READY | 等待全 run 日志名额，按有效截止时间优先 claim |
| RUNNING | 按平台版本读全部页并执行该请求规则，完成后写 PASSED、FAILED 或 ERROR |
| PASSED / FAILED / ERROR / CANCELLED | 验证终态。仅报告/清理层读取，普通重试不重新执行 |

来源无结束契约在首次执行前报前置错误。INCOMPLETE、TIMED_OUT、已删除或过期直接结束为证据 ERROR。401/403 直接标访问错误，短暂连接故障、429/5xx 按轮询节奏有界重试，遵循在期限内的 Retry-After。重试后再次排队，释放验证名额，避免某个故障请求占住唯一日志槽。

读取端将批查取得的 version 带入首屏 expected_version，逐页核对 request、version、upper_offset、capture_state、availability 和 cursor。409 丢弃当前未完成快照，重回 WAITING，期限保持。410 终结为证据错误。实际响应字节、事件数、页数分别受 snapshot_max_bytes、snapshot_max_events、snapshot_max_pages 限制，游标循环或协议矛盾立即报错。全部页读取并验证完成后，快照可以在本地内存中完成规则计算，日志平台的后续 TTL 不撤销已经取得的完整快照。

读取与执行占同一个 log 名额，每个槽同一时刻最多一次事件 HTTP 请求。状态巡检另有全 run 一个 HTTP 名额，清理提交名额由第三片限制。两类名额分别计数并有测试观测，不能让状态轮询被长时间规则计算阻断。待办预算统计所有未终结请求，达到 pending_request_limit 后新 prepare 明确报容量问题，已登记任务继续收敛。

检查期限在请求 scope 开始时保存为绝对 UTC 时间。每轮调度同时检查本地剩余时间，获知 expires_at 后按更早的时间限制取证。过程内计时使用 monotonic 防止单次等待受时钟调整放大，恢复仍按原绝对截止时间。数据库等待、HTTP、分页、重试与规则执行各受剩余时间限制。完整快照已在期限内取得时，规则计算另外服从 check_timeout_seconds，其结果能在平台日志过期后持久化。

规则通过第一片的受控解释器运行。每个已获得日志槽的请求在可终止的 spawn 子进程执行全部 checks，总计算时间默认 2 秒。超时终止并回收该子进程，记录规则错误。输入字节上限、事件数、表达式/期望值限制和解释器计步预算共同约束资源。子进程退出码异常产生规则执行错误，父协调器和其他请求继续。

取消分显式取消与异常中断。SIGINT、Console 取消或系统终止请求首先停止启动新 suite 与新验证，通知 pytest 进程组收尾，至多等待 cancel_grace_seconds。回收验证子进程并保存已到达结果，未完成项变 CANCELLED。仅对核对过启动身份的本轮子进程组执行结束操作。取消过程中尚未提交的清理意图由第三片保留并标明状态。父进程异常死亡通过进程锁失效和持久事实在下次恢复时识别为 INTERRUPTED。

协调器自身不可恢复的异常须通知主运行停止继续执行，并持久化能保存的失败信息。已有请求与已得到结果保留，主进程输出非零终止结果。日志后台异常不能被打印后忽略、同时让主运行显示成功。

## 7. 恢复与第三片交接

run 的执行控制状态为 RUNNING → DRAINING → FINISHED，另有 CANCELLED、INTERRUPTED。DRAINING 表示所有 suite 的即时阶段已经结束，仍在收敛日志或清理提交。FINISHED 只描述协调已结束，业务通过与退出码由第三片决定。

恢复命令按以下顺序执行。

1. 在原 workspace 定位状态库，校验 schema 和规则执行器版本及记录的输出路径，获取 run 进程锁。状态缺失、版本不可解释或已有活跃所有者时明确失败。使用库内规则与 expected，不用当前 profile 覆盖旧规则。
2. 增加 owner_epoch。若存在先前遗留 pytest 进程，核对其运行身份后有界结束。无法确认的即时执行记录标中断，后续事实不能当作已成功收尾。
3. 校对已有终态及结果投影，回收旧 claim。PREPARED 缺关联或必需 expected 时以明确关联/输入错误终结，已冻结完整输入的任务根据原期限继续批查或直接记超期。内存快照丢失后重新取证，平台已不可用时报告证据错误。
4. run、case、请求和规则身份均沿用原值。普通恢复仅处理异常中断的未完成项以及已有幂等清理意图。已显式取消的检查保持 CANCELLED。FINISHED 且已无待提交项时直接返回其既有结果。
5. 通知第三片按原 run 和 unit 输出位置重新生成结果。只有全部即时执行事实及日志结果满足成功条件时才允许通过。业务调用未得到确定执行结果的旧 attempt 保留中断结果，后台日志通过不足以令它通过。

每个请求的全部检查结果在同一短事务提交，并通知第三片重新计算相关 case/unit/run。第三片在用例即时阶段及日志判定均确定后写清理 outbox，本片提供事务存储与周期调度。清理取得 202 回执或达到提交期限后收敛，物理删除状态不阻塞本轮退出。SQLite 状态提交和文件报告之间由第三片的幂等投影版本恢复，latest 更新须校验当前所有者。

本轮清理 accepted、failed、unknown 独立于业务 verdict。原幂等有效期、本地提交期限或原主体无法确认时不再次发送，交第三片报告原因。纯清理失败返回 1，主动取消返回 2，原 env/freshness 的 10 以及 pytest 自身异常退出码依第三片优先级保留。

状态库保存验证结果后可以释放事件快照。复原报告只读取保存结果和有界证据，不要求日志平台仍保留正文。涉及秘密的环境值、Token 和完整响应不写日志或状态库，响应派生 expected 仅保存作者明确选择且适合保留的字段。

## 8. 测试与验收

新增测试按 `tests/log_assertions/` 组织，pytest 插件/runner 测试必须真实启动子进程并使用隔离状态目录。测试 HTTP 服务可控制状态、分页和阻塞点。使用 barrier、Event、可控时钟及状态轮询，避免依赖几十毫秒 sleep。

| 场景 | 必须验证的结果 |
| --- | --- |
| `1 / 1` | 用例 B 的 setup 晚于 A teardown，A 日志尚未就绪时 B 已发请求。B 先就绪时后台可先验 B。最多一个验证槽 |
| `4 / 2` | 真实 xdist 进程中即时用例同时在途且最多 4，读取/验证最多 2，状态巡检独立有界 |
| task、module、target、all | 多 suite 启动顺序符合原选择器，前 suite 日志等待与后 suite 重叠，全 run 额度不倍增，case-id 过滤准确 |
| 透传与依赖 | 覆盖 CLI、task/unit、PYTEST_ADDOPTS、addopts 的并发冲突。缺 xdist 时业务调用计数为 0。旧纯 pytest 路线保持原行为 |
| 身份与多进程写入 | 同 TC-ID 跨 suite、参数化实例、重复 attempt 均可区分。相同scope重绑被拒绝。竞争 prepare 超上限时只允许预算内调用 |
| 状态机和快照 | 空列表、NOT_FOUND、无 end、损坏、超时、过期、409、410、429、5xx、跨页大小限制、版本变化时无部分快照误通过 |
| 存储故障与 claim | 模拟绑定/冻结前后、结果提交前后中断，恢复保持已提交事实。双协调器只有一个取得锁，旧 epoch/token 的结果不能覆盖新结果 |
| 取消与恢复 | 中断后仍沿用原请求和期限，业务调用计数不增加。显式取消后检查不恢复。已结束 run 重复 resume 返回已有结论 |
| 资源收敛 | 卡住的正则/规则超过计算期限终止子进程，其他请求可完成。取消后子进程可回收，SQLite 能正常关闭及重新打开 |
| 结果交接 | 在持久化后、通知结果层前中断，恢复能按原 run/unit 输出同一组阶段与规则事实，且不会重复执行已完成业务。以记录接收器验收本片，真实报告发布与 latest 的并发回归归第三片 |

实施提交运行 `python -m pytest tests/log_assertions -q` 与现有 run/report、selector、Console 回归。发布验收使用第四片的 Linux/Windows 或 macOS 环境矩阵、真实日志平台和 Agent Runner。每次验证保留命令、退出码、实际生效并发、实际在途最大数和状态迁移证据。
