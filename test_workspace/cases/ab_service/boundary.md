# AB 实验服务 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/ab_service、L2/0405
> 生成日期：2026-04-26

---

## 一、配置容错

### TC-ABS-030：白名单文件损坏时服务正常启动（白名单为空）
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. 白名单持久化文件路径为 `ab_experiment_sdk/data/whitelist.json`
  2. 将该文件内容写为非法 JSON：`this is not json`
  3. 实验配置文件 `ab_experiment_sdk/data/experiments.json` 使用默认配置
- **输入**：
  ```
  GET /api/v1/ab/whitelist
  ```
- **测试步骤**：
  1. 将 whitelist.json 写为非法内容
  2. 启动 AB 实验服务
  3. GET /api/v1/ab/whitelist
  4. [manual] 检查服务启动日志是否包含 warning："白名单文件读取失败，忽略"
- **预期结果**：
  - 服务正常启动，不崩溃
  - HTTP status_code == 200
  - response body == {}（白名单为空，损坏文件被忽略）
  - [manual] 日志包含 warning 级别信息

### TC-ABS-031：白名单文件内容为 JSON 数组时视为空白名单
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. 白名单持久化文件路径为 `ab_experiment_sdk/data/whitelist.json`
  2. 将该文件内容写为合法 JSON 但非 dict：`["not", "a", "dict"]`
  3. 实验配置文件使用默认配置
- **输入**：
  ```
  GET /api/v1/ab/whitelist
  ```
- **测试步骤**：
  1. 将 whitelist.json 写为 JSON 数组
  2. 启动 AB 实验服务
  3. GET /api/v1/ab/whitelist
- **预期结果**：
  - 服务正常启动
  - HTTP status_code == 200
  - response body == {}（非 dict 类型被视为空白名单）

### TC-ABS-032：实验配置文件不存在时自动创建空配置
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. 设置环境变量 `AB_SERVICE_EXPERIMENTS_PATH` 指向一个不存在的路径，如 `/tmp/ab_test_empty/experiments.json`
  2. 确保 `/tmp/ab_test_empty/` 目录不存在
- **输入**：
  ```
  GET /api/v1/ab/experiments
  ```
- **测试步骤**：
  1. 设置 AB_SERVICE_EXPERIMENTS_PATH 环境变量
  2. 启动 AB 实验服务
  3. GET /api/v1/ab/experiments
  4. 检查 `/tmp/ab_test_empty/experiments.json` 文件是否被创建
- **预期结果**：
  - 服务正常启动
  - HTTP status_code == 200
  - response body == []（空实验列表）
  - `/tmp/ab_test_empty/experiments.json` 文件已创建，内容为 `{"experiments": []}`

### TC-ABS-033：实验配置中策略 hash_range 格式异常时回退为 [0, 100]
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. 设置 AB_SERVICE_EXPERIMENTS_PATH 指向自定义配置文件
  2. 配置文件内容：
     ```json
     {
       "experiments": [
         {
           "name": "bad_range_exp",
           "strategies": [
             {"id": "s1", "hash_range": "not_a_list", "params": {"v": 1}},
             {"id": "s2", "hash_range": [0], "params": {"v": 2}},
             {"id": "s3", "hash_range": [0, "abc"], "params": {"v": 3}}
           ]
         }
       ]
     }
     ```
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "user_02",
    "request_id": "req_abs_033",
    "experiment_names": ["bad_range_exp"]
  }
  ```
- **测试步骤**：
  1. 创建自定义配置文件
  2. 启动 AB 实验服务
  3. GET /api/v1/ab/experiments/bad_range_exp，确认实验已加载
  4. POST /api/v1/ab/evaluate，body 为上述输入 JSON
  5. 检查 response.assignments
- **预期结果**：
  - 服务正常启动，不因格式异常崩溃
  - GET 返回实验信息，3 个策略的 hash_range 均被修正为 [0, 100]
  - evaluate 时 hash=13 命中第一个策略 s1（first-match，三个策略 hash_range 都是 [0, 100)，s1 排在最前）
  - response.assignments["bad_range_exp"].strategy_id == "s1"

---

## 二、评估边界

### TC-ABS-034：evaluate 请求中包含不存在的实验名时静默跳过
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动，默认配置
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "user_02",
    "request_id": "req_abs_034",
    "experiment_names": ["coarse_rank_exp_game", "totally_fake_exp"]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. POST /api/v1/ab/evaluate，body 为上述输入 JSON
  3. 检查 response.assignments
  4. [manual] 检查服务日志是否包含 warning："ab_sdk unknown experiment: totally_fake_exp"
- **预期结果**：
  - HTTP status_code == 200（不报错）
  - response.assignments 包含 "coarse_rank_exp_game" 的命中结果
  - response.assignments 中不包含 "totally_fake_exp" key
  - [manual] 日志包含 warning

### TC-ABS-035：hash_range 重叠时命中第一个匹配的策略
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动
  2. 通过 API 创建实验，策略 hash_range 有重叠：
     ```
     POST /api/v1/ab/experiments
     ```
     ```json
     {
       "name": "overlap_exp",
       "strategies": [
         {"id": "first_match", "hash_range": [0, 50], "params": {"order": 1}},
         {"id": "second_match", "hash_range": [10, 60], "params": {"order": 2}}
       ]
     }
     ```
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "user_02",
    "request_id": "req_abs_035",
    "experiment_names": ["overlap_exp"]
  }
  ```
  注：user_id="user_02"，hash=13，同时落入 [0, 50) 和 [10, 60) 两个区间
