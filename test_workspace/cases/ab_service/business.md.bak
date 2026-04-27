# AB 实验服务 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/ab_service、L2/0405
> 生成日期：2026-04-26

---

## 一、Hash 分流

### TC-ABS-018：hash 分流命中正确策略
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动（端口 8100），使用默认实验配置（`ab_experiment_sdk/data/experiments.json`），其中 `coarse_rank_exp_game` 包含三个策略：
     - `cr_v2_full`：hash_range [0, 30)
     - `cr_v1_baseline`：hash_range [30, 60)
     - `cr_off`：hash_range [60, 100)
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "user_02",
    "request_id": "req_abs_018",
    "experiment_names": ["coarse_rank_exp_game"]
  }
  ```
  注：user_id="user_02"，MD5 hash 值 = 13，落入 [0, 30) 区间
- **测试步骤**：
  1. 启动 AB 实验服务（默认配置）
  2. POST /api/v1/ab/evaluate，body 为上述输入 JSON
  3. 检查 response body 中 assignments
- **预期结果**：
  - HTTP status_code == 200
  - response.assignments["coarse_rank_exp_game"].strategy_id == "cr_v2_full"
  - response.assignments["coarse_rank_exp_game"].hit_reason == "hash"
  - response.assignments["coarse_rank_exp_game"].params 包含该策略的参数
  - response.trace_id 非空
  - response.user_id == "user_02"

### TC-ABS-019：hash 分流未命中任何策略时不返回该实验
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动
  2. 通过 API 创建自定义实验 `test_partial_exp`，仅覆盖部分流量：
     ```
     POST /api/v1/ab/experiments
     ```
     ```json
     {
       "name": "test_partial_exp",
       "strategies": [
         {"id": "partial_on", "hash_range": [0, 30], "params": {"enable": true}}
       ]
     }
     ```
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "bob",
    "request_id": "req_abs_019",
    "experiment_names": ["test_partial_exp"]
  }
  ```
  注：user_id="bob"，MD5 hash 值 = 32，不落入 [0, 30) 区间
- **测试步骤**：
  1. 启动 AB 实验服务
  2. 创建 test_partial_exp 实验
  3. POST /api/v1/ab/evaluate，body 为上述输入 JSON
  4. 检查 response.assignments
- **预期结果**：
  - HTTP status_code == 200
  - response.assignments 中不包含 "test_partial_exp" key（hash=32 未命中 [0, 30)，无 assignment）

