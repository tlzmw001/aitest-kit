# 优惠券推荐策略系统 — 数据流详解

用一个完整例子贯穿 pipeline 的每一步，展示请求数据如何流经各模块、各配置如何影响行为。

---

## 完整数据流示例

假设用户 `user_alice`，在游戏场景的移动端请求推荐优惠券。

### 第 1 步：请求进入

**HTTP 请求**：
```bash
POST http://localhost:8000/api/v1/recommend
Content-Type: application/json

{
  "user_id": "user_alice",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "context": {
    "timestamp": "2026-04-02T14:30:00Z",
    "channel": "app"
  },
  "items": [
    {
      "item_id": "COUPON_ACT_001",
      "coupon_type": "discount",
      "value": 80,
      "min_spend": 5000,
      "expire_days": 7
    },
    {
      "item_id": "COUPON_SHIP_001",
      "coupon_type": "free_shipping",
      "value": 0,
      "min_spend": 0,
      "expire_days": 30
    },
    {
      "item_id": "COUPON_MEM_001",
      "coupon_type": "fixed",
      "value": 5000,
      "min_spend": 20000,
      "expire_days": 1
    }
  ],
  "external": 0,
  "score_threshold": 0.5,
  "max_claim_per_request": 1
}
```

**关键请求参数说明**：

| 参数 | 含义 | 本例值 |
|------|------|--------|
| `external` | 打分路由，0=内部gRPC，1=外部HTTP（**必传**） | 0 |
| `score_threshold` | 发放分数阈值（**必传**） | 0.5 |
| `max_claim_per_request` | 单次最多发放券数（**必传**） | 1 |
| `policy_id` | 兜底策略标识，留空走正常打分 | "" |

> 这三个参数（external、score_threshold、max_claim_per_request）都是**请求级必传参数**，缺少任何一个都会返回 `INVALID_PARAM`。

入口代码：`coupon_service.py:99` `recommend_and_claim()`

---

### 第 2 步：参数校验

`coupon_service.py:131-140`

```python
# 基础必填校验
if not user_id or not scene_name or not device or not items:
    return self._error(CouponError.INVALID_PARAM)

# 请求级控制参数校验
claim_controls = self._resolve_claim_controls(
    external=external,              # 必须是 0 或 1
    score_threshold=score_threshold, # 必须在 [0.0, 1.0]
    max_claim_per_request=max_claim_per_request,  # 必须 >= 1
)
if claim_controls is None:
    return self._error(CouponError.INVALID_PARAM)
```

**`_resolve_claim_controls` 校验规则**（`coupon_service.py:407-425`）：

| 检查项 | 合法值 | 非法示例 |
|--------|--------|----------|
| `external` | `0` 或 `1` | `None`、`2`、`-1` |
| `score_threshold` | `0.0 ~ 1.0` | `None`、`1.5`、`-0.1` |
| `max_claim_per_request` | `>= 1` | `None`、`0`、`-1` |

本例：`external=0, score_threshold=0.5, max_claim_per_request=1` → 校验通过。

同时计算打分路由标识：
```python
route = 2 if external == 1 else 1   # 本例 route=1（内部gRPC）
request_id = req_id or str(uuid.uuid4())  # 自动生成 UUID
```

---

### 第 3 步：限流检查

`coupon_service.py:144-155`

**前提**：`config/settings.yaml` 中 `rate_limit.enabled: true`

**全局限流**：
```
Redis key: coupon:rate:global
类型:      ZSET（成员是时间戳）
操作:      ZREMRANGEBYSCORE 删除 1 秒前的记录
           → ZADD 当前时间戳
           → ZCARD 统计总数
判断:      总数 <= 1000 → 通过
```

**用户限流**：
```
Redis key: coupon:rate:user:user_alice
操作:      同上
判断:      总数 <= 10 → 通过
```

滑动窗口实现见 `redis_store.py:106-117`。

---

### 第 4 步：AB 实验分流

`coupon_service.py:158` → `experiment.py:28`

**Hash 计算**：
```python
digest = hashlib.md5("user_alice".encode()).hexdigest()
hash_value = int(digest, 16) % 100
# 假设结果 = 23
```

