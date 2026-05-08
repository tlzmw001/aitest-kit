# 优惠券推荐策略系统 v3：从一条请求看懂完整数据流

## 这份文档怎么读

这份文档不追求把所有代码逐行解释，而是想帮助第一次接触这个项目的人回答 3 个问题：

1. 一次请求进入系统后，先经过谁、后经过谁？
2. 每一步为什么存在？
3. 哪些配置会影响最终结果？

你可以把它当成“主链路导游图”。

---

## 先看一个真实请求

假设有这样一条 HTTP 请求：

```json
POST /api/v1/recommend
{
  "user_id": "user_alice",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "req-demo-001",
  "score_threshold": 0.5,
  "max_claim_per_request": 1,
  "context": {
    "channel": "app",
    "timestamp": "2026-04-25T10:00:00Z"
  },
  "items": [
    {
      "item_id": "COUPON_ACT_001",
      "coupon_type": "discount",
      "value": 80,
      "min_spend": 5000,
      "expire_days": 3
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
  ]
}
```

这条请求的目标是：

- 给用户 `user_alice`
- 在 `game + mobile`
- 从 3 张候选券里
- 选出最值得发的一张

---

## 总流程先记住这张图

```text
HTTP/gRPC 请求进入
-> 参数校验
-> 限流
-> 场景路由
-> 兜底判断
-> AB 实验
-> 粗排
-> 特征抽取
-> 调打分服务
-> 校准
-> 按分数发券
-> 返回结果
```

主实现都在：

- [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py)

---

## 第 1 步：请求进入接口层

HTTP 入口在：

- [http_app.py](/Users/zmw/AIAutoTest/coupon_system/http_app.py)

`POST /api/v1/recommend` 收到请求后，会把参数转成 Python 对象，然后调用：

- `CouponBizService.recommend_and_claim()`

也就是说：

- `http_app.py` 负责“接请求、做接口封装”
- `coupon_service.py` 负责“真正做业务”

---

## 第 2 步：参数校验

进入 [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py) 后，最先做的是基础校验。

必须要有：

- `user_id`
- `scene_name`
- `device`
- `items`
- `external`
- `score_threshold`
- `max_claim_per_request`

这里特别容易忽略的 3 个请求级控制参数是：

- `external`
  决定打分走内部 gRPC 还是外部 HTTP
- `score_threshold`
  决定分数多少才算推荐
- `max_claim_per_request`
  决定最多尝试发几张候选券

如果这些字段不合法，会直接返回：

- `code = 1001`
- `message = 参数无效`

---

## 第 3 步：限流

如果 `settings.yaml` 里开启了限流，系统会做两层保护：

1. 全局限流
- 防止整个系统瞬间流量太大

2. 用户限流
- 防止某个用户高频刷接口

这一层由：

- [redis_store.py](/Users/zmw/AIAutoTest/coupon_system/services/redis_store.py)

来做，使用的是 Redis 的滑动窗口逻辑。

你可以理解成：

> 在真正做推荐之前，先确认这个请求“能不能被处理”。

---

## 第 4 步：场景路由

这一步非常关键，因为后面很多决策都依赖 `scene_id`。

代码在：

- [scene_router.py](/Users/zmw/AIAutoTest/coupon_system/services/scene_router.py)

配置在：

- [scenes.json](/Users/zmw/AIAutoTest/coupon_system/config/scenes.json)

当前示例中：

- `scene_name = game`
- `device = mobile`
- `policy_id = ""`

所以会命中：

- `scene_id = 1001`

如果 `policy_id` 在兜底名单里，或者 `(scene_name, device)` 找不到配置，就会进入兜底场景 `3001`。

---

## 第 5 步：兜底判断

如果场景路由结果是兜底场景，系统会直接走兜底逻辑：

- 不请求 AB 实验
- 不调用打分服务
- 不做校准
- 所有 item 直接给一个兜底分

兜底分来源优先级是：

1. Redis 里 scene 级兜底分
2. 路由配置里的默认兜底分

这是一个很重要的设计点：

> 兜底链路是“快速返回”，不是“正常链路失败后勉强走一遍实验和校准”。

---

## 第 6 步：AB 实验分流

如果不是兜底场景，系统才会继续跑 AB 实验。

这里和旧版本最大的不同是：

不是所有请求都跑所有实验，而是：

1. 先拿到 `scene_id`
2. 再根据 [scene_experiments.json](/Users/zmw/AIAutoTest/coupon_system/config/scene_experiments.json) 看这个场景应该跑哪些实验
3. 再由 AB SDK 对这些实验做分流

例如当前：

- `scene_id = 1001`

会读取到：

