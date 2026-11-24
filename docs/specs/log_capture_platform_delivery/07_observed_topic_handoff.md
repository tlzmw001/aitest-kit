# 日志平台开发交接 · 多 Topic 收齐状态与事件查询

**交付目标**　日志平台回答“哪个来源的哪个请求已经收齐”。业务方和平台约定每个来源的完成条件，由平台在入库时计算、持久化并返回结果。AITest Kit 声明需要哪些来源，批量查状态，在来源返回 `COMPLETE + AVAILABLE` 时读取对应事件。等待期限和断言归 kit。本文为平台 v1 的增量契约，开发时先在实际仓库核对已有实现。

## 1. 平台如何认定收齐

每个 `source_id` 绑定一个集群和 topic，业务关联 ID 沿用 `format_ref` 映射成公共 `reqId`。一次调用的相同 ID 在各来源独立收集、授权和清理。

| 平台完成条件 | 入库时的状态转换 |
|---|---|
| 主链路的生产端 END | 沿用原单分区契约。此前事件与正常 END 已持久化、完整性检查通过后发布 COMPLETE。 |
| 异步来源的约定条数 | 首条有效事件使请求进入 COLLECTING。对同一来源和 ID，去重后有效事件数达到生产方约定的总数 N、所有这些事件均可查且无已知缺口时发布 COMPLETE。允许乱序和同一来源内跨分区到达。 |
| 无法声明结束条件 | 沿用 OBSERVED 供人工查询。此类来源无法向自动化承诺已收齐。 |

**按 Topic 配置。** 在 `log-platform.yaml` 中，每个 `sources[]` 项的 `cluster_ref/topic_env` 唯一绑定来源，`completion` 决定如何收齐。三类来源可共用同一个 `format_ref`。下面是各来源取自[完整配置示例](../log_capture_platform_configuration.md)的字段：

| 示例来源 | 该来源的 completion | 同一个 reqId 何时收齐 |
|---|---|---|
| source_a（主链路） | `{path: /eventType, equals_env: ADS_NORMAL_END_TYPE}` | 同一分区内收到生产方确认的结束值，结束事件及之前的事件已入库 |
| source_perf（性能） | `{mode: expected_count, count: 2}` | 收到两条独立业务事件，允许乱序或跨分区 |
| source_lake（入湖） | `{mode: expected_count, count: 1}` | 收到一条独立业务事件 |

**加载与兼容。** 显式 `sources[].completion` 整体覆盖格式默认值；省略时继承 `formats.<format_ref>.completion`。无法承诺收齐的来源显式填 `none`。两处均未配置、混用 END 与计数字段、未知字段、非法 N 均启动报错。N 是生产方约定的正整数，上限为 `ingest.max_events_per_request`。计量单位是一条成功入库的 Kafka 业务事件。JSON 的字段数、下载文件数或 HTTP 分页数都不参与计算。两个示例数字待实际接入时替换。

**在途请求。** 首次入库时为该请求固定有效策略的不可变版本、应收总数及去重口径；重放、重启和配置切换不得改变既有请求的结论。来源变更按配置手册的排空与分区切点流程处理，保留旧版本供已采集记录使用。同模式改 N 或 END 值不改变分页能力。若从 END 切换到计数或 none 等不同视图，应停用原消费者并为新策略使用新 source_id，保留旧来源的查询与清理能力。若要复用原 ID，须排空在途与积压，等旧快照及清理保留窗口结束再切换。

**条数作为完整性承诺的前提。** 示例的 2 表示业务方承诺每个适用请求恰好应有两条独立记录。如果条数随请求变化，先由业务方给平台提供该 ID 的权威应收数或结束信号；仅凭当前已入库条数无法推出最终总数。可能合法为零且没有事件通知的平台也无从区分“尚未发出”和“本次确实为零”。这两种情况不要配置一个猜测常量发布 COMPLETE。

**并发与迟到。** 同一事务写入事件、累计有效条数、状态和版本，提交数据库后再推进 Kafka 消费位置。相同 (source_id, partition, offset) 重放时不增加条数和版本。未配置额外标识时，启用计数的前提是生产方保证不同 Kafka 位置对应不同业务记录。生产方可能以新 offset 重投同一事件时，需在计数策略配置 `event_id_path`，例如 `/eventId`。取值为非空字符串，在当前 (source_id, reqId) 内唯一。相同业务键和相同业务 JSON 值（类型敏感、对象键顺序无关）只计一次，消费位置照常推进。业务键缺失、类型不符或同键内容冲突时记录原因，置为 INCOMPLETE，不将冲突记录用于凑足 N。已收齐后又出现新的有效业务记录违反约定，将该来源请求置为 INCOMPLETE、递增版本并记录额外事件原因；同批越过 N 时直接发布 INCOMPLETE。先前已交给消费者的结果无法追溯撤回，这也是上线前必须确认条数契约的原因。

已知缺口、截断、坏记录、超限及超时沿用既有不可用/不完整状态。TTL、删除标记和容量保护仍对所有来源生效。跨分区聚合需要保留每条事件的 partition/offset；仅 END 类型沿用“跨分区为生产协议异常”的规则。

## 2. 批量查状态，逐来源返回结果

支持新接口的平台在 `GET /v1/ui-settings` 返回 `readiness_batch_supported=true`。新增 `POST /v1/requests/readiness`。一次请求可以覆盖不同来源及不同请求 ID。只查待等待的组合，按授权后的 (source_id, reqId) 索引批量读请求状态表；状态轮询不读事件正文，也不在每轮重新统计事件表。若数据库按来源分表，可在一个 HTTP 请求内按来源分组查库。

请求体示例：

```json
{"items":[{"source_id":"main","reqId":"r1"},{"source_id":"perf","reqId":"r1"},{"source_id":"perf","reqId":"r2"}]}
```