**配置**（`config/experiments.json`）：
```json
{
  "experiments": [
    {
      "name": "coarse_rank_exp",
      "strategies": [
        {"id": "cr_on",  "hash_range": [0, 50],  "params": {"enable_coarse_rank": true, "truncate_count": 5, "truncate_rule": "top_value"}},
        {"id": "cr_off", "hash_range": [50, 100], "params": {"enable_coarse_rank": false}}
      ]
    },
    {
      "name": "calibration_exp",
      "strategies": [
        {"id": "cal_on",  "hash_range": [0, 50],  "params": {"enable_calibration": true}},
        {"id": "cal_off", "hash_range": [50, 100], "params": {"enable_calibration": false}}
      ]
    }
  ]
}
```

**匹配逻辑**（`experiment.py:62-70`）：
- hash=23，检查 `low <= 23 < high`
- `coarse_rank_exp`: 23 ∈ [0, 50) → 命中 `cr_on`
- `calibration_exp`: 23 ∈ [0, 50) → 命中 `cal_on`

**分流结果**：
```python
exp_result = {
    "coarse_rank_exp": ExperimentResult(
        strategy_id="cr_on",
        params={"enable_coarse_rank": True, "truncate_count": 5, "truncate_rule": "top_value"}
    ),
    "calibration_exp": ExperimentResult(
        strategy_id="cal_on",
        params={"enable_calibration": True}
    ),
}

# 写入响应的实验信息
experiment_info = {"coarse_rank_exp": "cr_on", "calibration_exp": "cal_on"}
```

> 如果 hash=75，则命中 `cr_off` + `cal_off`，粗排和校准都会被跳过。

---

### 第 5 步：场景路由

`coupon_service.py:164` → `scene_router.py:31`

**配置**（`config/scenes.json`）：
```json
{
  "routes": [
    {"scene_name": "game", "device": "mobile", "scene_id": 1001},
    {"scene_name": "game", "device": "pc",     "scene_id": 1002},
    {"scene_name": "game", "device": "pad",    "scene_id": 1003},
    {"scene_name": "ad",   "device": "mobile", "scene_id": 2001},
    {"scene_name": "ad",   "device": "pc",     "scene_id": 2002},
    {"scene_name": "ad",   "device": "pad",    "scene_id": 2003}
  ],
  "fallback_policy_ids": ["policy_fallback_001", "policy_fallback_002"],
  "fallback_scene_id": 3001,
  "fallback_score": 0.5
}
```

**路由逻辑**：
1. 检查 `policy_id=""` 是否在 `fallback_policy_ids` 中 → 否
2. 查找 `("game", "mobile")` → 找到 `scene_id=1001`

**路由结果**：
```python
SceneResult(scene_id=1001, is_fallback=False)
```

路由完成后写入日志：
```python
logger.info(
    "recommend request: reqId=%s user_id=%s item_ids=%s route=%d scene_id=%d",
    request_id, user_id, "COUPON_ACT_001,COUPON_SHIP_001,COUPON_MEM_001", 1, 1001,
)
```

---

### 第 6 步：粗排（实验控制）

`coupon_service.py:184-188`

因为 `cr_exp.params["enable_coarse_rank"] = True`，执行粗排。

**粗排逻辑**（`coarse_ranker.py:13`）：
```python
truncate_rule  = "top_value"
truncate_count = 5
```

当前 items 只有 3 个，`5 >= 3`，不截断，原样返回。

**如果有 10 个候选券**：
```
原始: [A(value=80), B(value=0), C(value=5000), D(value=200), E(value=100), ...]
按 value 降序排序: [C(5000), D(200), E(100), A(80), ...]
保留前 5 个: [C, D, E, A, ...]
```

**其他规则**：
- `top_min_spend`: 按 `min_spend` 降序截断
- `random`: 随机选 N 个

---

### 第 7 步：特征抽取

`coupon_service.py:190-203`

#### 7a. 用户特征（Redis 逐字段读取）

`feature_store.py:58-71` → `redis_store.py:84-87`

从 `settings.yaml` 读取特征列表：
```yaml
user_feature_keys:
  - "gender"
  - "age"
  - "total_spend"
  - "purchase_frequency"
  - "register_days"
  - "is_new_user"
  - "is_member"
```

