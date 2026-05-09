# 待测系统：智能优惠券推荐策略系统 v3

## 这份文档是给谁看的

这是一份给“小白”准备的项目总览。

如果你第一次接触这个仓库，建议这样读：

1. 先看这份 `overview v3`，知道系统里有哪些模块、它们各自负责什么。
2. 再看 `coupon_system_dataflow_v3.md`，跟着一条请求把主链路走一遍。
3. 最后再去看代码，就不会觉得文件很多、关系很乱。

这份文档基于当前代码实现整理，不再沿用早期版本里已经过时的描述。

---

## 一句话理解这个项目

这是一个“优惠券推荐 + 发放”系统。

它接收一批候选优惠券，结合：

- 当前请求信息
- 用户特征
- item 特征
- AB 实验
- 粗排策略
- 打分服务
- 校准规则

最后决定：

- 每张券的分数是多少
- 哪些券值得推荐
- 是否真的发券
- 发哪一张

---

## 现在的系统长什么样

当前项目主要由 3 块组成：

1. `coupon_system`
- 主业务系统
- 对外提供 HTTP 和 gRPC 接口
- 负责推荐、打分调用、校准、发券、查券

2. `ab_experiment_sdk`
- AB 实验能力
- 既可以本地 in-process 调用
- 也可以启动成独立的 FastAPI 服务，再通过 HTTP 远程调用

3. 打分服务
- 内部 gRPC 打分服务：`coupon_system/scoring_server/mock_server.py`
- 外部 HTTP 打分服务：`coupon_system/scoring_server/external_mock_server.py`
- 主服务会根据请求参数 `external` 决定调用哪一个

可以把它理解成：

```text
客户端请求
  -> coupon_system 主服务
     -> AB 实验
     -> 场景路由
     -> 粗排
     -> 特征抽取
     -> 打分服务
     -> 校准
     -> 发券
  -> 返回推荐结果
```

---

## 最重要的目录

### 1. 主业务代码

`coupon_system/`

这是项目核心。

最值得先看的文件：

- [main.py](/Users/zmw/AIAutoTest/coupon_system/main.py)
  启动入口，负责把所有组件组装起来。
- [http_app.py](/Users/zmw/AIAutoTest/coupon_system/http_app.py)
  HTTP 接口层。
- [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py)
  真正的主业务 pipeline。

如果你只想抓主线，优先读这 3 个文件。

### 2. 配置

`coupon_system/config/`

这里放的是“业务配置”：

- `settings.yaml`
  主配置，包含 Redis、限流、打分服务地址等。
- `scenes.json`
  场景路由配置。
- `scene_experiments.json`
  `scene_id -> 实验列表` 的映射。

注意：

- AB 实验的配置文件已经迁移到 `ab_experiment_sdk/data/experiments.json`
- 不再放在 `coupon_system/config/experiments.json`

### 3. AB 实验

`ab_experiment_sdk/`

这个目录里有两种用法：

- 本地模式：`ConfigBasedABExperimentSDK`
- 远程模式：`RemoteABExperimentSDK` + `service.py`

也就是说，AB 实验既可以作为一个 Python 包被直接调用，也可以作为一个独立服务运行。

### 4. 打分服务

`coupon_system/scoring_server/`

这里是 mock 打分服务，方便本地联调和测试。

### 5. 测试

`tests/`

如果你想知道“系统应该怎么工作”，测试是非常好的学习材料：

- [test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py)
  业务主链路测试
- [test_ab_service.py](/Users/zmw/AIAutoTest/tests/test_ab_service.py)
  AB 服务测试
- [test_ab_remote_client.py](/Users/zmw/AIAutoTest/tests/test_ab_remote_client.py)
  远程 AB 客户端测试

---

## 从启动入口看系统是怎么组装的

入口在 [main.py](/Users/zmw/AIAutoTest/coupon_system/main.py)。

启动时主要做 7 件事：

1. 编译 proto 文件
2. 读取配置
3. 初始化 Redis、AB SDK、场景路由、粗排器、特征仓库、打分客户端、校准器
4. 组装出一个 `CouponBizService`
5. 把这个 `biz_service` 注入 HTTP 应用
6. 启动 gRPC 服务
7. 启动 HTTP 服务

