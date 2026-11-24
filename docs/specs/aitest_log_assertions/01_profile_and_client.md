# 01 · 用例接入、断言规则与日志客户端

2026-11-19 · 详细实现 Spec · 尚未实现

本片落实[总体方案](../aitest_log_assertions_overall_design.md)第 3 节，交付可校验的 profile、生成接线、Harness 公共入口、规则解释器和日志 HTTP 客户端。登记持久化、并发与恢复由 [02](02_execution_and_recovery.md)实现；最终结果及清理准入由 [03](03_results_and_cleanup.md)实现；模板升级及 Agent 验收见 [04](04_acceptance_and_agent.md)。本片不修改待测服务协议。

## 1. 实施基线与兼容边界

已用 `git show v0.6.0:<path>` 核对发布基线：Python ≥ 3.9，已有 httpx、pytest、jsonschema、jsonpath-ng；下文现有路径均存在于该 tag。当前 checkout 的版本号不能替代实施基线。

- 保留 Markdown → profile gate → Case IR → generated pytest → freshness 链路；不修改 Markdown parser，不改变生成策略优先级。
- 首版将日志规则接入 `structured_case_flow`。旧 `steps[].assert`、`structured_assertions`、`case_bodies` 的语义与生成文本保持不变；不自动给旧 suite 开启日志检查。
- 只有含日志规则的被选调用才生成包装代码、依赖协调器及模块来源配置。没有该能力的旧 workspace 不要求日志平台、Token 或新运行配置。
- 新规则属于 suite profile，module profile 不接受 TC-ID 绑定规则；与 `case_bodies` 的策略冲突沿用既有门禁。
- 新运行配置位于 `aitest_config/log_assertions.yaml`；平台 URL、Token 只引用环境变量名，具体字段、优先级及期限归 02。Kafka 配置始终属于独立日志平台。

## 2. Profile 的确定语法

`case_flows.<TC-ID>.log_assertions` 为可选非空数组，与 `steps` 并列。每项是一个检查组，只允许下列字段；未知字段报错。

| 字段 | 类型、默认与约束 |
| --- | --- |
| `request_step` | 必填字符串，引用同一 flow 中唯一一个 `call` 步骤的 `save_as`；不能引用 `assign`、即时断言、其他 case 或不存在的名称。|
| `select` | 可选对象，默认 `{}`。仅允许 `eventType`、`stage`，值为非空字符串，按大小写敏感等值 AND 筛选；缺字段不匹配。空对象选全部事件。|
| `expected` | 可选对象，默认 `{}`；键为非下划线开头的 Python 标识符，值按第 3 节解析。|
| `checks` | 必填非空字符串数组；每项必须是一个受控 Python `assert`，按声明顺序执行。|
| `cleanup` | 可选 `on_success` 或 `retain`。同一步多个检查组的显式值必须一致；至少一个显式值时采用它，全部省略时为 `retain`。|

有日志规则的 flow 禁止重复使用任何 `save_as/assign` 名称，避免请求步骤被覆盖；旧 flow 保持现有规则。一个请求步骤只产生一个实际采集请求，内部重试或多请求必须拆为可单独命名的调用；不能让一个关联值代表多个尝试。

```yaml
variables:
  defaults:
    minimum_score: {value: 0.5}
case_flows:
  TC-DEMO-001:
    steps:
      - call: harness.query
        save_as: reply
      - assert: 'assert reply["code"] == 200'
    log_assertions:
      - request_step: reply
        select: {eventType: SCENE_HIT}
        expected:
          keyword: "命中"
          minimum: {from_var: minimum_score}
          response_score: {from_response: /score}
        cleanup: on_success
        checks:
          - 'assert len(events) == 1'
          - 'assert expected["keyword"] in events[0]["data"]["message"]'
          - 'assert events[0]["data"]["score"] >= expected["minimum"]'
          - 'assert events[0]["data"]["score"] == expected["response_score"]'
```