逐个读取 Redis：
```
GET coupon:user_feature:gender:user_alice          → "female"
GET coupon:user_feature:age:user_alice             → "28"
GET coupon:user_feature:total_spend:user_alice     → "12500"
GET coupon:user_feature:purchase_frequency:user_alice → (nil)  ← 缺失则跳过
GET coupon:user_feature:register_days:user_alice   → "365"
GET coupon:user_feature:is_new_user:user_alice     → "false"
GET coupon:user_feature:is_member:user_alice       → "true"
```

**结果**：
```python
user_features = {
    "gender": "female",
    "age": "28",
    "total_spend": "12500",
    "register_days": "365",
    "is_new_user": "false",
    "is_member": "true",
    # purchase_frequency 缺失，不在结果中
}
```

> 写入用户特征通过管理接口 `POST /api/v1/admin/user-features`，底层调用 `redis_store.set_user_features()`，pipeline 批量写入。

#### 7b. Item 特征（TSV 文件，启动时加载到内存）

`feature_store.py:73-75`

文件 `data/item_features.tsv`：
```tsv
COUPON_NEW_001	{"stock": 10000, "popularity": 0.7, "avg_conversion": 0.12}
COUPON_ACT_001	{"stock": 50000, "popularity": 0.85, "avg_conversion": 0.18}
COUPON_MEM_001	{"stock": 5000, "popularity": 0.6, "avg_conversion": 0.25}
COUPON_SHIP_001	{"stock": 100000, "popularity": 0.9, "avg_conversion": 0.30}
```

#### 7c. 合并特征

对每个 item，合并 TSV 文件特征和请求字段：
```python
# 以 COUPON_ACT_001 为例
item_features_from_tsv = {"stock": 50000, "popularity": 0.85, "avg_conversion": 0.18}
merged = {
    # 来自 TSV
    "stock": 50000,
    "popularity": 0.85,
    "avg_conversion": 0.18,
    # 来自请求
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}
```

**最终送入打分服务的数据**：
```python
scoring_items = [
    {"item_id": "COUPON_ACT_001",  "features": {"stock": 50000, "popularity": 0.85, "avg_conversion": 0.18, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}},
    {"item_id": "COUPON_SHIP_001", "features": {"stock": 100000, "popularity": 0.9, "avg_conversion": 0.30, "coupon_type": "free_shipping", "value": 0, "min_spend": 0, "expire_days": 30}},
    {"item_id": "COUPON_MEM_001",  "features": {"stock": 5000, "popularity": 0.6, "avg_conversion": 0.25, "coupon_type": "fixed", "value": 5000, "min_spend": 20000, "expire_days": 1}},
]
```

---

### 第 8 步：调用打分服务

`coupon_service.py:206-214` → `scoring_client.py:82`

#### 路由分发

```python
# coupon_service.py:206-214
scores = self._call_scoring(
    user_id=user_id,
    scene_id=scene.scene_id,
    user_features=user_features,
    context=context,
    items=scoring_items,
    external=external,    # 0 → 内部 gRPC
    req_id=request_id,
)
```

```python
# scoring_client.py:113-130
if external == 1:
    return self._score_external_http(...)   # 外部 HTTP → localhost:50053
return self._score_internal_grpc(...)       # 内部 gRPC → localhost:50052
```

本例 `external=0`，走内部 gRPC。

#### 内部 gRPC 路径（external=0）

**gRPC 请求构造**（`scoring_client.py:132-184`）：

所有特征值都转为 string 发送：
```protobuf
ScoreRequest {
  request_id: "uuid-xxx"
  user_id: "user_alice"
  scene_id: 1001
  user_features: {
    "gender": "female",
    "age": "28",
    "total_spend": "12500",
    "register_days": "365",
    "is_new_user": "false",
    "is_member": "true"
  }
  context_features: {
    "timestamp": "2026-04-02T14:30:00Z",
    "channel": "app"
  }
  items: [
    ItemFeatures { item_id: "COUPON_ACT_001",  features: {"stock": "50000", "popularity": "0.85", ...} },
    ItemFeatures { item_id: "COUPON_SHIP_001", features: {"stock": "100000", "popularity": "0.9", ...} },
    ItemFeatures { item_id: "COUPON_MEM_001",  features: {"stock": "5000", "popularity": "0.6", ...} },
  ]
}
```

