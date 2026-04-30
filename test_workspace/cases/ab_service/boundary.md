# ab_service 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L1/ab_service
> 生成日期：2026-04-26

---

## 共享配置

**接口**：`http://localhost:8100`

**基础请求体（Evaluate）**：

```json
{
  "user_id": "{{user_id}}",
  "request_id": "{{request_id}}",
  "context": {},
  "experiment_names": null
}
```

**标准前置**：
- AB 实验服务使用独立测试目录 `/tmp/aitest_ab_service_boundary/`
- 测试配置文件和白名单文件均为用例专用文件，不修改仓库默认 `ab_experiment_sdk/data/experiments.json`

**通用断言**：
- 成功请求：HTTP `2xx`
- 错误请求：响应体使用 FastAPI 标准格式

**变量定义**：
- `assign` = `response.body.assignments`

---

## 一、分流边界

### TC-ABS-023：hash_range 重叠时命中第一个匹配策略
- **优先级**：P2
- **场景变量**：
  - 请求覆盖：实验 `exp_abs_overlap` 策略顺序为 `s_first [0,80)`、`s_second [50,100)`
  - 前置操作：选择 hash=60 的 user_id
- **断言**：`assign["exp_abs_overlap"].strategy_id == "s_first"`

### TC-ABS-024：空策略实验评估后不返回 assignment
- **优先级**：P2 / 异常
- **场景变量**：
  - 前置操作：创建实验 `exp_abs_empty`，`strategies=[]`
  - 接口调用：evaluate 指定该实验
- **断言**：`assign == {}`

### TC-ABS-025：evaluate 指定不存在实验名时静默跳过
- **优先级**：P2 / 异常
- **场景变量**：接口调用：evaluate `experiment_names=["not_exists_exp"]`
- **断言**：`assign == {}`

---

## 二、文件容错

### TC-ABS-026：实验配置文件不存在时自动创建空配置
- **优先级**：P2
- **场景变量**：环境覆盖：使用不存在的 `AB_SERVICE_EXPERIMENTS_PATH=/tmp/aitest_ab_service_boundary/new/experiments.json` 启动服务
- **断言**：服务启动成功；`GET /api/v1/ab/experiments` 返回 `[]`；磁盘上创建 `experiments.json`

### TC-ABS-027：白名单文件损坏时忽略并以空白名单启动
- **优先级**：P2 / 异常
- **场景变量**：环境覆盖：白名单文件内容为 `{bad json`，启动服务
- **断言**：`GET /api/v1/ab/whitelist` 返回 `{}`； 日志包含 `白名单文件读取失败`
- **标记**：`[manual]`

### TC-ABS-028：实验策略 hash_range 格式异常时回退到 [0,100]
- **优先级**：P2 / 异常
- **场景变量**：请求覆盖：实验配置文件中策略 `s_bad` 的 `hash_range=["bad"]`
- **断言**：服务启动成功；evaluate 任一 user 可命中 `s_bad`

### TC-ABS-029：实验策略 params 非 dict 时回退为空 dict
- **优先级**：P2 / 异常
- **场景变量**：请求覆盖：实验配置文件中策略 `s_bad_params` 的 `params="bad"`
- **断言**：evaluate 命中后 `assign[exp].params == {}`

---

## 三、Schema 校验

### TC-ABS-030：evaluate 缺少 user_id 返回 422
- **优先级**：P2 / 异常
- **场景变量**：接口调用：`POST /api/v1/ab/evaluate` body 缺少 `user_id`
- **断言**：`status_code == 422`；`detail[*].loc` 包含 `["body","user_id"]`

### TC-ABS-031：创建实验 strategies 类型错误返回 422
- **优先级**：P2 / 异常
- **场景变量**：接口调用：`POST /api/v1/ab/experiments` body `{"name":"exp_abs_bad_schema","strategies":"bad"}`
- **断言**：`status_code == 422`

### TC-ABS-032：单用户白名单 strategy_map 类型错误返回 422
- **优先级**：P2 / 异常
- **场景变量**：接口调用：`PUT /api/v1/ab/whitelist/u_abs_bad_schema` body `{"strategy_map":"bad"}`
- **断言**：`status_code == 422`

---

## 四、服务隔离与远程 SDK

### TC-ABS-033：service 模块可独立导入
- **优先级**：P2
- **场景变量**：请求覆盖：在仅包含 `ab_experiment_sdk` 包的隔离 Python 进程中执行 `import ab_experiment_sdk.service`
- **断言**：import 成功，不依赖 `coupon_system`，无 `ImportError`

### TC-ABS-034：service 导入不在当前目录产生副作用文件
- **优先级**：P2
- **场景变量**：前置操作：在临时目录中执行 `import ab_experiment_sdk.service`，随后检查当前工作目录
- **断言**：当前目录下不会生成 `coupon_system/config/experiments.json` 或其他副作用文件

### TC-ABS-035：Remote SDK evaluate 端到端调用
- **优先级**：P1
- **场景变量**：
  - 前置操作：AB 服务启动，白名单 `u1 -> {"exp_game":"game_on"}`
  - 请求覆盖：调用 `RemoteABExperimentSDK.evaluate(user_id="u1", experiment_names=["exp_game"])`
- **断言**：返回 `request_id` 与请求一致；`assignments["exp_game"].strategy_id == "game_on"`；`hit_reason == "whitelist"`

### TC-ABS-036：Remote SDK 设置单用户白名单并验证 evaluate
- **优先级**：P1
- **场景变量**：接口调用：调用 `sdk.set_user_whitelist("u2", {"exp_cal":"cal_on"})`，随后 evaluate `user_id="u2"`、`experiment_names=["exp_cal"]`
- **断言**：evaluate 返回 `strategy_id == "cal_on"`；`hit_reason == "whitelist"`

### TC-ABS-037：Remote SDK 清除单用户白名单
- **优先级**：P1
- **场景变量**：
  - 前置操作：`u2` 白名单已存在
  - 请求覆盖：调用 `sdk.clear_whitelist("u2")`
- **断言**：`sdk.get_whitelist()` 不包含 `u2`

### TC-ABS-038：Remote SDK 批量覆盖白名单
- **优先级**：P1
- **场景变量**：
  - 前置操作：已有白名单数据
  - 请求覆盖：调用 `sdk.set_whitelist({"u3":{"exp_game":"game_on"}})`
- **断言**：`sdk.get_whitelist() == {"u3":{"exp_game":"game_on"}}`

### TC-ABS-039：Remote SDK 清空全部白名单
- **优先级**：P1
- **场景变量**：
  - 前置操作：已有白名单数据
  - 请求覆盖：调用 `sdk.clear_whitelist()`
- **断言**：`sdk.get_whitelist() == {}`

### TC-ABS-040：Remote SDK 遇到服务端 500 时抛出 HTTPStatusError
- **优先级**：P2 / 异常
- **场景变量**：
  - 协议：HTTP
  - 请求覆盖：mock AB 服务端对 `/api/v1/ab/evaluate` 固定返回 HTTP 500
  - 请求覆盖：调用 `sdk.evaluate(user_id="u_err")`
- **断言**：抛出 `httpx.HTTPStatusError`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_service | hash_range 重叠、空策略实验、不存在实验名跳过、配置文件不存在、白名单文件损坏、策略格式异常、Pydantic 422、service 导入隔离、Remote SDK evaluate/白名单管理/服务端 500 | SDK 网络超时/连接拒绝和重试机制未在旧用例中定义，暂不新增 |
| L2/0405 | AB 服务文件容错、Schema 校验、service 独立导入和无 cwd 副作用 | 无（仅限 ab_service 范围） |