上述业务名称和值仅用于交付示例和测试夹具。每组取得独立筛选后的 `events`，保留平台 offset 升序，不按业务 timestamp 重排；结束事件也包含在完整快照中，是否参与检查由 `select` 决定。无匹配得到空列表；不能替用户添加“至少一条”的隐式断言。

## 3. Expected 输入及冻结

`expected` 的每个顶层值是一个原子输入，规则如下；嵌套字典不会递归查找变量占位符。

| 写法 | 含义与解析时机 |
| --- | --- |
| 普通 JSON 值 | 静态常量；请求前校验、深拷贝并持久化。|
| `{from_var: name}` | 从现有 profile `variables.defaults/cases` 解析；遵守 case 覆盖 default 及 `require_env` 的前置失败语义，请求前冻结。|
| `{from_response: "/score"}` | 从被选调用的返回 JSON 值按 JSON Pointer 取值；空串取整个返回值，支持 `~0/~1` 及数组下标，请求返回后冻结。|
| `{literal: <JSON>}` | 强制字面值，用于值本身恰有保留字段的情况。|

出现 `from_var/from_response/literal` 中任意保留键时必须是且只能是对应的单键包装；否则门禁报错。静态字面值不得含凭证，敏感 env 也不得通过 expected 持久化。env 值仍按现有机制得到字符串，不隐式转数字。

返回值只有在使用 `from_response` 时要求是安全 JSON 值；Harness 应返回解析后的业务 JSON，不能传 `httpx.Response`、ORM 对象、fixture、客户端、函数或任意用户对象。只允许 `null/bool/str/int/有限float/list/字符串键dict`，拒绝循环结构、NaN/Infinity、非法键及深度超过 64；大整数保留 Python int。后台不重新读取环境变量或响应对象。

同一请求的所有输入冻结成功后才可执行任何检查组。Pointer 缺失、索引越界或不安全输入产生 `LOG_INPUT_ERROR`，保留来源指针和安全摘要；不执行剩余规则，不把输入错误记为业务断言失败。响应数据缺失本身若是业务预期，应显式把完整 JSON 作为输入后使用 `in/get` 检查。

## 4. Python 断言子集与判定

用标准库 `ast.parse(..., mode="exec")` 解析，每条恰好一个 `ast.Assert`；可选消息只能是字符串字面量。执行采用白名单 AST 解释器，不使用 `exec/eval`，不把日志字符串再解析成代码；解释器在 02 管理的可终止子进程中运行。

| 允许能力 | 明确边界 |
| --- | --- |
| 名称与值 | 仅 `events`、`expected`、JSON 常量、当前生成式的局部变量和下列纯函数；无 pytest、Harness、reply、模块或全局变量。|
| 索引与容器 | list/dict 的索引、JSON 常量 list/dict/tuple；字典只能用字符串键；不支持切片、集合、字典展开。|
| 布尔与比较 | `and/or/not`、`== != < <= > >=`、`in/not in`、`is/is not` 仅比较 None/True/False；短路规则保持 Python 行为。|
| 数值 | 一元 `+/-`，数值 `+ - * / %`；禁止集合/字符串乘法、幂、位运算、移位；整数中间值超过 4096 bit 报资源错误。|
| 纯函数 | `len(x)`、`any(iterable)`、`all(iterable)`、`regex_search(pattern,text)`、`regex_fullmatch(pattern,text)`。正则函数返回 bool，不暴露 Match 对象。|
| 方法 | 实际接收者为 str 时允许 `startswith/endswith/strip/lower/upper`；dict 时仅 `get(key[,default])`。只允许方法调用位置的这几个属性名，禁止其他属性访问。|
| 列表判断 | `any/all` 可接列表或单层生成式；生成式只允许一个局部名字、一个 for、可选 if；禁止嵌套生成式、推导式、异步遍历和变量泄漏。|

