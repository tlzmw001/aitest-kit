# AB 实验 Remote Client 测试用例

> 来源：tests/test_ab_remote_client.py
> 待测模块：ab_experiment_sdk.remote_client（远程 AB 实验 SDK 客户端）

---

## 一、远程评估

### TC-RC-001：远程 evaluate 端到端调用
- **关联**：L1/ab_service
- **前置条件**：AB 服务启动，白名单 u1 -> exp_game: game_on
- **输入**：RemoteABExperimentSDK.evaluate(user_id="u1", experiment_names=["exp_game"])
- **预期结果**：request_id 正确返回，assignments 包含 exp_game，strategy_id="game_on"，hit_reason="whitelist"

---

## 二、白名单远程管理

### TC-RC-002：通过 SDK 设置单用户白名单并验证 evaluate
- **关联**：L1/ab_service
- **前置条件**：AB 服务启动
- **输入**：sdk.set_user_whitelist("u2", {exp_cal: "cal_on"})，然后 evaluate
- **预期结果**：evaluate 返回 strategy_id="cal_on"，hit_reason="whitelist"

### TC-RC-003：通过 SDK 清除单用户白名单
- **关联**：L1/ab_service
- **前置条件**：u2 白名单已设置
- **输入**：sdk.clear_whitelist("u2")
- **预期结果**：白名单列表中不再包含 u2

### TC-RC-004：通过 SDK 批量设置白名单
- **关联**：L1/ab_service
- **前置条件**：有已有白名单
- **输入**：sdk.set_whitelist({u3: {exp_game: "game_on"}})
- **预期结果**：get_whitelist() 返回仅 u3 的数据

### TC-RC-005：通过 SDK 清空全部白名单
- **关联**：L1/ab_service
- **前置条件**：有白名单数据
- **输入**：sdk.clear_whitelist()
- **预期结果**：get_whitelist() 返回 {}

---

## 三、异常处理

### TC-RC-006：远程服务返回 500 时 SDK 抛出 HTTPStatusError
- **关联**：L1/ab_service
- **前置条件**：Mock 服务端始终返回 500
- **输入**：sdk.evaluate(user_id="u_err")
- **预期结果**：抛出 httpx.HTTPStatusError
