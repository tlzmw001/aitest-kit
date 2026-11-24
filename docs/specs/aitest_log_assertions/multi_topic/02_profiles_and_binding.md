# 分片 02 · 来源声明、代码生成与一次请求绑定

一次业务调用可以同时产生主链路、性能和入湖日志。本片让用例作者为每组内容断言选择来源，把同一次调用的关联 ID 交给这些来源，并保留现有 Harness 入口。收齐条件配置在日志平台，Kit 的 profile 描述本例需要核对的内容。

## 1. 作者写什么

模块在 `module.yaml` 维护默认来源与别名。以下均为示例 ID，业务方可以使用自己的名称。

```yaml
log_capture:
  source_id: demo-main
  sources:
    performance: {source_id: demo-perf}
    lake: {source_id: demo-lake}
```

suite 在 `profile_<suite>_suite.md` 的 `case_flows.<TC-ID>.log_assertions[]` 选来源。某组省略 `source` 即依赖模块默认来源。下例只等待主链路和性能日志，入湖不在本次计划里。

```yaml
case_flows:
  TC-DEMO-001:
    steps:
      - call: harness.query
        save_as: reply
      - assert: 'assert reply["code"] == 200'
    log_assertions:
      - request_step: reply
        select: {eventType: ROUTE_DECISION}
        cleanup: on_success
        checks: ['assert len(events) >= 1']
      - request_step: reply
        source: performance
        select: {stage: performance}
        expected: {tag: "耗时"}
        checks: ['assert any(expected["tag"] in e["data"]["message"] for e in events)']
```

| 输入 | 编译契约 |
|---|---|
| `log_capture.source_id` | 保留原必填非空字符串。它既是旧用例的默认来源，也是 Harness 绑定该步骤的锚点。未声明日志能力的模块可原样运行。 |
| `log_capture.sources` | 可选 mapping，键为非空字符串别名，值为恰含一个非空字符串 `source_id` 的对象。别名按原文区分大小写。多个别名可以指向同一实际来源，也可以指向默认来源。 |
| 组级 `source` | 若显式填写，必须是模块中已声明的别名；空值、未知别名或直接写未声明的实际 ID 都报错。省略字段使用默认值。 |
| checks、select、expected | 沿用当前受控字符串断言、`eventType/stage`、`literal/from_var/from_response`。每组只获得本来源整份快照中符合 select 的事件。原有每步骤 32 组限制、每组 32 条 checks 上限和整步期望大小限制仍生效。 |
| cleanup | 按 **(request_step, 解析后的 source_id)** 归并。全部省略时为 retain；存在唯一显式值时同一实际来源的其他省略组继承。显式 retain 与 on_success 冲突报错。两个不同来源允许各自指定。 |

## 2. 从 registry 到 generated

1. 扩展 `registry/models.py:LogCapture` 和 `registry/loader.py` 的 module 解析。保留 `LogCapture(source_id)` 的旧构造，给映射提供空默认值。在 `codegen_profile.schema.json` 的 `$defs.logAssertionGroup` 增加可选字符串 `source`，同步仓库与 workspace 模板两份 schema。
2. 在 `codegen/log_assertion_validation.py` 中让 gate 与 planner 共用来源解析及 cleanup 归并。格式错误沿用组级诊断 E533；来源未解析、清理声明冲突沿用 E536，表达式和 expected 错误继续用 E534/E535。JSON Schema 提前阻止错误时保留已有 schema 诊断。错误至少指出 module 或 `case_flows.<TC-ID>.log_assertions[i].<field>`、别名和冲突来源，禁止自动回退到默认源。
3. `codegen/case_flow_planner.py` 向 `build_log_groups` 传模块映射，原始 `group_index` 始终是该 flow 的 log_assertions 列表下标。**逐步骤判别新旧语义**：同一步任一组显式选 source，整步所有组的规则都写入已解析的 `source_id`，包括省略 source 的组。旧步骤所有组均省略时沿用原规则形状。模块声明了别名但本步骤未使用，也走旧形状。
4. `codegen/ir.py`、`log_assertion_rendering.py` 共享上述字段约定。新形状将具体 `source_id` 纳入原有规范 JSON 的 `rule_sha256`，保留原 `executor_version=1` 和表达式执行器。旧形状不输出 `source_id: null`，不改变旧规则 hash 或原 generated 文件字节。注意当前 IR dump 和渲染使用 `asdict`，给 dataclass 追加字段时须检查两个出口。重映射已用别名应使对应新用例 freshness check 失败，重新生成后反映新目标。
5. `--validate-profile` 校验来源与清理要求；`--dump-ir` 可定位步骤锚点、实际来源和组下标；`--explain <TC-ID>` 按步骤列出这些来源、对应组以及 read/cleanup 权限需求。这些命令均可离线使用；运行时预检再检查平台实际授权。正常生成、`--check` 和上述诊断入口沿用同一 gate。

生成器仍给一个业务 call 包装一个 `log_request_step(request_step=…, source_id=…, rules=…, expected_inputs=…)`。wrapper 的 `source_id` 保持模块锚点，rules 内的 `source_id` 告诉运行时该组应取的实际来源。新旧规则以整步为单位，禁止同一步只给部分组写入 source_id。即使新形状最终只依赖一个异步来源，仍按新步骤的 readiness 超时语义处理。