禁止 import、赋值、海象、lambda、函数/类定义、异常处理、任意循环语句、其他函数调用、反射、下划线属性、文件/网络/进程访问。每个 AST 节点执行计费，生成式每次迭代也计费；达到预算立即停止，不能只对源码节点数计费。

```python
assert "命中" in events[0]["data"]
assert regex_search(r"scene=\d+", events[0]["data"])
assert len(events) > 0 and all(e["data"]["score"] >= expected["minimum"] for e in events)
assert any(e["data"].get("selected") is True for e in events)
```

`all([])` 仍为 True，要求非空必须像示例显式声明。正则 pattern 必须是源码字符串字面量，门禁用 `re.compile` 校验；文本必须是 str。子进程时限覆盖灾难回溯，线程超时不能替代硬终止。

| 结果 | 判定 |
| --- | --- |
| `PASSED` | 当前请求所有组、所有 check 的测试表达式为真。|
| `FAILED / ASSERTION_FAILURE` | 表达式正常求值为假；报告组序号、check 序号、原文和有界证据定位。|
| `ERROR / RULE_ERROR` | KeyError/IndexError/TypeError/除零、解释器资源超限或执行超时；不是已证实的业务不符。|
| `ERROR / LOG_INPUT_ERROR` | expected 无法取得或冻结，规则尚未开始执行。|

每组遇首个失败/错误即停止该组后续 check，其他组仍执行以保留发现；请求结果按 ERROR > FAILED > PASSED 合并。报告保留未执行原因。规则执行总时限由 02 的 `execution.check_timeout_seconds` 控制，默认每请求 2 秒，不因组数增加而重置。

硬上限：每条源码 4096 字符、AST 512 节点、深度 32；每请求最多 32 组、每组 32 条；每请求冻结 expected JSON 编码 ≤ 65536 B；每请求求值最多 100000 次节点/迭代；正则 pattern ≤ 1024 字符、文本 ≤ 65536 字符。先检查长度再解析；超限是明确规则错误。旧即时 Python 断言不受这套新增限制。

## 5. Harness、generated 与运行时接线

module registry 新增可选 `module.yaml.log_capture: {source_id: "实际来源标识"}`。source_id 为非空字符串；首版一个 module 固定一个来源，多源通过不同 module 配置。加载后保留于 ModuleContext/ModuleBinding，预检在本单元发出业务请求前确认所选来源可见、enabled、completion_supported 及 read 动作；申请 on_success 的计划还需 cleanup 动作。来源 actions 只是初检，实际请求级 403 仍是访问错误。

接入 fixture 从 Kit 已解析的 `ModuleContext.log_capture.source_id` 传入 Harness，供示例的 `self.log_source_id` 使用；不得再维护一份来源字面量。保持既有公开构造调用兼容，可用可选关键字配置本模块新增接入；未接入 module 的 fixture/Harness 无须修改。

Kit 对 Harness 的公共入口固定为：

```python
from aitest_kit.log_assertions import bind_log_request, log_capture_requested

def query(self):
    if not log_capture_requested():
        return self.client.query().json()
    payload = self.call_with_capture().json()
    bind_log_request(self.log_source_id, payload["trace_id"])
    return payload
```

`log_capture_requested() -> bool` 只读取当前请求步骤上下文。仅在本次调用的日志计划已成功登记且 scope 仍有效时返回 True。示例中的 `call_with_capture` 由该业务的 Harness 实现。Mixer 可以在这个分支中生成独立 reqId、先绑定关联值，再按自己的协议设置 mask 并发送。旧用例、同一用例未声明日志的调用都走原协议，连返回体里的 trace_id 也无须存在。通过测试比较这两类调用的实际请求参数和响应处理。

