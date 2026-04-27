# 服务启动说明

本文档记录本地开发和测试用例执行前需要启动的服务、默认端口、启动顺序和健康检查命令。

## 服务列表

| 服务 | 协议 | 默认地址 | 启动入口 | 说明 |
|---|---|---|---|---|
| Redis | TCP | `127.0.0.1:6379` | `redis-server` | 主服务用于库存、领取记录、用户特征、限流计数 |
| AB 实验服务 | HTTP | `127.0.0.1:8100` | `python3 -m ab_experiment_sdk.service` | 提供实验评估、实验管理、白名单管理 |
| 内部打分服务 | gRPC | `127.0.0.1:50052` | `python3 -m coupon_system.scoring_server.mock_server` | 主服务 `external=0` 时调用 |
| 外部打分服务 | HTTP | `127.0.0.1:50053/score` | `python3 -m coupon_system.scoring_server.external_mock_server` | 主服务 `external=1` 时调用 |
| 待测 HTTP 服务 | HTTP | `127.0.0.1:8000` | `python3 -m coupon_system.main` | 优惠券推荐 HTTP API |
| 待测 gRPC 服务 | gRPC | `127.0.0.1:50051` | `python3 -m coupon_system.main` | 优惠券推荐 gRPC API，由主服务同进程启动 |

## 启动顺序

推荐按依赖从下游到上游启动：

1. Redis
2. AB 实验服务
3. 内部 gRPC 打分服务
4. 外部 HTTP 打分服务
5. 待测主服务

主服务启动时会读取 `AB_SERVICE_URL`。如果不设置该变量，主服务会使用进程内本地 AB SDK；测试远程 AB 服务链路时应显式设置 `AB_SERVICE_URL`。

## 启动命令

以下命令在仓库根目录执行。

### 1. Redis

如果 Redis 已经在 `127.0.0.1:6379` 监听，不需要重复启动：

```bash
lsof -nP -iTCP:6379 -sTCP:LISTEN
```

如果没有监听进程，启动 Redis：

```bash
redis-server
```

如果本机 Redis 使用 Homebrew 安装，也可以按本机习惯用服务方式启动：

```bash
brew services start redis
```

### 2. AB 实验服务

本地测试建议只监听回环地址：

```bash
env AB_SERVICE_HOST=127.0.0.1 python3 -m ab_experiment_sdk.service
```

可用环境变量：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `AB_SERVICE_HOST` | `0.0.0.0` | AB 服务监听地址 |
| `AB_SERVICE_PORT` | `8100` | AB 服务监听端口 |
| `AB_SERVICE_EXPERIMENTS_PATH` | `ab_experiment_sdk/data/experiments.json` | 实验配置文件路径 |

### 3. 内部 gRPC 打分服务

```bash
python3 -m coupon_system.scoring_server.mock_server
```

可用环境变量：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `SCORING_PORT` | `50052` | 内部 gRPC 打分服务端口 |

### 4. 外部 HTTP 打分服务

```bash
python3 -m coupon_system.scoring_server.external_mock_server
```

可用环境变量：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `EXTERNAL_SCORING_PORT` | `50053` | 外部 HTTP 打分服务端口 |

### 5. 待测主服务

```bash
env AB_SERVICE_URL=http://localhost:8100 python3 -m coupon_system.main
```

主服务会在同一个进程中启动：

- HTTP API：默认 `0.0.0.0:8000`
- gRPC API：默认 `0.0.0.0:50051`

可用环境变量：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `HTTP_PORT` | `8000` | 待测 HTTP 服务端口 |
| `GRPC_PORT` | `50051` | 待测 gRPC 服务端口 |
| `COUPON_CONFIG_PATH` | `coupon_system/config/settings.yaml` | 主配置文件路径 |
| `AB_SERVICE_URL` | 空 | 远程 AB 服务地址；为空时使用本地 SDK 模式 |
| `AB_SDK_WHITELIST_JSON` | 空 | 本地 SDK 模式下的白名单 JSON |

## 配置依赖

主服务默认读取 `coupon_system/config/settings.yaml`。与启动相关的默认依赖如下：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `redis.url` | `redis://localhost:6379/0` | Redis 连接地址 |
| `scoring_service.host` | `localhost` | 内部 gRPC 打分服务主机 |
| `scoring_service.port` | `50052` | 内部 gRPC 打分服务端口 |
| `external_scoring_service.host` | `localhost` | 外部 HTTP 打分服务主机 |
| `external_scoring_service.port` | `50053` | 外部 HTTP 打分服务端口 |
| `external_scoring_service.path` | `/score` | 外部 HTTP 打分接口路径 |

不要直接修改 `.env` 或项目配置文件来临时切换端口；本地临时启动优先使用环境变量。

## 健康检查

### HTTP 健康检查

```bash
curl -sS http://127.0.0.1:8100/health
curl -sS http://127.0.0.1:8000/health
```

期望返回：

```json
{"status":"ok"}
```

```json
{"status":"ok","version":"0.2.0"}
```

### Redis 连通性

```bash
redis-cli -h 127.0.0.1 -p 6379 ping
```

期望返回：

```text
PONG
```

### 外部 HTTP 打分服务连通性

```bash
curl -sS -X POST http://127.0.0.1:50053/score \
  -H 'Content-Type: application/json' \
  -d '{"user_features":{},"context_features":{},"items":[{"item_id":"CHECK","features":{}}]}'
```

期望返回 `code == 0`，并包含 `scores`：

```json
{"code":0,"message":"success","scores":[{"item_id":"CHECK","score":0.2}]}
```

`score` 带随机噪声，具体数值不固定。

### 端口监听检查

```bash
lsof -nP -iTCP:6379 -sTCP:LISTEN
lsof -nP -iTCP:8100 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:50051 -sTCP:LISTEN
lsof -nP -iTCP:50052 -sTCP:LISTEN
lsof -nP -iTCP:50053 -sTCP:LISTEN
```

## 常见问题

### 端口被占用

先用 `lsof` 找到占用端口的进程，再决定是否复用、停止或换端口：

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

如果换端口，优先通过对应环境变量指定，并保持主服务配置与依赖服务地址一致。

### 主服务启动了但推荐链路失败

先确认下游依赖都已启动：

- Redis：`redis-cli -h 127.0.0.1 -p 6379 ping`
- AB 实验服务：`curl -sS http://127.0.0.1:8100/health`
- 内部打分服务：`lsof -nP -iTCP:50052 -sTCP:LISTEN`
- 外部打分服务：`curl -sS -X POST http://127.0.0.1:50053/score ...`

如果只访问 `/health` 成功，不代表完整推荐链路可用；推荐链路还依赖 Redis、AB 服务和对应打分服务。

### Codex 沙箱内启动服务失败

在 Codex 沙箱环境里，绑定本机端口可能返回 `operation not permitted`。这种情况下需要授权命令在沙箱外执行。服务本身的启动命令不变。
