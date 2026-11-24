# Deferred log assertions

Add log rules to the suite profile only when the Markdown case calls for log evidence. A group belongs to one request and uses the `save_as` value from a call in that case flow.

```yaml
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
          score: {from_response: /score}
        checks:
          - 'assert len(events) == 1'
          - 'assert events[0]["data"]["score"] == expected["score"]'
```

- Set `log_capture.source_id` in the module registry and pass that value to the Harness. Use `log_capture_requested()` before adding service-specific capture parameters. Call `bind_log_request(source_id, correlation_value)` as soon as the service-specific ID is available, before the request if the Harness generates it, or after the response if the service generates it.
- Keep immediate response checks in `steps[].assert`. Deferred checks can read `events`, the selected log entries in platform order, and `expected`. Use a constant, `{from_var: name}`, or `{from_response: /path}` for an expected value. Use `{literal: ...}` when an expected object itself has a provider key. Supply safe JSON values and exclude credentials and sensitive fields.
- Use Python `assert` with indexing, comparisons, boolean and numeric operators, `len`, `any`, `all`, `regex_search` or `regex_fullmatch`. For plain text use `assert "hit" in events[0]["data"]`. Check the count before indexing when event presence is itself a business expectation.
- Select by `eventType` and/or `stage`. Use `cleanup: on_success` to request cleanup after test verification when a run coordinator is available. The default is `retain`.
- Run `aitest codegen --suite-file … --validate-profile`, then use `--dump-ir` or `--explain TC-DEMO-001` to see the binding and checks. Generate and run `--check` after profile changes. E533 covers request binding and group shape, E534 check syntax, E535 expected input, and E536 module capture or cleanup. Run the generated suite via `aitest run` to activate its recorder.
- The initialized workspace includes a runnable codegen example under `examples/log_assertions/`.

## 执行与恢复

通过 `aitest run --suite-file …` 启动日志检查。配置使用
`aitest_config/log_assertions.yaml`，suite 和 task 都会自动读取。
`platform.base_url` 可直接填写日志平台或该任务可访问的 HTTP(S) 隧道地址，支持服务路径前缀。
省略时读取 `platform.base_url_env` 指定的变量（默认 `AITEST_LOG_BASE_URL`）。
Token 通过 `platform.token_env` 指定的变量读取（默认 `AITEST_LOG_TOKEN`）。
恢复时沿用原运行的地址绑定。日志条件在 pytest 选出用例后预检。

```yaml
schema_version: 1
execution:
  case_concurrency: 1
  log_concurrency: 1
  request_timeout_seconds: 120
  poll_interval_seconds: 1
state:
  directory: .aitest/runs
  retention_seconds: 86400
```

`--case-concurrency` 与 `--log-concurrency` 可以覆盖配置。并行业务用例需要
`aitest-kit[parallel]`。等待采集完成的请求会让出证据读取与断言名额。

异常中断后，在原工作区执行 `aitest run --resume RUN_ID`。恢复读取原规则、
请求关联值和截止时间。命令单独输出日志验证数与退出结果，详细阶段及检查事实
保存在工作区的 SQLite 状态库。

## 查看结果与清理回执

- 使用 `aitest run` 执行后，在对应运行目录或 Console 查看日志验证进度。最终 JSON、Markdown 和 JUnit 会纳入日志断言。日志断言失败时退出码为 1。
- `cleanup: on_success` 只在用例全部即时阶段和日志断言通过后，对声明清理的请求提交精确 ID。报告记录受理回执。清理失败保留业务通过计数，并使整轮返回非零。失败用例的日志按平台 TTL 保留。
- 运行中断后用 `aitest run --resume <run_id>` 恢复，业务请求不会重发。只在提交期限内、使用同一平台与 Token 重试已登记的清理请求。`aitest report` 可离线重渲染结果。

## 多来源日志

模块的 `log_capture.source_id` 是默认来源，也是 Harness 调用 `bind_log_request` 时传入的来源。其它来源在 module.yaml 中用别名声明。

```yaml
log_capture:
  source_id: demo
  sources:
    perf: {source_id: demo-perf}
```

同一步骤写两个断言组即可同时验证主链路和性能日志。组省略 `source` 时使用默认来源，填写 `source: perf` 时只读性能来源。只需要性能证据时，仅写带 `source: perf` 的一组。Harness 为每次业务请求绑定一次同一个关联 ID。每组的 `events` 只含该来源的快照中符合筛选条件的事件。收齐条件由日志平台配置，`len(events)` 用于检查业务证据的条数。

JSON 和 Markdown 按步骤和来源显示状态。查看来源的 `last_observation` 能看到最近平台状态、时间和已收条数。若平台明确超时，或者最近仍未齐并超过请求期限，来源标记 `LOG_READINESS_TIMEOUT`，内容检查标记 `not_run`。证据过期、网络或协议故障表现为取证错误。整例通过后只清理明确使用 `on_success` 的来源。

初始化后可检查 `examples/log_assertions/test_workspace/suites/demo/log_grouped/` 的两条用例。依次运行 `aitest codegen --suite-file … --validate-profile`、`--dump-ir`、`--explain TC-DEMO-001`、生成、`--check` 和 `aitest run --suite-file …`。

清理队列由 `aitest_config/log_assertions.yaml` 的 `cleanup` 配置。

- `queue_timeout_seconds` 默认 120，从登记清理意图时起算。
- `submit_timeout_seconds` 默认 15，从首次提交开始计算重试总预算。
- `cleanup_concurrency` 默认 4，限制本轮同时提交的数量。
