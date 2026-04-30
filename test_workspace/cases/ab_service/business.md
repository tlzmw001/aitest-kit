# ab_service 业务测试用例

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
- AB 实验服务按项目方式启动，默认端口 `8100`
- 使用独立测试数据文件启动服务：`AB_SERVICE_EXPERIMENTS_PATH=/tmp/aitest_ab_service/experiments.json`
- 基础实验 `exp_ab_basic` 包含两组策略：`s_a hash_range=[0,50)`、`s_b hash_range=[50,100)`，params 分别可识别
- 每条用例结束后清理测试创建的实验和白名单

**通用断言**：
- 成功请求：HTTP `2xx`
- 错误请求：响应体格式为 `{"detail": "<message>"}` 或 FastAPI 422 标准数组

**变量定义**：
- `assign` = `response.body.assignments`

---

## 一、健康检查与评估

### TC-ABS-001：健康检查返回 ok
- **优先级**：P0
- **场景变量**：接口调用：`GET /health`
- **断言**：`response.status_code == 200`；`response.body == {"status":"ok"}`

### TC-ABS-002：hash 分流命中半开区间策略
- **优先级**：P1
- **场景变量**：接口调用：`POST /api/v1/ab/evaluate`，`user_id` 选择 `md5(user_id)%100` 落入 `s_a` 的 `[0,50)`，`experiment_names=["exp_ab_basic"]`
- **断言**：`assign["exp_ab_basic"].strategy_id == "s_a"`；`hit_reason == "hash"`

### TC-ABS-003：白名单优先于 hash 分流
- **优先级**：P1
- **场景变量**：
  - 前置操作：先 `PUT /api/v1/ab/whitelist/u_abs_white`，body `{"strategy_map":{"exp_ab_basic":"s_b"}}`
  - 接口调用：再 evaluate `user_id="u_abs_white"`、`experiment_names=["exp_ab_basic"]`
- **断言**：`assign["exp_ab_basic"].strategy_id == "s_b"`；`hit_reason == "whitelist"`

### TC-ABS-004：experiment_names 为 null 时评估全部实验
- **优先级**：P1
- **场景变量**：
  - 接口调用：evaluate 请求 `experiment_names=null`
  - 请求覆盖：服务中至少存在 `exp_ab_basic` 和 `exp_ab_extra`
- **断言**：`assign` 包含所有可命中的实验 key

### TC-ABS-005：experiment_names 为空数组时返回空 assignments
- **优先级**：P1
- **场景变量**：接口调用：evaluate 请求 `experiment_names=[]`
- **断言**：`assign == {}`

### TC-ABS-006：experiment_names 指定实验时只评估该实验
- **优先级**：P1
- **场景变量**：接口调用：evaluate 请求 `experiment_names=["exp_ab_basic"]`
- **断言**：`set(assign.keys()) <= {"exp_ab_basic"}`

---

## 二、实验管理

### TC-ABS-007：列出所有实验
- **优先级**：P1
- **场景变量**：
  - 前置操作：服务已初始化 `exp_game` 和 `exp_cal` 两个实验
  - 接口调用：调用 `GET /api/v1/ab/experiments`
- **断言**：`response.status_code == 200`；返回列表包含 `exp_game` 和 `exp_cal`

### TC-ABS-008：获取单个实验详情
- **优先级**：P1
- **场景变量**：
  - 请求覆盖：`exp_game` 已存在
  - 接口调用：调用 `GET /api/v1/ab/experiments/exp_game`
- **断言**：`response.status_code == 200`；`response.body.name == "exp_game"`

### TC-ABS-009：创建实验并可查询
- **优先级**：P1
- **场景变量**：接口调用：`POST /api/v1/ab/experiments`，body 为 `{"name":"exp_abs_create","strategies":[{"id":"s1","hash_range":[0,100],"params":{"k":"v"}}]}`
- **断言**：创建返回 `name=="exp_abs_create"`；随后 `GET /api/v1/ab/experiments/exp_abs_create` 返回同名实验

### TC-ABS-010：更新实验整体替换策略列表
- **优先级**：P1
- **场景变量**：前置操作：已有 `exp_abs_update`，执行 `PUT /api/v1/ab/experiments/exp_abs_update`，body 中策略只保留 `s_new`
- **断言**：更新后 `GET` 返回的 `strategies[*].id == ["s_new"]`

