# API Map: validation_ratelimit

## 端点

| Method | Path / Service | 认证 | 用途 |
|--------|----------------|------|------|
| POST | `/api/v1/recommend` | no | HTTP 推荐接口，覆盖参数校验、Schema 校验和限流 |
| gRPC | `coupon.CouponService/Recommend` | no | gRPC 推荐接口，覆盖 optional 字段校验和限流 |
| POST | `/api/v1/admin/stock` | no | 测试前置：初始化优惠券库存 |
| GET | `/health` | no | 隔离服务启动后的健康检查 |

## 认证

- 当前用例文档未声明鉴权要求。
- fixture 不注入 token、cookie 或 API key。

## 请求体参考

### POST `/api/v1/recommend`

```json
{
  "user_id": "u_rate_default",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "req_rate_default",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {
      "item_id": "COUPON_VAL_001",
      "coupon_type": "discount",
      "value": 80,
      "min_spend": 5000,
      "expire_days": 7
    }
  ]
}
```

## 环境变量

### 连接层（必须有才能发请求）

- `HTTP_BASE_URL` — 默认 HTTP 服务地址；conftest 默认值为 `http://localhost:8000`。
- `GRPC_TARGET` — 默认 gRPC 服务地址；conftest 默认值为 `localhost:50051`。
- `AB_SERVICE_URL` — 启动隔离低 QPS coupon 服务时透传的 AB 服务地址；conftest 默认值为 `http://localhost:8100`。
- `REDIS_URL` — Redis 地址；conftest 默认值为 `redis://localhost:6379/0`。

### 认证层（必须有才能鉴权）

- 无。

### 资源层（特定 case 需要的已存在资源 ID）

- 无外部预置资源。库存通过公开测试前置接口 `/api/v1/admin/stock` 初始化。

### 业务层（可替换的测试输入）

- `user_id`、`reqId/req_id`、`external`、`score_threshold`、`max_claim_per_request`、`items` 来自 Markdown 用例。
- 限流类用例需要临时启动隔离 coupon 服务，并通过临时配置覆盖 `rate_limit`。

## 信息缺口

- 限流 Redis 不可用场景需要控制外部 Redis 生命周期，当前黑盒自动化环境不可稳定保证。
- 同一时间戳限流精度需要可控服务端时钟，当前黑盒自动化环境不可直接控制。
- HTTP item 子结构 Schema 校验与当前实现存在 mismatch，不能作为稳定通过用例。

## Case variables/env 矩阵

| case_id | profile variables | required env | optional env | 缺失行为 |
|---------|-------------------|--------------|--------------|----------|
| TC-VAL-001~TC-VAL-013, TC-GRPC-001~TC-GRPC-004, TC-SCHEMA-001~TC-SCHEMA-003 | 无 | `HTTP_BASE_URL`, `GRPC_TARGET`, `REDIS_URL` | `AB_SERVICE_URL` | 默认 conftest 值可用于本地集成环境 |
| TC-RATE-001~TC-RATE-007 | 无 | `REDIS_URL` | `AB_SERVICE_URL` | 启动隔离低 QPS 服务失败时测试失败 |
| TC-RATE-008~TC-RATE-010, TC-SCHEMA-004 | 无 | 不生成自动化 flow | 无 | skipped |

## 状态影响分析

| case_id | 动作类型 | 创建资源？ | 唯一值？ | cleanup？ | 幂等？ |
|---------|----------|------------|----------|----------|--------|
| TC-VAL-001~TC-VAL-011 | 参数校验请求 | 否 | 是，`user_id/reqId` | 清理限流 key | 是 |
| TC-VAL-012~TC-VAL-013 | 请求标识自动生成 | 否 | 是，`user_id` | 清理限流 key | 是 |
| TC-GRPC-001~TC-GRPC-004 | gRPC 字段校验请求 | 否 | 是，`user_id/req_id` | 清理限流 key | 是 |
| TC-SCHEMA-001~TC-SCHEMA-003 | HTTP Schema 校验请求 | 否 | 是，`user_id/reqId` | 清理限流 key | 是 |
| TC-RATE-001~TC-RATE-007 | 限流请求序列 | 启动临时服务进程 | 是，`user_id` | 终止进程 + 清理限流 key | 否 |
| TC-RATE-008~TC-RATE-010, TC-SCHEMA-004 | 环境/实现细节边界 | 不生成自动化 flow | 不适用 | 不适用 | 不适用 |

## 自动化可行性判定

可执行：TC-VAL-001, TC-VAL-002, TC-VAL-003, TC-VAL-004, TC-VAL-005, TC-VAL-006, TC-VAL-007, TC-VAL-008, TC-VAL-009, TC-VAL-010, TC-VAL-011, TC-VAL-012, TC-VAL-013, TC-GRPC-001, TC-GRPC-002, TC-GRPC-003, TC-GRPC-004, TC-SCHEMA-001, TC-SCHEMA-002, TC-SCHEMA-003, TC-RATE-001, TC-RATE-002, TC-RATE-003, TC-RATE-004, TC-RATE-005, TC-RATE-006, TC-RATE-007

可行性存疑（保持 skipped）：TC-RATE-008, TC-RATE-009, TC-RATE-010, TC-SCHEMA-004

原因：
- TC-RATE-008/009 需要控制 Redis 可用性，不能修改仓库 `.env` 或运行配置。
- TC-RATE-010 需要控制服务进程内时间。
- TC-SCHEMA-004 是已知 mismatch，不应作为稳定通过自动化。
