# 分片 01 · 平台连接、批量状态与事件快照

本片交付 Kit 到日志平台的 HTTP 客户端及配置接线。平台判定收齐，返回来源视图、请求状态和版本；协调器使用本片接口调度未决项。协议以[平台交接稿](../../log_capture_platform_delivery/07_observed_topic_handoff.md)为准。

## 1. 一个 run 使用哪个平台

`aitest run` 自动读取 workspace 的 `aitest_config/log_assertions.yaml`。为 `platform` 新增可选字段 `base_url`，配置版本继续为 1。以下是格式示例。

```yaml
schema_version: 1
platform:
  base_url: http://bridge.example.invalid:21001/logs/
  token_env: AITEST_LOG_TOKEN
```

| 输入 | 运行行为 |
|---|---|
| YAML 含 `base_url` | 直接采用该 URL。允许 HTTP、HTTPS、显式端口和服务基础路径。即使 `base_url_env` 指向另一个地址，也采用 YAML。 |
| YAML 省略 `base_url` | 从本单元已加载的环境读 `base_url_env` 指定的变量，缺省 `AITEST_LOG_BASE_URL`。无平台调用的旧 suite 可以在无 URL、无 Token 的环境运行。 |
| 显式 null、空白、非字符串、缺 scheme/host、含 userinfo、查询串或片段 | 配置失败。错误提示指出字段，避免回显输入。env 提供的 URL 在需要使用时做相同校验。 |
| Token | 始终从 `token_env` 指向的变量读取，缺省 `AITEST_LOG_TOKEN`。兼容 shell、现有 dotenv 加载及 task 的 env_files。YAML 不新增明文 token 字段。 |

实现从 `log_assertions/config.py` 的 `RunSettings`、`_SECTIONS`、`load_settings` 一直接到 `coordinator.py:credentials` 和 `run.py:resume`。首次连接前解析有效地址、规范化末尾斜线，使用同一个值计算既有 URL hash 与构造客户端；`/logs/` 下的请求应实际到达 `/logs/v1/…`。客户端沿用显式 HTTP transport、`trust_env=False`、关闭重定向、Bearer header。预检、状态、翻页和清理共用连接池及凭证。

同一 run 的多个执行单元比较**有效 URL 与 Token 身份**；采用 YAML 直配时，各单元被覆盖的 URL 环境变量可以不同。同一 run 出现多个有效入口或身份时明确报错。不同任务可以使用各自 workspace 的隧道地址。Agent 在任务启动前用获得授权的 `connect_host/connect_port` 和原服务路径维护本次工作副本。Kit 按文件取值，隧道由 Windows 侧建立。真实可达性须从 Runner 检验。

**恢复。** 用当前 workspace 的状态目录定位旧库，从 `run.settings` 恢复原设置。新库持久化经验证的直配地址或原 env 引用、现有 URL hash、带盐 Token 指纹和单元 env 文件路径。旧库缺 `base_url` 按 env 模式解码。直配 A 的旧 run 遇到 YAML 改 B 时仍联系 A；env 模式重新加载原引用，解析到 B 时在首次 HTTP 前按原 URL hash 拒绝。多单元恢复也比较有效值。保留原只读取证的权限预检和清理的**原 Token 指纹匹配**要求；凭证值不得进入库、报告和日志。已有终态且无待办的恢复无需网络。

## 2. 协商来源能力

沿用 `log_assertions/client.py:LogPlatformClient` 的 `get_limits` 与 `list_sources`。每个客户端从 `GET /v1/ui-settings` 读取并缓存 `batch_reqids_max`、`page_size_max` 与可选布尔 `readiness_batch_supported`。保留旧 `get_limits()` 返回的两个限制键，另以客户端属性暴露新标志；标志缺省为 false，类型错误报协议错误。上限仍为 `min(200, batch_reqids_max)`、`min(100, page_size_max)`，两个平台上限均须为正整数。

从 `GET /v1/sources` 解析每个已选来源的 `evidence_view`，供正常预检、后台取证和恢复共用。

| 来源声明 | 预检与快照读取 |
|---|---|
| `single_partition`，或旧响应省略视图且 `completion_supported=true` | 选择原单分区视图。 |
| `partitioned` | 选择跨分区视图。平台对此类来源通常返回 `completion_supported=false`。 |
| 来源未启用、无可断言视图、未知视图或动作不足 | 报出具体来源及所缺能力，在该单元业务调用前停止。每个实际来源要求 read；声明 on_success 的来源还要求 cleanup。 |

旧平台回退条件是缺少或关闭批查能力，且所需来源仍能通过来源预检。能力与权限按该次 run 的入口、身份和来源解析；恢复时重新发现能力，校验与已登记的快照视图一致（历史单分区记录按旧契约解释）。

## 3. 客户端接口与校验

在现有客户端增加 `get_readiness(pairs, *, deadline)`；`pairs` 是有序的 `(source_id, reqId)` 对列表。每次方法调用只发一个 HTTP 请求，由协调器去重、按上限分批并决定重试。保留现有 `get_statuses(source_id, correlation_values, *, deadline)`。

