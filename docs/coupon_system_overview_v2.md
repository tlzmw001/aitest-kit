# 待测系统：智能优惠券推荐策略系统 v2

## 架构

三服务架构（两个进程）：

**主服务进程**（双协议，共享 `CouponBizService` 实例）：
- HTTP (FastAPI) :8000
- gRPC :50051

**打分服务进程**（独立 gRPC 服务）：
- gRPC :50052

**数据层**：
- Redis :6379

## 核心变更

v2 从简单的"领券"服务重构为完整的**推荐策略系统**：

| 维度 | v1 | v2 |
|------|----|----|
| 券来源 | YAML 静态模板 | 请求动态传入候选券列表 |
| 场景路由 | 单字段 scene | 三字段组合 (scene_name, device, policy_id) |
| 打分服务 | 进程内 mock | 独立 gRPC 服务 |
| 实验能力 | 无 | AB 实验分流（粗排/校准） |
| 粗排 | 无 | 可配置截断规则 |
| 特征抽取 | 单一用户画像 JSON | 用户特征(Redis) + item特征(TSV) |
| 分数校准 | 无 | 场景级线性校准 y=kx+b |
| Pipeline | 领券 | 推荐+发放 |

## 目录结构

```
coupon_system/
├── main.py                     # 启动入口（改）
├── http_app.py                 # HTTP 路由（改）
├── config/
│   ├── __init__.py             # 配置加载（改）
│   ├── settings.yaml           # 主配置（改）
│   ├── scenes.json             # 场景路由配置（新）
│   ├── experiments.json        # AB实验配置（新）
│   └── calibration.json        # 校准系数（新）
├── services/
│   ├── coupon_service.py       # 主 pipeline（改）
│   ├── redis_store.py          # Redis 操作（改）
│   ├── experiment.py           # AB实验分流（新）
│   ├── scene_router.py         # 场景路由（新）
│   ├── coarse_ranker.py        # 粗排（新）
│   ├── feature_store.py        # 特征抽取（新）
│   ├── scoring_client.py       # 打分服务客户端（新）
│   ├── calibrator.py           # 分数校准（新）
│   └── grpc_servicer.py        # 策略服务实现（改）
├── protos/
│   ├── coupon.proto            # 策略服务 proto（改）
│   └── scoring.proto           # 打分服务 proto（新）
├── data/
│   └── item_features.tsv       # item 特征文件（新）
└── scoring_server/
    ├── __init__.py
    └── mock_server.py          # Mock 打分服务（新）
```

## API 接口

### 主服务

| 接口 | HTTP | gRPC | 说明 |
|------|------|------|------|
| 推荐+发放 | `POST /api/v1/recommend` | `Recommend` | 新主链路 |
| 查询用户券 | `GET /api/v1/coupons/{user_id}` | `QueryUserCoupons` | 保留 |
| 设置用户特征 | `POST /api/v1/admin/user-features` | 无 | 改名 |
| 初始化库存 | `POST /api/v1/admin/stock` | 无 | 保留 |
| 查询库存 | `GET /api/v1/admin/stock/{coupon_id}` | 无 | 保留 |
| 健康检查 | `GET /health` | 无 | 保留 |

**删除接口**：`POST /api/v1/coupon/claim`、`POST /api/v1/coupon/evaluate`

### 打分服务

| 接口 | gRPC | 说明 |
|------|------|------|
| 打分 | `Score` | 接收用户/item特征，返回分数列表 |

## 推荐+发放 Pipeline

```
请求进入 → 参数校验 → 限流 → AB实验分流 → 场景路由
  ↓
粗排(实验控制) → 特征抽取 → 打分服务(gRPC) → 校准(实验控制)
  ↓
发放最优券 → 返回结果
```

### 详细流程

1. **参数校验**：user_id、scene_name、device、items 必填
2. **限流**：全局 1000 QPS + 单用户 10 QPS
3. **AB实验分流**：hash(user_id) % 100 → 命中策略
4. **场景路由**：
   - policy_id 在 fallback 列表 → 返回兜底分数 0.5
   - (scene_name, device) → scene_id 查表
5. **粗排**（实验控制）：
   - 实验开启 → 按规则截断候选券（top_value/top_min_spend/random）
   - 实验关闭 → 跳过
6. **特征抽取**：
   - 用户特征：从 Redis 读取 7 个特征字段
   - Item 特征：从 TSV 文件读取（启动时加载到内存）
7. **打分服务**：gRPC 调用独立打分服务
8. **校准**（实验控制）：
   - 实验开启 → 按场景系数校准 `y = k*x + b`
   - 实验关闭 → 跳过
