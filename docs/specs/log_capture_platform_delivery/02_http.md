# 02 · HTTP 接口与共享数据契约

本片交付独立日志平台的 FastAPI 路由、输入输出模型与契约测试。Web、CLI、AITest 和远程 MCP 共享以下字段、权限及错误语义。实现位置为独立工程的 `src/log_platform/api/`、`src/log_platform/services/`、`tests/contract/`。下文示例均为测试夹具，仅进入测试文件。[开发评审稿](../log_capture_platform_review.md) · [配置及限额](../log_capture_platform_configuration.md)

已有 v1 平台的本轮升级范围见[多来源收齐与分页取证](07_observed_topic_handoff.md)。本页同时给出兼容端点与增量接口。

## 1. 传输、权限和分页

- 所有普通 `/v1` 操作和远程 `/mcp` 验证 `Authorization: Bearer <token>`，包括请求签发下载链接。独立文件路由 `GET /v1/downloads/{ticket}` 接受专用短时票据。来自浏览器、IP、隧道或自定义标头本身均不能代替凭证。缺失或无效 Bearer 返回 401。
- 操作人员共用 `human` Token，在逐个授权的来源上用 `all_reqids: true` 允许 read/export/cleanup。Agent 使用独立 `agent` Token，按来源、前缀及动作授权。浏览器首次粘贴 Token，用来源发现验证成功后才写入当前 origin 的 localStorage，刷新时复用。普通 Bearer 接口返回 401 时清除已存 Token 并重新输入，403 保留 Token 并提示本操作未获授权。
- 从 `server.public_url_env` 和可选 `server.download_url_env` 解析可信 origin，校验实际 Host（含端口）及请求中出现的 Origin（匹配协议、主机和端口），拒绝未知地址或 null Origin。服务间 HTTP 可不带 Origin。多用户桥接可用 `server.additional_host_envs` 明确增加允许的 Host（含端口），不增加浏览器 Origin、CORS 权限或链接生成基址。跨源网页不开放 CORS，URL 生成不采用来访 Host 或转发头。凭证、正文、DSN 不进日志。API 响应发 `Cache-Control: no-store`。
- GET 的 `source_id` 在 query，单来源 POST 的 `source_id` 在 JSON body；readiness 的每个 items 元素携带自己的 source_id 与 reqId。来源发现、界面参数和全局健康摘要可直接访问；票据下载从已绑定的记录取得来源和精确请求集合；其余接口来源必填。请求定位键是 `(source_id,reqId)`。输入 `reqIds` 必须为非空、无重复的字符串数组，失败时整批拒绝。
- 业务服务函数显式检查已验证的 Token 主体、动作和来源/请求归属。授权需匹配同一项 source + ID 范围 + action grant，无范围时列表为空。显式越权范围统一 403，与记录是否存在无关。精确批量中任一项越权时整批 403，无部分读取或写入。游标、事件 ID、预览 ID 和任务 ID 都不授予权限。
- 普通 ID 在请求详情路径中按单个 UTF-8 URL 段转义。含斜线、字面 `.` / `..` 整段或以 `~` 开头的 ID 使用路径段 `~<base64url(原始 UTF-8，无填充)>`。客户端公共构造函数和服务端各解码一次，可往返传入值。query、JSON 和响应中的 `reqId` 始终是原值。批量状态路由按 POST 方法匹配，ID 为 `status` 的请求仍可 GET。
- 服务时间用 UTC RFC 3339 字符串，原始业务消息中的 `timestamp` 按原值保留。数字字节用十进制 B。Kafka `offset`、`end_offset`、`upper_offset`、`next_offset`、分区起点及水位用十进制**字符串**，避免浏览器数字精度丢失。
- 列表请求 `page_size`、`cursor`，响应 `{"items":[],"next_cursor":null}`。默认 50、最大 100，受单响应 8 MB 上限约束。没有下一页时返回 null。游标为服务端校验的不可篡改标识，绑定调用者、来源、排序/筛选、领域对象及分页边界；不跨查询复用。前端用已有页游标实现“上一页”。单 API 进程首版可用启动时生成的服务端随机密钥签名游标；重启后旧游标返回 422 INVALID_CURSOR，客户端回到首屏。清理预览与幂等回执按数据库记录恢复。
- 时间过滤 `from`（含）、`to`（不含），使用平台时间。无效日期、颠倒区间或未知业务过滤条件报 422。客户端处理返回上限，不截断 JSON、不展示虚构的总数。