所以你可以把 `CouponBizService` 理解成“整个系统的大脑”，其他模块都是它调用的部件。

---

## 最核心的类：`CouponBizService`

文件： [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py)

这个类最重要的方法是：

- `recommend_and_claim()`
- `query_user_coupons()`

其中 `recommend_and_claim()` 是项目最重要的一条主链路。

它做的事情可以概括成：

```text
校验请求
-> 限流
-> 场景路由
-> AB 实验
-> 粗排
-> 特征抽取
-> 调打分服务
-> 校准
-> 发放最优券
-> 返回结果
```

如果你在读代码时只能记住一件事，那就是：

> 这个项目本质上就是围绕 `recommend_and_claim()` 展开的。

---

## 系统里的几个关键概念

### 1. 场景路由

路由规则在 [scenes.json](/Users/zmw/AIAutoTest/coupon_system/config/scenes.json)。

输入：

- `scene_name`
- `device`
- `policy_id`

输出：

- `scene_id`
- 是否兜底

兜底逻辑有两种情况：

- `policy_id` 命中兜底名单
- `(scene_name, device)` 没有配置

一旦进入兜底场景：

- 不跑 AB 实验
- 不打分
- 不校准
- 直接用兜底分构造结果

### 2. AB 实验

这里不是“所有请求都统一跑全部实验”，而是：

1. 先完成场景路由，拿到 `scene_id`
2. 再根据 [scene_experiments.json](/Users/zmw/AIAutoTest/coupon_system/config/scene_experiments.json) 确定这个场景要跑哪些实验
3. 再由 AB SDK 对这些实验做分流

这能让不同场景拥有不同实验集合，结构更清晰。

### 3. 粗排

文件： [coarse_ranker.py](/Users/zmw/AIAutoTest/coupon_system/services/coarse_ranker.py)

粗排不是精排模型，它做的是“先把候选券缩小到更合适的一批”。

可以把它理解成 4 个阶段：

1. 先决定最后最多保留多少张券
2. 再看有没有“优先保送”的券
3. 再看哪些券需要过滤掉
4. 剩下的券再排序、打散、截断

最重要的参数是：

- `truncate_count`
  最终最多保留多少张券
- `prior_count`
  在正式排序前，先保送多少张优先券
- `prior_rule`
  保送券之间如何排序，当前支持 `top_value` 和 `random`
- `filters`
  过滤条件列表，多个条件是 AND 关系
- `sort_keys`
  多维加权排序，优先级高于旧版 `truncate_rule`
- `diversity`
  打散配置，避免某一类券过多
- `truncate_rule`
  旧版简单排序规则，当前支持 `top_value`、`top_min_spend`、`random`

下面用一个小例子说明。

假设我们有 6 张候选券：

| item_id | coupon_type | value | min_spend | expire_days | isPrior |
|--------|-------------|-------|-----------|-------------|---------|
| A | discount | 80 | 5000 | 3 | false |
| B | discount | 100 | 6000 | 7 | true |
| C | free_shipping | 0 | 0 | 30 | false |
| D | fixed | 5000 | 20000 | 1 | true |
| E | discount | 60 | 3000 | 10 | false |
| F | fixed | 3000 | 15000 | 5 | false |

### 先看 `truncate_count`

如果只配置：

```json
{
  "truncate_count": 3,
  "truncate_rule": "top_value"
}
```

系统会按 `value` 从高到低排序，然后只保留前 3 张：

- D(5000)
- F(3000)
- B(100)

也就是说，`truncate_count` 决定的是“最后最多能进下一步的数量”，它是粗排里最核心的总开关。

### 再看 `prior_count + prior_rule`

如果配置：

```json
{
  "truncate_count": 4,
  "prior_count": 2,
  "prior_rule": "top_value",
  "truncate_rule": "top_value"
}
```

系统会先从 `isPrior=true` 的券里挑出 2 张保送券。

当前保送候选是：

- B(value=100)
- D(value=5000)

