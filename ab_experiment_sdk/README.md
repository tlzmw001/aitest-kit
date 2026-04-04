# ab_experiment_sdk

`ab_experiment_sdk` is the standalone AB experiment package used by `coupon_system`.

## Package Scope

- AB request/response protocol
- Experiment config models
- Built-in config-based router (`ConfigBasedABExperimentSDK`)
- Whitelist-first strategy assignment (`whitelist > hash`)
- Request-level experiment filtering (`ABExperimentRequest.experiment_names`)

## Integration Contract

Business services should only depend on:

- `ABExperimentSDK` (protocol)
- `ABExperimentRequest`
- `ABExperimentResponse`

This keeps business logic decoupled from SDK internals and makes it easier to ship
the SDK independently in the future.

Whitelist is an SDK capability and should be injected by business code via SDK methods,
instead of being mixed into business experiment configuration.

Example:

```python
from ab_experiment_sdk import ConfigBasedABExperimentSDK

sdk = ConfigBasedABExperimentSDK(experiment_config)
sdk.set_user_whitelist(
    "u_whitelist_001",
    {"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_on"},
)
```

## Future Split Path

1. Keep this package in monorepo and iterate API contracts.
2. Release as an independent wheel package.
3. Move to dedicated repository when needed, without changing business-facing protocol.