9. **发放**：
   - 选择最高分 item
   - 分数 >= 阈值(0.5) → 扣库存 + 记录领取
   - 分数 < 阈值 → 不发放
10. **返回**：scene_id、实验信息、所有 item 打分结果、发放的券

## 请求/响应结构

### RecommendRequest

```json
{
  "user_id": "user_12345",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "policy_001",
  "context": {
    "timestamp": "2026-04-02T10:00:00Z",
    "channel": "app"
  },
  "items": [
    {
      "item_id": "COUPON_ACT_001",
      "coupon_type": "discount",
      "value": 20.0,
      "min_spend": 100.0,
      "expire_days": 7
    }
  ]
}
```

### RecommendResponse

```json
{
  "code": 0,
  "message": "success",
  "scene_id": 1001,
  "experiment_info": {
    "coarse_rank_exp": "cr_on",
    "calibration_exp": "cal_on"
  },
  "results": [
    {
      "item_id": "COUPON_ACT_001",
      "score": 0.75,
      "calibrated_score": 1.0,
      "recommended": true
    }
  ],
  "coupon": {
    "id": "uuid-xxx",
    "item_id": "COUPON_ACT_001",
    "user_id": "user_12345",
    "status": "active",
    "claimed_at": "2026-04-02T10:00:00Z",
    "expire_at": "2026-04-09T10:00:00Z"
  }
}
```

## 错误码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1001 | 参数无效 |
| 1002 | 场景不存在 |
| 1003 | 优惠券不存在 |
| 1004 | 券不适用当前场景 |
| 1005 | 已领取过 |
| 1006 | 库存不足 |
| 1007 | 超过领取次数限制 |
| 1008 | 非新用户 |
| 1009 | 非会员 |
| 1010 | 限流 |
| 1011 | 模型拒绝 |
| 1012 | 打分服务错误（新增） |
| 5000 | 内部错误 |

## 场景路由

### 路由表

| scene_name | device | scene_id |
|------------|--------|----------|
| game | mobile | 1001 |
| game | pc | 1002 |
| game | pad | 1003 |
| ad | mobile | 2001 |
| ad | pc | 2002 |
| ad | pad | 2003 |

### 兜底策略

- **触发条件**：policy_id 在 `["policy_fallback_001", "policy_fallback_002"]`
- **行为**：跳过打分，返回 scene_id=3001，所有 item 分数=0.5

## AB 实验

### 分流算法

```python
hash_value = hashlib.md5(user_id.encode()).digest()[0] % 100
# 根据 hash_value 落入策略的 hash_range
```

### 实验配置

#### coarse_rank_exp（粗排实验）

| 策略 | hash_range | 参数 |
|------|-----------|------|
| cr_on | [0, 50) | enable_coarse_rank=true, truncate_count=5, truncate_rule="top_value" |
| cr_off | [50, 100) | enable_coarse_rank=false |

#### calibration_exp（校准实验）

| 策略 | hash_range | 参数 |
|------|-----------|------|
| cal_on | [0, 50) | enable_calibration=true |
| cal_off | [50, 100) | enable_calibration=false |

## 粗排规则

| 规则 | 说明 |
|------|------|
| top_value | 按 item.value 降序，保留前 N |
| top_min_spend | 按 item.min_spend 降序，保留前 N |
| random | 随机选 N 个 |

默认 N=5（由实验配置控制）

## 特征抽取

### 用户特征（Redis）

从 Redis 读取 7 个特征字段，key 格式：`coupon:user_feature:{feature_name}:{user_id}`

| 特征名 | 类型 | 说明 |
|--------|------|------|
| gender | string | 性别 |
| age | int | 年龄 |
| total_spend | float | 累计消费 |
| purchase_frequency | int | 购买频次 |
| register_days | int | 注册天数 |
| is_new_user | bool | 是否新用户 |
| is_member | bool | 是否会员 |

### Item 特征（TSV 文件）

文件路径：`coupon_system/data/item_features.tsv`

格式：`item_id\t{json}`

| item_id | stock | popularity | avg_conversion |
|---------|-------|------------|----------------|
| COUPON_NEW_001 | 10,000 | 0.7 | 0.12 |
| COUPON_ACT_001 | 50,000 | 0.85 | 0.18 |
| COUPON_MEM_001 | 5,000 | 0.6 | 0.25 |
| COUPON_SHIP_001 | 100,000 | 0.9 | 0.30 |

## 打分服务

### 协议

gRPC，proto 定义：`coupon_system/protos/scoring.proto`

### 请求结构

