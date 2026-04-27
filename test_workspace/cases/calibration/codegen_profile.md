# calibration 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `http_base_url` | conftest session | 主服务地址，默认 `http://localhost:8000` |
| `ab_base_url` | conftest session | AB 实验服务地址，默认 `http://localhost:8100` |
| `setup_calibration` | conftest | 每条用例的前置操作入口，接受 `case_id` 参数 |

### setup_calibration 做了什么

1. 写校准文件：根据 `_CASE_CONFIGS[case_id]` 向 `coupon_system/calibration/scene_game/{linear,piecewise}/` 写入 999.json（或 998.json），利用 calibrator 取最大序号文件的机制覆盖默认 1.json
2. 设置 AB 白名单：调用 `PUT /api/v1/ab/whitelist/{user_id}` 强制命中 `cal_on`（或 `cal_off`）+ `cr_off`
3. 初始化库存：调用 `POST /api/v1/admin/stock` 设置 coupon 库存
4. teardown：删除测试校准文件 + 清理 AB 白名单

### 新增用例时如何扩展

在 `conftest.py` 的 `_CASE_CONFIGS` 字典中添加条目：

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
| 校准目录不存在 / calibration_dir 为空 | BLOCKED — 无运行时实验参数覆盖 API |

## 已知阻塞项

- TC-CAL-015/016/019/025：需要自定义 `calibration_dir` 路径，当前无运行时实验参数覆盖 API
- TC-CAL-020/021：需要精确控制打分结果（s==0.3, s==1.0），推荐接口无法稳定构造

## 调试经验

1. **500 错误排查**：recommend 接口 500 时，看服务端终端 traceback，常见原因：Redis 未连接、AB 服务不可达、内部模块初始化不完整
2. **校准不生效**：检查 999.json 是否写入正确目录、conditions 字段是否在 `_MATCHABLE_FIELDS`（item_id, coupon_type, device, external, gender, age, total_spend）
3. **白名单不生效**：确认主服务走的是 RemoteABExperimentSDK（`AB_SERVICE_URL` 已设置），白名单通过 AB 服务 API 设置而非环境变量
4. **httpx 403**：系统代理问题，http_helper 已用 `httpx.HTTPTransport()` 绕过