**Mock 打分服务处理**（`scoring_server/mock_server.py`）：

对每个 item 单独计算分数：
```
base_score = 0.5

用户特征加分:
  is_new_user="false" → 不加分
  is_member="true"    → +0.10
  total_spend=12500 > 10000 → +0.10

Item 特征加分:
  popularity * 0.1

随机噪声: uniform(-0.05, +0.05)

最终: clamp(sum, 0, 1)
```

**各 item 打分结果**（假设噪声分别为 +0.02, -0.01, +0.03）：
```
COUPON_ACT_001:  0.5 + 0.10 + 0.10 + 0.85*0.1 + 0.02 = 0.805
COUPON_SHIP_001: 0.5 + 0.10 + 0.10 + 0.9*0.1  - 0.01 = 0.780
COUPON_MEM_001:  0.5 + 0.10 + 0.10 + 0.6*0.1  + 0.03 = 0.790
```

**gRPC 响应**：
```python
scores = [
    ItemScore(item_id="COUPON_ACT_001",  score=0.805),
    ItemScore(item_id="COUPON_SHIP_001", score=0.780),
    ItemScore(item_id="COUPON_MEM_001",  score=0.790),
]
```

#### 外部 HTTP 路径（external=1）

如果 `external=1`，走另一条路径（`scoring_client.py:186-239`）：

```python
# 配置（settings.yaml）
external_scoring_service:
  host: "localhost"
  port: 50053
  timeout: 2.0
  path: "/score"
  user_id_salt: "coupon_external_uid_salt"
```

1. **user_id 加密**：`sha256("coupon_external_uid_salt:user_alice")` → 64 位 hex
2. **HTTP POST** 到 `http://localhost:50053/score`
3. 请求体与 gRPC 类似，但用 JSON 格式
4. 响应格式：`{"code": 0, "scores": [{"item_id": "...", "score": 0.8}, ...]}`

---

### 第 9 步：分数校准（实验控制）

`coupon_service.py:238-260`

因为 `cal_exp.params["enable_calibration"] = True`，执行校准。

**配置**（`config/calibration.json`）：
```json
{
  "1001": {"k": 1.2, "b": 0.1},
  "1002": {"k": 0.9, "b": 0.05},
  "1003": {"k": 1.0, "b": 0.0},
  "2001": {"k": 1.1, "b": 0.08},
  "2002": {"k": 0.95, "b": 0.03},
  "2003": {"k": 1.0, "b": 0.0},
  "default": {"k": 1.0, "b": 0.0}
}
```

**校准公式**（`calibrator.py:48`）：
```
calibrated = clamp(k * score + b, 0, 1)
```

**本例 scene_id=1001, k=1.2, b=0.1**：
```
COUPON_ACT_001:  clamp(1.2 * 0.805 + 0.1) = clamp(1.066) = 1.0
COUPON_SHIP_001: clamp(1.2 * 0.780 + 0.1) = clamp(1.036) = 1.0
COUPON_MEM_001:  clamp(1.2 * 0.790 + 0.1) = clamp(1.048) = 1.0
```

> 1001 的 k=1.2, b=0.1 非常激进，高分段容易打满 1.0。
> 如果是 scene_id=1002（k=0.9, b=0.05）：
> - 0.805 → clamp(0.9*0.805 + 0.05) = 0.7745

**校准后判定 recommended**：
```python
recommended = calibrated_score >= score_threshold  # score_threshold 来自请求参数
# 本例: 1.0 >= 0.5 → True（全部推荐）
```

**构建 results**：
```python
results = [
    {"item_id": "COUPON_ACT_001",  "score": 0.805, "calibrated_score": 1.0, "recommended": True},
    {"item_id": "COUPON_SHIP_001", "score": 0.780, "calibrated_score": 1.0, "recommended": True},
    {"item_id": "COUPON_MEM_001",  "score": 0.790, "calibrated_score": 1.0, "recommended": True},
]
```

---

### 第 10 步：发放最优券

`coupon_service.py:262-263` → `_do_claim()`（`coupon_service.py:333-378`）