## 2. 来源发现和界面参数

`GET /v1/sources` 返回 `{"items":[Source]}`。授权范围内的停用来源仍可返回，只要仍有可访问的元数据。数组可为空。`actions` 是当前用户在该来源拥有的动作并集，只用于决定是否提供入口；ID 级权限仍在实际访问时校验。`event_fields` 取自该来源的可映射事件字段，`filter_fields` 的每项有 name、label、type，未配置 label 时返回 name。

```json
{"items":[{"source_id":"source_b","name":"订单","enabled":true,"state":"RUNNING","format_ref":"orders_v1","completion_supported":true,"evidence_view":"single_partition","event_fields":["eventType"],"filter_fields":[{"name":"orderId","label":"订单号","type":"string"}],"actions":["read","export","cleanup"]}]}
```

`GET /v1/ui-settings` 返回下列白名单字段。值取部署配置。页面使用这些值控制分页、多选、轮询与预览，服务端独立复核限额。

```json
{"poll_interval_ms":2000,"hidden_poll_interval_ms":10000,"page_size_default":50,"page_size_max":100,"batch_reqids_max":200,"readiness_batch_supported":true,"max_preview_targets":1000,"export_max_requests":20,"export_max_uncompressed_bytes":100000000,"mcp_enabled":true}
```

升级后的平台对支持收齐快照的来源返回 `evidence_view`（旧来源 `single_partition`，计数来源 `partitioned`）。`completion_supported` 继续供旧客户端判断单分区 END 快照能力。平台实现并启用跨来源批查后才发布 `readiness_batch_supported=true`。

## 3. 请求、状态和事件

`Request` 对象用于列表、详情、批量状态和事件页的快照头。`actions` 精确对应该请求与调用者。`reason` 为 null 或 `{code,message}`。`stored_bytes` 为该请求已接收并持久化的原始消息字节计数，代表证据规模。释放物理磁盘的情况见健康接口。

```json
{"source_id":"source_b","reqId":"dbg-001","format_ref":"orders_v1","capture_state":"COMPLETE","availability":"AVAILABLE","version":2,"first_seen_at":"2026-11-11T08:00:00Z","expires_at":"2026-11-11T08:05:00Z","event_count":2,"stored_bytes":168,"end_received":true,"end_offset":"42","completion_basis":"producer_end","expected_event_count":null,"reason":null,"actions":["read","export","cleanup"]}
```

| 字段 | 值与含义 |
| --- | --- |
| `capture_state` | `COLLECTING` 等待来源的完成条件，`COMPLETE` 已按该条件收齐并持久化，`INCOMPLETE` 已知缺口/超限，`TIMED_OUT` 承诺结束但超时，`OBSERVED` 来源无结束契约。 |
| `availability` | `AVAILABLE` 可读，`DELETE_PENDING` 清理已受理且隐藏，`DELETED` 已物理清理业务记录，`EXPIRED` TTL 已到且不可读。|
| `completion_basis` | `producer_end` 使用结束事件，`expected_count` 使用生产方约定的应收条数，`none` 仅观察。该字段描述来源规则，当前结论见 capture_state。|
| `expected_event_count` | 计数来源返回该请求首次入库时冻结的应收总数；END、none 或只有预删标记时为 null。event_count 表示实收，客户端用 capture_state 判断收齐。 |
| `version` | 已观察请求的单调递增整数。每次事件、状态或可用性改变均推进。`end_offset` 在没有结束记录时为 null。|
| 未观察到的请求 | 未知 ID 在批量查询中使用明确的 `NOT_FOUND` 结果。先清理后到达的请求可仅有删除标记，`availability` 有值，`capture_state/first_seen_at/expires_at/end_offset/format_ref/version` 可为 null，`event_count/stored_bytes` 为 0。该请求的日志不会因缺少采集记录被报告为可用。 |

