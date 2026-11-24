# AITest 多 Topic 日志断言 · 评审稿

**日志平台判定各来源是否收齐，AITest Kit 消费判定结果。** 一个来源对应一个集群里的一个 topic。生产方与日志平台约定主链路的 END，以及异步来源应收哪些记录、收多少才算完成。Kit 只需要知道本次业务请求的关联 ID、用例依赖的来源和内容断言。

## 1. 一条用例的执行过程

以一条同时验证主链路和性能日志的用例为例。

| 平台返回的事实 | kit 行为 |
|---|---|
| 业务请求刚发出 | Harness 只绑定一次关联 ID。后台登记两个来源和同一个截止时间。pytest 继续执行即时断言和后续用例。 |
| 主链路 COMPLETE + AVAILABLE，性能 COLLECTING | 主链路进入证据读取队列；读完并验证后保存结果。下轮只查性能。入湖来源不属于本用例，全程不用查。 |
| 性能 COMPLETE + AVAILABLE | 读取平台给出的版本，执行性能日志断言，合并即时检查与各来源结果。整例通过后，才提交显式声明的逐来源清理。 |
| 截止时性能仍 COLLECTING 或 NOT_FOUND | 新多来源用例记 FAILED / LOG_READINESS_TIMEOUT，命令退出非零。报告显示主链路结果、等待中的性能来源和最后一次平台响应时间。保留证据。 |

从请求步骤登记时起共用 execution.request_timeout_seconds，现版默认 120 秒，默认轮询间隔 1 秒。翻页、重试和恢复沿用同一截止时间。平台明确返回采集超时也使验证失败。鉴权失败、持续断网、证据过期或有缺口归为基础设施 ERROR，命令同样非零。平台附带的已收条数可供排障；kit 不用条数推导就绪。没有成功的状态响应时，报告显示“未知”。

## 2. 轮询与正文读取

**现版 0.7.0。** 协调器在已到查询时间的请求中轮流选来源。POST /v1/requests/status 每次带一个 source_id 和一批 reqIds，批大小取平台限制与 200 的较小值。轮询只查状态。状态就绪后调 GET /v1/requests/{reqId}/events，带 source_id、expected_version、include_data=true 和 page_size，每页最多 min(平台上限, 100) 条。有 next_cursor 才请求下一页。客户端在预算内收齐同一版本的所有页，再在本地按 eventType/stage 筛选，多组 checks 共享这份快照。版本冲突或游标失效会丢弃该次分页、重新查询。现版校验单分区 offset 顺序，每份快照默认上限为 8,000,000 字节。

**拟议接口。** 状态以一对 (source_id, reqId) 为单位；HTTP 按同一平台、同一凭证把到期未完成的对合批。平台声明 readiness_batch_supported 时，kit 使用 POST /v1/requests/readiness，发送 items 数组，逐对读取平台返回的 FOUND/NOT_FOUND、Request.capture_state、availability 和 version。按对数限流、去重、拆批；优先临近截止的项并避免单一来源长期占用队列。未声明批量能力时，保留同源 status 分批路径，前提是来源能够提供兼容的完成状态和快照。缺少完成契约的来源在预检中指出。

以同一轮 30 个到期 ID、每个查 3 个来源、批上限 200 对为例：逐条查要 90 次 HTTP；现有按来源分批要 3 次；混合批查要 1 次，返回 90 个状态项。已有两类完成时，下一轮只剩第三类的 30 项。此处估算的是同一轮待查项的网络往返；30 个新请求/秒可能累积更多在途项。平台按复合键集合读取状态元数据，SQL 查询计划与真实隧道延迟留待压测。

**取证仍按单一来源和请求分页。** 主链路用原单分区事件页；允许跨分区的来源依据平台快照能力使用 evidence_view=partitioned，按 (partition, offset) 验证稳定分页和唯一性。仅接受 COMPLETE + AVAILABLE 的一致快照。平台提供 event_count 供校验传输是否缺页，业务内容断言也可以检查条数，这两处都发生在平台已确认收齐之后。并发数沿用 case_concurrency / log_concurrency；等待状态无需占用取证名额。

## 3. 配置与兼容

**日志平台连接地址直接放在 `aitest_config/log_assertions.yaml`。** `aitest run` 会自动读取此文件。下面的 `platform.base_url` 是本次 kit 升级新增字段；token_env、并发、轮询和超时是现有配置。示例地址仅说明格式，运行时使用当前任务已授权的日志服务入口。

```yaml
schema_version: 1
platform:
  base_url: http://bridge.example.invalid:21001
  token_env: AITEST_LOG_TOKEN
execution:
  request_timeout_seconds: 120
  poll_interval_seconds: 1
```

显式 base_url 优先。省略时沿用 0.7.0 的 base_url_env（默认 AITEST_LOG_BASE_URL）；旧 workspace 无需迁移。显式空值、非 HTTP(S) URL 或含用户信息、查询串、片段的 URL 报配置错误。允许保留服务基础路径。Token 继续按 token_env 从任务运行环境或已有的凭证文件加载。实现时，单 suite、task、并发执行、来源预检、后台状态查询、分页和清理均复用同一解析结果。恢复使用原运行的地址绑定和凭证校验，避免转到其他任务入口。验收覆盖 YAML 直配、旧变量兼容、两种地址同时存在、无效地址、运行间配置变更及恢复。