`bind_log_request(source_id: str, correlation_value: str) -> bool`：在当前已选步骤中同步持久化绑定，成功返回 True；无日志步骤上下文时返回 False，使同一个 Harness 能用于旧用例。存在上下文但协调器缺失、参数非法、来源不符或持久化失败时抛 `LogBindingError`，不得返回 False 吞错。重复绑定相同二元组幂等，改绑另一值或跨请求复用关联值报错。不能靠业务字段名或 reqId 前缀推断当前请求。

客户端生成关联值的服务应在发送前调用 bind，返回关联值的服务按示例在响应后调用。业务适配只提交来源和唯一关联值；`mask`、header、协议字段映射归 Harness。fixture 只创建/释放资源，不等待 Kafka 或平台日志。

generated 为被引用的 call 生成下列内部包装，原调用参数、save_as 及后续即时断言保持不变：

```python
with log_request_step(request_step="reply", rules=RULES,
                      expected_inputs=STATIC_INPUTS) as scope:
    reply = harness.query()
    scope.freeze_response(reply)
```

`log_request_step` 和 `scope.freeze_response` 的运行实现归 02：进入时先事务保存计划、规则版本/hash、静态输入、请求身份及截止时间，再设置当前步骤 ContextVar，只有提交成功才调用 Harness；返回后一次事务冻结响应输入。无动态输入也调用 freeze_response 标记输入齐备。退出总是重置 ContextVar，进程/线程边界不隐式传播。

登记身份统一为 `(run_id, unit_index, nodeid, attempt, request_step)`；nodeid 保留参数化后缀。02 的 case_instance_id 由前四项派生。外部查询键仅 `(source_id, correlation_value)`。同一步多个组共用一份登记和日志快照。因前序即时断言失败而未执行的步骤不登记假请求，报告为 NOT_STARTED，不产生清理。

业务抛错且未绑定时终结该计划为 `LOG_BINDING_ERROR`；正常返回却未绑定也同样报错。已绑定且 expected 全部静态时，scope 退出即使带业务异常也标记输入齐备，使后台仍可取证；动态输入无法取得时为 LOG_INPUT_ERROR。保留原业务异常作为 pytest 失败主因，绑定/输入错误作为独立日志错误；finalizer 不能覆盖原异常。

分片 1 定义上述 scope 的调用协议和公共函数外观，以本地记录替身验证 register → bind → freeze/exit 的调用顺序，不实现 SQLite 或调度。规则解释器提供 `evaluate_request(rules, events, expected_inputs)` 纯计算入口，接受安全值并返回各组结果；分片 2 负责将其置于受限子进程及接入真实持久化。分片 1 可独立通过，只有分片 2 接线后才能宣称真实 run 已具备此能力。

## 6. 日志 HTTP 客户端

实现 `aitest_kit/log_assertions/client.py`，只实现平台 HTTP 适配，不消费 Kafka。下表方法全部是 async，并统一接受关键字参数 `deadline`（事件循环单调时钟的绝对秒数）。认证为 Bearer；使用 `httpx.AsyncClient(transport=httpx.AsyncHTTPTransport())`、禁止重定向，base_url/env Token 来自 02 已解析配置，禁止在诊断记录 Token、完整 headers 或正文。

| Python 方法 | HTTP 与返回契约 |
| --- | --- |
| `list_sources()` | GET `/v1/sources`，返回授权 Source 列表，含 completion_supported/actions。|
| `get_limits()` | GET `/v1/ui-settings`，每轮启用日志时在预检读取一次 `batch_reqids_max` 和 `page_size_max`。校验为正整数并缓存；运行时用二者与 Kit 上限中的较小值。|
| `get_statuses(source_id, correlation_values)` | POST `/v1/requests/status`，JSON `{source_id,reqIds}`；非空、无重复、单源，每批至多 min(200, batch_reqids_max) 项。按输入逐项核对结果，不允许漏项/重项/换ID。|
| `read_snapshot(source_id, correlation_value, expected_version)` | GET `/v1/requests/{reqId}/events`，query 必带 source_id、expected_version、include_data=true；page_size=min(100, page_size_max)，用返回的 next_cursor 发下一页，返回同版本完整快照。|
| `submit_cleanup(source_id, correlation_values, idempotency_key)` | POST `/v1/cleanup`，精确无重复 reqIds 及 `Idempotency-Key`；只把合法 202 视为已受理，返回 source_id/job_id/state/accepted_at/target_count。|
| `get_cleanup(source_id, job_id, cursor=None)` | GET `/v1/cleanup/{job_id}`，source_id 必填，返回回执页；本轮不要求等待物理删除。|

