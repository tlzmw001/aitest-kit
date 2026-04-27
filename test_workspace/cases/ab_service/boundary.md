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
  "experiment_names": {{experiment_names}}
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

### TC-ABS-019：hash_range 重叠时命中第一个匹配策略
- **优先级**：P2
- **场景变量**：实验 `exp_abs_overlap` 策略顺序为 `s_first [0,80)`、`s_second [50,100)`；选择 hash=60 的 user_id
- **断言**：`assign["exp_abs_overlap"].strategy_id == "s_first"`

### TC-ABS-020：空策略实验评估后不返回 assignment
- **优先级**：P2 / 异常
- **场景变量**：创建实验 `exp_abs_empty`，`strategies=[]`；evaluate 指定该实验
- **断言**：`assign == {}`

### TC-ABS-021：evaluate 指定不存在实验名时静默跳过
- **优先级**：P2 / 异常
- **场景变量**：evaluate `experiment_names=["not_exists_exp"]`
- **断言**：`assign == {}`

---

## 二、文件容错

### TC-ABS-022：实验配置文件不存在时自动创建空配置
- **优先级**：P2
- **场景变量**：使用不存在的 `AB_SERVICE_EXPERIMENTS_PATH=/tmp/aitest_ab_service_boundary/new/experiments.json` 启动服务
- **断言**：服务启动成功；`GET /api/v1/ab/experiments` 返回 `[]`；磁盘上创建 `experiments.json`

### TC-ABS-023：白名单文件损坏时忽略并以空白名单启动
- **优先级**：P2 / 异常
- **场景变量**：白名单文件内容为 `{bad json`，启动服务
- **断言**：`GET /api/v1/ab/whitelist` 返回 `{}`；`[manual]` 日志包含 `白名单文件读取失败`

### TC-ABS-024：实验策略 hash_range 格式异常时回退到 [0,100]
- **优先级**：P2 / 异常
- **场景变量**：实验配置文件中策略 `s_bad` 的 `hash_range=["bad"]`
- **断言**：服务启动成功；evaluate 任一 user 可命中 `s_bad`

### TC-ABS-025：实验策略 params 非 dict 时回退为空 dict
- **优先级**：P2 / 异常
- **场景变量**：实验配置文件中策略 `s_bad_params` 的 `params="bad"`
- **断言**：evaluate 命中后 `assign[exp].params == {}`

---

## 三、Schema 校验

### TC-ABS-026：evaluate 缺少 user_id 返回 422
- **优先级**：P2 / 异常
- **场景变量**：`POST /api/v1/ab/evaluate` body 缺少 `user_id`
- **断言**：`status_code == 422`；`detail[*].loc` 包含 `["body","user_id"]`

### TC-ABS-027：创建实验 strategies 类型错误返回 422
- **优先级**：P2 / 异常
- **场景变量**：`POST /api/v1/ab/experiments` body `{"name":"exp_abs_bad_schema","strategies":"bad"}`
- **断言**：`status_code == 422`

### TC-ABS-028：单用户白名单 strategy_map 类型错误返回 422
- **优先级**：P2 / 异常
- **场景变量**：`PUT /api/v1/ab/whitelist/u_abs_bad_schema` body `{"strategy_map":"bad"}`
- **断言**：`status_code == 422`

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/ab_service | hash_range 重叠、空策略实验、不存在实验名跳过、配置文件不存在、白名单文件损坏、策略格式异常、Pydantic 422 | SDK 网络超时/连接拒绝和重试机制属远程客户端专项，不在 ab_service 本模块新增 |
| L2/0405 | AB 服务文件容错、Schema 校验 | 无（仅限 ab_service 范围） |