| 端点 | 输入及成功输出 |
| --- | --- |
| `GET /v1/requests` | `source_id` 必填。可选 `reqId` 精确或 `reqId_prefix` 字面前缀（二选一）、`from/to` 筛选 first_seen_at、`filter.<name>`、分页。200 返回 `Page<Request>`，仅含当前范围内 AVAILABLE 请求。|
| `GET /v1/requests/{reqId}` | `source_id`。200 为 Request，并增加 `dimension_values`，公开维度名映射为快照内不同标量值数组。某事件缺字段时不造值。有界展示每维最多前 10 个不同值（按该来源事件页的稳定顺序首次出现），存在更多时将该名字放入 `truncated_dimensions`。|
| `POST /v1/requests/status` | `{source_id,reqIds}`，默认最多 200 项。200 为 `{items:[{reqId,result,request}]}`，完全按输入顺序一一对应。已观察或有标记返回 `result="FOUND"` 与 Request；未知返回 `result="NOT_FOUND",request=null`。过期、已清理和待清理仍返回已有元数据，可用性可区分。元数据也到期后才返回未知。|
| `POST /v1/requests/readiness` | `{items:[{source_id,reqId}]}`。每批最多 batch_reqids_max 对，200 按输入顺序逐对返回 `{source_id,reqId,result,request}`。只读已持久化的状态；超限 422、任一越权整批 403。[契约与样例](07_observed_topic_handoff.md) |
| `GET /v1/requests/{reqId}/events` | `source_id`、可选 `eventType`、`stage`、`include_data`（默认 false）、`expected_version`、分页。200 为 `{request,upper_offset,items:[Event],next_cursor}`，此结构用于单分区来源。计数来源默认人工浏览返回 {request,items,next_cursor}，可查看尚在采集的可用事件；按数值 (partition,offset) 排序，续页绑定版本，不返回单一 upper_offset。多分区自动化完整快照须指定 `evidence_view=partitioned` 和 expected_version，返回 `{evidence_view,request,items,next_cursor}`，全量按数值 (partition,offset) 升序。|
| `GET /v1/requests/{reqId}/events/{event_id}` | `source_id`、`expected_version`、`view=data\|raw`。200 默认返回 `{event:EventMeta,data?:JSON}`。raw 返回完整业务 JSON 对象本身，两个视图均设置 `X-Request-Version`。event_id 必须归属本请求。|

下列为事件元数据夹具。`partition` 是整数，`timestamp` 是按来源单位规范化后的 UTC 字符串，未映射的业务字段省略，`ingested_at` 始终提供。`dimensions` 是该事件确有值且符合类型的可筛选字段。`event_id` 是稳定、不透明的字符串。事件列表含正文时在每项上增加 `data`。映射路径不存在时省略，命中 JSON null 时传 `"data": null`。

```json
{"event_id":"ev-a","partition":0,"offset":"41","ingested_at":"2026-11-11T08:00:00Z","eventType":"priced","dimensions":{"orderId":"O-7"},"is_end":false}
```

- 请求列表按 `(first_seen_at DESC, reqId DESC)` 精确续页，使用确定性二进制 ID 排序。首次响应冻结此次搜索的时间上界，后页仍执行授权、过期和清理检查。并发更新可让条目离开列表。此列表用于查找请求，完整断言只读取请求级事件快照。
- `filter.<name>` 使用来源公示的类型做等值匹配。string 区分大小写，integer 用十进制，boolean 只接受 `true/false`。多维条件必须由同一个事件同时满足。未声明的字段、重复过滤项和类型不符返回 422。
- 单分区视图的事件首屏从同一数据库快照读取 Request、已入库最高 `upper_offset` 与事件页。`upper_offset` 是该请求内真实最大位置，可为空，不是请求事件数。下一页绑定身份、请求版本、上界和查询条件。自动化可在首屏带批量状态取得的 `expected_version`，正文点击带当前事件页的版本。
- 请求详情、事件首屏、续页及单事件读取都先验证权限、可用性，再核对版本。已过期或删除返回 410，版本变化返回 409。只有仍可用、版本相同的 COMPLETE 快照可用于完整断言。未知事件 ID 或属于另一请求时返回 404。GET 不必带 `expected_version` 即可读取当前快照；基于上一次读取点击或断言时须传该值。若并行取得请求详情与事件页，两者版本不同则重取详情再展示维度。
- 原文和压缩导出保持输入的字段大小写、层级、JSON 类型与数字值，允许空白和对象键顺序变化。后端避免经浮点转换再序列化业务值。前端原文用文本响应，展示或复制大整数、高精度小数时保留数字字面值。原始 JSON 在 HTML 内按文本渲染。