模块来源映射、组级来源选择与检查表达式分别放在 module.yaml 和 suite profile；Topic、END 条件与应收数由日志平台服务端维护。

模块维护日志来源别名，suite 只在对应断言组选择来源。以下为拟新增配置。其中服务请求的采集参数和 ID 注入方式仍由各自的 Harness 决定。

```yaml
log_capture:
  source_id: mixer-main
  sources:
    performance: {source_id: mixer-perf}
    lake: {source_id: mixer-lake}
```

```yaml
log_assertions:
  - request_step: reply
    select: {eventType: ROUTE_DECISION}
    checks: ['assert len(events) >= 1']
  - request_step: reply
    source: performance
    select: {eventType: PERF}
    checks: ['assert any("duration" in e["data"] for e in events)']
```

省略 source 使用原默认来源。旧 profile、bind_log_request 签名、旧生成结果、旧运行的结算分类和默认保留策略继续兼容。source 名称、topic、END 值和采集阈值均无须硬编码在 kit。多组共享同一步骤同一实际来源时只登记一次，复用同一快照；组间清理声明不一致时在 profile gate 报错。

| 改动范围 | 实现与验收点 |
|---|---|
| Registry / profile / codegen | 模块声明别名，suite 选择来源。validate-profile、dump-ir、explain、预检显示所需来源、读取权限和清理权限。更新 schema、说明和模板 skills。 |
| 绑定、SQLite 和恢复 | 将现有 UNIQUE(attempt,step) 扩展到 (attempt,step,source)，保留 (source,correlation) 冲突保护。注册、绑定、冻结断言输入时事务化覆盖相关来源。旧运行库按版本迁移，保留历史结果、截止时间和清理幂等键。恢复只继续未结算项，不重发业务请求。 |
| 协调器 / HTTP / 报告 | 状态合批，按来源版本分页。报告按一条用例计数，展开显示每个来源最后状态、检查结果及失败原因。清理范围仍是整例通过后声明 on_success 的精确 (source_id, reqId)。 |

## 4. 云端任务的 Windows 隧道与权限

已核对 naiyue-test-agent 工作区 HEAD 493bb43、aitest-kit v0.7.0。云端模板依赖锁为 0.7.0，实际任务优先使用项目 .venv。

```text
Runner 容器 / aitest run 的后台协调器
    → 开发机的 connect_host:connect_port
    → 已建立的 SSH 反向转发 → Windows → 日志平台 HTTP 服务
```

**现状。** Agent 的 cloud_runner/kernel.py 将当轮 command.services 放进模型上下文；kit 工具使用 bootstrap.tool_environment 创建子进程。aitest_kit 工具接收 CLI 参数和 timeout，目前没有单次设置 env 的参数。单独一次 Bash 的 export 不会传给随后另一次 kit 工具调用。kit 协调线程使用同一次 CLI 的运行环境，HTTP 客户端直连配置 URL；状态和事件页共用这一入口。

**云端使用流程。** Windows 负责建立 SSH 隧道。各任务有独立可写的工作区，Agent 在启动 kit 前，从当轮已授权的日志服务入口读取 connect_host、connect_port 及原基础路径，写入本任务 `aitest_config/log_assertions.yaml` 的 `platform.base_url`。只更新这个字段，保留已有的超时、并发与凭证引用。文件不存在时可在授权范围内创建。Runner 已提供当轮路由；当前版本没有自动写回 YAML 的步骤。项目执行说明可约定 Agent 在每次新运行前核对并维护该字段，仍需遵守部署权限和项目授权。

同一命令适用于不同用户和任务。升级后，suite 和 task 都走 YAML 自动加载入口，无需为隧道地址设置 AITEST_ENV_FILE 或追加 task.env_files。任务原有的业务参数与 Token 仍可沿用自己的加载方式。切换入口只影响新发起的运行。

**连通条件。** 当前使用明文 HTTP，平台需接受桥接 URL 发送的 Host（含端口）。按原 Host 路由或 HTTPS/SNI 的目标需保留原 authority。Windows 的“测试端口”只验证 Windows 到目标的 TCP 连接。最终验收应从同一 Runner、同一 Python 带认证调用 /v1/sources 和 /v1/ui-settings，再执行一条真实日志断言用例。[平台 HTTP 配置契约](../log_capture_platform_configuration.md)

## 5. 交付顺序

平台先实现并发布[平台接口交接稿](../log_capture_platform_delivery/07_observed_topic_handoff.md)的来源完成状态与可发现能力；kit 再实现多来源绑定、合批轮询和版本化快照读取。覆盖旧用例、仅异步来源、混合状态、超批上限、部分来源超时、跨分区翻页、恢复和失败零清理。在新 kit 上验证两个任务从各自的 log_assertions.yaml 读取不同入口，并经各自隧道执行真实状态查询。公司 Windows、SSH 与实际部署仍需在目标环境联调。
