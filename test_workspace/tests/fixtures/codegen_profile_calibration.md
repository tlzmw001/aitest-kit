# calibration 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `http_base_url` | conftest session | 主服务地址，默认 `http://localhost:8000` |
| `ab_base_url` | conftest session | AB 实验服务地址，默认 `http://localhost:8100` |
| `setup_calibration` | fixtures/calibration.py | 每条用例的前置操作入口，接受 `case_id` 参数 |

### setup_calibration 做了什么

1. 创建隔离校准目录：根据 `_CASE_CONFIGS[case_id]` 在 pytest `tmp_path` 下创建 `linear/`、`piecewise/`，并写入该用例需要的规则文件或异常文件
2. 覆盖 AB 实验参数：调用 `GET /api/v1/ab/experiments/calibration_exp_game` 保存原配置，再调用 `PUT /api/v1/ab/experiments/calibration_exp_game` 临时把 `cal_on.params.calibration_dir` 指向本用例的隔离目录
3. 设置 AB 白名单：调用 `PUT /api/v1/ab/whitelist/{user_id}` 强制命中 `cal_on`（或 `cal_off`）+ `cr_off`
4. 初始化库存：调用 `POST /api/v1/admin/stock` 设置 coupon 库存
5. teardown：恢复 `calibration_exp_game` 原配置 + 清理 AB 白名单；临时目录由 pytest 管理

### 新增用例时如何扩展

在 `test_workspace/tests/fixtures/calibration.py` 的 `_CASE_CONFIGS` 字典中添加条目：

```python
"TC-CAL-028": {
    "linear": {"999.json": [{"conditions": {"device": "mobile"}, "k": 1.5, "b": 0.1}]},
},
```

如果需要特殊白名单策略，在 `_WHITELIST_MAP` 中添加覆盖。

## 请求模板

基础请求体固定字段：`scene_name="game"`, `device="mobile"`, `external=0`, `score_threshold=0.0`, `max_claim_per_request=1`

用例间差异：
- `user_id`：`u_cal_{tc_number}`（如 `u_cal_001`）
- `reqId`：`req_cal_{tc_number}`
- `items[0].item_id`：business 用 `COUPON_CAL_001`，boundary 用 `COUPON_CAL_BOUNDARY_001`

通过 `_req(user_id, req_id, **overrides)` helper 生成，overrides 合并到基础请求体。

## 断言模式

| 用例中的断言 | 生成的 pytest 代码 | 说明 |
|-------------|-------------------|------|
| `cal == round(clamp(k * s + b), 4)` | `assert cal == pytest.approx(max(0, min(1, k * s + b)), abs=1e-4)` | 线性校准 |
| `cal == s` | `assert cal == pytest.approx(s)` | 未校准/降级 |
| 分段+线性串联 | 先按 s 所在区间算 mid，再 `1.2 * mid + 0.05` | 见 TC-CAL-002/012 |
| `response.code == 0` | `assert resp["code"] == 0` | 通用断言，每条都有 |

关键变量提取模式：
```python
s = resp["results"][0]["score"]
cal = resp["results"][0]["calibrated_score"]
```

## setup 映射

用例 Markdown 中的场景变量 → fixture 调用的映射规则：

| 场景变量描述 | 映射到 _CASE_CONFIGS |
|-------------|---------------------|
| 线性校准文件规则 conditions=X, k=Y, b=Z | `"linear": {"999.json": [{"conditions": X, "k": Y, "b": Z}]}` |
| 分段文件配置 [a,b)->k=K,b=B, ... | `"piecewise": {"999.json": [{"conditions": ..., "segments": [...]}]}` |
| 线性目录同时存在多版本 | 用 `998.json` + `999.json` 两个文件 |
| 校准文件 JSON 解析失败 | `"linear_raw": {"999.json": "{bad json"}` |
| 校准文件不是 list | `"linear_raw": {"999.json": '{"k":2,"b":0}'}` |
| 实验关闭 | `_WHITELIST_MAP` 中设为 `_CAL_OFF` |
| 校准目录不存在 / calibration_dir 为空 | 通过 AB 实验管理 API 临时覆盖 `cal_on.params.calibration_dir` |

## 已知阻塞项

- TC-CAL-020/021：需要精确控制打分结果（s==0.3, s==1.0），推荐接口无法稳定构造

## 调试经验

1. **500 错误排查**：recommend 接口 500 时，看服务端终端 traceback，常见原因：Redis 未连接、AB 服务不可达、内部模块初始化不完整
2. **校准不生效**：检查 999.json 是否写入正确目录、conditions 字段是否在 `_MATCHABLE_FIELDS`（item_id, coupon_type, device, external, gender, age, total_spend）
3. **白名单不生效**：确认主服务走的是 RemoteABExperimentSDK（`AB_SERVICE_URL` 已设置），白名单通过 AB 服务 API 设置而非环境变量
4. **httpx 403**：系统代理问题，http_helper 已用 `httpx.HTTPTransport()` 绕过
5. **主服务内部 AB 调用 403 导致 recommend 500**：pytest 到 AB 服务的 helper 绕过代理后，主服务进程里的 `RemoteABExperimentSDK` 仍可能受环境代理影响。服务端 traceback 形态为 `coupon_service.py -> remote_client.py -> response.raise_for_status()`，错误是 `Client error '403 Forbidden' for url 'http://localhost:8100/api/v1/ab/evaluate'`，且 AB 服务日志没有对应 evaluate 请求。启动主服务时使用 `AB_SERVICE_URL=http://127.0.0.1:8100` 并设置 `NO_PROXY=localhost,127.0.0.1`、`no_proxy=localhost,127.0.0.1` 可避免本机 AB 调用被代理截走。
6. **默认校准文件污染断言**：只写某一类校准规则不等于只执行该类规则。calibrator 会分别加载 `calibration_dir.piecewise` 和 `calibration_dir.linear`，先分段后线性串联；如果测试只覆盖 piecewise 目录但仍指向默认 linear 目录，默认 `linear/1.json` 会继续参与计算，导致”仅分段”断言失败。fixture 必须为每条用例提供隔离的 linear/piecewise 目录，并通过 AB 实验参数把 `cal_on.calibration_dir` 指向这些目录。

## emitter 规则

以下 YAML 块供 `emitter.py` 的 `load_profile_rules()` 读取，覆盖通用规则无法处理的 calibration 特有断言。

```yaml
assertion_rules:
  - pattern: 'mid = round(clamp(k_pw * s + b_pw), 4)'
    template: piecewise_cascade
    params:
      segments: [[0.3, 0.5, 0.1], [0.7, 1.0, 0.0], [1.0, 1.5, -0.2]]
      linear_k: 1.2
      linear_b: 0.05

  - pattern: 'mid = k_pw * s + b_pw'
    template: piecewise_cascade
    params:
      segments: [[0.3, 0.5, 0.1], [0.7, 1.0, 0.0], [1.0, 1.5, -0.2]]
      linear_k: 1.2
      linear_b: 0.05

  - pattern: 'cal == round(clamp(1.2 * mid + 0.05), 4)'
    template: skip
    params: {}

  - pattern: '按 `s` 所在区间计算'
    template: piecewise_only
    params:
      segments: [[0.3, 0.5, 0.1], [0.7, 1.0, 0.0], [1.0, 1.5, -0.2]]
```

模板说明：
- `piecewise_cascade`：先按 s 所在区间选 k_pw/b_pw 算 mid，再用 linear_k * mid + linear_b 算 cal
- `piecewise_only`：只按 s 所在区间选 k/b 直接算 cal，不串联线性
