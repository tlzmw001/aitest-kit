# API Map: calibration

path: test_workspace/targets/coupon_system/api_maps/api_map_calibration.md

## 端点

| Method | Path / RPC | 认证 | 用途 |
|--------|------------|------|------|
| POST | /api/v1/recommend | 无 | 通过推荐主链路触发校准 |
| gRPC | coupon.CouponService/Recommend | 无 | 通过 gRPC 推荐主链路触发校准 |
| POST | /api/v1/admin/stock | 无 | 初始化候选券库存 |
| POST | /api/v1/admin/user-features | 无 | 初始化用户特征 |
| PUT | /api/v1/ab/experiments/{name} | 无 | 临时覆盖校准实验策略 |
| PUT | /api/v1/ab/whitelist/{user_id} | 无 | 强制用户命中指定实验策略 |

## 认证

- calibration 用例当前只访问本地测试服务和 AB 实验服务，公开文档未要求鉴权。
- 运行前置是服务地址和下游服务可用性，不是 token。

## 请求体参考

### POST /api/v1/recommend

```json
{
  "user_id": "u_cal_default",
  "scene_name": "game",
  "device": "mobile",
  "policy_id": "",
  "external": 0,
  "reqId": "req_cal_default",
  "score_threshold": 0.0,
  "max_claim_per_request": 1,
  "context": {},
  "items": [
    {
      "item_id": "COUPON_CAL_001",
      "coupon_type": "discount",
      "value": 80,
      "min_spend": 5000,
      "expire_days": 7
    }
  ]
}
```

### PUT /api/v1/ab/experiments/calibration_exp_game

```json
{
  "name": "calibration_exp_game",
  "strategies": [
    {
      "id": "aitest_tc_cal_001",
      "hash_range": [0, 100],
      "params": {
        "enable_calibration": true,
        "calibration_dir": {
          "linear": "/tmp/aitest_calibration_x/TC-CAL-001/linear",
          "piecewise": "/tmp/aitest_calibration_x/TC-CAL-001/piecewise"
        }
      }
    }
  ]
}
```

## 环境变量

### 连接层

- COUPON_SYSTEM_BASE_URL — coupon_system HTTP 服务地址，如 `http://127.0.0.1:8000`
- COUPON_AB_BASE_URL — AB 实验服务地址，如 `http://127.0.0.1:8100`
- COUPON_GRPC_TARGET — coupon_system gRPC 服务地址，如 `127.0.0.1:50051`

### 认证层

- 无。

### 资源层

- 无固定外部资源 ID。fixture 为每条 case 创建独立临时校准目录，并用唯一 user_id/reqId 避免状态互相影响。

### 业务层

- 线性/分段规则由 suite profile 通过 `case_flows.kwargs` 显式传入。
- 用户特征由 suite profile 通过 `user_features` 显式传入；缺省为空。

## 信息缺口

- HTTP/gRPC 推荐链路依赖 Redis、AB 服务、内部打分服务；这些服务不可用时应归类为环境问题。
- AB 实验服务会持久化实验配置；fixture 运行后需要恢复原实验配置并清理白名单。

## Case variables/env 矩阵

| case_id | profile variables | required env | optional env | 缺失行为 |
|---------|-------------------|--------------|--------------|----------|
| TC-CAL-001~014 | 无 | COUPON_SYSTEM_BASE_URL, COUPON_AB_BASE_URL, COUPON_GRPC_TARGET | 无 | fail-fast，报告为 PRECONDITION_MISSING |

## 状态影响分析

| case_id | 动作类型 | 创建资源？ | 唯一值？ | cleanup？ | 幂等？ |
|---------|----------|------------|---------|----------|-------|
| TC-CAL-001~014 | 覆盖 AB 实验、写临时校准文件、初始化库存、推荐请求 | 是 | user_id, reqId, temp dir | restore experiment + clear whitelist + remove temp dir | 是 |

## 自动化可行性判定

| case_id | automation_status | reason_type | required_capability | cleanup_strategy | evidence_ref | resume_condition |
|---------|-------------------|-------------|---------------------|------------------|--------------|------------------|
| TC-CAL-001~014 | auto_executable | none | HTTP/gRPC API + AB 管理 API | fixture teardown restore | L1/calibration + docs/prd/0404_calibration.md | already executable |