平台协议以[交接稿 02](../log_capture_platform_delivery/02_http.md)为准。请求 ID 编码共用一个函数：普通值按一个 UTF-8 URL 段转义；含 `/`、整段 `.`/`..` 或以 `~` 开头时用 `~` 加无填充 base64url；JSON/query 中保留原始值。不能用 urljoin 让业务 ID 改写主机或路径。

每个 HTTP 请求只尝试一次，客户端不 sleep；状态轮询和失败重试由 02 在剩余期限内安排。分页是一次逻辑读取中的多次请求，不是自动重试。每个请求超时取配置 timeout 与剩余截止时间的较小值；截止前无法发请求时立即停止。02 用 `asyncio.wait_for` 约束整个批查或 read_snapshot 的剩余时间，包含全部分页；客户端异步流在 finally/aclose 释放连接，CancelledError 原样传播，不能吞掉后重试。慢速持续送字节也不得绕过整体截止时间。

read_snapshot 不在服务端传 select，各组复用完整快照后本地筛选。每页核对 source_id/reqId、COMPLETE、AVAILABLE、相同 version/upper_offset，event_id 唯一、offset 单调、请求分区一致；最后累计事件数必须等于该版本 event_count。保留 data 缺失与显式 null 区别，不字符串化 JSON，不按 offset 数值差推算事件数。

单 HTTP 响应硬上限为 8000000 B。单快照有效预算读取 02 的 `execution.snapshot_max_bytes/snapshot_max_events/snapshot_max_pages`，默认分别为 8000000 B / 10000 / 1000，可配置更低值，首版硬上限等于上述默认值。流式累计解压后的 HTTP 正文字节，各页合计恰好等于预算时允许，继续读到超出预算的字节时立即关闭。游标循环、空页仍有 next_cursor 或超限，返回相应的 `PLATFORM_PROTOCOL_ERROR` 或 `EVIDENCE_LIMIT`。完整快照返回后才开始求值。

| 情况 | 交给 02 的结果 |
| --- | --- |
| NOT_FOUND、COLLECTING | 待观察/采集中，保留截止时间继续轮询；不返回空证据成功。|
| COMPLETE + AVAILABLE | 可按明确 version 读取；获知 expires_at 后收紧读取窗口。|
| INCOMPLETE、TIMED_OUT、OBSERVED；DELETE_PENDING/DELETED/EXPIRED | 明确证据错误及 reason；不得尝试完整性断言。|
| 409 VERSION_CONFLICT；422 INVALID_CURSOR | 丢弃本次所有页，通知协调器重新查状态并从第一页开始，仍受原期限约束。|
| 401/403、其他 422、未知错误码/畸形响应 | 不重试参数或权限错误；结构化报告访问/协议问题。|
| 网络错误、408、429、5xx | 可重试访问错误，保存安全原因；429/503 解析有界 Retry-After，不延长截止时间。|
| 410 | 证据不可用终态；保留服务端 availability。|
| 清理 409 IDEMPOTENCY_CONFLICT | 明确清理错误，不换键重发。响应丢失后用原精确集合与原键重试。|

列表 actions 不代替权限校验，精确批量 403 不拆单探测。cleanup 意图和幂等键由 02/03 先持久化，客户端不自行生成新键、不按前缀删除。未知/已过期清理回执不等于“从未提交”。

## 7. Schema、IR、诊断与文件归属