- `coarse_rank_exp_game`
- `calibration_exp_game`

AB 配置在：

- [experiments.json](/Users/zmw/AIAutoTest/ab_experiment_sdk/data/experiments.json)

AB 的实现有两种模式：

1. 本地模式
- 直接调用 `ConfigBasedABExperimentSDK`

2. 远程模式
- 调用 `RemoteABExperimentSDK`
- 再转发到 [ab_experiment_sdk/service.py](/Users/zmw/AIAutoTest/ab_experiment_sdk/service.py)

但无论哪种模式，返回的结果结构都一样：

- 哪个实验命中了哪个策略
- 每个策略附带哪些 `params`

这些参数后面会直接控制粗排和校准。

---

## 第 7 步：粗排

当前命中到的粗排实验如果开启了 `enable_coarse_rank=true`，就会执行粗排。

代码在：

- [coarse_ranker.py](/Users/zmw/AIAutoTest/coupon_system/services/coarse_ranker.py)

粗排不是模型，它更像“候选券预处理器”。

为了更容易理解，我们直接用一个“真实风格”的粗排配置来演算一次。

假设 AB 实验给出的粗排参数是：

```json
{
  "enable_coarse_rank": true,
  "truncate_count": 5,
  "prior_count": 2,
  "prior_rule": "top_value",
  "filters": [
    {"field": "expire_days", "op": "gte", "value": 3}
  ],
  "sort_keys": [
    {"field": "value", "weight": 0.6},
    {"field": "min_spend", "weight": -0.3}
  ],
  "diversity": {
    "enabled": true,
    "group_field": "coupon_type",
    "max_per_group": 2
  }
}
```

这里最重要的几个参数分别表示：

- `truncate_count = 5`
  最终最多保留 5 张券
- `prior_count = 2`
  先保送 2 张优先券
- `prior_rule = top_value`
  保送券之间按 `value` 从高到低排
- `filters`
  先筛掉不满足条件的券
- `sort_keys`
  用多维加权分数排序
- `diversity`
  再做打散，避免同类券太多

假设当前候选券有 7 张：

| 原始顺序 | item_id | coupon_type | value | min_spend | expire_days | isPrior |
|---------|---------|-------------|-------|-----------|-------------|---------|
| 1 | A | discount | 80 | 5000 | 3 | false |
| 2 | B | discount | 100 | 6000 | 7 | true |
| 3 | C | free_shipping | 0 | 0 | 30 | false |
| 4 | D | fixed | 5000 | 20000 | 1 | true |
| 5 | E | discount | 60 | 3000 | 10 | false |
| 6 | F | fixed | 3000 | 15000 | 5 | false |
| 7 | G | fixed | 2000 | 12000 | 8 | false |

### 阶段 0：先看 `truncate_count`

不管后面怎么排，系统最后最多只会留下：

- 5 张券

所以你可以先把 `truncate_count` 理解成“总名额”。

### 阶段 1：保送优先券

因为：

- `prior_count = 2`
- `prior_rule = top_value`

系统先只看 `isPrior = true` 的券：

- B(value=100)
- D(value=5000)

再按 `top_value` 排序：

- D
- B

这 2 张券会被直接保送，先占掉 2 个名额。

此时：

- 已保送：`[D, B]`
- 剩余候选：`[A, C, E, F, G]`
- 剩余名额：`5 - 2 = 3`

这里有一个很重要的细节：

- 保送结果的顺序不是原始输入顺序
- 而是 `prior_rule` 计算后的顺序

### 阶段 2：过滤

因为过滤条件是：

```json
[
  {"field": "expire_days", "op": "gte", "value": 3}
]
```

所以剩余候选里只保留：

- `expire_days >= 3` 的券

当前剩余候选是：

- A(expire_days=3)
- C(expire_days=30)
- E(expire_days=10)
- F(expire_days=5)
- G(expire_days=8)

它们都满足条件，所以过滤后仍然是：

- `[A, C, E, F, G]`

如果这一步里有某张券 `expire_days < 3`，它会在这里被提前淘汰，后面连排序都进不去。

### 阶段 3：排序

因为配置了 `sort_keys`，所以这一步不会走旧版 `truncate_rule`，而是走多维加权排序。

当前排序规则是：

- `value` 权重 `+0.6`
- `min_spend` 权重 `-0.3`

这表示：

- 面值越高越好
- 门槛越高越差

系统不会直接用原值相加，而是会先把每个字段做归一化，再乘权重求综合分。

如果只用直觉理解，大致会得到这样一类排序结果：

- F：面值高，虽然门槛高，但综合分仍然很强
- G：面值较高，门槛也偏高
- A：面值一般，门槛中等
- E：面值略低，但门槛更低
- C：面值最低