按 `prior_rule=top_value` 排序后，保送结果是：

- D
- B

然后把它们从原候选里拿走，剩下：

- A
- C
- E
- F

再按 `truncate_rule=top_value` 排序，补足还缺的 2 张：

- F
- A

所以最终结果是：

- D
- B
- F
- A

这里有两个容易记错的点：

- 保送券会先占掉名额
- 保送券的顺序由 `prior_rule` 决定，不是原始输入顺序

### 再看 `filters`

如果配置：

```json
{
  "truncate_count": 4,
  "filters": [
    {"field": "expire_days", "op": "gte", "value": 3},
    {"field": "coupon_type", "op": "neq", "value": "free_shipping"}
  ],
  "truncate_rule": "top_value"
}
```

含义是：

- `expire_days >= 3`
- `coupon_type != free_shipping`

过滤后会去掉：

- C，因为它是 `free_shipping`
- D，因为它的 `expire_days = 1`

剩下：

- A
- B
- E
- F

再按 `top_value` 排序：

- F
- B
- A
- E

### 再看 `sort_keys`

如果配置：

```json
{
  "truncate_count": 3,
  "sort_keys": [
    {"field": "value", "weight": 0.6},
    {"field": "min_spend", "weight": -0.3}
  ]
}
```

含义不是简单的“先按 value 再按 min_spend 排序”，而是：

- 先对每个字段做归一化
- 再用权重求一个综合分
- `weight` 为负数表示“越大越吃亏”

这个例子里：

- `value` 越大越好
- `min_spend` 越大越差

所以高面值、低门槛的券会更靠前。

这就是为什么 `sort_keys` 更像“粗粒度打分规则”，而不只是简单排序。

### 再看 `diversity`

如果配置：

```json
{
  "truncate_count": 4,
  "truncate_rule": "top_value",
  "diversity": {
    "enabled": true,
    "group_field": "coupon_type",
    "max_per_group": 1
  }
}
```

系统会先排序，再做打散。

假设排序结果是：

- D(fixed)
- F(fixed)
- B(discount)
- A(discount)
- E(discount)
- C(free_shipping)

因为 `max_per_group=1`，先选时每种 `coupon_type` 最多拿 1 张：

- D(fixed)
- B(discount)
- C(free_shipping)

这时还缺 1 张，系统会从之前被压下去的券里做回填：

- F

最终结果可能是：

- D
- B
- C
- F

也就是说，`diversity` 不是“绝对不能重复”，而是“先尽量分散，不够再回填”。

### 旧版 `truncate_rule` 什么时候生效

如果没有配置 `sort_keys`，系统才会走 `truncate_rule`：

- `top_value`
  按 `value` 降序
- `top_min_spend`
  按 `min_spend` 降序
- `random`
  随机打乱后截断

### 一个完整组合例子

如果配置：

