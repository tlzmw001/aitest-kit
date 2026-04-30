# validation_ratelimit 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `setup_validation_ratelimit` | fixtures/validation_ratelimit.py | 初始化库存、清理限流 key，限流用例启动隔离低 QPS 主服务 |

## 请求模板

本模块覆盖三类请求：

- 业务层参数校验：使用推荐接口返回业务错误体 `ERR`
- HTTP Schema 校验：使用 `http_helper.post_response` 保留 422 response，不走 `raise_for_status`
- gRPC optional 字段校验：构造请求时省略对应字段，让服务端 `HasField(...)` 返回 false
- 限流：使用临时配置启动隔离主服务，不修改仓库配置文件或 `.env`

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| `response.body == err` / `response == err` | `assert resp == ERR` |
| `response.body == limited` / `response == limited` | `assert resp == LIMITED` |
| `response.status_code == 422` | raw response 断言 |
| `detail[*].loc` | 解析 422 JSON 后断言 loc |
| 限流多次请求 | 显式发送多次请求并断言每次响应 |

## emitter 规则

```yaml
extra_imports:
  - from test_workspace.tests.fixtures.validation_ratelimit import BOUNDARY_ITEM, ERR, LIMITED
case_bodies:
  TC-VAL-001: |
    case = setup_validation_ratelimit(case_id="TC-VAL-001")
    resp = case.http("", "req-val-001", external=0, score_threshold=0.5, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-002: |
    case = setup_validation_ratelimit(case_id="TC-VAL-002")
    resp = case.http("u_val_scene_empty", "req-val-002", scene_name="", external=0, score_threshold=0.5, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-003: |
    case = setup_validation_ratelimit(case_id="TC-VAL-003")
    resp = case.http("u_val_device_empty", "req-val-003", device="", external=0, score_threshold=0.5, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-004: |
    case = setup_validation_ratelimit(case_id="TC-VAL-004")
    resp = case.http("u_val_items_empty", "req-val-004", items=[], external=0, score_threshold=0.5, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-005: |
    case = setup_validation_ratelimit(case_id="TC-VAL-005")
    resp = case.grpc_missing("u_val_grpc_missing_control", "req-val-005", "external")
    assert resp == ERR
  TC-VAL-006: |
    case = setup_validation_ratelimit(case_id="TC-VAL-006")
    resp = case.http("u_val_http_external_2", "req-val-006", external=2, score_threshold=0.5, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-007: |
    case = setup_validation_ratelimit(case_id="TC-VAL-007")
    resp = case.grpc("u_val_grpc_external_2", "req-val-007", external=2, score_threshold=0.5, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-008: |
    case = setup_validation_ratelimit(case_id="TC-VAL-008")
    resp = case.http("u_val_http_threshold_low", "req-val-008", external=0, score_threshold=-0.01, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-009: |
    case = setup_validation_ratelimit(case_id="TC-VAL-009")
    resp = case.grpc("u_val_grpc_threshold_high", "req-val-009", external=0, score_threshold=1.01, max_claim_per_request=1)
    assert resp == ERR
  TC-VAL-010: |
    case = setup_validation_ratelimit(case_id="TC-VAL-010")
    resp = case.http("u_val_http_max_claim_0", "req-val-010", external=0, score_threshold=0.5, max_claim_per_request=0)
    assert resp == ERR
  TC-VAL-011: |
    case = setup_validation_ratelimit(case_id="TC-VAL-011")
    resp = case.grpc("u_val_grpc_max_claim_0", "req-val-011", external=0, score_threshold=0.5, max_claim_per_request=0)
    assert resp == ERR
  TC-VAL-012: |
    case = setup_validation_ratelimit(case_id="TC-VAL-012")
    resp = case.http("u_reqid_http_auto", "", external=0, score_threshold=0.0, max_claim_per_request=1)
    assert resp["code"] == 0
    # MANUAL CHECK: 应用日志存在 recommend request:，其中 reqId= 的值匹配 UUID 正则
  TC-VAL-013: |
    case = setup_validation_ratelimit(case_id="TC-VAL-013")
    resp = case.grpc("u_reqid_grpc_auto", "", external=0, score_threshold=0.0, max_claim_per_request=1)
    assert resp["code"] == 0
    # MANUAL CHECK: 应用日志存在 recommend request:，其中 reqId= 的值匹配 UUID 正则
  TC-SCHEMA-001: |
    case = setup_validation_ratelimit(case_id="TC-SCHEMA-001")
    body = case.body("u_schema_external_missing", "req-schema-001", external=0, score_threshold=0.5, max_claim_per_request=1)
    body.pop("external")
    resp = case.http_response(body)
    assert resp.status_code == 422
    locs = [item["loc"] for item in resp.json()["detail"]]
    assert ["body", "external"] in locs
  TC-SCHEMA-002: |
    case = setup_validation_ratelimit(case_id="TC-SCHEMA-002")
    body = case.body("u_schema_threshold_missing", "req-schema-002", external=0, score_threshold=0.5, max_claim_per_request=1)
    body.pop("score_threshold")
    resp = case.http_response(body)
    assert resp.status_code == 422
    locs = [item["loc"] for item in resp.json()["detail"]]
    assert ["body", "score_threshold"] in locs
  TC-SCHEMA-003: |
    case = setup_validation_ratelimit(case_id="TC-SCHEMA-003")
    body = case.body("u_schema_max_claim_missing", "req-schema-003", external=0, score_threshold=0.5, max_claim_per_request=1)
    body.pop("max_claim_per_request")
    resp = case.http_response(body)
    assert resp.status_code == 422
    locs = [item["loc"] for item in resp.json()["detail"]]
    assert ["body", "max_claim_per_request"] in locs
  TC-GRPC-001: |
    case = setup_validation_ratelimit(case_id="TC-GRPC-001")
    resp = case.grpc_missing("u_grpc_external_missing", "req-grpc-001", "external")
    assert resp == ERR
  TC-GRPC-002: |
    case = setup_validation_ratelimit(case_id="TC-GRPC-002")
    resp = case.grpc_missing("u_grpc_threshold_missing", "req-grpc-002", "score_threshold")
    assert resp == ERR
  TC-GRPC-003: |
    case = setup_validation_ratelimit(case_id="TC-GRPC-003")
    resp = case.grpc_missing("u_grpc_max_claim_missing", "req-grpc-003", "max_claim_per_request")
    assert resp == ERR
  TC-GRPC-004: |
    case = setup_validation_ratelimit(case_id="TC-GRPC-004")
    resp = case.grpc("u_grpc_valid", "req-grpc-004", external=0, score_threshold=0.5, max_claim_per_request=1)
    assert resp["code"] == 0
  TC-RATE-001: |
    case = setup_validation_ratelimit(case_id="TC-RATE-001")
    r1 = case.http("u_rate_old_user", "req-rate-001-1", external=0, score_threshold=0.0, max_claim_per_request=1)
    r2 = case.http("u_rate_old_user", "req-rate-001-2", external=0, score_threshold=0.0, max_claim_per_request=1)
    r3 = case.http("u_rate_old_user", "req-rate-001-3", external=0, score_threshold=0.0, max_claim_per_request=1)
    assert r1["code"] == 0
    assert r2["code"] == 0
    assert r3 == LIMITED
  TC-RATE-002: |
    case = setup_validation_ratelimit(case_id="TC-RATE-002")
    r1 = case.http("u_rate_http_global_1", "req-rate-002-1", external=0, score_threshold=0.0, max_claim_per_request=1)
    r2 = case.http("u_rate_http_global_2", "req-rate-002-2", external=0, score_threshold=0.0, max_claim_per_request=1)
    r3 = case.http("u_rate_http_global_3", "req-rate-002-3", external=0, score_threshold=0.0, max_claim_per_request=1)
    assert r1["code"] == 0
    assert r2["code"] == 0
    assert r3 == LIMITED
  TC-RATE-003: |
    case = setup_validation_ratelimit(case_id="TC-RATE-003")
    r1 = case.grpc("u_rate_grpc_global_1", "req-rate-003-1", external=0, score_threshold=0.0, max_claim_per_request=1)
    r2 = case.grpc("u_rate_grpc_global_2", "req-rate-003-2", external=0, score_threshold=0.0, max_claim_per_request=1)
    r3 = case.grpc("u_rate_grpc_global_3", "req-rate-003-3", external=0, score_threshold=0.0, max_claim_per_request=1)
    assert r1["code"] == 0
    assert r2["code"] == 0
    assert r3 == LIMITED
  TC-RATE-004: |
    case = setup_validation_ratelimit(case_id="TC-RATE-004")
    r1 = case.http("u_rate_http_user", "req-rate-004-1", external=0, score_threshold=0.0, max_claim_per_request=1)
    r2 = case.http("u_rate_http_user", "req-rate-004-2", external=0, score_threshold=0.0, max_claim_per_request=1)
    assert r1["code"] == 0
    assert r2 == LIMITED
  TC-RATE-005: |
    case = setup_validation_ratelimit(case_id="TC-RATE-005")
    r1 = case.grpc("u_rate_grpc_user", "req-rate-005-1", external=0, score_threshold=0.0, max_claim_per_request=1)
    r2 = case.grpc("u_rate_grpc_user", "req-rate-005-2", external=0, score_threshold=0.0, max_claim_per_request=1)
    assert r1["code"] == 0
    assert r2 == LIMITED
  TC-RATE-006: |
    case = setup_validation_ratelimit(case_id="TC-RATE-006")
    r1 = case.http("u_rate_http_window", "req-rate-006-1", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
    r2 = case.http("u_rate_http_window", "req-rate-006-2", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
    case.wait_rate_key_gone("u_rate_http_window")
    r3 = case.http("u_rate_http_window", "req-rate-006-3", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
    assert r1["code"] == 0
    assert r2 == LIMITED
    assert r3["code"] == 0
  TC-RATE-007: |
    case = setup_validation_ratelimit(case_id="TC-RATE-007")
    r1 = case.grpc("u_rate_grpc_window", "req-rate-007-1", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
    r2 = case.grpc("u_rate_grpc_window", "req-rate-007-2", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
    case.wait_rate_key_gone("u_rate_grpc_window")
    r3 = case.grpc("u_rate_grpc_window", "req-rate-007-3", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
    assert r1["code"] == 0
    assert r2 == LIMITED
    assert r3["code"] == 0
```
