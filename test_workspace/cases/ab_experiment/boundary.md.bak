# AB 实验分流 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/ab_experiment、L2/0404、L2/0405
> 生成日期：2026-04-25

---

## 一、Hash 分流边界

### TC-AB-007：hash 值恰好等于 hash_range 下界时命中
- **关联**：L1/ab_experiment
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动，默认实验配置。`coarse_rank_exp_game` 策略 `cr_v1_baseline` 的 hash_range 为 [30, 60)
  2. 主服务启动，`AB_SERVICE_URL=http://localhost:8100`
  3. user_id="u_0048"，MD5 hash 值 = 30，恰好等于 [30, 60) 的下界
  4. Redis 中设置 u_0048 的用户特征
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "u_0048",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_007",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 服务和主服务
  2. POST /api/v1/recommend，body 为上述输入 JSON
  3. 检查 response.experiment_info["coarse_rank_exp_game"]
- **预期结果**：
  - response.experiment_info["coarse_rank_exp_game"] == "cr_v1_baseline"（hash=30 落入 [30, 60)，下界包含，命中）

### TC-AB-008：hash 值恰好等于 hash_range 上界时不命中当前策略
- **关联**：L1/ab_experiment
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动，默认实验配置。`coarse_rank_exp_game` 策略 `cr_v2_full` 的 hash_range 为 [0, 30)，`cr_v1_baseline` 为 [30, 60)
  2. 主服务启动，`AB_SERVICE_URL=http://localhost:8100`
  3. user_id="u_0048"，MD5 hash 值 = 30，恰好等于 [0, 30) 的上界
  4. Redis 中设置 u_0048 的用户特征
- **输入**：同 TC-AB-007
- **测试步骤**：
  1. 同 TC-AB-007
  2. 验证 hash=30 不命中 cr_v2_full（上界不包含），而是命中 cr_v1_baseline
- **预期结果**：
  - response.experiment_info["coarse_rank_exp_game"] == "cr_v1_baseline"（不是 "cr_v2_full"）
  - 半开区间 [low, high)：hash=30 不在 [0, 30) 内，在 [30, 60) 内

---

## 二、白名单降级

### TC-AB-009：白名单 strategy_id 无效时降级到 hash 分流
- **关联**：L1/ab_experiment
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动，默认实验配置
  2. 主服务启动，`AB_SERVICE_URL=http://localhost:8100`
  3. 通过 AB 服务 API 设置白名单，user_id="user_02" 在 coarse_rank_exp_game 中强制命中一个不存在的策略 ID：
     ```
     PUT /api/v1/ab/whitelist/user_02
     ```
     ```json
     {"strategy_map": {"coarse_rank_exp_game": "nonexistent_strategy"}}
     ```
  4. user_id="user_02"，MD5 hash 值 = 13，正常 hash 分流应命中 cr_v2_full（[0, 30)）
  5. Redis 中设置 user_02 的用户特征
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "user_02",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_009",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 服务和主服务
  2. 设置无效白名单
  3. POST /api/v1/recommend，body 为上述输入 JSON
  4. 检查 response.experiment_info
  5. [manual] 检查 SDK 日志是否有 warning 关于无效白名单 strategy_id
- **预期结果**：
  - response.code == 0
  - response.experiment_info["coarse_rank_exp_game"] == "cr_v2_full"（白名单 strategy_id 无效，降级到 hash 分流，hash=13 命中 cr_v2_full）
  - [manual] SDK 日志包含 warning 级别日志，提示白名单 strategy_id 无效

---

## 三、远程 SDK 超时

### TC-AB-010：远程 SDK 请求超时时主服务返回 HTTP 500
- **关联**：L2/0405
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. 启动一个 mock 服务监听端口 8100，对 /api/v1/ab/evaluate 请求延迟 3 秒后响应（超过 RemoteABExperimentSDK 默认 timeout=2.0s）
  2. 主服务启动，`AB_SERVICE_URL=http://localhost:8100`
  3. scene_experiments.json 使用默认配置
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "u_timeout",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_010",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 mock 慢响应服务和主服务
  2. POST /api/v1/recommend，body 为上述输入 JSON
  3. 检查 HTTP status code
- **预期结果**：
  - HTTP status_code == 500（RemoteABExperimentSDK 抛出 httpx.ReadTimeout，无 try/except 捕获，异常上抛到 FastAPI 层）

---

## 四、配置容错

### TC-AB-011：本地模式白名单通过环境变量注入
- **关联**：L2/0405
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. 不启动 AB 实验服务
  2. 环境变量 `AB_SERVICE_URL` 不设置（本地模式）
  3. 环境变量 `AB_SDK_WHITELIST_JSON` 设置为：
     ```
     AB_SDK_WHITELIST_JSON='{"user_02": {"coarse_rank_exp_game": "cr_off"}}'
     ```
  4. 实验配置文件使用默认配置
  5. scene_experiments.json 使用默认配置
  6. Redis 中设置 user_02 的用户特征
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "user_02",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_011",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 设置 AB_SDK_WHITELIST_JSON 环境变量
  2. 启动主服务（本地模式）
  3. POST /api/v1/recommend，body 为上述输入 JSON
  4. 检查 response.experiment_info
- **预期结果**：
  - response.code == 0
  - response.experiment_info["coarse_rank_exp_game"] == "cr_off"（白名单优先于 hash，强制命中 cr_off）
  - response.experiment_info["calibration_exp_game"] == "cal_on"（calibration 实验无白名单，走 hash 分流，hash=13 命中 cal_on）

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_experiment | hash 分流边界值（半开区间）、白名单 strategy_id 无效时降级行为 | （无） |
| L2/0405 | 远程 SDK 网络超时、本地模式白名单环境变量注入 | AB 服务启动顺序依赖 |