于是排序后可以近似理解为：

- `[F, G, A, E, C]`

这里不用死记每个分数，你只要记住：

> `sort_keys` 更像“粗粒度打分公式”，不是简单的先按 A 字段、再按 B 字段排序。

### 阶段 4：打散

因为配置了：

```json
"diversity": {
  "enabled": true,
  "group_field": "coupon_type",
  "max_per_group": 2
}
```

所以系统会在排序结果上做一层“同类券数量控制”。

当前排序结果：

- F(fixed)
- G(fixed)
- A(discount)
- E(discount)
- C(free_shipping)

规则是：

- 每种 `coupon_type` 最多先拿 2 张

这个例子里：

- `fixed` 最多先拿 2 张：F、G
- `discount` 最多先拿 2 张：A、E
- `free_shipping` 最多先拿 2 张：C

因为我们只剩 3 个名额，所以按顺序拿到 3 张后就够了：

- `[F, G, A]`

### 阶段 5：拼接最终结果

最后系统会把：

- 保送结果：`[D, B]`
- 主排序结果：`[F, G, A]`

拼起来，得到粗排最终输出：

- `[D, B, F, G, A]`

这就是后面真正送去打分服务的候选券列表。

### 再补一个“打散回填”的例子

如果把 `diversity.max_per_group` 改成：

```json
"max_per_group": 1
```

那么在排序结果 `[F, G, A, E, C]` 上先选时，会得到：

- F(fixed)
- A(discount)
- C(free_shipping)

这时刚好还是 3 张，所以不需要回填。

但如果我们还有更多名额，比如还需要第 4 张，系统会从之前因为“同类太多”而被压下去的券里继续补：

- G 或 E

这就是代码里“先打散，不够再回填”的逻辑。

### 如果没有配置 `sort_keys`

这时系统才会走旧版 `truncate_rule`：

- `top_value`
  按 `value` 降序
- `top_min_spend`
  按 `min_spend` 降序
- `random`
  随机打乱后截断

所以粗排的完整心智模型可以记成一句话：

> 先按 `truncate_count` 确定总名额，再按“保送 -> 过滤 -> 排序 -> 打散”的顺序，把候选券缩成更值得送去打分的一批。

---

## 第 8 步：特征抽取

粗排结束后，系统开始准备打分所需的特征。

代码在：

- [feature_store.py](/Users/zmw/AIAutoTest/coupon_system/services/feature_store.py)

特征来自 3 个地方：

1. 用户特征
- 从 Redis 读
- 读取哪些字段由 `settings.yaml` 的 `user_feature_keys` 决定

2. item 特征
- 从 [item_features.tsv](/Users/zmw/AIAutoTest/coupon_system/data/item_features.tsv) 读取
- 启动时加载到内存

3. 请求自带的 item 字段
- 例如：
  - `coupon_type`
  - `value`
  - `min_spend`
  - `expire_days`

最后会合成一份 `scoring_items`，发给打分服务。

---

## 第 9 步：调用打分服务

代码在：

- [scoring_client.py](/Users/zmw/AIAutoTest/coupon_system/services/scoring_client.py)

这里有两条路：

### 路线 A：内部 gRPC

当：

- `external = 0`

系统会调用内部 gRPC 打分服务。

### 路线 B：外部 HTTP

当：

- `external = 1`

系统会调用外部 HTTP 打分服务，并对 `user_id` 做 hash 脱敏。

当前请求示例里：

- `external = 0`

所以会走内部 gRPC。

如果打分服务异常，系统不会立刻崩，而是进入“打分失败兜底判断”：

1. 先看总开关 `fallback.enabled`
- 如果是 `false`，直接返回 `SCORING_ERROR`

2. 如果 `fallback.enabled = true`，再区分失败类型
- 超时：走 `fallback.on_scoring_timeout`
- 服务不可用：走 `fallback.on_scoring_unavailable`

3. 再看对应失败类型下的 `action`
- 如果 `action != "allow"`，返回 `SCORING_ERROR`
- 如果 `action == "allow"`，继续走兜底分

4. 兜底分来源
- 先查 Redis 里是否有这个 `scene_id` 的兜底分
- 没有的话，用当前失败类型配置里的 `default_score`

举个例子。

如果配置是：

```yaml
fallback:
  enabled: true
  on_scoring_timeout:
    action: "allow"
    default_score: 0.5
  on_scoring_unavailable:
    action: "allow"
    default_score: 0.3
```

那么：

- 打分超时时，默认会用 `0.5`
- 服务不可用时，默认会用 `0.3`

如果你把其中一个改成：

