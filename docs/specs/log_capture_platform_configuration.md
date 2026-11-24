# 日志平台配置与多 Kafka 接入契约

2026-11-24 修订。本文定义首版配置及按 Topic 判定收齐的升级契约，实际服务需按交接稿实施与联调。

关联文档：[总体方案](log_capture_platform_spec.md)、[技术选型与页面](log_capture_platform_technical_design.md)。本文件只定义独立日志平台的配置，不修改 AITest 的 `aitest.yaml`、环境文件或真实部署。

开发评审先读[精简方案](log_capture_platform_review.md)。本文配置项维持 snake_case；业务报文中的 reqId、eventType 等使用开发协议的原始大小写，不因此把 reqid_prefixes 等运维参数一并改名。

## 1. 多 Kafka 的接入单位

采用两层配置：`clusters` 保存集群连接，`sources` 保存日志来源。一个 source 固定绑定一个 cluster 和一个 topic；同一 cluster 可以提供多个 source，多个 cluster 也可以同时消费。

```text
Kafka 集群 A ── topic A1 ── source_a1 ── 独立 consumer ──┐
             └ topic A2 ── source_a2 ── 独立 consumer ──┤
Kafka 集群 B ── topic B1 ── source_b1 ── 独立 consumer ──┤
                                                      ▼
                                      共享写入调度与 PostgreSQL
                                      共享 TTL、清理和 20 GB 额度
```

`bootstrap_servers` 中的多个地址只是同一集群的入口，不能把不同集群地址拼在一起。首版不使用 topic 正则订阅；增加 topic 就增加一个明确的 source。

每个 source 通过 `format_ref` 选择报文映射。同一种格式可在不同集群或 topic 复用。一条 Kafka 业务消息承载一个 UTF-8 JSON 事件。多个 topic 即使使用相同格式，也可以为各自的 source 配置不同的收齐规则。

| 对象 | 身份与隔离规则 |
| --- | --- |
| 请求 | `(source_id, reqId)`；不同来源的同名 reqId 不合并、不互删 |
| 事件位置 | `source_id + topic + partition + offset`；END 来源的同一请求固定在一个分区，计数来源可跨分区 |
| 消费进度 | 键为 `source_id + topic + partition`，值为下一待处理位置 next_offset，不为每条消息新增水位记录 |
| consumer group | 每个 source 使用独立且稳定的 group_id，不共用业务消费者的 group |
| API、CLI、MCP | 查询、状态、申请下载和清理指定 source_id。用票据 GET 下载时，来源和精确目标由签发记录绑定。readiness 可在同一批次逐项指定不同来源；清理与导出仍按单来源提交 |
| 页面 | 先选数据源，再查请求；首版不做跨来源混合结果表 |
| 容量 | 20 GB 是全平台总额；连接池、队列和导出并发同样不按 source 倍增 |

一个 source 对应独立消费循环，连接失败不会让其他 source 等待它重连。各来源共享有界写入调度，轮流获得处理机会，不能让繁忙来源无限占用批次；同一分区的数据库事务仍按顺序提交。数据库故障和总容量不足会影响所有来源，首版不承诺资源完全隔离。

此前的 30 请求/秒用于整个平台合计输入的容量计算，不代表增加一个 source 就多出 30 请求/秒的承载能力。若实际变成每个来源各 30 请求/秒，需要重新压测，不能复制单来源预算。

## 2. 配置文件与加载规则

- 独立文件建议命名为 `log-platform.yaml`。路径由 `--config` 指定，未指定时读取 `LOG_PLATFORM_CONFIG`；都未提供则报配置缺失，不搜索 AITest workspace。
- API 与 worker 使用同一版本配置；首版校验后受控重启生效，不做热更新或网页配置编辑器。
- 平台的策略结构和应收条数写入 `log-platform.yaml`。`*_env` 表示平台 API/worker 进程的环境变量名称，加载时取其值；部署器可以从自己的 env 文件注入。云端测试任务的 dotenv 供 kit 使用，不参与平台加载。必需变量未设置或为空立即失败；日志和诊断只显示变量名，不显示值。
- 未知字段、重复 ID、无效引用、范围错误、重复集群/topic 绑定、重复 group 绑定直接报错，不忽略拼写错误。
- source 的 cluster_ref 必须引用当前 clusters；授权的 source_id 可以引用当前 sources 或数据库 source_registry 中已注册但停用/移除的来源，后者只保留已有数据的访问权限。数据库引用在连接后校验，无此身份则拒绝该授权。
- 连接地址与凭证格式通过校验后，某个 Kafka 不可达属于该来源的运行故障；不因它不可达而停掉其他来源。数据库不可达则整个平台未就绪。
- 配置中的字节均为十进制 B，`seconds` 为秒、`ms` 为毫秒。相对路径按配置文件目录解析；凭证和证书路径需要限制文件权限。
- 部署时记录脱敏后的配置版本摘要，健康信息可核对 API/worker 是否一致；不把原始配置或密码散列公开给普通客户端。