**发放逻辑**：

```python
# 1. 筛选 recommended=True 的券
recommended = [ACT_001, SHIP_001, MEM_001]  # 全部推荐

# 2. 按 calibrated_score 降序排序
# 全是 1.0，保持原顺序

# 3. 取前 max_claim_per_request=1 个
candidates = [ACT_001]  # 只尝试第一个

# 4. 库存扣减
remaining = redis.decr_stock("COUPON_ACT_001")
# Redis: DECR coupon:stock:COUPON_ACT_001 → 假设从 100 变为 99
# remaining=99 >= 0 → 扣减成功
```

> 如果 `max_claim_per_request=2`，会尝试前两个候选券。如果第一个无库存，还能尝试第二个。

**记录领取**（3 个 Redis 写操作）：
```
# 1. 记录用户已领取
SADD    coupon:user:user_alice:claimed  "COUPON_ACT_001"
EXPIRE  coupon:user:user_alice:claimed  604800

# 2. 保存券实例
SET     coupon:instance:uuid-abc123  '{"instance_id":"uuid-abc123","item_id":"COUPON_ACT_001","user_id":"user_alice","status":"claimed","coupon_type":"discount","value":80,"min_spend":5000,"expire_time":1743696600,"claim_time":1743091800}'
EXPIRE  coupon:instance:uuid-abc123  604800

# 3. 关联到用户
SADD    coupon:user:user_alice:instances  "uuid-abc123"
EXPIRE  coupon:user:user_alice:instances  604800
```

**券实例数据**：
```python
coupon_data = {
    "instance_id": "uuid-abc123",
    "item_id": "COUPON_ACT_001",
    "user_id": "user_alice",
    "status": "claimed",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_time": 1743696600,   # now + 7*86400
    "claim_time": 1743091800,    # now
}
```

---

### 第 11 步：返回响应

`coupon_service.py:265-272`

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
    {"item_id": "COUPON_ACT_001",  "score": 0.805, "calibrated_score": 1.0, "recommended": true},
    {"item_id": "COUPON_SHIP_001", "score": 0.780, "calibrated_score": 1.0, "recommended": true},
    {"item_id": "COUPON_MEM_001",  "score": 0.790, "calibrated_score": 1.0, "recommended": true}
  ],
  "coupon": {
    "instance_id": "uuid-abc123",
    "item_id": "COUPON_ACT_001",
    "user_id": "user_alice",
    "status": "claimed",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_time": 1743696600,
    "claim_time": 1743091800
  }
}
```

---

## 异常路径示例

### 路径 A：命中兜底策略（policy_id 触发）

**请求**：`policy_id = "policy_fallback_001"`

**数据流**：
```
参数校验 ✓ → 限流 ✓ → AB分流 → 场景路由
                                   ↓
                    policy_id 在 fallback_policy_ids 中
                                   ↓
                    SceneResult(scene_id=3001, is_fallback=True, fallback_score=0.5)
                                   ↓
                    跳过粗排/特征/打分/校准
                                   ↓
                    _resolve_fallback_score(3001, 0.5)
                        ↓ 先查 Redis: GET coupon:fallback:score:3001
                        ↓ 未命中，再查 GET coupon:fallback:score:default
                        ↓ 未命中，使用配置值 0.5
                                   ↓
                    所有 item score=0.5, 0.5 >= threshold → 发放第一个
```

**响应**：
```json
{
  "code": 0,
  "message": "兜底策略",
  "scene_id": 3001,
  "coupon": {...}
}
```

> 如果运维通过 Redis 设置了场景级兜底分：
> `SET coupon:fallback:score:3001 "0.9"` → 兜底分变为 0.9

### 路径 B：打分服务超时

**配置**：
```yaml
fallback:
  on_scoring_timeout:
    action: "allow"
    default_score: 0.5
```

**数据流**：
```
参数校验 ✓ → 限流 ✓ → AB分流 → 场景路由(1001) → 粗排 → 特征抽取
                                                              ↓
                                              gRPC 调用超时（>2秒）
                                                              ↓
                                              _call_scoring 返回 _ScoringFailure.TIMEOUT
                                                              ↓
                                              检查 fallback.on_scoring_timeout:
                                                action="allow" → 走兜底
                                                default_score=0.5
                                                              ↓
                                              _resolve_fallback_score(1001, 0.5)
                                                先查 Redis → 未命中 → 用 0.5
                                                              ↓
                                              所有 item score=0.5, 0.5 >= 0.5 → 发放