### TC-ABS-020：experiment_names 为 None 时评估全部实验
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动，默认配置包含 4 个实验：coarse_rank_exp_game、calibration_exp_game、coarse_rank_exp_ad、calibration_exp_ad
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "user_02",
    "request_id": "req_abs_020"
  }
  ```
  注：不传 experiment_names 字段（等价于 None），user_id="user_02" hash=13
- **测试步骤**：
  1. 启动 AB 实验服务（默认配置）
  2. POST /api/v1/ab/evaluate，body 为上述输入 JSON（不含 experiment_names）
  3. 检查 response.assignments
- **预期结果**：
  - HTTP status_code == 200
  - response.assignments 包含所有 4 个实验的命中结果（hash=13 在各实验中均有命中策略）

### TC-ABS-021：experiment_names 为空列表时返回空 assignments
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动，默认配置
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "user_02",
    "request_id": "req_abs_021",
    "experiment_names": []
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. POST /api/v1/ab/evaluate，body 为上述输入 JSON
  3. 检查 response.assignments
- **预期结果**：
  - HTTP status_code == 200
  - response.assignments == {}（空列表不评估任何实验）

---

## 二、实验持久化与重启恢复

### TC-ABS-022：实验增删改持久化到 experiments.json，重启后恢复
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动，默认配置
- **输入**：
  创建实验：
  ```
  POST /api/v1/ab/experiments
  ```
  ```json
  {
    "name": "persist_test_exp",
    "strategies": [
      {"id": "persist_on", "hash_range": [0, 50], "params": {"flag": true}},
      {"id": "persist_off", "hash_range": [50, 100], "params": {"flag": false}}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. POST /api/v1/ab/experiments 创建 persist_test_exp
  3. 确认创建成功：GET /api/v1/ab/experiments/persist_test_exp，status_code == 200
  4. 重启 AB 实验服务（停止后重新启动，不传额外参数）
  5. GET /api/v1/ab/experiments/persist_test_exp
  6. POST /api/v1/ab/evaluate，user_id="user_02"，experiment_names=["persist_test_exp"]
- **预期结果**：
  - 步骤 5：status_code == 200，实验仍存在，strategies 与创建时一致
  - 步骤 6：status_code == 200，response.assignments["persist_test_exp"] 有命中结果（hash=13 命中 persist_on）

### TC-ABS-023：更新实验为整体替换策略列表
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  1. AB 实验服务启动
  2. 已创建实验 persist_test_exp（含 persist_on 和 persist_off 两个策略）
     或使用默认实验 coarse_rank_exp_game（含 3 个策略）
- **输入**：
  ```
  PUT /api/v1/ab/experiments/coarse_rank_exp_game
  ```
  ```json
  {
    "name": "coarse_rank_exp_game",
    "strategies": [
      {"id": "new_single_strategy", "hash_range": [0, 100], "params": {"version": "v3"}}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. GET /api/v1/ab/experiments/coarse_rank_exp_game，确认原有 3 个策略
  3. PUT /api/v1/ab/experiments/coarse_rank_exp_game，body 为上述输入 JSON（只含 1 个策略）
  4. GET /api/v1/ab/experiments/coarse_rank_exp_game，检查策略列表
- **预期结果**：
  - 步骤 3：status_code == 200
  - 步骤 4：strategies 长度 == 1，strategies[0].id == "new_single_strategy"（原有 3 个策略被完全替换，不是追加）

---

## 三、错误场景

### TC-ABS-024：GET 不存在的实验返回 404
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务启动，默认配置
  2. 实验名 "nonexistent_exp" 不存在
- **输入**：
  ```
  GET /api/v1/ab/experiments/nonexistent_exp
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. GET /api/v1/ab/experiments/nonexistent_exp
  3. 检查 HTTP status code 和 response body
- **预期结果**：
  - HTTP status_code == 404
  - response.body.detail == "experiment not found"

### TC-ABS-025：PUT 不存在的实验返回 404
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务启动
  2. 实验名 "nonexistent_exp" 不存在
- **输入**：
  ```
  PUT /api/v1/ab/experiments/nonexistent_exp
  ```
  ```json
  {
    "name": "nonexistent_exp",
    "strategies": [
      {"id": "s1", "hash_range": [0, 100], "params": {}}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. PUT /api/v1/ab/experiments/nonexistent_exp，body 为上述 JSON
  3. 检查 HTTP status code 和 response body
- **预期结果**：
  - HTTP status_code == 404
  - response.body.detail == "experiment not found"

### TC-ABS-026：DELETE 不存在的实验返回 404
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务启动
  2. 实验名 "nonexistent_exp" 不存在
- **输入**：
  ```
  DELETE /api/v1/ab/experiments/nonexistent_exp
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. DELETE /api/v1/ab/experiments/nonexistent_exp
  3. 检查 HTTP status code 和 response body
- **预期结果**：
  - HTTP status_code == 404
  - response.body.detail == "experiment not found"

### TC-ABS-027：PUT 更新实验时 path 名与 body 名不一致返回 400
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务启动，默认配置
  2. 实验 coarse_rank_exp_game 已存在
- **输入**：
  ```
  PUT /api/v1/ab/experiments/coarse_rank_exp_game
  ```
  ```json
  {
    "name": "different_name",
    "strategies": [
      {"id": "s1", "hash_range": [0, 100], "params": {}}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. PUT /api/v1/ab/experiments/coarse_rank_exp_game，body 中 name="different_name"（与 path 不一致）
  3. 检查 HTTP status code 和 response body
- **预期结果**：
  - HTTP status_code == 400
  - response.body.detail == "path name and payload name mismatch"

### TC-ABS-028：GET 不存在的用户白名单返回 404
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务启动
  2. 用户 "no_such_user" 无白名单记录
- **输入**：
  ```
  GET /api/v1/ab/whitelist/no_such_user
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. GET /api/v1/ab/whitelist/no_such_user
  3. 检查 HTTP status code 和 response body
- **预期结果**：
  - HTTP status_code == 404
  - response.body.detail == "user whitelist not found"

### TC-ABS-029：DELETE 不存在的用户白名单静默成功
- **关联**：L1/ab_service
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  1. AB 实验服务启动
  2. 用户 "no_such_user" 无白名单记录
- **输入**：
  ```
  DELETE /api/v1/ab/whitelist/no_such_user
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. DELETE /api/v1/ab/whitelist/no_such_user
  3. 检查 HTTP status code
- **预期结果**：
  - HTTP status_code == 200（dict.pop(key, None) 静默成功，不返回 404）
  - response.body.cleared == true

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_service | hash 分流正确性（命中/未命中）、experiment_names 三种行为（None/空列表/指定）、实验持久化+重启恢复、更新为整体替换策略列表、GET/PUT/DELETE 实验名不存在 404、PUT path-body 名不一致 400、GET 用户白名单不存在 404、DELETE 用户白名单静默成功 | hash_range 重叠行为 |
| L2/0405 | （本轮无新增，已有覆盖见 ab_experiment 模块用例） | AB 服务启动顺序依赖 |
