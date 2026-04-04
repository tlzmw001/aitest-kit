# ab_experiment_sdk

`ab_experiment_sdk` 是 `coupon_system` 使用的独立 AB 实验 SDK 包。

## 包职责

- AB 实验请求/响应协议
- 实验配置模型
- 内置基于配置的分流实现（`ConfigBasedABExperimentSDK`）
- 白名单优先策略命中（`whitelist > hash`）
- 请求级实验过滤能力（`ABExperimentRequest.experiment_names`）

## 接入约定

业务服务建议仅依赖以下接口：

- `ABExperimentSDK`（协议）
- `ABExperimentRequest`
- `ABExperimentResponse`

这样可以保持业务逻辑与 SDK 内部实现解耦，便于 SDK 后续独立发布与迭代。

白名单属于 SDK 提供的能力，不应混在业务实验配置中；应由业务侧通过 SDK 接口注入。

示例：

```python
from ab_experiment_sdk import ConfigBasedABExperimentSDK

sdk = ConfigBasedABExperimentSDK(experiment_config)
sdk.set_user_whitelist(
    "u_whitelist_001",
    {"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_on"},
)
```

## 后续拆分路径

1. 先在当前单仓库内持续演进 SDK 协议。
2. 再将该包发布为独立 wheel 包。
3. 最后按需要迁移到独立仓库，且尽量不改变业务侧协议。
