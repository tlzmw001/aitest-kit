# AB 实验服务拆分方案

## Context

当前 AB 实验是一个 in-process 的 Python 包（`ab_experiment_sdk/`），由 `coupon_system` 直接实例化并调用。未来目标是建设独立的 AB 实验平台（前端+后端），支持实验管理、白名单配置、可视化。本次先完成后端服务拆分：将实验评估和管理能力独立为 FastAPI 服务，SDK 变为轻量 HTTP 客户端。

## 决策

- **实验 CRUD**：完整 CRUD API，变更持久化回 JSON 文件
- **场景映射**：`scene_experiments.json` 留在 `coupon_system`，AB 服务不感知场景概念
- **协议**：HTTP (FastAPI)，SDK 用 httpx 调用

## 文件变更清单

| 文件 | 操作 | 行数估算 | 说明 |
|------|------|----------|------|
| `ab_experiment_sdk/service.py` | 新建 | ~350 | FastAPI 服务：evaluate + 实验 CRUD + 白名单 CRUD |
| `ab_experiment_sdk/remote_client.py` | 新建 | ~130 | `RemoteABExperimentSDK`，实现 `ABExperimentSDK` Protocol |
| `ab_experiment_sdk/__init__.py` | 修改 | +2 | 导出 `RemoteABExperimentSDK` |
| `coupon_system/main.py` | 修改 | ~5 | 根据 `AB_SERVICE_URL` 环境变量切换 local/remote SDK |
| `tests/test_ab_service.py` | 新建 | ~250 | 服务端测试（evaluate、实验 CRUD、白名单 CRUD） |
| `tests/test_ab_remote_client.py` | 新建 | ~150 | 远程客户端测试（round-trip、错误处理） |

不修改：`coupon_service.py`、`client.py`、`models.py`、已有测试。

## 1. AB 实验服务 (`ab_experiment_sdk/service.py`)

**启动方式**：`python -m ab_experiment_sdk.service` 或 `uvicorn ab_experiment_sdk.service:app`

**配置**（环境变量）：
- `AB_SERVICE_HOST`（默认 `0.0.0.0`）
- `AB_SERVICE_PORT`（默认 `8100`）
- `AB_SERVICE_EXPERIMENTS_PATH`（默认 `coupon_system/config/experiments.json`）
- `AB_SDK_WHITELIST_JSON`（可选，启动时加载初始白名单）

**内部实现**：服务内部持有 `ConfigBasedABExperimentSDK` 实例，复用全部 hash/白名单逻辑，零重复。实验配置变更时同步更新内部 SDK 实例和 JSON 文件。

### API 设计

#### 核心 — 实验评估

```
POST /api/v1/ab/evaluate
```
- Request: `{user_id, request_id?, context?, experiment_names?}`
- Response: `{request_id, user_id, assignments: {exp_name: {experiment_name, strategy_id, params, hit_reason}}, trace_id}`
- 直接序列化现有 `ABExperimentResponse` / `ABExperimentAssignment`

#### 实验管理 CRUD

```
GET    /api/v1/ab/experiments              → 列出所有实验
GET    /api/v1/ab/experiments/{name}       → 查询单个实验详情
POST   /api/v1/ab/experiments              → 创建实验
PUT    /api/v1/ab/experiments/{name}       → 更新实验（整体替换策略列表）
DELETE /api/v1/ab/experiments/{name}       → 删除实验
```

创建/更新/删除后：
1. 更新内存中的 `ExperimentConfig`
2. 重建 `ConfigBasedABExperimentSDK` 实例（保留当前白名单）
3. 持久化到 JSON 文件

#### 白名单管理

```
GET    /api/v1/ab/whitelist                → 查看全部白名单
PUT    /api/v1/ab/whitelist                → 整量替换白名单
DELETE /api/v1/ab/whitelist                → 清空全部白名单
GET    /api/v1/ab/whitelist/{user_id}      → 查看单用户白名单
PUT    /api/v1/ab/whitelist/{user_id}      → 设置单用户白名单
DELETE /api/v1/ab/whitelist/{user_id}      → 清除单用户白名单
```

#### 健康检查

```
GET /health → {"status": "ok"}
```

### Pydantic 模型

在 `service.py` 内定义请求/响应模型，镜像现有 dataclass 结构：