```

**响应**：`code=0, coupon={...}`

### 路径 C：打分服务不可用

**配置**：
```yaml
fallback:
  on_scoring_unavailable:
    action: "allow"
    default_score: 0.3
```

**数据流**：
```
... → gRPC 连接失败 / 返回 code≠0
    → _call_scoring 返回 _ScoringFailure.UNAVAILABLE
    → 检查 fallback.on_scoring_unavailable:
        action="allow" → 走兜底
        default_score=0.3
    → 所有 item score=0.3, 0.3 < threshold(0.5) → 不发放
```

**响应**：`code=0, coupon=null`

> **超时 vs 不可用的差异**：超时用 default_score=0.5（发放），不可用用 0.3（不发放）。
> 如果将 action 改为 `"deny"`，则直接返回 `code=1012 打分服务异常`。

### 路径 D：请求级阈值拦截

**请求**：`score_threshold=0.95`

```
... → 打分结果 score=0.8
    → recommended = 0.8 >= 0.95? → False
    → 无推荐券 → 不发放
```

**响应**：`code=0, results=[{..., "recommended": false}], coupon=null`

### 路径 E：max_claim_per_request 与库存不足

**请求**：2 个候选券，A(score=0.9, 库存=0)，B(score=0.8, 库存=100)

```
max_claim_per_request=1:
  → 只尝试 A → 库存不足 → 跳过 → 无更多候选 → coupon=null

max_claim_per_request=2:
  → 尝试 A → 库存不足 → 跳过
  → 尝试 B → 库存扣减成功 → 发放 B → coupon={item_id: "B"}
```

---

## 配置速查

### settings.yaml — 主配置

```yaml
rate_limit:                          # 限流
  enabled: true
  max_qps: 1000                      # 全局 QPS 上限
  per_user_qps: 10                   # 单用户 QPS 上限
  window_seconds: 1                  # 滑动窗口（秒）

fallback:                            # 兜底策略
  enabled: true
  on_scoring_timeout:                # 打分超时
    action: "allow"                  #   allow=走兜底, deny=返回错误
    default_score: 0.5               #   兜底分数
  on_scoring_unavailable:            # 打分不可用
    action: "allow"
    default_score: 0.3

scoring_service:                     # 内部打分服务（gRPC）
  host: "localhost"
  port: 50052
  timeout: 2.0                       # 超时时间（秒）
  enabled: true

external_scoring_service:            # 外部打分服务（HTTP）
  host: "localhost"
  port: 50053
  timeout: 2.0
  enabled: true
  path: "/score"                     # HTTP 端点路径
  user_id_salt: "coupon_external_uid_salt"  # user_id 加密盐

redis:
  url: "redis://localhost:6379/0"
  key_prefix: "coupon:"
  stock_ttl: 86400                   # 库存 key TTL（1 天）
  user_claim_ttl: 604800             # 领取记录 TTL（7 天）

user_feature_keys:                   # 从 Redis 读取的用户特征字段列表
  - "gender"
  - "age"
  - "total_spend"
  - "purchase_frequency"
  - "register_days"
  - "is_new_user"
  - "is_member"

