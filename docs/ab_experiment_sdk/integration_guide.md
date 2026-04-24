# AB 实验 SDK 接入指南

## 概述

AB 实验 SDK 提供实验分流能力：业务系统传入用户 ID 和需要评估的实验列表，SDK 返回每个实验命��的策略及其参数。

分流��先级：**白名单 > hash 分流**。

两种接入模式：
- **远程模式**（推荐）：业务系统通过 `RemoteABExperimentSDK` 调用独立���署的 AB 实验服务
- **本地模式**：业务系统在进程内实例化 `ConfigBasedABExperimentSDK`，适用于���发调试

两种模式实现同一个 `ABExperimentSDK` Protocol，业��代码无需感���差异。

## 快速开始

### 1. 启动 AB 实验服务

```bash
python -m ab_experiment_sdk.service
```

默���监听 `0.0.0.0:8100`，可通过环境变量配置：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `AB_SERVICE_HOST` | `0.0.0.0` | 监听地址 |
| `AB_SERVICE_PORT` | `8100` | 监听端口 |
| `AB_SERVICE_EXPERIMENTS_PATH` | `ab_experiment_sdk/data/experiments.json` | 实验配置文件路径 |

启动后访问 `http://localhost:8100/docs` 查看 API 文档。

### 2. 初始化 SDK 客户端

```python
from ab_experiment_sdk import RemoteABExperimentSDK

sdk = RemoteABExperimentSDK(
    base_url="http://localhost:8100",
    timeout=2.0,  # 秒，默认 2.0
)
```

### 3. 评估实验

```python
from ab_experiment_sdk import ABExperimentRequest

response = sdk.evaluate(ABExperimentRequest(
    user_id="user_12345",
    request_id="req-001",          # 可选，用于日志追踪
    experiment_names=["my_exp"],   # 要评估的实验名列表，None 表示评估全部
))

# 遍历命中结果
for exp_name, assignment in response.assignments.items():
    print(f"实验: {assignment.experiment_name}")
    print(f"策略: {assignment.strategy_id}")
    print(f"参数: {assignment.params}")
    print(f"命中原因: {assignment.hit_reason}")  # "hash" 或 "whitelist"
```

### 4. 关闭连接

```python
sdk.close()
```

## 数据结构

### ABExperimentRequest（请求）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | `str` | 是 | 用户 ID，用于 hash 分流 |
| `request_id` | `str` | 否 | 请求标识，用于日志追踪 |
| `context` | `dict` | 否 | 上下文信息，透传不参与分流 |
| `experiment_names` | `list[str]` 或 `None` | 否 | 要评估的实验名列表 |

`experiment_names` 的行为：
- `None`：评估服务端配置的全部实验
- `[]`：不评估任何实验，返回空结果
- `["exp_a", "exp_b"]`：只评估指定实验

### ABExperimentResponse（响应）

| 字段 | 类型 | 说明 |
|------|------|------|
| `request_id` | `str` | 回传请求标识 |
| `user_id` | `str` | 回传用户 ID |
| `assignments` | `dict[str, ABExperimentAssignment]` | 命中结果，key 为实验名 |
| `trace_id` | `str` | 服务端生成的追踪 ID |

### ABExperimentAssignment（单个实验命中结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| `experiment_name` | `str` | 实验名 |
| `strategy_id` | `str` | 命中的策略 ID |
| `params` | `dict` | 策略参数，业务侧按需读取 |
| `hit_reason` | `str` | `"hash"` 或 `"whitelist"` |

## 分��机制

### Hash 分流

对 `user_id` 做 MD5 取模（mod 100），落入策略的 `hash_range` 区间���命中。

```
user_id="u001" → MD5 → int → % 100 = 42

策略��置:
  strategy_a: hash_range [0, 30)   → 不命中
  strategy_b: hash_range [30, 60)  → 命中 ✓
  strategy_c: hash_range [60, 100) → 不命中
```

`hash_range` 为左闭右开区间 `[low, high)`。

### 白名单

白名单优先级高于 hash 分流，用于测试验证时强���指定用户命中��定策略。

白名单通过服务 API 管理（见下��），持久化到本地文件，服务重启自动恢复。

## 服务端管理 API

### 实验管理