| 平台能力 | 请求 | 成功响应 |
|---|---|---|
| 批查启用 | `POST /v1/requests/readiness`，如 `{"items":[{"source_id":"main","reqId":"r1"},{"source_id":"perf","reqId":"r1"}]}` | `items` 与输入逐位置一一对应，外层和 FOUND 内层的两项身份都要校验。 |
| 批查缺省或关闭 | 将到期对按来源分组，各自 `POST /v1/requests/status`，如 `{"source_id":"main","reqIds":["r1","r2"]}` | 沿用 0.7.0 响应校验。调用端用请求的 source_id 和每项 reqId 恢复复合键。 |

请求中每对占一个名额，拒绝空批、超限、空 ID 和重复对；同一 reqId 跨来源合法。响应缺项、多项、重复、错序、来源混淆、FOUND 身份不符、NOT_FOUND 的 request 非 null、未知状态均为协议错误。可选 `expected_event_count` 有值时须为正整数，用于报告已收/应收；旧平台可缺省。仅 `capture_state=COMPLETE` 且 `availability=AVAILABLE` 才允许取证，COLLECTING 即使已收数等于应收数也继续等待。HTTP 403 对整批生效；成功响应通过完整校验后才推进其中任何一项。平台声明了批查但返回 404、鉴权错误或坏响应时显式报错。

平台返回 `422 TOO_MANY_TARGETS` 且携带更小的合法上限，交调度器按新上限重排；其他 422 不拆批，403 不拆批探测。沿用现有超时、可重试的网络/408/429/5xx 错误和受截止时间限制的 Retry-After；HTTP 客户端不自行循环重试。

## 4. 收齐后按来源读取一份快照

向 `read_snapshot(source_id, correlation_value, expected_version, *, deadline)` 追加**可选**关键字 `evidence_view`，默认 `single_partition`。已有调用及现有单分区返回结构继续可用。协调器传入该来源已协商的视图和状态给出的 version。多组规则共享同一来源的整份事件列表，随后本地筛选。

每页调用 `GET /v1/requests/{encodedReqId}/events`，保留现有 ID 路径编码、`source_id / expected_version / include_data=true / page_size`。第二页起附 `cursor`。每页校验请求身份、COMPLETE、AVAILABLE、version、稳定的 event_count、items 与 next_cursor。整个读取共用原 deadline 和总预算，默认最多 8,000,000 响应字节、10,000 条事件、1,000 页。

| 视图 | GET 差异与整份快照的不变量 |
|---|---|
| single_partition | 沿用旧 GET 形状。每页 upper_offset 一致，事件属于同一分区，数值 offset 严格递增且不超过上界；末项 offset 与上界相等。空快照按旧契约处理。 |
| partitioned | 增加 `evidence_view=partitioned`，每页校验返回同名视图。按数值 `(partition, offset)` 在页内和跨页严格递增；跨分区相同 offset 合法。此视图不需要 upper_offset。快照返回 request、items 和 evidence_view。 |

两条路径均检查 event_id 跨页唯一、最后页唯一事件总数等于 event_count、重复/空转游标、数字类型、字节和页数上限。offset 沿用平台十进制字符串编码，按整数比较；不据 offset 间距推断丢失事件。409 VERSION_CONFLICT 或 422 INVALID_CURSOR 使整份在读快照失效，协调器回到查状态。410、403、预算超限、200 坏页不能产生部分断言结果。客户端保留原始业务 JSON 数值、空值和字段大小写。

## 5. 本片验收

在 `tests/test_log_platform_client.py` 用 MockTransport 记录 URL、请求体、页次和次数；在 `tests/log_assertions/` 以临时 workspace 和本机 HTTP 替身覆盖正常入口与恢复。用虚构测试凭证验证脱敏。

| 场景 | 必须观察到 |
|---|---|
| 直配 + 相冲突 env、纯旧 env、无效 YAML、子路径，两个独立工作区 | 分别命中有效入口；非法值报字段错误；路径未丢失；零日志旧 suite 无需凭证。 |
| 新/旧库恢复，直配 A 后改 B、env 从 A 改 B、同一 URL 不同 token 的清理 | 恢复走原目标或在网络前拒绝；不向错误目标或以错误身份提交清理。 |
| 新标志 true/false/缺失/类型错误，跨来源同 ID，旧 END、计数、纯观察来源 | 协商限值/视图正确；旧调用形状兼容；不支持的来源在预检阻止业务调用。 |
| 混合 FOUND/NOT_FOUND、响应缺/错/重项、限额、403、状态启用但路由缺失 | 一次 HTTP 处理合法批，不误认同名 ID，非法整批无部分提交，不隐式切换协议。 |
| 分区 0/offset 9、10 和分区 1/offset 9 分两页；中间版本变化、游标无效、相同 ID、错序、丢页或超预算 | 合法情况恰读两页；异常时无部分事件交给执行器。单分区仍拒绝跨分区。 |

实现后运行 `python3 -m pytest -q tests/test_log_platform_client.py tests/log_assertions`。全量构建、wheel 与公司隧道联调由最后验收分片记录。