新增 LogAssertionGroupIR 包含 request_step、group_index、select、expected 的 provider/source 描述、checks 原文及位置、cleanup、executor_version=1、规则 SHA-256；其对应 RequestPlan 按 request_step 分组。hash 对规范化规则、输入来源、清理策略及执行器版本计算，JSON 键排序、UTF-8 编码；动态输入值只进入运行状态，不进入 codegen freshness。

规则源码和执行版本均持久化，恢复不重读已编辑的 profile；执行器不支持旧版本时明确拒绝恢复，不能重新解释成最新语义。模板新增诊断：E533 日志结构/请求步骤；E534 AST 语法/名称/操作/资源上限；E535 expected 来源；E536 cleanup 冲突或模块日志声明错误。消息必须含 profile 路径、TC-ID、组/check 索引及字段；错误使 gate 阻止 IR/emitter。

| 位置 | 实施要求 |
| --- | --- |
| `codegen/profile.py`、`profile_validator.py`、`profile_merge.py`、`resolved_profile.py` | 接受 flow 新字段、保留 suite 归属，新增独立 `log_assertion_validation.py` 承担校验；避免继续扩大已有超 500 行文件。|
| `codegen/profile_variables.py`、`planner.py` | 收集 from_var 引用并纳入既有变量解析；同一变量只解析一次。|
| `codegen/ir.py`、`case_flow_planner.py`、`flow_rendering.py`、`ir_renderer.py`、`explain.py` | 生成计划/包装；新逻辑拆独立 `log_assertion_rendering.py`，旧无日志分支不变。|
| `registry/models.py`、`loader.py` | 加载/传递可选 log_capture；只有用例含日志规则时门禁才要求该声明，不影响旧 module。|
| 两份 `aitest_config/schemas/codegen_profile.schema.json` | 同步仓库与 `aitest_kit/templates/project_workspace/` 包内版本；增加可选 flow 字段、group/provider schema；不放宽未知字段校验。|
| 新 `log_assertions/{__init__,rules,values,client}.py` | 公共绑定入口、AST 白名单解释器、安全输入/Pointer、HTTP DTO/错误；运行 scope/持久化实现归 02；每文件 ≤ 500 行。|
| profile/config 手册、troubleshooting、模板 refs、skills | 新增 `aitest_config/refs/log-assertions.md` 并同步包内模板；test-scaffold/test-codegen 三处本仓 skills 与唯一模板 skills 同步能力及范例。|

`--validate-profile` 离线完成所有静态检查，不访问平台；`--dump-ir`、`--explain` 展示请求步骤、筛选、每条原文、expected 来源、清理策略及新能力版本；`--check` 感知规则变化，仍不发送业务请求。平台来源能力、当前 Token、动态返回类型在运行前/运行时验证。

旧 workspace 优先读取自己的 schema。04 的 upgrade 流程必须交付更新 schema 与指南，保留自定义内容、显示冲突，禁止覆盖用户文件或只升级 wheel 后假定新字段可用。

示例唯一源为 `aitest_kit/templates/project_workspace/examples/log_assertions/`；`pyproject.toml` 的该 package-data 增加实际嵌套文件的明确匹配，核对 wheel/sdist 成员。init 复制到 workspace 的 `examples/log_assertions/`，不自动注册或填入业务 targets/suites；不建立仓库根 examples 的第二份维护源。

分片 1 交付可独立生成与 collect 的最小样例，含 README、知识/用例、`test_workspace/targets/demo/modules/log_demo/` 的 Harness/fixture/profile/registry，以及 `test_workspace/suites/demo/log_assertions/suite.yaml` 与 suite profile。分片 1 的测试从已初始化临时 workspace 的 examples 目录复制这些资产到对应 test_workspace 位置，并执行 gate、IR、codegen、freshness 与 collect。分片 4 复用这份样例，增加多请求场景并提供端到端 HTTP 服务。

