# logging 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `setup_logging` | fixtures/logging.py | 启动带 INFO logging 配置的隔离主服务进程并采集 stdout/stderr |

## 请求模板

日志字段断言需要真实 stdout/stderr，因此不复用已运行的 session 服务。每条可执行日志用例通过 `setup_logging` 创建随机 HTTP/gRPC 端口的独立进程，调用推荐接口后停止进程并读取日志。

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| `log 包含 ...` | 生成对 `logs` 字符串的精确字段包含断言 |
| `log 中 reqId=...UUID...` | 生成正则断言 |
| `stdout/stderr 或采集器中存在 ...` | 生成 stdout/stderr 字符串断言 |

## setup 映射

| 场景变量描述 | fixture 行为 |
|-------------|--------------|
| 显式配置 INFO | 子进程启动前调用 `logging.basicConfig(level=logging.INFO)` |
| 库存 | 按请求 items 通过子进程 admin API 初始化库存 |

## emitter 规则

```yaml
extra_imports:
  - import re
case_bodies:
  TC-LOG-001: |
    case = setup_logging(case_id="TC-LOG-001")
    case.start_with_info_logging()
    resp = case.request("u_log_http_internal", "req-log-001", external=0)
    logs = case.stop_and_logs()
    assert resp["code"] == 0
    assert "recommend request: reqId=req-log-001" in logs
    assert "user_id=u_log_http_internal" in logs
    assert "item_ids=COUPON_LOG_001,COUPON_LOG_002" in logs
    assert "route=1" in logs
    assert "scene_id=1001" in logs
  TC-LOG-002: |
    case = setup_logging(case_id="TC-LOG-002")
    case.start_with_info_logging()
    resp = case.grpc_request("u_log_grpc_internal", "req-log-002", external=0)
    logs = case.stop_and_logs()
    assert resp["code"] == 0
    assert "recommend request: reqId=req-log-002" in logs
    assert "user_id=u_log_grpc_internal" in logs
    assert "route=1" in logs
    assert "scene_id=1001" in logs
  TC-LOG-003: |
    case = setup_logging(case_id="TC-LOG-003")
    case.start_with_info_logging()
    resp = case.request("u_log_http_external", "req-log-003", external=1)
    logs = case.stop_and_logs()
    assert resp["code"] == 0
    assert "recommend request: reqId=req-log-003" in logs
    assert "user_id=u_log_http_external" in logs
    assert "route=2" in logs
    assert "scene_id=1001" in logs
  TC-LOG-004: |
    case = setup_logging(case_id="TC-LOG-004")
    case.start_with_info_logging()
    resp = case.grpc_request("u_log_grpc_external", "req-log-004", external=1)
    logs = case.stop_and_logs()
    assert resp["code"] == 0
    assert "recommend request: reqId=req-log-004" in logs
    assert "user_id=u_log_grpc_external" in logs
    assert "route=2" in logs
    assert "scene_id=1001" in logs
  TC-LOG-005: |
    case = setup_logging(case_id="TC-LOG-005")
    case.start_with_info_logging()
    resp = case.request("u_log_auto_reqid", "", external=0)
    logs = case.stop_and_logs()
    assert resp["code"] == 0
    assert re.search(r"recommend request: reqId=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", logs)
  TC-LOG-006: |
    case = setup_logging(case_id="TC-LOG-006")
    case.start_with_info_logging()
    resp = case.request("u_log_fallback", "req-log-006", external=0, policy_id="policy_fallback_001")
    logs = case.stop_and_logs()
    assert resp["code"] == 0
    assert "recommend request: reqId=req-log-006" in logs
    assert "scene_id=3001" in logs
  TC-LOG-007: |
    case = setup_logging(case_id="TC-LOG-007")
    case.start_with_info_logging()
    resp = case.request("u_log_no_route_internal", "req-log-007", external=0)
    case.stop_and_logs()
    assert resp["code"] == 0
    # MANUAL CHECK: 内部打分服务收到的请求字段中不存在 route
  TC-LOG-008: |
    case = setup_logging(case_id="TC-LOG-008")
    case.start_with_info_logging()
    resp = case.request("u_log_no_route_external", "req-log-008", external=1)
    case.stop_and_logs()
    assert resp["code"] == 0
    # MANUAL CHECK: 外部打分服务收到的 JSON body 中不存在 route
  TC-LOG-010: |
    case = setup_logging(case_id="TC-LOG-010")
    case.start_with_info_logging()
    resp = case.request("u_log_010", "req-log-010", external=0, items=[{"item_id": "COUPON_LOG_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}])
    logs = case.stop_and_logs()
    assert resp["code"] == 0
    assert "recommend request: reqId=req-log-010" in logs
```
