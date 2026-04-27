# AB 实验分流 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/ab_experiment、L2/0404、L2/0405
> 生成日期：2026-04-25

---

## 一、Hash 分流

### TC-AB-001：hash 分流命中正确策略
- **关联**：L1/ab_experiment
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动（端口 8100），使用默认实验配置（`ab_experiment_sdk/data/experiments.json`），其中 `coarse_rank_exp_game` 包含三个策略：
     - `cr_v2_full`：hash_range [0, 30)
     - `cr_v1_baseline`：hash_range [30, 60)
     - `cr_off`：hash_range [60, 100)
  2. `coupon_system/config/scene_experiments.json` 使用默认配置：scene_id 1001 映射到 `["coarse_rank_exp_game", "calibration_exp_game"]`
  3. 主服务启动，环境变量 `AB_SERVICE_URL=http://localhost:8100`（远程模式）
  4. user_id="user_02"，MD5 hash 值 = 13，落入 [0, 30) 区间，命中 `cr_v2_full`
  5. Redis 中设置 user_02 的用户特征（确保 pipeline 不在特征阶段报错）
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
    "reqId": "req_ab_001",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务（默认配置）和主服务（AB_SERVICE_URL=http://localhost:8100）
  2. POST /api/v1/recommend，body 为上述输入 JSON
  3. 检查 response.experiment_info
- **预期结果**：
  - response.code == 0
  - response.experiment_info["coarse_rank_exp_game"] == "cr_v2_full"
  - response.experiment_info["calibration_exp_game"] == "cal_on"（hash=13 落入 calibration_exp_game 的 [0, 50) 区间）

### TC-AB-002：hash 分流未命中任何策略
- **关联**：L1/ab_experiment
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动，通过 API 创建自定义实验 `test_partial_exp`，仅包含一个策略：
     - `partial_on`：hash_range [0, 30)（只覆盖 30% 流量）
     ```
     POST /api/v1/ab/experiments
     ```
     ```json
     {"name": "test_partial_exp", "strategies": [{"id": "partial_on", "hash_range": [0, 30], "params": {"enable_coarse_rank": true, "truncate_count": 3}}]}
     ```
  2. `coupon_system/config/scene_experiments.json`：
     ```json
     {"scene_experiments": {"1001": ["test_partial_exp"]}, "default_experiments": []}
     ```
  3. 主服务启动，环境变量 `AB_SERVICE_URL=http://localhost:8100`
  4. user_id="bob"，MD5 hash 值 = 32，不落入 [0, 30) 区间
  5. Redis 中设置 bob 的用户特征
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "bob",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_002",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 服务，通过 API 创建 test_partial_exp 实验
  2. 以自定义 scene_experiments.json 启动主服务
  3. POST /api/v1/recommend，body 为上述输入 JSON
  4. 检查 response.experiment_info
- **预期结果**：
  - response.code == 0
  - response.experiment_info 中不包含 `test_partial_exp` key（hash=32 未命中任何策略，该实验不产生 assignment）

---

## 二、场景-实验映射

### TC-AB-003：场景 ID 无实验映射时返回空实验信息
- **关联**：L2/0404
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动（默认配置）
  2. `coupon_system/config/scenes.json` 新增一条路由（非兜底场景）：
     ```json
     {"scene_name": "test", "device": "mobile", "scene_id": 9001, "description": "测试场景"}
     ```
  3. `coupon_system/config/scene_experiments.json` 不包含 scene_id 9001 的映射，default_experiments 为空：
     ```json
     {"scene_experiments": {"1001": ["coarse_rank_exp_game"], ...}, "default_experiments": []}
     ```
  4. 主服务启动，`AB_SERVICE_URL=http://localhost:8100`
  5. Redis 中设置用户特征
  
  注意：scene_name 不匹配任何路由时，场景路由模块会走兜底（is_fallback=True），pipeline 在兜底分支直接返回 experiment_info={}，不会到达 AB 实验步骤。因此必须使用一个合法的非兜底 scene_name+device 组合，且其 scene_id 不在 scene_experiments 映射中。
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "u_no_scene",
    "scene_name": "test",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_003",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 修改 scenes.json 添加 test 场景路由
  2. 启动 AB 服务和主服务
  3. POST /api/v1/recommend，body 为上述输入 JSON
  4. 检查 response.experiment_info
- **预期结果**：
  - response.experiment_info == {}（scene_id=9001 不在 scene_experiments 映射中，fallback 到 default_experiments=[]，SDK 收到空列表不评估任何实验）

---

## 三、SDK 模式切换