### TC-ABS-011：删除实验后查询返回 404
- **优先级**：P1
- **场景变量**：前置操作：创建 `exp_abs_delete` 后执行 `DELETE /api/v1/ab/experiments/exp_abs_delete`，再 `GET` 同名实验
- **断言**：删除响应 `{"deleted": true}`；后续查询 `status_code == 404`、`detail == "experiment not found"`

### TC-ABS-012：实验增删改持久化到文件并重启恢复
- **优先级**：P1
- **场景变量**：环境覆盖：使用独立 `AB_SERVICE_EXPERIMENTS_PATH` 创建 `exp_abs_persist`，重启 AB 服务
- **断言**：重启后 `GET /api/v1/ab/experiments/exp_abs_persist` 返回 200

---

## 三、白名单管理

### TC-ABS-013：查询全部白名单
- **优先级**：P1
- **场景变量**：
  - 前置操作：服务已有白名单 `u_white -> {"exp_game":"game_on"}`
  - 接口调用：调用 `GET /api/v1/ab/whitelist`
- **断言**：`response.status_code == 200`；响应体包含 `u_white`

### TC-ABS-014：单用户白名单设置和查询
- **优先级**：P1
- **场景变量**：
  - 接口调用：`PUT /api/v1/ab/whitelist/u_abs_user`，body `{"strategy_map":{"exp_ab_basic":"s_a"}}`
  - 请求覆盖：随后 `GET /api/v1/ab/whitelist/u_abs_user`
- **断言**：查询返回 `{"exp_ab_basic":"s_a"}`

### TC-ABS-015：全量白名单替换和查看
- **优先级**：P1
- **场景变量**：接口调用：`PUT /api/v1/ab/whitelist`，body `{"u_abs_1":{"exp_ab_basic":"s_a"},"u_abs_2":{"exp_ab_basic":"s_b"}}`
- **断言**：`GET /api/v1/ab/whitelist` 返回两个用户的策略映射

### TC-ABS-016：删除单用户白名单
- **优先级**：P1
- **场景变量**：
  - 前置操作：`user_b` 白名单已存在
  - 接口调用：调用 `DELETE /api/v1/ab/whitelist/user_b`，随后查询该用户白名单
- **断言**：删除响应 `{"cleared": true}`；再次 `GET /api/v1/ab/whitelist/user_b` 返回 `404`

### TC-ABS-017：清空全部白名单
- **优先级**：P1
- **场景变量**：前置操作：先设置全量白名单，再 `DELETE /api/v1/ab/whitelist`
- **断言**：删除响应 `{"cleared": true}`；`GET /api/v1/ab/whitelist` 返回 `{}`

### TC-ABS-018：白名单持久化并重启恢复
- **优先级**：P1
- **场景变量**：前置操作：设置 `u_abs_persist` 白名单后重启 AB 服务
- **断言**：重启后 `GET /api/v1/ab/whitelist/u_abs_persist` 返回原策略映射

---

## 四、错误场景

### TC-ABS-019：创建重名实验返回 409
- **优先级**：P1 / 异常
- **场景变量**：前置操作：连续两次 `POST /api/v1/ab/experiments` 创建 `exp_abs_dup`
- **断言**：第二次 `status_code == 409`；`detail == "experiment already exists: exp_abs_dup"`

### TC-ABS-020：更新实验路径名与 body 名不一致返回 400
- **优先级**：P1 / 异常
- **场景变量**：接口调用：`PUT /api/v1/ab/experiments/exp_abs_path`，body `{"name":"exp_abs_body","strategies":[]}`
- **断言**：`status_code == 400`；`detail == "path name and payload name mismatch"`

### TC-ABS-021：查询不存在用户白名单返回 404
- **优先级**：P1 / 异常
- **场景变量**：接口调用：`GET /api/v1/ab/whitelist/u_abs_not_exists`
- **断言**：`status_code == 404`；`detail == "user whitelist not found"`

### TC-ABS-022：删除不存在用户白名单静默成功
- **优先级**：P1
- **场景变量**：接口调用：`DELETE /api/v1/ab/whitelist/u_abs_not_exists`
- **断言**：`status_code == 200`；`response.body == {"cleared": true}`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_service | 健康检查、hash/白名单评估、experiment_names 三种行为、实验列表/详情查询、实验 CRUD、实验持久化、白名单 CRUD、白名单持久化、404/409/400/删除不存在白名单 | hash_range 重叠、文件损坏、配置文件缺失、格式异常、422 由 boundary.md 覆盖 |
| L2/0405 | AB 服务健康检查、CRUD、白名单优先级、持久化 | 无（仅限 ab_service 范围） |
