# Old Case Migration Spec

## 目标

将 `test_workspace/cases/old-cases/` 中的旧版用例按模块分类，转写为当前“共享配置 + 精简用例”格式，写入对应模块的新用例文件。旧文件保留在 `old-cases/` 作为归档，不移动、不删除。

## 输入范围

- `test_workspace/cases/old-cases/coupon_service.md`
- `test_workspace/cases/old-cases/ab_service.md`
- `test_workspace/cases/old-cases/ab_remote_client.md`

## 输出范围

- `test_workspace/cases/validation_ratelimit/`
- `test_workspace/cases/scene_routing/`
- `test_workspace/cases/ab_experiment/`
- `test_workspace/cases/rough_ranking/`
- `test_workspace/cases/feature_scoring/`
- `test_workspace/cases/calibration/`
- `test_workspace/cases/issuance/`
- `test_workspace/cases/ab_service/`
- `test_workspace/cases/logging/`

## 分类规则

- `TC-VAL`、`TC-SCHEMA`、`TC-GRPC` 中参数/Schema/协议校验用例 → `validation_ratelimit`
- `TC-ROUTE` → `scene_routing`
- `TC-EXP` → `ab_experiment`
- `TC-CR` 和 gRPC `is_prior -> isPrior` 映射 → `rough_ranking`
- `TC-CLAIM`、`TC-QUERY` → `issuance`
- `TC-FAIL`、`TC-FEAT`、内部/外部打分路由能力 → `feature_scoring`
- `TC-LOG` → `logging`
- `TC-CAL` → `calibration`
- `TC-ABS` 和 `TC-RC` → `ab_service`

## 编号规则

- 使用 `TEST_SPEC.md` 的模块缩写表。
- 单前缀模块按 `TC-{PREFIX}-001..N` 连续。
- `validation_ratelimit` 存在多个合法前缀，按前缀分别连续：`VAL`、`SCHEMA`、`GRPC`、`RATE`。
- 迁移后检查每个文件内同一前缀编号从 `001` 开始，无空洞、无重复。

## 不做事项

- 不修改 `old-cases/` 归档文件。
- 不执行 pytest。
- 不修改生产代码。