## 4. 下载

`POST /v1/exports` 使用 `{source_id,reqIds}`，所有目标均需 export 权限。最多 20 个请求、100 MB 未压缩、全局并发 1，实际读取当前配置。同一有界事务取得所有目标的一致快照，确认可用性、体积与内存预算，释放读事务再开始发送。任一目标未知、失效、越权或超限时整批返回结构化错误。已采集的部分日志可以导出，清单写明当时的采集状态。

200 使用 `Content-Type: application/gzip`、`Content-Disposition: attachment; filename="capture-<服务端生成标识>.jsonl.gz"`。不设置 HTTP `Content-Encoding: gzip`，使客户端保存 gzip 文件本身。不要将用户输入作为文件路径或文件名。每行 UTF-8 JSON，使用 LF，导出顺序按输入 reqIds。单分区来源的请求内按 offset 升序，多分区来源的请求内按数值 (partition,offset) 升序。

| 行 | 约定 |
| --- | --- |
| 第一行 `kind=manifest` | `export_version=1, source_id, exported_at, requests`。requests 按输入顺序含每个请求的 `reqId,format_ref,version,capture_state,availability,completion_basis,event_count`，标明部分证据。|
| 中间行 `kind=event` | `reqId,event_id,partition,offset,ingested_at,raw`。raw 是该条完整业务 JSON，每条事件出现一次。|
| 末行 `kind=trailer` | `event_count,events_sha256`。对全部中间行的**实际未压缩 UTF-8 字节**按顺序计算 SHA-256，每行包含末尾 LF；零行对空字节计算。|

任何断流都不能当作完整文件。CLI 确认 gzip 可解、清单及末行齐全、总数和校验和一致后才完成文件命名。传输中新发生的 TTL 过期不改变已形成的快照，也不延长服务端 TTL。

远程 Agent **首选通过可达的隧道 base URL 直接 POST**。Python 用 httpx 发送 Bearer 与精确选择，流式写入 Agent 所在机器的临时文件，验证 gzip、manifest、trailer 和 SHA-256 后再命名。客户端提供真实隧道入口，并从 `LOG_PLATFORM_TOKEN` 读取服务端发给 Agent 的密钥，无需安装平台 CLI。核心调用如下，外层负责临时文件清理及校验。

```python
with httpx.Client(timeout=timeout, follow_redirects=False) as client:
    with client.stream("POST", f"{base_url.rstrip('/')}/v1/exports",
                       headers={"Authorization": f"Bearer {agent_token}"},
                       json={"source_id": source_id, "reqIds": req_ids}) as response:
        response.raise_for_status()
        for chunk in response.iter_raw():
            temporary_file.write(chunk)
```

### 4.1 给远程 Agent 和普通 Fetch 的下载链接

| 端点 | 输入及成功输出 |
| --- | --- |
| `POST /v1/export-links` | Bearer 鉴权，输入 `{source_id,reqIds}`，目标上限和逐项 export 授权与即时导出一致。对当前可用目标在一个快照中绑定版本，持久化票据元数据后返回 201 JSON，字段为 `download_url,web_url,expires_at`。尚未观察到的目标返回 404，已过期或已清理的目标返回 410。 |
| `GET /v1/downloads/{ticket}` | 持票可以用普通 GET 直接取附件，无需自定义 header、登录会话、cookie 或 POST。返回 200 gzip，使用上节同一压缩 JSONL、响应头和资源限额。服务端直接发送文件字节，Fetch 不需要执行 JavaScript 或跟随登录跳转。 |

响应示例中的主机与票据为占位值。

```json
{"download_url":"http://agent-tunnel.example:14000/v1/downloads/TICKET_PLACEHOLDER","web_url":"http://log-host.example:4000/export?source_id=source_a&reqId=at-001","expires_at":"2026-11-11T08:01:00Z"}
```