```bash
# 列出所有实验
curl http://localhost:8100/api/v1/ab/experiments

# 查询单个实验
curl http://localhost:8100/api/v1/ab/experiments/my_exp

# 创建实验
curl -X POST http://localhost:8100/api/v1/ab/experiments \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "my_exp",
    "strategies": [
      {"id": "control",   "hash_range": [0, 50],  "params": {"enabled": false}},
      {"id": "treatment", "hash_range": [50, 100], "params": {"enabled": true}}
    ]
  }'

# 更新实验（整体替换策略列表）
curl -X PUT http://localhost:8100/api/v1/ab/experiments/my_exp \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "my_exp",
    "strategies": [
      {"id": "control",   "hash_range": [0, 30],  "params": {"enabled": false}},
      {"id": "treatment", "hash_range": [30, 100], "params": {"enabled": true}}
    ]
  }'

# 删除实验
curl -X DELETE http://localhost:8100/api/v1/ab/experiments/my_exp
```

### 白名单管理

```bash
# 查看全部白名单
curl http://localhost:8100/api/v1/ab/whitelist

# 设置单用户白名单（强制 user_001 在 my_exp 中命中 treatment）
curl -X PUT http://localhost:8100/api/v1/ab/whitelist/user_001 \
  -H 'Content-Type: application/json' \
  -d '{"strategy_map": {"my_exp": "treatment"}}'

# 查看单用户白名单
curl http://localhost:8100/api/v1/ab/whitelist/user_001

# 清除单用户白名单
curl -X DELETE http://localhost:8100/api/v1/ab/whitelist/user_001

# 整量替换全部白名单
curl -X PUT http://localhost:8100/api/v1/ab/whitelist \
  -H 'Content-Type: application/json' \
  -d '{"user_001": {"my_exp": "treatment"}, "user_002": {"my_exp": "control"}}'

# 清空全部白名单
curl -X DELETE http://localhost:8100/api/v1/ab/whitelist
```

白名单也可通过 SDK 客户端操作：

```python
sdk.set_user_whitelist("user_001", {"my_exp": "treatment"})
sdk.get_whitelist()
sdk.clear_whitelist("user_001")
sdk.clear_whitelist()  # 清空全部
```

## 接入示例

### 典���业务接入

```python
from ab_experiment_sdk import ABExperimentRequest, RemoteABExperimentSDK

# 初始化（应用启动时创��一次，全局复用）
sdk = RemoteABExperimentSDK(base_url="http://localhost:8100")

def handle_request(user_id: str, scene_experiments: list[str]):
    """业���请求处理"""
    result = sdk.evaluate(ABExperimentRequest(
        user_id=user_id,
        experiment_names=scene_experiments,
    ))

    # 读取实���参��驱动业务逻辑
    for exp_name, assignment in result.assignments.items():
        if assignment.params.get("enable_new_feature"):
            # 走新逻辑
            pass
        else:
            # 走旧逻辑
            pass
```

### 本地模式（开发调试）

```python
from ab_experiment_sdk import (
    ConfigBasedABExperimentSDK,
    ABExperimentRequest,
)
from ab_experiment_sdk.models import (
    Experiment,
    ExperimentConfig,
    ExperimentStrategy,
)

config = ExperimentConfig(experiments=[
    Experiment(
        name="my_exp",
        strategies=[
            ExperimentStrategy(id="on",  hash_range=[0, 50],  params={"flag": True}),
            ExperimentStrategy(id="off", hash_range=[50, 100], params={"flag": False}),
        ],
    ),
])
sdk = ConfigBasedABExperimentSDK(config)

# 用法与远程模式完全一致
response = sdk.evaluate(ABExperimentRequest(
    user_id="test_user",
    experiment_names=["my_exp"],
))
```

## 实验配置格式

实验配置存储在 `ab_experiment_sdk/data/experiments.json`：

```json
{
  "experiments": [
    {
      "name": "实验名（全局唯一）",
      "strategies": [
        {
          "id": "策略ID（实验内唯一）",
          "hash_range": [0, 50],
          "params": {
            "业务参数key": "业务参数value"
          }
        },
        {
          "id": "另一个策略",
          "hash_range": [50, 100],
          "params": {}
        }
      ]
    }
  ]
}
```

**注意事项**：
- `hash_range` 为 `[low, high)`，取值范围 0-100，各策略区间不应重叠
- `params` 由业务侧自行定���和解读，SDK 不做校���，原样透传
- 通过服务 API 进��的增删改会自动持久化到该文件

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