## 8. 失败测试与分片验收

先新增失败测试，再做本片实现；测试使用 fake transport、内存输入、受控本地运行适配，不访问真实业务/Kafka、不生成假通过结论。

1. `tests/test_log_assertion_profile.py`：合法静态/变量/响应输入；跨 case/assign/重复名字引用；未知字段；provider 歧义；缺变量；cleanup 冲突；错写 reply；AST 越权；文本、JSON、正则、any/all；每项定位准确。
2. `tests/test_log_assertion_rules.py`：字符串/列表/JSON 类型保持；empty all；布尔短路；索引/类型错误与 false 区分；数量检查失败跳过同组后续；其他组继续；计步、源码、大小、嵌套；没有活对象进入执行器。正则硬超时、强杀后释放执行名额的进程测试归 02。
3. `tests/test_log_assertion_binding.py`：本地记录替身模拟登记失败不发业务调用；前置/响应后绑定；source 不符、重复改绑、跨请求重复ID；无上下文旧调用返回 False；缺协调器明确失败；异常不覆盖；静态/动态输入分流；未执行步骤无假登记。真实 SQLite 提交、崩溃与恢复验证归 02。
4. `tests/test_log_platform_client.py`：特殊 ID 往返、两来源同ID；完整多页/空快照；409重取、410终止；重复event/cursor/错版本/数量不符；大小上限；NOT_FOUND 不成功；响应丢失后清理原键原集合；403不拆批。
5. 扩展 `tests/test_codegen_ir.py`、`test_codegen_profile_validator.py`、`test_codegen_suite_profile.py`、`test_registry_contexts.py`：IR/解释/生成/collect 接线；旧输出快照和配置保持；规则变更触发 freshness；模板与仓库 schema 等价。

实现后必须记录以下命令的真实结果；当前 Spec 不宣称这些测试已通过。`LOG_EXAMPLE_WORKSPACE` 为本片测试已准备好示例资产的临时 workspace 绝对路径；测试进程提供服务 env，命令不读取真实凭证：

```bash
python3 -m compileall -q aitest_kit/codegen aitest_kit/log_assertions
python3 -m pytest tests/test_log_assertion_profile.py tests/test_log_assertion_rules.py tests/test_log_assertion_binding.py tests/test_log_platform_client.py tests/test_codegen_ir.py tests/test_codegen_profile_validator.py tests/test_codegen_suite_profile.py tests/test_registry_contexts.py -q
: "${LOG_EXAMPLE_WORKSPACE:?需要已准备的临时示例 workspace}"
LOG_EXAMPLE_SUITE="$LOG_EXAMPLE_WORKSPACE/test_workspace/suites/demo/log_assertions/suite.yaml"
python3 -m aitest_kit.cli codegen --workspace "$LOG_EXAMPLE_WORKSPACE" --suite-file "$LOG_EXAMPLE_SUITE" --validate-profile
python3 -m aitest_kit.cli codegen --workspace "$LOG_EXAMPLE_WORKSPACE" --suite-file "$LOG_EXAMPLE_SUITE" --dump-ir
python3 -m aitest_kit.cli codegen --workspace "$LOG_EXAMPLE_WORKSPACE" --suite-file "$LOG_EXAMPLE_SUITE" --explain TC-DEMO-001
python3 -m aitest_kit.cli codegen --workspace "$LOG_EXAMPLE_WORKSPACE" --suite-file "$LOG_EXAMPLE_SUITE"
python3 -m aitest_kit.cli codegen --workspace "$LOG_EXAMPLE_WORKSPACE" --suite-file "$LOG_EXAMPLE_SUITE" --check
python3 -m pytest "$LOG_EXAMPLE_WORKSPACE/test_workspace/generated" --collect-only -q
```

真实服务联调在 04 执行；本片通过的 fake HTTP、profile gate 或 collect 不能替代生产端结束契约、平台 TTL 与权限的真实验证。