### TC-AB-004：本地模式 SDK 读取配置文件评估实验
- **关联**：L1/ab_experiment
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. 不启动 AB 实验服务（验证本地模式不依赖远程服务）
  2. 环境变量 `AB_SERVICE_URL` 不设置或设为空字符串（触发本地模式，使用 ConfigBasedABExperimentSDK）
  3. 实验配置文件 `ab_experiment_sdk/data/experiments.json` 使用默认配置（包含 coarse_rank_exp_game 等实验）
  4. `coupon_system/config/scene_experiments.json` 使用默认配置
  5. user_id="u_local_sdk"，MD5 hash 值 = 42，在 coarse_rank_exp_game 中命中 `cr_v1_baseline`（[30, 60)），在 calibration_exp_game 中命中 `cal_on`（[0, 50)）
  6. Redis 中设置 u_local_sdk 的用户特征
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "u_local_sdk",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_004",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 确认 AB 实验服务未启动
  2. 不设置 AB_SERVICE_URL 环境变量，启动主服务
  3. POST /api/v1/recommend，body 为上述输入 JSON
  4. 检查 response.experiment_info
- **预期结果**：
  - response.code == 0
  - response.experiment_info["coarse_rank_exp_game"] == "cr_v1_baseline"
  - response.experiment_info["calibration_exp_game"] == "cal_on"
  - 请求正常完成，不因 AB 服务未启动而报错

---

## 四、异常场景

### TC-AB-005：AB 服务不可用时主服务返回 HTTP 500
- **关联**：L1/ab_experiment
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务未启动（端口 8100 无监听）
  2. 主服务启动，环境变量 `AB_SERVICE_URL=http://localhost:8100`（远程模式）
  3. `coupon_system/config/scene_experiments.json` 使用默认配置（scene_id 1001 有映射）
  4. scene_name="game" 映射到有实验的 scene_id，确保 pipeline 会尝试调用 AB 服务
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "u_ab_down",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_005",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 确认 AB 实验服务未启动（端口 8100 无响应）
  2. 启动主服务（远程模式）
  3. POST /api/v1/recommend，body 为上述输入 JSON
  4. 检查 HTTP status code 和 response body
- **预期结果**：
  - HTTP status_code == 500（L1 明确标注：无降级，异常直接上抛到 FastAPI 层）
  - response body 包含错误信息（具体格式由 FastAPI 异常处理决定）

### TC-AB-006：映射中包含不存在的实验名时静默跳过
- **关联**：L1/ab_experiment
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务启动，仅配置实验 `coarse_rank_exp_game`
  2. `coupon_system/config/scene_experiments.json` 映射中包含一个不存在的实验名：
     ```json
     {"scene_experiments": {"1001": ["coarse_rank_exp_game", "nonexistent_exp"]}, "default_experiments": []}
     ```
  3. 主服务启动，远程模式
  4. 白名单设置 user_id="u_skip_test" 在 `coarse_rank_exp_game` 中命中 `cr_v2_full`（确保至少一个实验有结果）
     通过 AB 服务 API：
     ```
     PUT /api/v1/ab/whitelist/u_skip_test
     ```
     ```json
     {"strategy_map": {"coarse_rank_exp_game": "cr_v2_full"}}
     ```
  5. Redis 中设置用户特征
- **输入**：
  ```
  POST /api/v1/recommend
  ```
  ```json
  {
    "user_id": "u_skip_test",
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": "req_ab_006",
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [
      {"item_id": "c1", "coupon_type": "discount", "value": 500, "min_spend": 1000, "expire_days": 7}
    ]
  }
  ```
- **测试步骤**：
  1. 按前置条件启动服务并配置白名单
  2. POST /api/v1/recommend，body 为上述输入 JSON
  3. 检查 response.experiment_info
  4. [manual] 检查 AB 服务日志是否包含 warning：`ab_sdk unknown experiment: nonexistent_exp`
- **预期结果**：
  - response.code == 0（请求正常完成，不因不存在的实验名报错）
  - response.experiment_info["coarse_rank_exp_game"] == "cr_v2_full"
  - response.experiment_info 中不包含 `nonexistent_exp` 的 key
  - [manual] AB 服务或 SDK 日志中应有 warning 级别日志：`ab_sdk unknown experiment: nonexistent_exp`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_experiment | hash 分流正确性（MD5 % 100）、AB 服务不可用时无降级、实验名不存在的静默跳过、SDK 远程/本地模式切换 | （无） |
| L2/0404 | 场景-实验映射配置为空时行为 | SDK 替代直接配置读取的正确性、增强能力不配置时的向后兼容（属粗排模块） |
| L2/0405 | AB 服务不可用时主服务行为 | 远程 SDK 网络超时/重试（见 boundary.md TC-AB-010）、AB 服务启动顺序依赖 |