```python
class EvaluateRequest(BaseModel):
    user_id: str
    request_id: str = ""
    context: dict = {}
    experiment_names: Optional[list[str]] = None

class StrategyModel(BaseModel):
    id: str
    hash_range: list[int] = [0, 100]
    params: dict = {}

class ExperimentModel(BaseModel):
    name: str
    strategies: list[StrategyModel] = []

class AssignmentModel(BaseModel):
    experiment_name: str
    strategy_id: str
    params: dict = {}
    hit_reason: str = "hash"

class EvaluateResponse(BaseModel):
    request_id: str
    user_id: str
    assignments: dict[str, AssignmentModel] = {}
    trace_id: str = ""
```

## 2. 远程客户端 (`ab_experiment_sdk/remote_client.py`)

```python
class RemoteABExperimentSDK:
    """实现 ABExperimentSDK Protocol，通过 HTTP 调用 AB 实验服务。"""

    def __init__(self, base_url: str, timeout: float = 2.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def evaluate(self, request: ABExperimentRequest) -> ABExperimentResponse: ...
    def set_whitelist(self, whitelist: dict) -> None: ...
    def set_user_whitelist(self, user_id: str, strategy_map: dict) -> None: ...
    def clear_whitelist(self, user_id: Optional[str] = None) -> None: ...
    def close(self) -> None: ...
```

- `evaluate()`: POST `/api/v1/ab/evaluate`，将 JSON 响应反序列化为 `ABExperimentResponse` + `ABExperimentAssignment`
- 白名单方法：映射到对应 REST 端点
- 错误处理：HTTP 错误 raise，不静默吞掉（调用方 pipeline 上层处理）
- `close()`：关闭 httpx 连接池

## 3. coupon_system 切换 (`coupon_system/main.py`)

在 `main()` 中 SDK 初始化处（第 126-128 行）改为：

```python
ab_service_url = os.environ.get("AB_SERVICE_URL", "")
if ab_service_url:
    from ab_experiment_sdk import RemoteABExperimentSDK
    experiment_sdk = RemoteABExperimentSDK(base_url=ab_service_url)
    # 白名单通过 AB 服务 API 管理，不在业务侧注入
else:
    experiment_sdk = ConfigBasedABExperimentSDK(experiment_config)
    experiment_sdk.set_whitelist(_load_ab_sdk_whitelist_from_env())
```

- `AB_SERVICE_URL` 未设置 → 走本地 SDK（现有行为，零影响）
- `AB_SERVICE_URL=http://localhost:8100` → 走远程客户端
- `coupon_service.py` 完全不动，因为它只依赖 `ABExperimentSDK` Protocol

## 4. 实现顺序

1. **`ab_experiment_sdk/service.py`** — 服务端，可独立测试
2. **`tests/test_ab_service.py`** — 用 FastAPI TestClient 测试所有端点
3. **`ab_experiment_sdk/remote_client.py`** — HTTP 客户端
4. **`tests/test_ab_remote_client.py`** — 客户端 round-trip 测试
5. **`ab_experiment_sdk/__init__.py`** — 导出新类
6. **`coupon_system/main.py`** — 加环境变量切换逻辑

## 5. 验证方式

```bash
# 1. 现有测试不破坏
pytest tests/ -q

# 2. 服务端测试
pytest tests/test_ab_service.py -v

# 3. 远程客户端测试
pytest tests/test_ab_remote_client.py -v

# 4. 手动端到端验证
# 终端1：启动 AB 服务
python -m ab_experiment_sdk.service
# 终端2：调用 evaluate
curl -X POST http://localhost:8100/api/v1/ab/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u001","experiment_names":["coarse_rank_exp_game"]}'
# 终端3：启动 coupon_system（远程模式）
AB_SERVICE_URL=http://localhost:8100 python -m coupon_system.main
```

## 关键复用

- `ConfigBasedABExperimentSDK`（`client.py:61`）：服务内部直接使用，不重写 hash/白名单逻辑
- `ABExperimentSDK` Protocol（`client.py:45`）：`RemoteABExperimentSDK` 实现同一协议
- `ExperimentConfig` / `Experiment` / `ExperimentStrategy`（`models.py`）：服务端共用
- `ABExperimentRequest` / `ABExperimentResponse` / `ABExperimentAssignment`（`client.py`）：客户端序列化/反序列化目标
- `load_experiment_config()`（`coupon_system/config/__init__.py:173`）：服务启动时复用此函数加载实验