200 响应含同序、逐项对应的 `items`。示例仅摘录 Request 的关键字段，实际 `request` 沿用现有完整对象与空值规则：

```json
{"items":[
  {"source_id":"main","reqId":"r1","result":"FOUND","request":{"source_id":"main","reqId":"r1","capture_state":"COMPLETE","availability":"AVAILABLE","completion_basis":"producer_end","version":3,"event_count":3,"expected_event_count":null}},
  {"source_id":"perf","reqId":"r1","result":"FOUND","request":{"source_id":"perf","reqId":"r1","capture_state":"COLLECTING","availability":"AVAILABLE","completion_basis":"expected_count","version":1,"event_count":1,"expected_event_count":2}},
  {"source_id":"perf","reqId":"r2","result":"NOT_FOUND","request":null}
]}
```

- 完整 Request 新增 `expected_event_count`：计数来源返回该请求首次入库时固定的 N，END、none 或只有删除标记时返回 null。与 event_count 一起供人查看“已收/应收”。kit 只消费平台状态、可用性与版本。已过期或清理仍有元数据时返回相应 availability。
- 每批含 1 至 `GET /v1/ui-settings` 返回的 `batch_reqids_max` 个唯一组合。同一个 ID 分属两个来源占两项。超限返回 422 TOO_MANY_TARGETS 并给出上限，客户端分批提交。每个成功响应覆盖整批；无需状态响应游标。实际待查 K 项、批上限 B 时，每轮 HTTP 次数为 ⌈K/B⌉。已收齐的组合退出待查队列。
- 逐项核对 Token 对来源、前缀及 read 的权限，任一越权整批返回 403；重复/无效组合返回 422。保留 `POST /v1/requests/status` 的原请求、原响应和授权约定，缺少批查能力标志时，kit 可对已支持状态和快照协议的来源回退到按来源批查多个 ID；来源缺少必要能力则预检失败。运行中协议或授权错误直接报告，不以回退掩盖错误。

## 3. 收齐后的正文读取

沿用 `GET /v1/requests/{reqId}/events`。每次只读取一个 (source_id, reqId) 的一页事件。query 带 `source_id`、状态响应的 `expected_version`、`include_data=true` 与 `page_size`；有 `next_cursor` 时附 cursor 读下一页。自动化读取整份来源快照，再按断言组筛选；一个来源有多个断言组也只取这份快照一次。

- `GET /v1/sources` 在可以自动化读取的来源上公布 `evidence_view`。原 END 来源为 `single_partition`，旧平台缺省时仍按现有单分区能力协商；新计数来源为 `partitioned`。为兼容 0.7.0，`completion_supported` 继续表示旧客户端能走的单分区 END 快照能力，计数来源返回 false。新客户端通过 `evidence_view=partitioned` 识别可读取的新来源。纯观察来源无可断言视图。
- END 来源继续使用已有 GET 参数和响应（含 `upper_offset`）。计数来源的普通 GET 供人工浏览，未收齐时可查看当前可用事件；按 (partition, offset) 排序，续页检查 request.version，无单一 upper_offset。kit 的完整快照 GET 显式指定 `evidence_view=partitioned`，要求 `COMPLETE + AVAILABLE` 和对应版本，返回 `evidence_view`、完整 `request`、`items` 与 `next_cursor`。此视图以数值 (partition, offset) 稳定排序，offset 按现有十进制字符串编码，各分区 offset 可以相同。跨分区顺序仅用于分页。该自动化视图要求整份快照，不接受 eventType/stage 筛选，所有页内唯一事件数之和必须等于 request.event_count。
- 同页的权限、可用性、版本、状态和事件读取使用一致快照。游标绑定身份、来源、请求、视图、版本和排序键。版本变化返回 409 VERSION_CONFLICT；客户端丢弃旧页并重查状态。不可用返回 410，越权 403，非法游标 422 INVALID_CURSOR，已知缺口的当前版本拒绝作为完整快照返回。人工调试仍能按已有权限查看和导出未完成事件。
- 界面与导出对计数来源展示所有分区，使用同一稳定排序；详情保持原始业务字段大小写。旧单分区来源的列表、详情、下载及精确清理接口沿用现有契约。

## 4. 交付与验收

1. 对一个 reqId 模拟 main 已收 END、perf 已到 1/2、lake 未到，一次状态调用覆盖三组；下一轮只查 perf 和 lake。之后 perf 跨分区到齐，状态与两页正文均可查。测试覆盖一批多 reqId，同一 reqId 跨来源，超限分批及越权整批拒绝。
2. 验证来源级显式 END/不同 N/none、旧 format 继承、来源覆盖、缺省非法值、区分 bool 与整数、配置变更不追改旧请求。覆盖业务去重键相同的重投、键冲突或缺失、消费重放、并发写、进程重启、乱序、N 后多收、计数不足超时、缺口/超限和过期清理。同一 source 的不同分区相同 offset 应分别可查。同一事件重放不改变计数或版本。
3. 验证有新版本或中途失效的多页快照不会拼接出成功，旧 0.7.0 仍能查询、断言和清理原 END 来源。A 来源的精确清理不能影响 B 来源的同名 ID。
4. 在独立平台仓交付 OpenAPI 增量、来源配置样例、数据迁移/回退说明和契约测试结果。先发布兼容接口，再按来源启用计数规则。真实 topic、规则与生产重投语义由生产方和平台共同确认。

配套自动化方案见[多 Topic 日志断言评审稿](../aitest_log_assertions/multi_topic_review.md)。原平台依据见[后端设计](01_backend.md)、[HTTP v1](02_http.md)及[来源配置](../log_capture_platform_configuration.md)。