以下为可评审的字段示例。`cluster_a` 等是配置占位标识，不代表已接入真实 Kafka；环境变量的真实值在部署时提供。

```yaml
schema_version: 1

server:
  listen_host: 127.0.0.1
  listen_port: 4000
  public_url_env: LOG_PLATFORM_PUBLIC_URL
  download_url_env: LOG_PLATFORM_DOWNLOAD_URL
  additional_host_envs: [LOG_PLATFORM_TUNNEL_A_ORIGIN, LOG_PLATFORM_TUNNEL_B_ORIGIN]

database:
  dsn_env: LOG_PLATFORM_DATABASE_DSN
  api_pool_max: 4
  worker_pool_max: 4
  statement_timeout_ms: 5000
  lock_timeout_ms: 1000

storage:
  quota_path_env: LOG_PLATFORM_DATA_ROOT
  limit_bytes: 20000000000
  pause_at_bytes: 16000000000
  resume_free_bytes: 5000000000
  partition_seconds: 60

retention:
  ttl_seconds: 300
  capture_timeout_seconds: 120
  metadata_seconds: 3600
  preview_seconds: 60

ingest:
  max_sources: 8
  poll_timeout_ms: 100
  max_poll_interval_ms: 300000
  max_event_bytes: 50000
  max_events_per_request: 100
  batch_max_events: 500
  batch_max_bytes: 4000000
  batch_max_wait_ms: 100
  queue_budget_bytes: 64000000
  kafka_queue_budget_bytes: 64000000
  max_write_batches: 2

cleanup:
  poll_interval_ms: 1000
  max_wait_seconds: 5
  batch_max_requests: 100
  batch_max_events: 1000
  batch_max_payload_bytes: 10000000

control:
  metadata_budget_bytes: 256000000
  max_pending_cleanup_targets: 20000
  max_active_previews: 100
  max_preview_targets: 1000
  max_error_records: 1000

api:
  batch_reqids_max: 200
  page_size_default: 50
  page_size_max: 100
  response_max_bytes: 8000000
  request_timeout_seconds: 15

export:
  max_requests: 20
  max_uncompressed_bytes: 100000000
  max_concurrent: 1
  link_ttl_seconds: 60
  max_active_links: 100
  memory_budget_bytes: 256000000
  snapshot_timeout_ms: 5000
  send_timeout_seconds: 120

mcp:
  enabled: true
  response_max_bytes: 256000
  tool_timeout_seconds: 15

ui:
  poll_interval_ms: 2000
  hidden_poll_interval_ms: 10000

logging:
  level: INFO
  api_max_total_bytes: 50000000
  worker_max_total_bytes: 50000000

clusters:
  - id: cluster_a
    bootstrap_servers_env: KAFKA_A_BOOTSTRAP_SERVERS
    security_protocol: SASL_SSL
    sasl_mechanism: SCRAM-SHA-512
    username_env: KAFKA_A_USERNAME
    password_env: KAFKA_A_PASSWORD
  - id: cluster_b
    bootstrap_servers_env: KAFKA_B_BOOTSTRAP_SERVERS
    security_protocol: SASL_SSL
    sasl_mechanism: SCRAM-SHA-512
    username_env: KAFKA_B_USERNAME
    password_env: KAFKA_B_PASSWORD

sources:
  - id: source_a
    name: 广告主链路
    format_ref: ads_v1
    cluster_ref: cluster_a
    topic_env: KAFKA_A_LOG_TOPIC
    completion: {path: /eventType, equals_env: ADS_NORMAL_END_TYPE}
    group_id: log-platform-source-a
    enabled: true
    bootstrap_policy: latest
  - id: source_perf
    name: 性能日志
    format_ref: ads_v1
    cluster_ref: cluster_a
    topic_env: KAFKA_PERF_TOPIC
    group_id: log-platform-perf
    completion: {mode: expected_count, count: 2}
    enabled: true
    bootstrap_policy: latest
  - id: source_lake
    name: 入湖日志
    format_ref: ads_v1
    cluster_ref: cluster_a
    topic_env: KAFKA_LAKE_TOPIC
    group_id: log-platform-lake
    completion: {mode: expected_count, count: 1}
    enabled: true
    bootstrap_policy: latest
  - id: source_b
    name: 日志来源 B
    format_ref: orders_v1
    cluster_ref: cluster_b
    topic_env: KAFKA_B_LOG_TOPIC
    group_id: log-platform-source-b
    enabled: true
    bootstrap_policy: latest

formats:
  ads_v1:
    req_id: /reqId
    event_type: /eventType
    stage: /stage
    payload: /data
    filter_fields:
      slotId: {path: /slotId, type: string}
      route: {path: /route, type: integer}
      mediaId: {path: /mediaId, type: string}
      algoSceneId: {path: /algoSceneId, type: integer}
      mediaSource: {path: /mediaSource, type: integer}
  orders_v1:
    req_id: /context/trace_id
    event_type: /kind
    payload: /body
    completion: {path: /done, equals: true}
    filter_fields:
      orderId: {path: /order/id, type: string}

auth:
  tokens:
    - id: agent
      token_env: LOG_PLATFORM_TOKEN_AGENT
      grants:
        - source_id: source_a
          all_reqids: true
          actions: [read, export]
        - source_id: source_perf
          reqid_prefixes: [at-]
          actions: [read, cleanup]
        - source_id: source_lake
          reqid_prefixes: [at-]
          actions: [read, cleanup]
        - source_id: source_a
          reqid_prefixes: [at-]
          actions: [cleanup]
    - id: human
      token_env: LOG_PLATFORM_TOKEN_HUMAN
      grants:
        - source_id: source_a
          all_reqids: true
          actions: [read, export, cleanup]
        - source_id: source_perf
          all_reqids: true
          actions: [read, export, cleanup]
        - source_id: source_lake
          all_reqids: true
          actions: [read, export, cleanup]
        - source_id: source_b
          all_reqids: true
          actions: [read, export, cleanup]
```