item_feature_file: "data/item_features.tsv"  # item 特征文件路径
```

### scenes.json — 场景路由

| scene_name | device | scene_id | 说明 |
|------------|--------|----------|------|
| game | mobile | 1001 | 游戏移动端 |
| game | pc | 1002 | 游戏PC端 |
| game | pad | 1003 | 游戏平板 |
| ad | mobile | 2001 | 广告移动端 |
| ad | pc | 2002 | 广告PC端 |
| ad | pad | 2003 | 广告平板 |
| (兜底) | - | 3001 | 未匹配/兜底策略 |

兜底触发：`policy_id` 在 `["policy_fallback_001", "policy_fallback_002"]` 中，或 `(scene_name, device)` 组合不存在。

### experiments.json — AB 实验

| 实验名 | 策略 | hash_range | 效果 |
|--------|------|-----------|------|
| coarse_rank_exp | cr_on | [0, 50) | 开启粗排，按 top_value 截断前 5 |
| coarse_rank_exp | cr_off | [50, 100) | 关闭粗排 |
| calibration_exp | cal_on | [0, 50) | 开启分数校准 |
| calibration_exp | cal_off | [50, 100) | 关闭分数校准 |

### calibration.json — 校准系数

| scene_id | k | b | 效果 |
|----------|---|---|------|
| 1001 | 1.2 | 0.1 | game+mobile，激进提升 |
| 1002 | 0.9 | 0.05 | game+pc，保守降低 |
| 1003 | 1.0 | 0.0 | game+pad，不调整 |
| 2001 | 1.1 | 0.08 | ad+mobile，轻微提升 |
| 2002 | 0.95 | 0.03 | ad+pc，轻微降低 |
| 2003 | 1.0 | 0.0 | ad+pad，不调整 |
| default | 1.0 | 0.0 | 兜底，不调整 |

---

## Redis Key 全览

| Key 模式 | 类型 | 用途 | TTL |
|----------|------|------|-----|
| `coupon:stock:{coupon_id}` | STRING(int) | 库存计数 | 86400s |
| `coupon:user:{uid}:claimed` | SET | 已领券 ID 集合 | 604800s |
| `coupon:user:{uid}:scene_count:{scene}` | STRING(int) | 场景领取计数 | 604800s |
| `coupon:user_profile:{uid}` | STRING(JSON) | 用户画像（v1 遗留） | 86400s |
| `coupon:user_feature:{feature_name}:{uid}` | STRING | 单个用户特征 | 86400s |
| `coupon:instance:{uuid}` | STRING(JSON) | 券实例详情 | 604800s |
| `coupon:user:{uid}:instances` | SET | 用户持有券实例 ID | 604800s |
| `coupon:rate:{key_suffix}` | ZSET | 滑动窗口限流 | window+1s |
| `coupon:fallback:score:{scene_id}` | STRING(float) | 场景级兜底分 | 86400s |
| `coupon:fallback:score:default` | STRING(float) | 全局默认兜底分 | 86400s |

---

## Pipeline 一览图

```
                          请求
                           │
                    ┌──────▼──────┐
                    │  参数校验    │  user_id / scene_name / device / items 必填
                    │             │  external / score_threshold / max_claim_per_request 必传且合法
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  限流检查    │  Redis ZSET 滑动窗口
                    │             │  全局 1000 QPS + 用户 10 QPS
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  AB实验分流  │  md5(uid) % 100 → hash_range 匹配
                    │             │  决定粗排和校准是否开启
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  场景路由    │  (scene_name, device) → scene_id
                    │             │  policy_id → 兜底
                    └──────┬──────┘
                           │
                  ┌────────┼────────┐
                  │ is_fallback?    │
                  │                 │
               Yes│              No│
                  ▼                 ▼
          ┌──────────┐     ┌──────────┐
          │ 兜底响应  │     │   粗排    │  实验控制, top_value / top_min_spend / random
          │ score=0.5 │     └────┬─────┘
          │ 跳过打分  │          │
          └──────────┘   ┌──────▼──────┐
                         │  特征抽取    │  用户: Redis 7 字段
                         │             │  Item: TSV 文件 (内存)
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │  打分服务    │  external=0 → gRPC :50052
                         │             │  external=1 → HTTP  :50053 (uid 加密)
                         └──────┬──────┘
                                │
                        ┌───────┼───────┐
                        │  成功?        │
                        │               │
                     成功│           失败│
                        ▼               ▼
                 ┌──────────┐   ┌──────────────┐
                 │  校准     │   │ 区分失败类型  │
                 │ y=kx+b   │   │ TIMEOUT → 兜底0.5
                 │ 实验控制  │   │ UNAVAIL → 兜底0.3
                 └────┬─────┘   │ action=deny → 报错
                      │         └──────────────┘
                      ▼
               ┌──────────┐
               │  发放     │  按 calibrated_score 降序
               │          │  score >= threshold → 扣库存 + 记录
               └────┬─────┘
                    │
                    ▼
                  响应
```
