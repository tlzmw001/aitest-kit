# test-codegen 项目上下文

本文件包含当前项目（智能优惠券推荐系统）的 codegen 专属配置。换项目时重写本文件，不改 SKILL.md。

## 项目路径

| 路径 | 用途 |
|------|------|
| `test_workspace/tests/conftest.py` | 全局 session fixtures（http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker） |
| `test_workspace/tests/fixtures/{module}.py` | 模块 fixture |
| `test_workspace/tests/helpers/http.py` | HTTP 客户端（httpx + HTTPTransport 绕过 macOS 代理） |
| `test_workspace/tests/helpers/grpc_ops.py` | gRPC 客户端（dict ↔ protobuf 转换） |
| `test_workspace/tests/helpers/redis_ops.py` | Redis 操作 + RedisTracker 自动清理 |
| `test_workspace/tests/generated/` | codegen 生成的 pytest 文件 |
| `aitest_config/project_config.yaml` | 项目级 codegen 配置 |

## 项目断言模式表

以下断言模式是本项目特有的，新项目需要替换：

| 断言模式 | 生成方式 | 项目专属原因 |
|---------|---------|-------------|
| `coupon == null` | `assert resp["coupon"] is None` | coupon 是本项目业务概念 |
| `coupon.item_id == top_result.item_id` | `assert resp["coupon"]["item_id"] == max(...)["item_id"]` | coupon 选最高分逻辑 |
| `cal == round(clamp(k * s + b), 4)` | `assert cal == pytest.approx(max(0, min(1, k * s + b)), abs=1e-4)` | 校准公式 |
| `cal == s` | `assert cal == pytest.approx(s)` | 不校准场景 |

以下断言模式是通用的，新项目可直接复用：

| 断言模式 | 生成方式 |
|---------|---------|
| `response.code == 固定值` | `assert resp["code"] == 固定值` |
| `response.xxx == 固定值` | `assert resp["xxx"] == 固定值` |
| `response.xxx >= 固定值` | `assert resp["xxx"] >= 固定值` |
| `set(response.results[*].item_id) == {集合}` | `assert {r["item_id"] for r in resp["results"]} == {集合}` |
| `len(xxx) == N` | `assert len(xxx) == N` |
| `response.body == xxx` | `assert resp == xxx` |

## 协议偏好

- HTTP 是主要协议，所有模块都有 HTTP 接口
- gRPC 是辅助协议，部分模块有 gRPC 接口（推荐、查询）
- gRPC 用例通过场景变量中的 `协议：gRPC` 标识

## 已知限制

- `scene_experiments.json` 不支持热更新，依赖运行时修改配置的用例需标记为待测系统 bug
- gRPC mock scoring 服务没有公开故障注入接口，打分故障边界场景标记为可行性存疑
- 限流测试需要隔离服务实例（随机端口 + 临时配置文件），不能用默认服务

## 模块分类参考

| 模块 | module_type | 说明 |
|------|-------------|------|
| calibration | standard_recommend | 标准推荐接口 |
| ab_experiment | standard_recommend | 标准推荐接口 + request_overrides |
| feature_scoring | standard_recommend | 标准推荐接口 + request_overrides |
| issuance | standard_recommend | 标准推荐接口 + case_bodies（多请求/查询） |
| scene_routing | standard_recommend | 标准推荐接口 + request_overrides |
| ab_service | multi_endpoint | 独立 AB 服务，多端点 CRUD |
| logging | subprocess_capture | 需要隔离子进程采集日志 |
| rough_ranking | isolated_service | 需要隔离服务 + scoring proxy |
| validation_ratelimit | isolated_service | 限流用例需要隔离服务 + 低 QPS 配置 |