## 3. 日常需要填写的配置

| 配置 | 必填与默认 | 说明 |
| --- | --- | --- |
| `server.listen_host/listen_port` | 本地调试默认 `127.0.0.1:4000` | 远程接入时将 listen_host 设为开发机可达的内网 IP，Uvicorn 直接提供工作台、REST 和 MCP |
| `server.public_url_env` | 必填 | 用户浏览器可达的公开基地址，仅 scheme、host 和端口。工作台、详情及 web_url 以此生成；开发机当前 HTTP 监听 4000。 |
| `server.download_url_env` | 可选 | 指向远程 Agent/Fetch 可达的可信隧道入口，仅 scheme、host 和端口。若提供，由此生成 download_url；省略整个配置项则回退 public_url。示例中的 LOG_PLATFORM_DOWNLOAD_URL 需填写真实值或省略该项。 |
| `server.additional_host_envs` | 可选，默认空列表 | 列出额外隧道入口的环境变量名。每个值为精确的 HTTP(S) origin，按与两个基地址相同的规则解析；仅将其主机和端口加入 API 受信 Host，供各用户不同桥接端口访问。 |
| `database.dsn_env` | 必填 | 数据库连接串的环境变量名；API/worker 共用数据库，不共用连接对象 |
| `storage.quota_path_env` | 必填 | 被监测的专用配额目录/卷；所有计入额度的持久化文件必须实际受同一配额约束 |
| `clusters[].id` | 必填且唯一 | 配置内部稳定名称，sources 通过它引用连接 |
| `bootstrap_servers_env` | 必填 | 一个集群的 broker 地址列表；不使用业务 API 的 URL |
| `security_protocol` | 必填 | `PLAINTEXT/SSL/SASL_PLAINTEXT/SASL_SSL`；示例选择 SASL_SSL，实际按环境确认 |
| `sasl_mechanism` | 使用 SASL 时必填 | 首版内置配置支持 `PLAIN/SCRAM-SHA-256/SCRAM-SHA-512` |
| `username_env/password_env` | 使用上述 SASL 时必填 | 分开为不同集群配置凭证，不共用默认密码 |
| `ca_file_env` | 可选 | 私有 CA 时填写；省略时使用系统信任库，始终验证证书及主机名 |
| `client_cert_file_env/client_key_file_env` | mTLS 时成对提供 | 可选 `client_key_password_env`；均为环境变量引用，不在 YAML 放密钥内容 |
| `sources[].id` | 必填且不可改绑 | source_id，进入请求身份、权限、链接、进度和清理记录 |
| `sources[].name` | 必填，可改 | 页面展示名；改名不改变 source_id |
| `cluster_ref/topic_env` | 必填 | 一个来源绑定一个集群和一个精确 topic |
| `format_ref` | 必填 | 引用 formats 中已声明的版本名，同格式来源可共用 |
| `sources[].completion` | 省略时继承该 format 的 completion | 每个 topic 在此选择 END、固定应收条数或仅观察；两层均缺失时报配置错误。形态与例子见第 3.2 节。 |
| `group_id` | 必填且稳定 | 同集群内本平台各 source 不共用 group；也不得与外部业务消费者共用 |
| `enabled` | 默认 true | false 停止该来源消费，已有日志仍按原 TTL 可查、可删 |
| `bootstrap_policy` | 默认 latest | 仅没有历史进度的新分区生效，可选 earliest；不用于已有分区的故障恢复 |
| `auth.tokens[].id/token_env` | 至少一个有效凭证 | ID 可诊断，Token 仅从环境读取；高熵值、可轮换、不输出到日志 |
| `grants` | 必填，默认无权限 | 显式列出 source、字面 reqId 前缀和 read/export/cleanup 权限 |

权限按 grant 整体匹配，不把不同 grant 的 source、前缀、动作交叉组合。空前缀不允许；管理凭证如确需整个来源范围，单独配置 `all_reqids: true` 并省略 `reqid_prefixes`，不隐含全局管理员。无论读取权限是否覆盖整个来源，前缀删除 API 仍拒绝空前缀。