**分片单独交付时的运行保护。** 0.7.0 的 recorder 始终按 wrapper 的锚点登记，遇到新规则可能在错误来源上验证通过。新规则的执行须与分片 03 的事务和调度接线一起开放。若先交付本片的生成与离线检查，在 `aitest run` 的选中用例预检识别新规则，提示“当前执行器尚未支持组级日志来源”并在业务调用前退出。旧形状可照常执行。对将新 generated 文件复制到 0.7.0 的场景，仅为含新步骤的测试函数在首个业务步骤前检查运行包的多来源能力；旧包缺该能力时明确失败。通过运行包能力识别，用户无需新增配置。

## 3. Harness 与事务边界

**公开入口。** `aitest_kit.log_assertions.log_capture_requested()` 与 `bind_log_request(source_id, correlation_value)` 的签名、布尔返回值、线程/scope 有效期和幂等约定保持兼容。业务 Harness 按本服务约定生成或读取关联值，按需注入采集开关，在原步骤 scope 内用**模块默认锚点**绑定一次。Kit 不注入指定业务字段，也不在 fixture 中轮询。只有 performance 组时，仍然绑定 demo-main 锚点，后台只登记 demo-perf。

| 时机 | 本片与持久化分片的交接 |
|---|---|
| 业务调用前 | `scope.py` 按原顺序编译 expected 的静态值、变量和响应指针。向 recorder 调用一次 `register(step, anchor, rules, inputs)`。按实际来源分组，记录同一截止时间，在一个事务内登记所有来源。超过 pending_request_limit 时整步失败，业务请求尚未发出。 |
| Harness 取得 ID | `bind_log_request(anchor, value)` 通过 recorder 的不透明 handle 在一个事务内将相同 value 绑定到所有实际来源。相同 scope 的重复同值可安全返回 true；改绑、锚点不匹配、空值、跨步骤占用同一 (source_id, value) 时明确失败。事务失败不能留下可进入队列的部分绑定。 |
| 返回业务响应 | 仍由 generated 调用一次 `scope.freeze_response(reply)`。先对全部组求值、脱敏字段检查并验证大小，再一次性冻结各来源 inputs。只要一步有某个必需响应指针失效，整步记 LOG_INPUT_ERROR。 |
| 异常或未绑定 | 保留原业务异常及 pytest 结果。已绑定且全为静态期望时沿用 0.7 可冻结取证；缺绑定或原绑定失败记 LOG_BINDING_ERROR；需要未取得的响应输入时记 LOG_INPUT_ERROR。失败不产生任何来源的清理意图。 |

`RequestRecorder.register/bind/freeze/fail` 形参不变，保留单来源测试 recorder。生产 `runtime.py:SQLiteRecorder` 与 store 以 handle 标识整个步骤。每个来源同时保存相应规则及对应输入。例：某一步的前三组实际来源为 A、B、A，期望输入依次为 x、y、z；A 保存规则 0、2 和 x、z，B 保存规则 1 和 y。若 flow 有其他步骤交错，`group_index` 可为任意非连续原下标；应以本步输入列表位置配对，再保留全局下标作诊断。分片 03 实现实际 SQLite 事务、唯一性、迁移和恢复。

## 4. 运行时如何发现依赖

`log_assertions/discovery.py:plan_sources/planned_steps` 从 generated 的字面量规则解析数据，供 `has_log_plans`、`pytest_plugin.py:pytest_collection_finish` 和报告计划使用，无需导入执行用例。旧形状解析为锚点单源；新形状按规则实际来源去重。每个来源仅当有组选了 on_success 时才要求 cleanup，跨选中用例汇总权限时取并集。案例选择、参数化和 xdist 沿用现有 pytest 选择结果。无法解析的已识别 wrapper 元数据应显式报错，避免误当普通无日志用例放行。

报告计划也按 (step, source_id) 展开，保留该来源实际组。某一步未执行时仍能指出哪些来源未启动；运行时声明和库内实绩对账不能只比较 step。仅依赖 B 的用例允许锚点 A 在当前 Token 的可见来源列表里不存在，平台只须授权 B。本片提供发现规则及测试，调度、缺项结算与报告接线见后续分片。

## 5. 本片验收

| 测试入口 | 用例及断言 |
|---|---|
| registry / profile gate | 覆盖未知别名、空来源、错误映射、两别名同源 cleanup 冲突、跨源独立 cleanup、缺省继承、超 32 组、旧 module；非法输入在业务、emitter 前退出。 |
| `tests/test_log_assertion_profile.py` | 在临时 init workspace 分别运行 validate-profile、dump-ir、explain、生成、check 和 pytest collect。旧 profile 对比升级前的 generated 字节与规则 hash；新 profile 看实际 source_id、权限和原路径。更换模块别名指向后 check 发现过期。 |
| `tests/test_log_assertion_binding.py` | 记录仅一次 register/业务调用/bind/freeze。测仅异步源、A/B/A 分组与交错下标、重复同值、改绑、缺绑定、指针错误、原业务异常、敏感期望及无 scope。 |
| 分片 03 尚未接线 / 旧运行包执行新 generated | 准备仅验证 B 的用例，令锚点 A 已有满足断言的日志。新形状必须非零退出，观察到业务调用、正文读取、清理提交均为 0；同环境旧形状用例仍能运行。03 接线后，相同新用例只读取 B。 |
| 预检与发现 | 选中仅性能用例时只查性能权限；选中混合用例时列出 main、performance；未选 lake 时不校验 lake。retain 来源只需 read，一组 on_success 令该实际来源要求 cleanup。旧 generated 与新 generated 可同时发现。 |

实现后运行 `python3 -m pytest -q tests/test_log_assertion_profile.py tests/test_log_assertion_binding.py tests/test_log_assertion_rules.py`；分片 03 再通过真实 SQLite 与 pytest worker 验证事务和并发。外部 Agent 使用的配置手册、模板示例和 wheel 安装走最后验收分片。
