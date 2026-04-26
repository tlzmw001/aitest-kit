# AB 实验服务

独立部署的 AB 实验管理与分流服务，供业务系统通过 SDK 调用。

## 接口

- HTTP 基础 URL：`http://localhost:8100`（可通过 AB_SERVICE_HOST / AB_SERVICE_PORT 环境变量配置）
- 核心端点：`POST /api/v1/ab/evaluate`（实验评估）
- 管理端点：实验 CRUD（`/api/v1/ab/experiments`）+ 白名单 CRUD（`/api/v1/ab/whitelist`），完整列表见下方"API 一览"
- 健康检查：`GET /health`
- 无 gRPC 接口

## 输入

### 实验评估请求（POST /api/v1/ab/evaluate）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | str | 是 | 用于 hash 分流 |
| `request_id` | str | 否 | 请求标识，用于日志追踪 |
| `context` | dict | 否 | 上下文信息，透传不参与分流 |
| `experiment_names` | list[str] / None | 否 | 要评估的实验列表 |

`experiment_names` 行为：
- `None` → 评估全部实验
- `[]` → 不评估，返回空
- `["exp_a"]` → 只评估指定实验

## 输出

### 评估响应

| 字段 | 类型 | 说明 |
|------|------|------|
| `request_id` | str | 回传 |
| `user_id` | str | 回传 |
| `assignments` | dict[str, Assignment] | 命中结果，key=实验名 |
| `trace_id` | str | 服务端追踪 ID |

### Assignment

| 字段 | 类型 | 说明 |
|------|------|------|
| `experiment_name` | str | 实验名 |
| `strategy_id` | str | 命中策略 ID |
| `params` | dict | 策略参数，原样透传 |
| `hit_reason` | str | "hash" 或 "whitelist" |

## 业务规则

### 分流

1. 白名单优先级 > hash 分流
2. hash 分流：MD5(user_id) % 100，落入 [low, high) 区间即命中
3. 各策略的 hash_range 不应重叠，取值范围 0-100

### 实验管理 API

4. 支持实验 CRUD：创建/查询/更新/删除
5. 更新实验为整体替换策略列表
6. 增删改自动持久化到 experiments.json 文件

### 白名单管理 API

7. 支持单用户白名单设置/查看/清除
8. 支持全量白名单替换/查看/清空
9. 白名单持久化到本地文件，服务重启自动恢复

### 部署

10. 默认监听 0.0.0.0:8100
11. 可通过环境变量配置：AB_SERVICE_HOST、AB_SERVICE_PORT、AB_SERVICE_EXPERIMENTS_PATH

## 错误场景

- 统一用 FastAPI HTTPException，响应体格式 `{"detail": "<message>"}`
- 404：GET/PUT/DELETE 实验名不存在（"experiment not found"）；GET 用户白名单不存在（"user whitelist not found"）
- 409：POST 创建实验时名称重复（"experiment already exists: <name>"）
- 400：PUT 更新实验时路径名与 body 名不一致（"path name and payload name mismatch"）
- 422：请求体 Pydantic 校验失败（FastAPI 默认格式，detail 是数组）
- 注意：DELETE 用户白名单不会 404，内部用 dict.pop(key, None) 静默成功

## 可观测状态

- 健康检查：`GET /health`
- `trace_id`：每次评估生成
- Swagger 文档：`/docs`

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/v1/ab/evaluate` | 实验评估 |
| GET | `/api/v1/ab/experiments` | 列出所有实验 |
| GET | `/api/v1/ab/experiments/{name}` | 查询单个实验 |
| POST | `/api/v1/ab/experiments` | 创建实验 |
| PUT | `/api/v1/ab/experiments/{name}` | 更新实验 |
| DELETE | `/api/v1/ab/experiments/{name}` | 删除实验 |
| GET | `/api/v1/ab/whitelist` | 查看全部白名单 |
| PUT | `/api/v1/ab/whitelist` | 整量替换白名单 |
| DELETE | `/api/v1/ab/whitelist` | 清空全部白名单 |
| GET | `/api/v1/ab/whitelist/{user_id}` | 查看单用户白名单 |
| PUT | `/api/v1/ab/whitelist/{user_id}` | 设置单用户白名单 |
| DELETE | `/api/v1/ab/whitelist/{user_id}` | 清除单用户白名单 |

## 已有测试覆盖

- [cases/old-cases/ab_service.md] AB 服务 API
  - 已覆盖：健康检查、白名单评估、实验 CRUD（创建/查询/更新/删除）、创建重名 409、白名单 CRUD（单用户/全量/清空）、白名单持久化+重启恢复
- [test_workspace/cases/ab_service/business.md] AB 服务业务+异常用例
  - 已覆盖：hash 分流正确性（命中/未命中）、experiment_names 三种行为（None/空列表/指定）、实验持久化+重启恢复、更新为整体替换策略列表、GET/PUT/DELETE 实验名不存在 404、PUT path-body 名不一致 400、GET 用户白名单不存在 404、DELETE 用户白名单静默成功
- [test_workspace/cases/ab_service/boundary.md] AB 服务边界用例
  - 已覆盖：hash_range 重叠行为（first-match）、白名单文件损坏容错、实验配置文件不存在自动创建、策略格式异常回退、evaluate 含不存在实验名静默跳过、空策略实验评估、Pydantic 422 校验
- [cases/old-cases/ab_remote_client.md] 远程 SDK
  - 已覆盖：远程 evaluate 端到端、SDK 白名单 CRUD、远程服务 500 异常
  - 未覆盖：网络超时/连接拒绝、SDK 重试机制、并发 evaluate 请求

## 关联 L2

- [0405](../L2/0405.md) — AB 实验服务独立部署