只接受普通 GET 的 Fetch 可使用两步流程。远程 MCP 的 `logs_export` 复用签发服务，将三个字段原样返回。服务端用 `server.download_url_env` 指向的可信 Agent 隧道基地址生成 download_url，未配置时用公开基地址；web_url 始终使用 `server.public_url_env`。Agent 把 download_url 交给实际可达该入口、能处理二进制响应的 Fetch。用户打开 web_url，用已验证的人类 Token 确认选择后下载。web_url 不携带凭证。

- 用密码学安全随机数生成器为每张票据生成至少 32 字节随机值，base64url 无填充编码。数据库只存票据摘要，绑定签发凭证的稳定身份、单来源、精确有序 reqIds、签发时每项版本及期限。签发时不产生压缩文件。有效期取 `min(签发时间 + export.link_ttl_seconds, 所有选中请求的 expires_at)`，默认票据至多 60 秒。
- GET 用摘要查票，未知票据返回 404；已知票据到期返回 410 `LINK_EXPIRED`，元数据清理后也返回 404。对仍有效的票据，在构建同一个有界下载快照时复核原签发身份及每个目标**当前** export 授权、可用性、版本。授权已撤销返回 403，任一目标已删除、待清理或过期返回 410 `GONE`；仍可用但版本改变返回 409 `VERSION_CONFLICT`。整批通过后才发 200。GET 不接受额外的目标、来源和版本覆盖参数。
- 获取中断可在票据有效期内复用**同一链接**重试；每次兑换重新鉴权和校验，期限不续。签发和 GET 并发受不同预算约束，全局最多 `export.max_active_links` 张有效票据（默认 100），已过期记录按批回收，控制元数据预算不足拒绝新增。签发端对同一调用方和同一精确目标集合的并发重复请求做有界节流，超额返回 429 `BUSY`。客户端缓存本次操作返回的链接，传输重试不重复签发。
- 签发及兑换的成功与错误响应均设 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`。应用、Uvicorn 访问日志、追踪、指标标签及错误日志只记录路由模板 `/v1/downloads/{ticket}`；不记录真实 path、完整下载 URL、签发响应或 Bearer。配置公开地址时使用受控网络的真实主机，不从来访 Host 拼接。

## 5. 清理、幂等和回执

`POST /v1/cleanup`、`POST /v1/cleanup/by-prefix` 要求 `Idempotency-Key` 头，CLI、MCP 和浏览器为每个新意图生成 UUID，并在网络重试中复用。唯一键为（调用者、来源、幂等键），意图摘要含操作种类以及规范化的无序精确 ID 集合或 preview_id。事务内持久化任务、逐项目标和删除标记再返回 202。保存期内，同键同摘要返回原 job_id，复用同键但更换参数或操作种类的请求返回 409，并发提交只受理一次。已提交前缀任务的同键重试先查回执，再检查预览有效期。

| 端点 | 输入及成功输出 |
| --- | --- |
| `POST /v1/cleanup` | `{source_id,reqIds}`，最多 200 个，有 cleanup 权限即可精确放弃尚在途或尚未观察到的请求。返回 202 `{source_id,job_id,state,accepted_at,target_count}`，Location 给出带 source_id 的任务查询地址。|
| `POST /v1/cleanup/preview` | `{source_id,reqId_prefix,before,limit}`。before 为 first_seen_at 的排他上界，必须 ≤ 服务端当前时间；limit 为正整数且 ≤ max_preview_targets。200 返回冻结集合的回执，字段见下例。|
| `POST /v1/cleanup/by-prefix` | `{source_id,preview_id}`，提交冻结目标，不重新做前缀搜索。返回与精确清理相同的 202。预览仅允许原调用者、原来源使用，复核目标权限。|
| `GET /v1/cleanup` | `source_id`、可选 `state` 和分页。200 `Page<Job>`，按 `(accepted_at DESC,job_id DESC)`。按发起 Token 主体及其当前 cleanup 授权过滤。共用人类 Token 的浏览器可查看该凭证发起的回执。Agent 的任务属于 Agent 凭证。详情同样检查主体归属。|
| `GET /v1/cleanup/{job_id}` | `source_id`、分页。200 `{job,items:[CleanupItem],next_cursor}`。items 为该任务的有界逐项结果，按任务内稳定序号升序。|

```json
{"source_id":"source_b","preview_id":"pv-a","reqId_prefix":"dbg-","before":"2026-11-11T08:02:00Z","expires_at":"2026-11-11T08:03:00Z","target_count":1,"skipped_collecting_count":0,"observed_count":0,"sample_reqIds":["dbg-001"]}
```

预览仅接受非空字面前缀，整个前缀须落在当前 Token 的 cleanup 授权范围。使用 all_reqids 的授权来源可选任意非空字面前缀。只冻结可用目标并保存当时的版本。默认跳过 COLLECTING，可包含 OBSERVED，单列 `observed_count`。达到上限后若仍有匹配项目则 422 `TOO_MANY_TARGETS`，让调用者缩窄前缀或时间。`sample_reqIds` 最多 10 项，`target_count` 为完整集合数量。空集合可预览，提交返回 422 `EMPTY_TARGETS`。预览默认保留 60 秒。

提交只处理仍符合预览的冻结项目。版本/可用性改变的项目为 SKIPPED，并写入明确原因。仅为实际接受的目标建立幂等删除标记。预览之后新到的同前缀请求不进入本次任务。精确清理覆盖在途 ID，处理后仍需按删除标记抑制迟到数据。

```json
{"job":{"job_id":"job-a","source_id":"source_b","mode":"exact","reqId_prefix":null,"state":"DONE","accepted_at":"2026-11-11T08:02:00Z","finished_at":"2026-11-11T08:02:06Z","target_count":1,"pending_count":0,"running_count":0,"done_count":1,"skipped_count":0,"failed_count":0},"items":[{"reqId":"dbg-001","state":"DONE","reason":null}],"next_cursor":null}
```

Job 的 mode 为 `exact|prefix`。各项状态 `PENDING/RUNNING/DONE/SKIPPED/FAILED` 的数量之和等于 target_count。任务 `ACCEPTED` 已持久受理，`RUNNING` 正在处理，`DONE` 所有项 DONE。全部失败为 `FAILED`，含跳过项或部分失败为 `PARTIAL_FAILED`。终态字段 finished_at 才有值。清理指向已无事件的 ID 时，成功写下抑制标记也可为 DONE。读回执按当前权限校验整个集合，无权限时详情不泄露被撤权 ID。受理后的重试继续返回 202，即使任务已结束，真实状态仍可回查。DONE 表示目标业务数据已处理；磁盘占用见运行状态。

## 6. 健康与错误

`GET /v1/health` 对有来源授权的 Bearer 身份返回 `observed_at, storage, sources`。storage 含 `state,used_bytes,limit_bytes,filesystem_free_bytes,pause_at_bytes,resume_free_bytes,reason`，state 为 `NORMAL/PAUSED/UNKNOWN`。sources 中每项含 `source_id,state,reason,lag,last_ingested_at,has_gap`。state 为 `CONNECTING/RUNNING/DISABLED/ERROR/PAUSED`。lag 表示各分区最新已知 Kafka 高水位与持久化 next_offset 的差值合计，为十进制字符串；未知指标用 null，错误摘要不暴露地址、凭证或业务原文。无来源授权时 403。

运维页可在同一端点传 `source_id` 及分页，响应额外含 `items,next_cursor` 返回该来源的分区。分区行含 `partition,start_offset,next_offset,high_watermark,has_gap`。有界错误摘要通过 source.reason 表达。worker 心跳过期时，启用来源返回 ERROR 及 `WORKER_STALE`，失效的实时采样返回 null。消费者在线且没有新消息时保持 RUNNING。消费因容量暂停时，只要健康数据仍可用就返回 200 并给出 PAUSED；依赖故障导致不能读取数据时返回 503。

以下是同一总览响应的形状，容量数值只作测试输入。

```json
{"observed_at":"2026-11-11T08:01:00Z","storage":{"state":"NORMAL","used_bytes":6000000000,"limit_bytes":20000000000,"filesystem_free_bytes":14000000000,"pause_at_bytes":16000000000,"resume_free_bytes":5000000000,"reason":null},"sources":[{"source_id":"source_b","state":"RUNNING","reason":null,"lag":"0","last_ingested_at":"2026-11-11T08:00:02Z","has_gap":false}]}
```

所有 JSON 错误结构为 `{"error":{"code":"VERSION_CONFLICT","message":"请求已变化，请重新读取","details":{}}}`。details 只发送安全、结构化的纠错数据，例如 `current_version`、`availability`、`field` 或 `limit`。前端、CLI、MCP 依据 code 分支。

| HTTP | code 与恢复方式 |
| --- | --- |
| 401 / 403 | `UNAUTHENTICATED` 表示 Bearer 缺少或失效，网页清除已存 Token 并要求重新输入。`FORBIDDEN` 表示超出授权或 Host、Origin 不受信任，网页保留 Token。|
| 404 | `NOT_FOUND` 合法范围内的未知请求、事件、预览或任务。|
| 409 | `VERSION_CONFLICT` 重读请求及事件首屏；`IDEMPOTENCY_CONFLICT` 同一幂等键绑定了另一意图。|
| 410 | `GONE`，details.availability 为 DELETE_PENDING/DELETED/EXPIRED；`PREVIEW_EXPIRED` 重新预览；`LINK_EXPIRED` 票据到期，仍可用的日志可重新申请。|
| 413 | `EXPORT_TOO_LARGE` 导出数量或字节超限，缩小选择。|
| 422 | `INVALID_ARGUMENT`、`INVALID_CURSOR`、`TOO_MANY_TARGETS`、`EMPTY_TARGETS`，修正参数、重置分页或缩小前缀。|
| 429 / 503 | `BUSY` 并发或待办预算满，或 `UNAVAILABLE` 依赖不可读。可重试时给出 Retry-After，清理重试复用原键。|

## 7. 分片验收

1. 后端从路由生成 OpenAPI，前端用与本片同源的 DTO/夹具做组件测试。分别以受限前缀和两个来源验证每个公开端点，混合授权批次不产生副作用。
2. 测试嵌套请求标识、特殊路径段、原文整数 9007199254740993、布尔 false、数组、正文路径缺失及显式 null。两种来源同 ID 的读取、清理与下载完全独立。
3. 让事件在两页之间到达、在点开正文前过期或提交清理，分别得到 409 和 410。OBSERVED、TIMED_OUT、未知 ID 均不能标为 COMPLETE。模拟单页字节预算先耗尽，下一页能取到所有剩余记录。
4. 并发重复精确清理，核对同一任务；模拟接受成功但响应丢失，重试后仍能查询。预览后插入同前缀新请求、改变冻结请求版本、等待预览到期，核对冻结范围、逐项状态和重试结论。
5. 验证压缩包、计数与摘要，覆盖导出并发饱和、快照前过期、形成快照后清理、慢下载断流、SPA 刷新与 CLI 保存。验证 web_url 不含任何凭证，download_url 只含作用域明确的短时票据。
6. 从实际 Agent 网络用 HTTP 或远程 MCP 签发链接，再用普通 Fetch 或不带凭证头的 GET 下载，确认 200、gzip 可解、精确目标与清单摘要正确。测试同链接重试和服务重启后的兑换，复核签发 TTL 截断、403 撤权、409 版本变化、410 到期/已清理、404 未知/已回收、429 预算不足。用测试生成的票据检索日志和数据库，确认真实路径、票据明文、签发响应均未落入持久化诊断。
7. 两个浏览器各自首次粘贴 human Token，仅验证成功才持久化，刷新继续复用。校验 401 清除、403 保留，同一人类凭证能共享回执。Agent 可以导出 source_a 的 at- 请求，清理未授权前缀返回 403。无 Token 的普通 REST 及 MCP 返回 401。通过隧道用 httpx 直接 POST 下载，无需安装 CLI。核对两种链接的 origin、未设 download_url_env 时的回退及不可信 Host/Origin 的拒绝行为。两个已登记的桥接端口均应通过 Host 检查，未登记端口被拒绝；额外 Host 不扩大浏览器 Origin 范围。
