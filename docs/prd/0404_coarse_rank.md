# 粗排增强需求

## 技术方案

### Pipeline 总览

```
候选 items
  ↓
[阶段0] 保送 — isPrior=true 的 item 优先入选
  ↓ 剩余 items（未入选的 prior + 全部普通）
[阶段1] 过滤 — 按条件剔除不合格 item
  ↓
[阶段2] 多维排序 — 多字段归一化加权打分
  ↓
[阶段3] 打散+截断 — 多样性控制 + 兜底补满
  ↓
最终结果 = 保送入选 + 阶段3结果
```

### 阶段0：保送

从 items 中提取 `isPrior=true` 的优惠券，按策略选出最多 `prior_count` 个。

**实验参数：**
- `prior_count`：优先截断数，必须 <= `truncate_count`
- `prior_rule`：`"top_value"` 按 value 降序 | `"random"` 随机

**逻辑：**
1. 分两组：prior 组（`isPrior=true`）和普通组
2. prior 组按 `prior_rule` 排序
3. 取前 `prior_count` 个，不够就有多少取多少
4. 未入选的 prior item + 普通组 → 进入后续阶段

**缺省：** 没有 `prior_count` 参数时跳过此阶段

### 阶段1：过滤

按规则列表剔除不满足前置条件的 item。

**实验参数：**
```json
"filters": [
  {"field": "expire_days", "op": "gte", "value": 3},
  {"field": "value", "op": "gte", "value": 5},
  {"field": "coupon_type", "op": "in", "value": ["discount", "cash"]}
]
```

**支持的操作符：** `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`

**逻辑：** 所有条件取交集（AND），任一条件不满足则剔除

**缺省：** 没有 `filters` 参数时跳过此阶段

### 阶段2：多维排序

对每个 item 计算综合分，按综合分降序排列。

**实验参数：**
```json
"sort_keys": [
  {"field": "value", "weight": 0.6},
  {"field": "min_spend", "weight": -0.3},
  {"field": "expire_days", "weight": 0.1}
]
```

**逻辑：**
1. 对每个字段在当前候选集内做 min-max 归一化到 0~1：`normalized = (val - min) / (max - min)`
2. 综合分 = Σ(归一化值 × weight)
3. weight 正数 = 该字段越大越好，负数 = 越小越好
4. 按综合分降序排列
5. 某字段所有 item 值相同时（max == min），该字段归一化结果为 0，不影响排序

**缺省：** 没有 `sort_keys` 时回退到旧的 `truncate_rule`（`top_value` / `top_min_spend` / `random`），保持向后兼容

### 阶段3：打散 + 截断

目标数 = `truncate_count` - 保送入选数。按分数优先入选，同时控制每组不超限。

**实验参数：**
```json
"diversity": {
  "enabled": true,
  "group_field": "coupon_type",
  "max_per_group": 2
}
```

**逻辑：**
1. 遍历排序后的 items（分数从高到低）：
   - 该 item 所在组入选数 < `max_per_group` → 入选
   - 该 item 所在组入选数 >= `max_per_group` → 跳过，放入 backfill 池
   - 入选数达到目标数 → 停止
2. 兜底：如果入选数 < 目标数，从 backfill 池按分数顺序依次补入，直到凑满目标数
3. 最终结果 = 保送入选 + 本阶段结果

**缺省：** 没有 `diversity` 或 `enabled=false` 时直接按分数取前 N 个

### 完整实验参数示例

```json
{
  "name": "coarse_rank_exp_game",
  "strategies": [
    {
      "id": "cr_v2_full",
      "hash_range": [0, 30],
      "params": {
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
    },
    {
      "id": "cr_v1_baseline",
      "hash_range": [30, 60],
      "params": {
        "enable_coarse_rank": true,
        "truncate_count": 5,
        "truncate_rule": "top_value"
      }
    },
    {
      "id": "cr_off",
      "hash_range": [60, 100],
      "params": {
        "enable_coarse_rank": false
      }
    }
  ]
}
```

### 完整流转示例

输入 8 个 item，`truncate_count=5, prior_count=2, prior_rule=top_value, filter: expire_days>=3, diversity: max_per_group=2 by coupon_type`

```
输入:
  P1(prior, type=cash,     value=50, min_spend=30,  expire_days=7)
  P2(prior, type=cash,     value=40, min_spend=20,  expire_days=5)
  P3(prior, type=discount, value=30, min_spend=10,  expire_days=2)
  N1(type=cash,     value=90, min_spend=200, expire_days=10)
  N2(type=cash,     value=85, min_spend=50,  expire_days=8)
  N3(type=discount, value=80, min_spend=100, expire_days=4)
  N4(type=discount, value=70, min_spend=60,  expire_days=1)
  N5(type=cash,     value=60, min_spend=40,  expire_days=6)

阶段0 保送:
  prior 按 value 排序: [P1(50), P2(40), P3(30)]
  取 prior_count=2 → selected_prior = [P1, P2]
  剩余: [P3, N1, N2, N3, N4, N5]

阶段1 过滤 (expire_days >= 3):
  P3(expire_days=2) 剔除, N4(expire_days=1) 剔除
  剩余: [N1, N2, N3, N5]

阶段2 排序 (value×0.6 + min_spend×(-0.3)):
  归一化后加权打分 → N2 > N5 > N3 > N1
  （N1 面额最高但 min_spend=200 扣分严重）

阶段3 打散+截断 (目标=5-2=3, max_per_group=2 by coupon_type):
  N2(cash,     cash计数:1) → 入选
  N5(cash,     cash计数:2) → 入选
  N3(discount, discount计数:1) → 入选，够3个停止

最终: [P1, P2, N2, N5, N3]  共5个 ✓
```