- **测试步骤**：
  1. 启动 AB 实验服务
  2. 创建 overlap_exp 实验
  3. POST /api/v1/ab/evaluate，body 为上述输入 JSON
  4. 检查 response.assignments
- **预期结果**：
  - HTTP status_code == 200
  - response.assignments["overlap_exp"].strategy_id == "first_match"（first-match 策略，命中第一个匹配的）
  - response.assignments["overlap_exp"].hit_reason == "hash"

### TC-ABS-036：创建实验时 strategies 为空列表
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动
- **输入**：
  创建：
  ```
  POST /api/v1/ab/experiments
  ```
  ```json
  {
    "name": "empty_strategies_exp",
    "strategies": []
  }
  ```
  评估：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "user_id": "user_02",
    "request_id": "req_abs_036",
    "experiment_names": ["empty_strategies_exp"]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. POST /api/v1/ab/experiments 创建空策略实验
  3. GET /api/v1/ab/experiments/empty_strategies_exp，确认创建成功
  4. POST /api/v1/ab/evaluate，body 为上述评估输入 JSON
  5. 检查 response.assignments
- **预期结果**：
  - 步骤 2：status_code == 200，创建成功
  - 步骤 3：status_code == 200，strategies == []
  - 步骤 5：status_code == 200，response.assignments 中不包含 "empty_strategies_exp"（无策略可命中）

---

## 三、Pydantic 校验

### TC-ABS-037：evaluate 请求缺少必填字段 user_id 返回 422
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动
- **输入**：
  ```
  POST /api/v1/ab/evaluate
  ```
  ```json
  {
    "request_id": "req_abs_037"
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. POST /api/v1/ab/evaluate，body 不含 user_id
  3. 检查 HTTP status code
- **预期结果**：
  - HTTP status_code == 422
  - response.body.detail 为数组，包含 user_id 字段缺失的校验错误

### TC-ABS-038：创建实验请求缺少 name 字段返回 422
- **关联**：L1/ab_service
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  1. AB 实验服务启动
- **输入**：
  ```
  POST /api/v1/ab/experiments
  ```
  ```json
  {
    "strategies": [
      {"id": "s1", "hash_range": [0, 100], "params": {}}
    ]
  }
  ```
- **测试步骤**：
  1. 启动 AB 实验服务
  2. POST /api/v1/ab/experiments，body 不含 name
  3. 检查 HTTP status code
- **预期结果**：
  - HTTP status_code == 422
  - response.body.detail 为数组，包含 name 字段缺失的校验错误

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_service | hash_range 重叠行为（first-match）、白名单文件损坏容错、实验配置文件不存在自动创建、策略格式异常回退、evaluate 含不存在实验名静默跳过、空策略实验评估、Pydantic 422 校验 | （无） |
| L2/0405 | （无新增） | AB 服务启动顺序依赖 |
