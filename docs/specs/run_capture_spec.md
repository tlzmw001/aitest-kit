# Run Capture Spec

## Status

IMPLEMENTED

## Background

Company-project migration exposed a practical debugging gap: when generated or fixture-driven
tests fail, users often need the final request and response data so they can reproduce the
call with local tools. Existing `codegen --explain` and `--dump-ir` explain generation
decisions, but they do not execute the test or print the runtime request/response.

## Goals

- Add a short `aitest run --capture` switch.
- Write capture records into one file under the current run directory:

  ```text
  <run_dir>/capture.jsonl
  ```

- Auto-capture only framework-owned `default_http` cases.
- Provide a public helper for user-owned fixtures, helpers, and custom bodies:

  ```python
  from aitest_kit.helpers.capture import capture_io
  ```

- Let users decide if and how to redact sensitive data before passing it to `capture_io`.

## Non-Goals

- No automatic redaction.
- No request/response capture for `case_flow`, `case_body`, `manual`, or `skipped` strategies.
- No per-case capture files.
- No capture deduplication.
- No failure DSL.
- No automatic gRPC/SDK/client capture.
- No headers/env/cookies capture in the built-in default HTTP path.

## User Interface

### CLI

```bash
aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --capture
aitest run --target <target> --module <module> --capture
aitest run --task-file test_workspace/tasks/<task>.yaml --capture
```

`--capture` enables capture for the current run. The generated report bucket remains unchanged.

### Optional Config

`aitest_config/capture.yaml` is optional. If it is missing, built-in defaults apply.

```yaml
enabled: false

include:
  request: true
  response: true
  exception: true
  metadata: true

limits:
  string_length: 4096

output:
  file: capture.jsonl
```

CLI precedence:

```text
--capture > capture.yaml enabled > default false
```

First version uses `mode: always` semantics when capture is enabled. Users who want
failure-only custom capture should call `capture_io()` only from their own failure branch.

## Output

Each capture event is one JSON object per line.

```json
{"timestamp":"2026-06-09T19:00:00+08:00","case_id":"TC-ITEM-001","label":"POST /api/items","protocol":"http","request":{"user_id":"u1"},"response":{"status_code":400,"body":{"code":"INVALID_ITEM"}}}
```

For direct suite/case runs, the file lives in that run directory:

```text
test_workspace/reports/<target>/<module>/suites/<suite>/runs/<run_id>/capture.jsonl
test_workspace/reports/<target>/<module>/cases/<case_key>/runs/<run_id>/capture.jsonl
```

For task/module/target/all aggregate runs, the file lives in the aggregate run directory,
not under each unit:

```text
test_workspace/reports/<bucket>/runs/<run_id>/capture.jsonl
test_workspace/reports/<bucket>/runs/<run_id>/units/<unit>/result.json
```

## Built-In Auto Capture Boundary

Auto capture applies only to `default_http`.

```text
default_http:
  auto-capture request, response, and request-time exception.

structured_case_flow:
  no auto-capture, even when a step uses {request_ref: self}.

custom_case_body:
  no auto-capture.

manual / skipped:
  no capture.
```

This avoids duplicate records when a user-defined fixture already calls `capture_io()`.
`request_ref` only builds a body; it is not guaranteed to be the final request actually sent
by the fixture because user code may wrap, sign, transform, or convert it.

## Manual Capture API

User fixtures and helpers can capture any protocol by calling:

```python
capture_io(
    label="grpc CouponService/Recommend",
    protocol="grpc",
    request=req,
    response=resp,
    exception=exc,
    metadata={"failure_reason": "resp.code != 0"},
)
```

Inside generated test functions, `capture_io()` can infer the current case id
from the runtime case context. Explicit `case_id="TC-ITEM-001"` remains valid
and wins when users call the helper outside generated tests or want to override
the inferred identity. When capture is disabled, `capture_io()` is a no-op.

Users define business failure themselves:

```python
resp = client.call(req)
if resp.code != 0:
    capture_io(
        label="business failure",
        protocol="grpc",
        request=req,
        response=resp,
        metadata={"failure_reason": "resp.code != 0"},
    )
assert resp.code == 0
```

## Serialization Rules

Capture does not redact. It serializes a safe copy for writing:

- JSON primitives are preserved.
- `dict`, `list`, and `tuple` are traversed recursively.
- dataclasses use `dataclasses.asdict()`.
- pydantic-like objects use `model_dump()` or `dict()` when available.
- protobuf-like objects use `google.protobuf.json_format.MessageToDict()` when available.
- `httpx.Response` writes `status_code` and JSON/text body only.
- `BaseException` writes type and message.
- unknown objects fall back to `repr()`.
- long strings are truncated according to `limits.string_length`.

## Implementation Targets

- `aitest_kit/report/cli.py`
  - add `--capture`
  - load optional capture config
  - set capture env vars for pytest subprocess
  - pass one aggregate capture file path through task/selector runs

- `aitest_kit/report/task_runner.py`
  - propagate capture settings to unit runs
  - ensure aggregate runs write one shared capture file

- `aitest_kit/helpers/capture.py`
  - implement `capture_io()` and serialization

- `aitest_kit/codegen/ir_renderer.py`
  - import capture helper
  - auto-capture only `default_http`
  - use response-level HTTP helper so 4xx/5xx response bodies can be captured before `raise_for_status()`
  - set generated test case identity context for fixture-owned capture/logging

- Docs and tests
  - document `aitest run --capture`
  - test disabled/no-op, manual helper, default_http auto capture, task aggregate capture path, and no auto capture for case_flow.

## Verification

```bash
python3 -m pytest tests/test_capture.py tests/test_renderer.py tests/test_report_cli.py -q
python3 -m pytest tests -q
python3 -m compileall aitest_kit
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli run --suite-file test_workspace/suites/discount_system/discount_policy_smoke/suite.yaml --case-id TC-DP-002 --capture -- --collect-only -q
```