```json
{
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

系统实际执行顺序是：

1. 先保送 2 张优先券
2. 对剩余券按 `expire_days >= 3` 过滤
3. 对过滤后的券做多维加权排序
4. 再按 `coupon_type` 做打散
5. 最终凑满 `truncate_count = 5`

你可以把粗排理解成：

> 在精确打分前，先把明显不合适或优先级不高的候选券处理一下。

### 4. 特征抽取

文件： [feature_store.py](/Users/zmw/AIAutoTest/coupon_system/services/feature_store.py)

特征来自两边：

- 用户特征：来自 Redis
- item 特征：来自 TSV 文件，启动时读入内存

然后和请求里 item 自带的字段合并，送给打分服务。

### 5. 打分服务

文件： [scoring_client.py](/Users/zmw/AIAutoTest/coupon_system/services/scoring_client.py)

打分有两条路：

- `external=0`
  调内部 gRPC 服务
- `external=1`
  调外部 HTTP 服务

如果是外部 HTTP 路由，系统还会跳过 AB 实验。

### 6. 校准

文件： [calibrator.py](/Users/zmw/AIAutoTest/coupon_system/services/calibrator.py)

当前校准已经不是早期那种“按 scene 固定一个 k/b”。

现在的实现是：

- AB 实验决定是否启用校准
- 校准参数里给出两个目录：
  - `linear`
  - `piecewise`
- 每个目录取“数字最大”的 JSON 文件
- 根据请求字段和 item 字段命中规则
- 若两个都命中：
  - 先做分段校准
  - 再做线性校准
- 最后统一 clamp 到 `[0, 1]`

这部分是当前系统里相对复杂、但也很有代表性的配置驱动逻辑。

### 7. 发券

发券逻辑仍在 [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py)。

规则非常直接：

1. 先筛出 `recommended=True` 的券
2. 按 `calibrated_score` 降序
3. 从高到低尝试扣库存
4. 扣成功就记录实例并返回

所以系统不是“给每张券都发一张”，而是“选最优券发”。

---

## HTTP 和 gRPC 有什么关系

当前主服务同时暴露两套协议：

- HTTP：给普通接口调用方使用
- gRPC：给需要更强类型约束或更高性能的调用方使用

但它们最后都会走到同一个 `CouponBizService`。

这点很重要，因为它说明：

> 协议层只是入口不同，真正的业务逻辑只有一份。

---

## AB 实验服务现在是什么状态

AB 实验已经不只是本地包了。

当前代码支持两种模式：

### 本地模式

在 [main.py](/Users/zmw/AIAutoTest/coupon_system/main.py) 中，如果没有配置 `AB_SERVICE_URL`：

- 直接使用 `ConfigBasedABExperimentSDK`

### 远程模式

如果配置了 `AB_SERVICE_URL`：

- 主服务使用 `RemoteABExperimentSDK`
- 通过 HTTP 去调用独立的 AB 服务

AB 服务本身在 [service.py](/Users/zmw/AIAutoTest/ab_experiment_sdk/service.py) 中，支持：

- 实验评估
- 实验 CRUD
- 白名单 CRUD

所以从演进角度看，AB 能力已经开始从“工具类”走向“独立服务”。

---

## 如果你要开始读代码，推荐顺序

推荐按这个顺序看：

1. [main.py](/Users/zmw/AIAutoTest/coupon_system/main.py)
2. [http_app.py](/Users/zmw/AIAutoTest/coupon_system/http_app.py)
3. [coupon_service.py](/Users/zmw/AIAutoTest/coupon_system/services/coupon_service.py)
4. [scene_router.py](/Users/zmw/AIAutoTest/coupon_system/services/scene_router.py)
5. [coarse_ranker.py](/Users/zmw/AIAutoTest/coupon_system/services/coarse_ranker.py)
6. [feature_store.py](/Users/zmw/AIAutoTest/coupon_system/services/feature_store.py)
7. [scoring_client.py](/Users/zmw/AIAutoTest/coupon_system/services/scoring_client.py)
8. [calibrator.py](/Users/zmw/AIAutoTest/coupon_system/services/calibrator.py)
9. [redis_store.py](/Users/zmw/AIAutoTest/coupon_system/services/redis_store.py)
10. [ab_experiment_sdk/service.py](/Users/zmw/AIAutoTest/ab_experiment_sdk/service.py)

如果你觉得文件太多，就只盯住一条线：

`HTTP 请求 -> CouponBizService.recommend_and_claim() -> 返回结果`

这样最容易建立“整体感”。

---

## 这一版和旧文档最不一样的地方

如果你读过旧版文档，需要特别注意这些已经变化的点：

- AB 实验配置默认在 `ab_experiment_sdk/data/experiments.json`
- 场景和实验已经解耦，使用 `scene_experiments.json` 做映射
- 兜底场景不再请求实验，也不校准
- 校准已经升级为“目录 + 条件命中 + 分段/线性串联”
- AB 实验支持独立服务化
- 打分支持内部 gRPC 和外部 HTTP 两条路

---

## 下一步建议

看完这份文档后，最适合继续读的是：

- [coupon_system_dataflow_v3.md](/Users/zmw/AIAutoTest/docs/coupon_system/coupon_system_dataflow_v3.md)

因为它会用一条真实请求，把上面这些概念串起来。你会更容易把“模块是什么”和“代码怎么跑”对应起来。