操作人员共用 human Token，Agent 使用另一个 agent Token。示例中 Agent 可读、导出 source_a 所有 ID，仅有前缀 `at-` 的请求可清理。人工授权逐来源填写 `all_reqids: true`。浏览器首次粘贴 Token，验证成功后才保存在当前 origin 的 localStorage；刷新复用，普通 Bearer 接口返回 401 清除，403 保留。所有普通 `/v1` 和远程 MCP 调用均验证 Bearer。文件 GET 用此前签发的专用短时票据验证。

发放时，部署方分别调用两次 Python 的 `secrets.token_urlsafe(32)` 独立生成密钥。服务端运行环境分别保存到 `LOG_PLATFORM_TOKEN_HUMAN` 和 `LOG_PLATFORM_TOKEN_AGENT`。人类拿到 human 密钥后首次在浏览器粘贴；远程示例脚本从客户端环境变量 `LOG_PLATFORM_TOKEN` 读取部署方发给 Agent 的那一把密钥。配置文档和代码只记录变量名。

浏览器从公开入口访问，远程 Agent 可通过隧道访问同一 Uvicorn 服务的 REST 和 `/mcp`。对两项基地址按受信配置解析，仅接受 http 或 https 的 origin，拒绝用户名密码、非根路径、查询及 fragment。请求 Host（含端口）必须匹配受信 authority，可由两个基地址或 `server.additional_host_envs` 的精确配置提供。额外入口只用于 Host 校验，不扩展浏览器 Origin、CORS 或链接生成范围。请求中出现的 Origin 仍按既有浏览器 origin 白名单核验。额外入口拒绝通配符、用户信息、查询串、fragment、非根路径和空环境值。Uvicorn 关闭代理头信任。网页同源调用，客户端不能通过自填 Host 或转发头改变返回链接。PostgreSQL 使用 `listen_addresses='127.0.0.1'` 和 `port=4001`，API 与 worker 的 DSN 指向 `127.0.0.1:4001`。[PostgreSQL 监听参数](https://www.postgresql.org/docs/18/runtime-config-connection.html)

若 Kafka 使用 Kerberos/GSSAPI、OAuth 或公司专用认证插件，需要在接入时确认依赖和配置适配；本稿不把未经验证的认证机制写成已支持。预编译 Linux 客户端对 GSSAPI 有额外安装条件。[Confluent Python 客户端安装](https://docs.confluent.io/kafka-clients/python/current/overview.html#installation)

### 3.1 如何填写一份报文映射

上例的 `ads_v1` 来自广告业务截图。结束枚举通过 `ADS_NORMAL_END_TYPE` 填写开发确认的实际字符串。截图中的 `timestamp` 和 `schemaVersion` 仍保存在原始报文中。时间单位确认后，例如确认为毫秒，再配置 `timestamp: {path: /timestamp, unit: ms}`。

| 映射项 | 约定 |
| --- | --- |
| `req_id` | 必填。路径必须取到非空字符串，原样作为 API 的 `reqId`。同一来源内，每次调用唯一，所有相关事件用同一值。缺失或类型错误记录来源和 Kafka 坐标，按缺口处理。 |
| `event_type`、`stage`、`timestamp` | 选填。前两者映射字符串，数值时间显式标注 `s` 或 `ms`。无业务时间时可查看入库时间，保留两者各自含义。 |
| `payload` | 选填，默认空路径 `""` 表示整条消息。配置路径后可取任意 JSON 值。路径缺失时省略规范化 `data`，路径存在且值为 null 时返回 `data: null`。两者均可查看完整业务 JSON。 |
| `formats.<format_ref>.completion` | 兼容旧配置的默认收齐规则。来源显式配置 completion 时，以来源规则整体替换默认规则，不合并各字段。 |
| `filter_fields` | 选填。仅声明需检索的事件维度，键为公开名，可带 label，type 首版为 string、integer 或 boolean。字段缺失或类型不符不参与匹配，原值仍可查看。按来源校验过滤名与值，未知条件返回 422。 |

路径使用 JSON Pointer，严格区分大小写。配置中的未知键报错，**业务报文中新增的键随原文保存**。首版只支持固定路径取值及类型化等值判断。[RFC 6901](https://www.rfc-editor.org/rfc/rfc6901)

订单为假设的接入样例。对下面的消息，平台提取 `reqId=dbg-001`、筛选项 `orderId=O-7`，正文为数组。这条普通事件与下一条结束事件使用相同请求 ID。请求达到 `COMPLETE` 仍需满足顺序落库和无已知缺口的条件。

```json
{"context":{"trace_id":"dbg-001"},"kind":"priced","order":{"id":"O-7"},"body":[{"amount":8}]}
```

```json
{"context":{"trace_id":"dbg-001"},"kind":"finished","done":true}
```

请求列表沿用 `GET /v1/requests`。例如 `?source_id=source_b&filter.orderId=O-7` 匹配至少一个事件满足条件的请求。多个维度须在同一事件上同时满足。详情可取提取后的正文或完整业务 JSON，导出保留原始结构和格式版本名。

### 3.2 为每个 Topic 配置收齐条件

上例中主链路、性能、入湖三个来源共用 `ads_v1` 解析 `/reqId` 和正文，分别判断 END、两条或一条有效事件。条数 2 和 1 仅演示配置，正式值由生产方提供。计数单位是同一 `(source_id, reqId)` 下已持久化的独立事件。

| 来源 completion 的写法 | 启动校验与运行含义 |
| --- | --- |
| `{path: /eventType, equals_env: ADS_NORMAL_END_TYPE}` | END。JSON Pointer 指向业务字段；`equals_env` 读取部署环境中的非空字符串，或改用 `equals` 直接指定 JSON 标量。两者选一；事件字段类型和值均匹配才命中。此前记录及 END 可查且无缺口后 COMPLETE。 |
| `{mode: expected_count, count: 2}` | 固定总数。count 必须是 1 至 `ingest.max_events_per_request` 的整数，拒绝布尔、字符串、零及超限值。仅当生产方承诺每个适用请求固定有 N 条独立事件时才能启用。允许同一 ID 跨分区，入库 N 条、无缺口时 COMPLETE。 |
| `none` | 仅观察。即使 format 有 END 规则，此来源也不发布 COMPLETE。只能查阅、导出已有数据。 |

加载时先查 `sources[].completion`，缺省时取对应 `formats.<format_ref>.completion`。两处均缺失，或显式给出 null、空对象、未识别模式、混用 END 与 count 字段，一律报错并定位到配置路径。旧格式保留的结束规则仍有效，上例订单来源即从 `orders_v1` 继承。升级不需要给所有旧来源补一份相同配置。

计数可选 `event_id_path`（例如 `{mode: expected_count, count: 2, event_id_path: /eventId}`），填生产方定义的稳定业务事件 ID 的 JSON Pointer。此字段仅适用于计数策略。未配置时依赖生产方保证业务记录唯一，相同 Kafka 位置的重放始终去重。配置后同一请求内按该路径取非空字符串，同 ID 同内容重投计一次，缺失、无效或同 ID 内容冲突使请求 INCOMPLETE。

服务端将有效策略与版本绑定到请求，重启、重放和恢复都使用原规则。同一模式修改 N 或实际 END 值时，沿用第 5 节的版本与切换流程。END、计数、none 之间的变化会改变来源发现的能力与分页视图；需要立即接入时启用新 source_id 并停用旧消费者，允许继续按旧来源读取已有数据。若复用原 source_id，须先排空在途请求和 Kafka 积压，等待旧快照与清理回执的保留期结束，再启用新能力。去重、超收和变长条数的处理见[多 Topic 交接稿](log_capture_platform_delivery/07_observed_topic_handoff.md)。

## 4. 共享运行参数与含义

以下默认值只作为首轮实现和压测的起点。表中配置均全局生效，除运行日志分别限制 API/worker 外，不因接入更多 source 复制一份额度。

| 配置组 | 默认值 | 行为与约束 |
| --- | --- | --- |
| `storage` 总额/暂停/恢复 | 20 GB / 16 GB / 可用额度至少 5 GB | 先有界清理，再重新读取实际额度及文件系统余量；只删除逻辑行不能触发恢复 |
| `storage.partition_seconds` | 60 秒 | 请求 first_seen 决定固定桶；已有桶不因重启改变归属 |
| `retention.ttl_seconds` | 300 秒 | 从首次成功入库算起，不因查询、end 或后续事件续期；首版可配范围 1～600 秒 |
| `retention.capture_timeout_seconds` | 120 秒 | 仅对声明结束条件的来源计时，必须小于 TTL |
| `retention.metadata_seconds` | 3600 秒 | 删除/过期标记从失去可用性算起，终态任务从结束算起；应覆盖约定最大迟到时间 |
| `retention.preview_seconds` | 60 秒 | 预览冻结集合的有效期，到期重做预览 |
| `ingest.max_sources` | 8 | 同时启用来源的部署保护值；不是产品长期上限或性能保证 |
| `ingest.poll_timeout_ms` | 100 ms | 单次 poll 最长等待，可因消息/事件提前返回；同时受未刷新批次的剩余等待时间限制，不是固定扫描周期 |
| `ingest.max_poll_interval_ms` | 300000 ms | 映射客户端 max.poll.interval.ms；应用两次消费调用间隔的故障判定上限，正常循环远低于它；后台心跳不能替代 poll |
| `ingest.max_event_bytes/max_events_per_request` | 50,000 B / 100 条 | 完整 UTF-8 JSON、包含 end，需与生产端确认；超限明确记录不完整 |
| `ingest.batch_max_events/bytes/wait_ms` | 500 / 4 MB / 100 ms | 数量、字节、等待时间任一达到即处理；暂停和 DB 争用时不承诺这一延迟 |
| `ingest.queue_budget_bytes` | 64 MB | 应用层待写和在途载荷合计；读取后解析对象另需内存余量 |
| `ingest.kafka_queue_budget_bytes` | 64 MB | 各 consumer 预取队列的总目标，按启用来源分摊；不是 RSS 硬上限 |
| `ingest.max_write_batches` | 2 | 全局最多两个写事务，同分区不能并发越过前一批 |
| `database.api_pool_max/worker_pool_max` | 4 / 4 | 共最多 8 个应用连接；MCP 复用 API 池，不另开池；worker 给 GC 留一个名额 |
| `database.statement_timeout_ms/lock_timeout_ms` | 5000 / 1000 | 限定语句和锁等待；长迁移在维护流程单独设置，不占常规池 |
| `cleanup.poll_interval_ms/max_wait_seconds` | 1000 / 5 | 每秒检查；任务达到批量阈值或最老等待 5 秒即调度，不要求凑满 |
| `cleanup.batch_max_requests/events/payload_bytes` | 100 / 1000 / 10 MB | 一次删除事务同时受三个上限约束；大任务可拆批，部分成功不提前 DONE |
| `control.metadata_budget_bytes` | 256 MB | 计入 20 GB；对存活元数据做入库前估算和定期核验，不等于精确物理预留；已删除行的可复用页不继续算存活预算，物理文件仍由 storage 统计 |
| `control.max_pending_cleanup_targets` | 20,000 | 未完成清理目标总量；达到上限拒绝新增任务，已受理任务继续执行 |
| `control.max_active_previews/max_preview_targets` | 100 / 1000 | 限制未过期预览数和单次冻结目标数；不能用无限预览耗尽元数据 |
| `control.max_error_records` | 1000 | 最近错误摘要数，原始 payload 不保存在错误记录；缺口事实另在进度中保留 |
| `api.batch_reqids_max` | 200 | 批量状态或精确清理的单次目标上限。跨来源 readiness 按唯一 (source_id,reqId) 对计数 |
| `api.page_size_default/max` | 50 / 100 | 请求、事件、任务列表共用上限；返回 cursor，不提供假 total |
| `api.response_max_bytes/request_timeout_seconds` | 8 MB / 15 秒 | 普通响应到字节上限提前分页；不适用于下载流，单事件仍受事件上限 |
| `export.max_requests/max_uncompressed_bytes` | 20 / 100 MB | 同一次下载的目标和快照未压缩字节上限，含导出清单 |
| `export.max_concurrent/memory_budget_bytes` | 1 / 256 MB | 全局导出并发及编码、对象、压缩缓冲总预算；不足则拒绝或缩小范围 |
| `export.link_ttl_seconds` | 60 秒 | 新签发票据最长寿命，同时受选中日志最早 expires_at 裁剪。重试 GET 不续期，已形成的下载快照遵循原发送超时。 |
| `export.max_active_links` | 100 | 全局可同时生效的票据数，跨 HTTP、MCP 和全部来源共享；元数据计入 control.metadata_budget_bytes，饱和返回 429。 |
| `export.snapshot_timeout_ms/send_timeout_seconds` | 5000 / 120 | 快照读取有界；释放 DB 事务后发送，慢客户端超时释放缓冲 |
| `mcp.enabled` | true | 关闭时不挂载 `/mcp`，REST/CLI/页面仍工作 |
| `mcp.response_max_bytes/tool_timeout_seconds` | 256 KB / 15 秒 | 元数据优先、有界分页；超过时引导查单事件或下载，不静默截断 JSON |
| `ui.poll_interval_ms/hidden_poll_interval_ms` | 2000 / 10000 | 活跃页与后台页轮询；无待更新状态时停止轮询，恢复可见后刷新 |
| `logging.level` | INFO | 不记录 Token、票据、完整下载 URL、payload、DSN。Uvicorn 访问日志与追踪亦须使用脱敏后的下载路由模板；DEBUG 遵守相同规则。 |
| `logging.api_max_total_bytes/worker_max_total_bytes` | 各 50 MB | 分别包含活跃与轮转文件；数据库日志也需单独设置轮转并计入总配额 |

平台固定单个 GC 执行循环，不为每个 source 启动一套 GC。元数据预算耗尽时拒绝新增预览/清理任务、暂停需要新建元数据的采集，并明确告警；继续已有任务及 TTL 清理，不删除未到期 tombstone 或未完成任务来腾空间。consumer_progress 与 source 身份记录不按一小时 TTL 自动删除；进度中的缺口采用起止位置、计数等有界摘要，不无限保存错误原文或区间列表。

普通 VACUUM 产生可复用页但文件没有缩小时，首版仍以实际可用额度满足恢复阈值为必要条件；可等待过期桶回收，不自动执行 VACUUM FULL。恢复阈值采用保守策略，可能降低吞吐。后续利用可复用空间更积极恢复，需另行验证。[PostgreSQL 空间回收](https://www.postgresql.org/docs/current/routine-vacuuming.html)

客户端预取限制可能被 Fetch 批次超过，单事件 50 KB 也不代表 Fetch 只占 50 KB。接入时核对 broker 的消息批次限制和客户端 fetch/receive 参数；64 MB 预取目标不构成进程内存保证。[librdkafka 配置](https://docs.confluent.io/platform/current/clients/librdkafka/html/md_CONFIGURATION.html)

### 4.1 必须校验的组合约束

1. 所有数量/时间/字节上限为正数；`capture_timeout < ttl <= 600`，`metadata_seconds >= ttl_seconds`，`preview_seconds <= ttl_seconds`。
2. `pause_at_bytes < limit_bytes`，`0 < resume_free_bytes <= limit_bytes`，且 `limit_bytes - resume_free_bytes < pause_at_bytes`，保证恢复条件比暂停条件更保守且可达到。配置不能超过实际专用卷额度；还需监测宿主文件系统实际剩余空间。
3. `batch_max_bytes >= max_event_bytes`，应用队列能容纳所有并发写批次；API 响应上限应容纳单事件及外层字段。
4. `worker_pool_max >= max_write_batches + 1`；GC 保留名额，不能被消费任务占满。
5. `page_size_default <= page_size_max`；导出上限受单独预算控制，不能因普通 API 响应上限而截断下载。
6. 预览、普通清理批次和导出必须全部属于一个 source；Token 仍对每个目标检查权限，参数校验不能替代授权。
7. 任何 source 不能通过自定义 consumer 参数覆盖自动提交、恢复规则、分区顺序或共享资源上限；首版不暴露任意 Kafka 参数字典。
8. `poll_timeout_ms < max_poll_interval_ms`；耗时 SQL、清理和导出不能阻塞消费线程。批次刷新按剩余期限缩短 poll 等待；暂停数据接收时仍需及时服务回调。
9. `link_ttl_seconds` 和 `max_active_links` 均为正整数。签发按所有目标实际到期时间裁剪，即使运行配置变更也不能给旧日志续期。导出服务和票据回收使用同一时基。

## 5. 首次接入、重启与来源变化

Kafka 客户端固定 `enable.auto.commit=false`、`enable.auto.offset.store=false`、`auto.offset.reset=error`。这是本项目使用的 **librdkafka** 配置，不能照抄 Java 客户端的 `none` 值。[librdkafka 配置说明](https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md)

| 场景 | 行为 |
| --- | --- |
| 新 source / 新分区，无数据库进度 | 根据 bootstrap_policy 选择 earliest/latest，先持久化启动位置，再开始处理；不沿用碰巧存在的其他 group 进度 |
| 已有 source 重启 | 根据数据库已持久化位置恢复，Kafka group commit 不能覆盖更可信的数据库事实 |
| 位置已超出 Kafka 保留范围 | 暂停该来源并报告缺口，禁止用 latest 自动绕过 |
| 改 bootstrap 地址 | 只允许仍指向同一真实 Kafka 集群；第一次连接记录 cluster 身份，后续核验 |
| 改 topic、换集群、topic 删除重建 | 创建新 source_id；旧记录、旧进度不复用，旧 ID 不自动重新绑定 |
| 改展示名或凭证 | 重启生效，身份不变；凭证错误只影响该连接涉及的来源 |
| 变更报文映射 | 格式版本名绑定不可覆盖的映射定义（包括实际结束值），数据库保留旧定义供在库事件读取。兼容性新增业务字段直接保留。修改提取规则或 format 级结束默认值则建新格式版本。仅修改来源级有效收齐规则时，在该来源登记新的不可变策略版本，其他共用此格式的来源沿用原版本。切换前停旧格式发送、排空在途请求和积压，按分区记录新版本起始 offset 后再启用；需并行发送时分开 topic/source。 |
| enabled=false | 停止消费，保留身份、进度和已有数据；恢复时仍检查是否发生 Kafka 保留缺口 |
| 从 YAML 移除 source | 作为停止接入处理，不自动删除 source 注册记录、进度或日志；查看旧日志仍需保留相应授权 |
| 改 TTL | 仅影响新请求；已有 expires_at 不重新计算 |
| 改分钟桶周期 | 属于存储布局变更，需要维护迁移；不能普通重启就重划已有数据 |
| 改 group_id / 人工回退 offset | 属于显式运维迁移，普通重启拒绝；跳过必须记录缺口，历史回放使用隔离来源/存储 |

数据库保存 source_id、cluster 身份、topic 身份、group_id 和初始化位置绑定。启动核验真实 cluster/topic 元数据，实际 Kafka 版本不能提供可靠 topic 身份时须明确评估替代检测，不能宣称已自动识别 topic 重建。注册绑定由接入流程维护，不由普通查询或清理接口修改。

使用 latest 首次接入会排除启动边界之前的事件。平台就绪后再发需要完整断言的请求；AITest 可每轮检查来源是否就绪，不要求逐请求预登记。对接入边界上已经在途的请求，只有 end 而无事件计数/序号时不能独立证明完整，不纳入正常采集保证。

健康信息分别显示来源状态与全局状态：`CONNECTING/RUNNING/DISABLED/ERROR/PAUSED`，加 reason、lag、最近入库时间和启动边界。一个来源 ERROR 不伪装成所有来源正常；全局容量 PAUSED 也不能只显示为单个 Kafka 连接故障。

## 6. 页面、客户端与平台配置的边界

新增 `GET /v1/sources` 返回当前凭证可见的 source_id、展示名、启用与采集状态，以及 `format_ref`、旧版单分区 END 能力 `completion_supported`、完整快照视图 `evidence_view`、可用事件字段和 `filter_fields` 的公开名、类型、显示名。停止接入的来源在有授权且仍有可查询信息时仍可列出。CLI 的 `logs sources list` 与 MCP 的 `logs_list_sources` 复用这份描述。连接参数、凭证和映射原文均留在服务端。

页面按 `source_id` 构造路由、查询缓存、请求详情、选中集合和下载入口。切换数据源后清空当前请求/事件选择、cursor 及多选集合，取消旧请求；旧来源结果不得覆盖新来源。前缀清理的预览、幂等键和具体目标也绑定来源及调用方身份。

新增只读 `GET /v1/ui-settings` 返回有权限页面所需的轮询间隔、分页上限、导出上限、readiness_batch_supported 及 MCP 是否启用等非敏感值；字段采用明确白名单，不序列化整个配置对象。前端不内嵌 Kafka 地址、Token 或数据库配置。

页面不展示“设计稿”“TTL 建议”“后台批量物理删除”“API/CLI/MCP”等实现说明。保留数据源、状态、剩余时间、错误原因、清理范围确认及真实受理结果。开发注释只解释非直观的边界，例如为何取消旧来源请求；不逐行复述代码或写无意义占位注释。

| 使用方 | 需要知道 | 不需要知道 |
| --- | --- | --- |
| AITest | API 基地址、Token 环境变量名、source_id；自身等待期限、规则和清理策略 | Kafka 地址/认证、PG DSN、平台资源调度 |
| 人工页面 | 用户粘贴的共享 human Token、可见数据源和实际操作权限 | broker、group、连接池、WAL 参数 |
| 用户电脑 CLI | API 基地址、凭证、source_id、本地输出路径 | Kafka 和数据库凭证 |
| 远程 MCP 客户端 | HTTP MCP URL、Token、工具参数中的 source_id | 本地 stdio 启动命令、服务端文件路径 |

AITest 的等待期限要参考平台返回的 expires_at，并在证据过期时给出明确结果；平台不会为 AITest 隐式延长保留。AITest 的具体配置字段留给独立升级方案，不将上述 log-platform.yaml 塞进 aitest.yaml。

## 7. 部署前需提供的真实信息与验收

在目标 Linux 开发机执行下列只读命令检查两个 TCP 端口。空输出表示检查时未发现相应监听，有输出时核对 Local Address 与占用进程。

```bash
ss -H -ltnp '( sport = :4000 or sport = :4001 )'
```

真实值尚未要求填写，实施接入时统一提供：每个 Kafka 的网络地址、认证方式、topic、保留期及访问权限；PostgreSQL DSN；受配额保护的数据目录；客户端可达的 HTTP 地址和端口；Token 与来源/前缀授权；机器 CPU、内存和可用文件系统能力。保留期和 broker 最大消息批次是接入前提，不由本平台擅自改 Kafka 配置。

多来源验收至少覆盖：两个集群使用同名 reqId 时查询/导出/清理互不影响；其中一个认证失败时其他来源继续；关闭再恢复来源不丢失进度；topic 重建不套旧 offset；前缀删除不跨 source；网页切换后无旧响应覆盖；多来源并发时共享额度与池上限不倍增；配置错误能定位到字段且不泄露凭证。

远程下载在 Agent 实际运行网络验收。首选用 httpx 通过隧道入口带 Bearer 直接 `POST /v1/exports`，流式保存并校验 gzip，无需平台 CLI。仅接受 GET 的 Fetch 走兼容流程：先带 Bearer 请求 `POST /v1/export-links` 或调用远程 MCP 的 `logs_export`，再按 download_url 下载。分别验证配置隧道地址和省略配置的回退，web_url 应始终指向公开地址。用可控时钟检查票据与日志最早到期时间，并发签发验证票据限额和回收。在访问日志和错误报告中确认真实下载 path 已脱敏。[签发和兑换约定](log_capture_platform_delivery/02_http.md#41-给远程-agent-和普通-fetch-的下载链接)

所有容量参数在真实目标机压测后才能成为运行承诺。本轮交付的是配置合同和设计文件，没有连接 Kafka、修改 PostgreSQL 配置或部署远程 MCP。
