# AB 实验服务测试用例

> 来源：tests/test_ab_service.py
> 待测模块：ab_experiment_sdk.service（独立 AB 实验管理服务）

---

## 一、健康检查

### TC-ABS-001：健康检查接口返回 200
- **关联**：L1/ab_service
- **前置条件**：服务启动
- **输入**：GET /health
- **预期结果**：status_code=200，body={"status":"ok"}

---

## 二、实验评估

### TC-ABS-002：白名单用户评估命中白名单策略
- **关联**：L1/ab_service
- **前置条件**：初始白名单 u_white -> exp_game: game_on
- **输入**：POST /api/v1/ab/evaluate，user_id="u_white"，experiment_names=["exp_game"]
- **预期结果**：status_code=200，strategy_id="game_on"，hit_reason="whitelist"

---

## 三、实验管理 CRUD

### TC-ABS-003：列出所有实验
- **关联**：L1/ab_service
- **前置条件**：初始化 exp_game 和 exp_cal 两个实验
- **输入**：GET /api/v1/ab/experiments
- **预期结果**：status_code=200，返回列表包含 exp_game 和 exp_cal

### TC-ABS-004：获取单个实验详情
- **关联**：L1/ab_service
- **前置条件**：exp_game 已存在
- **输入**：GET /api/v1/ab/experiments/exp_game
- **预期结果**：status_code=200，name="exp_game"

### TC-ABS-005：创建新实验并持久化
- **关联**：L1/ab_service
- **前置条件**：exp_new 不存在
- **输入**：POST /api/v1/ab/experiments，name="exp_new"
- **预期结果**：status_code=200，持久化文件中包含 exp_new

### TC-ABS-006：更新已有实验的策略
- **关联**：L1/ab_service
- **前置条件**：exp_new 已创建
- **输入**：PUT /api/v1/ab/experiments/exp_new，修改 strategy_id 为 "new_off"
- **预期结果**：status_code=200，strategies[0]["id"]=="new_off"

### TC-ABS-007：删除实验
- **关联**：L1/ab_service
- **前置条件**：exp_new 已创建
- **输入**：DELETE /api/v1/ab/experiments/exp_new
- **预期结果**：status_code=200，deleted=True，再次 GET 返回 404

### TC-ABS-008：创建重名实验返回 409 冲突
- **���联**：L1/ab_service
- **前置条件**：exp_game 已存在
- **输入**：POST /api/v1/ab/experiments，name="exp_game"
- **预期结果**：status_code=409

---

## 四、白名单管理 CRUD

### TC-ABS-009：查询全部白名单
- **关联**：L1/ab_service
- **前置条件**：初始白名单包含 u_white
- **输入**：GET /api/v1/ab/whitelist
- **预期结果**：status_code=200，结果包含 "u_white"

### TC-ABS-010：设置单用户白名单
- **关联**：L1/ab_service
- **前置条件**：无
- **输入**：PUT /api/v1/ab/whitelist/user_a，body={strategy_map: {exp_cal: "cal_on"}}
- **预期结果**：status_code=200，返回 {exp_cal: "cal_on"}

### TC-ABS-011：查询单用户白名单
- **关联**：L1/ab_service
- **前置条件**：user_a 白名单已设置
- **输入**：GET /api/v1/ab/whitelist/user_a
- **预期结果**：status_code=200，返回 {exp_cal: "cal_on"}

### TC-ABS-012：批量覆盖白名单
- **关联**：L1/ab_service
- **前置条件**：有已有白名单
- **输入**：PUT /api/v1/ab/whitelist，body={user_b: {exp_game: "game_on"}}
- **预期结果**：status_code=200，白名单被完全替换

### TC-ABS-013：删除单用户白名单
- **关联**：L1/ab_service
- **前置条件**：user_b 白名单已存在
- **输入**：DELETE /api/v1/ab/whitelist/user_b
- **预期结果**：status_code=200，cleared=True，再次 GET 返回 404

### TC-ABS-014：清空全部白名单
- **关联**：L1/ab_service
- **前置条件**：有白名单数据
- **输入**：DELETE /api/v1/ab/whitelist
- **预期结果**：status_code=200，cleared=True，白名单为空

---

## 五、白名单持久化

### TC-ABS-015：白名单变更持久化到文件，重启后自动加载
- **关联**：L1/ab_service
- **前置条件**：第一次启动，设置 user_x 白名单
- **输入**：重启服务（不传 initial_whitelist），查询白名单
- **预期结果**：白名单文件存在，重启后 user_x 白名单仍在，evaluate 命中 whitelist

---

## 六、隔离性

### TC-ABS-016：service 模块可独立导入，不依赖 coupon_system
- **关联**：L2/0405
- **前置条件**：隔离环境，仅包含 ab_experiment_sdk 包
- **输入**：在独立 Python 进程中 import ab_experiment_sdk.service
- **预期结果**：import 成功，无 ImportError

### TC-ABS-017：service 导入不在当前目录产生副作用文件
- **关联**：L2/0405
- **前置条件**：在临时目录中运行
- **输入**：import ab_experiment_sdk.service，检查 cwd 是否有新文件
- **预期结果**：当前目录下不会生成 coupon_system/config/experiments.json