```protobuf
message ScoreRequest {
  string request_id = 1;
  string user_id = 2;
  int32 scene_id = 3;
  map<string, string> user_features = 4;
  map<string, string> context_features = 5;
  repeated ItemFeatures items = 6;
}
```

### 响应结构

```protobuf
message ScoreResponse {
  int32 code = 1;
  string message = 2;
  repeated ItemScore scores = 3;
}

message ItemScore {
  string item_id = 1;
  float score = 2;
}
```

### Mock 打分逻辑

基础分 0.5 + 特征加分 + 随机噪声：

- `is_new_user=true`: +0.15
- `is_member=true`: +0.10
- `total_spend > 10000`: +0.10；`> 5000`: +0.05
- `popularity * 0.1`（来自 item 特征）
- 随机噪声：[-0.05, +0.05]
- 最终 clamp 到 [0.0, 1.0]

### 故障注入

- `set_simulate_failure(True)` → 返回 code=5000
- `set_simulate_timeout(True, seconds)` → sleep 后返回 code=5000

## 分数校准

### 公式

```
calibrated = clamp(k * raw_score + b, 0, 1)
```

### 系数配置

| scene_id | k | b | 说明 |
|----------|---|---|------|
| 1001 | 1.2 | 0.1 | game+mobile 提升 |
| 1002 | 0.9 | 0.05 | game+pc 轻微降低 |
| 1003 | 1.0 | 0.0 | game+pad 不调整 |
| 2001 | 1.1 | 0.08 | ad+mobile 提升 |
| 2002 | 0.95 | 0.03 | ad+pc 轻微降低 |
| 2003 | 1.0 | 0.0 | ad+pad 不调整 |
| default | 1.0 | 0.0 | 兜底不调整 |

## Redis Key

| Key 模式 | 类型 | 用途 | TTL |
|----------|------|------|-----|
| `coupon:stock:{coupon_id}` | STRING | 库存计数 | 86400s |
| `coupon:user:{uid}:claimed` | SET | 已领券ID集合 | 604800s |
| `coupon:user:{uid}:scene_count:{scene}` | STRING | 场景领取计数 | 604800s |
| `coupon:user_profile:{uid}` | STRING(JSON) | 用户画像（v1遗留） | 86400s |
| `coupon:user_feature:{feature_name}:{uid}` | STRING | 单个用户特征（新） | 86400s |
| `coupon:instance:{uuid}` | STRING(JSON) | 券实例 | 604800s |
| `coupon:user:{uid}:instances` | SET | 用户持有券实例ID | 604800s |
| `coupon:rate:{key_suffix}` | ZSET | 滑动窗口限流 | window+1s |

## 配置文件

### settings.yaml

```yaml
rate_limit:
  enabled: true
  global_qps: 1000
  per_user_qps: 10
  window_seconds: 1

fallback:
  enabled: true
  on_timeout:
    action: allow
    default_score: 0.5
  on_unavailable:
    action: allow
    default_score: 0.3

scoring_service:
  host: localhost
  port: 50052
  timeout: 2.0
  enabled: true

redis:
  url: redis://localhost:6379/0
  key_prefix: coupon:
  stock_ttl: 86400
  user_claim_ttl: 604800

claim:
  score_threshold: 0.5
  max_claim_per_request: 1

user_feature_keys:
  - gender
  - age
  - total_spend
  - purchase_frequency
  - register_days
  - is_new_user
  - is_member

item_feature_file: data/item_features.tsv
```

### scenes.json

6 个路由 + 兜底配置（见"场景路由"章节）

### experiments.json

2 个实验配置（见"AB 实验"章节）

### calibration.json

7 个场景系数 + default（见"分数校准"章节）

## 启动

### 主服务

```bash
python -m coupon_system.main
```

启动流程：
1. 编译 proto（coupon.proto + scoring.proto）
2. 加载 4 个配置文件
3. 初始化 Redis 连接
4. 初始化 8 个依赖模块
5. 启动 HTTP 服务（:8000）
6. 启动 gRPC 服务（:50051）

### 打分服务

```bash
python -m coupon_system.scoring_server.mock_server
```

监听端口：50052（可通过 `SCORING_PORT` 环境变量修改）

## 测试

```bash
# 单元测试
pytest tests/test_coupon_service.py -v

# 覆盖率
pytest tests/ --cov=coupon_system --cov-report=html
```

测试覆盖：
- 参数校验（4 tests）
- 场景路由（4 tests）
- AB 实验（1 test）
- 粗排（2 tests）
- 推荐+发放（5 tests）
- 打分失败（2 tests）
- 校准（3 tests）
- 特征抽取（3 tests）
- 查询券（3 tests）
- 限流（1 test）

共 28 个测试用例。