```yaml
on_scoring_timeout:
  action: "reject"
  default_score: 0.5
```

那么超时场景就不会再兜底，而是直接返回错误。

---

## 第 10 步：校准

拿到原始分数后，系统会看当前命中的校准实验有没有开启：

- `enable_calibration`

如果开启，就进入：

- [calibrator.py](/Users/zmw/AIAutoTest/coupon_system/services/calibrator.py)

当前校准逻辑是“配置驱动”的，不再是简单的固定公式。

它的流程是：

1. 从实验参数里拿到两个目录
- `linear`
- `piecewise`

2. 每个目录只取数字最大的 JSON 文件

3. 用这些字段去匹配规则：
- `item_id`
- `coupon_type`
- `device`
- `external`
- `gender`
- `age`
- `total_spend`

4. 命中情况有 4 种：
- 只命中分段
- 只命中线性
- 两个都命中
- 两个都没命中

5. 如果两个都命中：
- 先做分段校准
- 再做线性校准

6. 最后统一 clamp 到 `[0, 1]`

这一步的意义是：

> 打分服务给的是“模型原始分”，校准负责把它调整成更适合业务决策的分数。

---

## 第 11 步：生成结果列表

完成校准后，系统会把每个 item 组装成统一结果：

```json
{
  "item_id": "COUPON_ACT_001",
  "score": 0.72,
  "calibrated_score": 0.81,
  "recommended": true
}
```

其中：

- `score`
  原始打分
- `calibrated_score`
  校准后的分数
- `recommended`
  是否超过阈值

这一步还没有真正发券，只是先生成“推荐判断结果”。

---

## 第 12 步：按分数发券

接下来系统会做真正的发券动作。

逻辑在：

- [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py)
  的 `_do_claim()`

规则很清晰：

1. 先筛出 `recommended=True` 的券
2. 按 `calibrated_score` 从高到低排序
3. 最多尝试 `max_claim_per_request` 张券
4. 对每张券尝试扣库存
5. 第一张扣库存成功的券就发出去

发券成功后会在 Redis 里记录：

- 用户是否领过这张券
- 券实例数据
- 用户名下的券实例集合

所以系统不是“推荐结果 = 发券结果”。

更准确地说：

- 推荐结果是对所有候选券的判断
- 发券结果是从推荐券里挑一个真正能发出去的

---

## 第 13 步：返回响应

最终返回给调用方的结果主要有 4 块：

1. `scene_id`
- 这次请求最终归属哪个场景

2. `experiment_info`
- 这次命中的实验策略

3. `results`
- 每张候选券的分数、校准分、是否推荐

4. `coupon`
- 最终实际发出去的券
- 如果没发出去就是 `null`

---

## 用一句话串起来这条链路

一条请求进入系统后，主服务会先判断“这是谁、在哪个场景、能不能处理”，再决定“要跑哪些实验、哪些券先留下来、怎么打分、要不要校准”，最后从推荐券里选出一张最合适、且库存允许的券发出去。

---

## 读代码时最容易卡住的点

### 1. 为什么先路由再实验

因为实验已经是按场景拆开的，不同 `scene_id` 要跑的实验不同。

### 2. 为什么 `results` 里有很多券，但 `coupon` 只有一张

因为系统会先给所有候选券打标签和打分，再只选择一张最优券做真正发放。

### 3. 为什么还有“兜底”

因为线上系统不能完全依赖下游永远正常。

兜底保证在：

- 路由异常
- 打分服务异常
- 配置特殊命中

这些情况下，系统仍然能可控返回。

### 4. 为什么 AB 既像包又像服务

因为项目正在往“独立 AB 平台”方向演进，所以保留了：

- 本地调用模式
- 远程服务模式

两种用法。

---

## 学习建议

如果你准备开始真正读代码，建议用下面这条线路：

1. 先看 [http_app.py](/Users/zmw/AIAutoTest/coupon_system/http_app.py)
2. 再看 [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py)
3. 遇到不会的步骤，再分别跳去：
- [scene_router.py](/Users/zmw/AIAutoTest/coupon_system/services/scene_router.py)
- [coarse_ranker.py](/Users/zmw/AIAutoTest/coupon_system/services/coarse_ranker.py)
- [feature_store.py](/Users/zmw/AIAutoTest/coupon_system/services/feature_store.py)
- [scoring_client.py](/Users/zmw/AIAutoTest/coupon_system/services/scoring_client.py)
- [calibrator.py](/Users/zmw/AIAutoTest/coupon_system/services/calibrator.py)
- [redis_store.py](/Users/zmw/AIAutoTest/coupon_system/services/redis_store.py)

这样最容易建立“代码地图”。
