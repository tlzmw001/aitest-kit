# 校准增强需求

## 技术方案

### Pipeline 总览

```
请求进入
  ↓
根据 scene_id 找到校准实验 → 未开启则跳过
  ↓
加载两个目录下序号最大的校准文件（分段目录 + 线性目录）
  ↓
用请求字段匹配分段文件的条件（从上到下，首条命中）→ 命中/未命中
用请求字段匹配线性文件的条件（从上到下，首条命中）→ 命中/未命中
  ↓
两个都命中 → 先分段校准，再线性校准（串联）
只命中分段 → 只做分段校准
只命中线性 → 只做线性校准
都没命中 → 不校准，原分返回
  ↓
最终结果 clamp 到 [0, 1]
```

### 校准文件加载

每个场景的校准实验指定两个目录路径，分别存放线性校准文件和分段校准文件。

**文件命名规则：**
- 文件名为纯数字 + `.json`，如 `1.json`, `2.json`, `100.json`
- 数字越大代表版本越新
- 加载时取目录中序号最大的文件

**实验参数：**
```json
{
  "enable_calibration": true,
  "calibration_dir": {
    "linear": "calibration/scene_game/linear",
    "piecewise": "calibration/scene_game/piecewise"
  }
}
```

**缺省：** 目录不存在或目录为空时，该类型视为未命中

### 条件匹配

校准文件中每条规则包含一组条件，用请求中的字段进行匹配。

**匹配规则：**
1. 多字段取交集（AND），所有字段都满足才算命中
2. 字段值做等值匹配（`==`）
3. 从上到下逐条匹配，命中第一条即停止
4. 不允许配置空条件
5. 所有条件都未命中则该类型不生效

### 线性校准

对分数进行线性变换：`y = k * x + b`

**校准文件格式（如 `linear/3.json`）：**
```json
[
  {"conditions": {"platform": "ios", "is_new_user": true}, "k": 1.2, "b": 0.05},
  {"conditions": {"platform": "ios"}, "k": 1.1, "b": 0.02},
  {"conditions": {"platform": "android"}, "k": 0.95, "b": 0.01}
]
```

**逻辑：**
1. 从上到下匹配条件，命中第一条取对应的 k, b
2. 计算 `calibrated = k * score + b`

### 分段校准

根据分数所在区间使用不同的 k, b 进行线性变换。

**校准文件格式（如 `piecewise/3.json`）：**
```json
[
  {
    "conditions": {"platform": "ios"},
    "segments": [
      {"range": [0.0, 0.3], "k": 0.8, "b": 0.01},
      {"range": [0.3, 0.7], "k": 1.0, "b": 0.0},
      {"range": [0.7, 1.0], "k": 1.2, "b": -0.05}
    ]
  },
  {
    "conditions": {"platform": "android"},
    "segments": [
      {"range": [0.0, 0.5], "k": 0.9, "b": 0.02},
      {"range": [0.5, 1.0], "k": 1.1, "b": -0.03}
    ]
  }
]
```

**区间边界规则：**
- 左闭右开：`[0.0, 0.3)`, `[0.3, 0.7)`
- 最后一段右闭：`[0.7, 1.0]`

**逻辑：**
1. 从上到下匹配条件，命中第一条取对应的 segments
2. 根据当前分数落在哪个区间，使用该区间的 k, b 计算 `calibrated = k * score + b`

### 串联计算

当分段和线性都命中时，按顺序串联执行：

```
原始分数
  ↓ 分段校准
中间分数 = k_piecewise * 原始分数 + b_piecewise
  ↓ 线性校准
最终分数 = k_linear * 中间分数 + b_linear
  ↓ clamp
最终分数 = max(0, min(1, 最终分数))
```

中间步骤不做 clamp，只在最终结果做一次。

### 完整实验参数示例

```json
{
  "name": "calibration_exp_game",
  "strategies": [
    {
      "id": "cal_v2",
      "hash_range": [0, 50],
      "params": {
        "enable_calibration": true,
        "calibration_dir": {
          "linear": "calibration/scene_game/linear",
          "piecewise": "calibration/scene_game/piecewise"
        }
      }
    },
    {
      "id": "cal_off",
      "hash_range": [50, 100],
      "params": {
        "enable_calibration": false
      }
    }
  ]
}
```

### 完整流转示例

请求字段：`{"platform": "ios", "is_new_user": true}`，原始分数 `0.5`

```
加载校准文件:
  linear 目录: [1.json, 2.json, 3.json] → 加载 3.json
  piecewise 目录: [1.json, 2.json] → 加载 2.json

分段校准条件匹配:
  规则1: {"platform": "ios"} → 命中 ✓
  segments: [0.0, 0.3) k=0.8 b=0.01 | [0.3, 0.7) k=1.0 b=0.0 | [0.7, 1.0] k=1.2 b=-0.05
  分数 0.5 落在 [0.3, 0.7) → k=1.0, b=0.0
  中间分数 = 1.0 * 0.5 + 0.0 = 0.5

线性校准条件匹配:
  规则1: {"platform": "ios", "is_new_user": true} → 命中 ✓
  k=1.2, b=0.05
  最终分数 = 1.2 * 0.5 + 0.05 = 0.65

clamp: 0.65 在 [0, 1] 范围内，无需截断

最终校准分数 = 0.65
```

目前支持配置的字段包括：
  字段     │   来源   │                                                                                                          
  ├─────────────┼──────────┤                                                                                                          
  │ item_id     │ item     │                                                                                                          
  ├─────────────┼──────────┤                                                                                                          
  │ coupon_type │ item     │                                                                                                          
  ├─────────────┼──────────┤                                                                                             
  │ device      │ 请求入参 │                                                                                                          
  ├─────────────┼──────────┤                                                                                                          
  │ external    │ 请求入参 │                                                                                                          
  ├─────────────┼──────────┤                                                                                                          
  │ gender      │ 用户特征 │                                                                                                          
  ├─────────────┼──────────┤                                                                                             
  │ age         │ 用户特征 │                                                                                                          
  ├─────────────┼──────────┤                                                                                                          
  │ total_spend │ 用户特征

配置其他字段，视为这个校准条件有问题，不进行命中