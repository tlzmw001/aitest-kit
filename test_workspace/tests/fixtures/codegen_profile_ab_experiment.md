# ab_experiment 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `http_base_url` | conftest session | 主服务 HTTP 地址 |
| `grpc_target` | conftest session | 主服务 gRPC 地址 |
| `ab_base_url` | conftest session | AB 实验服务地址 |
| `setup_ab_experiment` | fixtures/ab_experiment.py | 初始化库存和用例所需 AB 白名单 |

## 请求模板

业务用例使用推荐接口，基础字段来自 Markdown 共享配置。`external=0` 走内部打分和 AB 实验，`external=1` 跳过实验评估。

## 断言模式

| 用例中的断言 | 生成规则 |
|-------------|----------|
| `exp` 只包含 game/ad 实验 | 对 `resp["experiment_info"].keys()` 做子集断言 |
| `exp["..."] == "..."` | 对 `resp["experiment_info"]` 指定 key 断言 |
| `exp == no_exp` | `resp["experiment_info"] == {}` |
| AB 服务启动顺序类断言 | 需要测试环境编排启动顺序，Markdown 中标记为可行性存疑，不生成默认单请求代码 |

## setup 映射

| 场景变量描述 | fixture 行为 |
|-------------|--------------|
| 初始化库存 | 设置 `COUPON_AB_001`、`COUPON_AB_BOUNDARY_001` 库存 |
| 白名单优先 | 对生成代码实际 user_id 写入 AB 白名单 |

## emitter 规则

```yaml
request_overrides:
  TC-AB-001:
    user_id: u_ab_hash_http
    reqId: req-ab-001
    scene_name: game
    device: mobile
    external: 0
  TC-AB-002:
    user_id: u_ab_hash_grpc
    req_id: req-ab-002
    scene_name: ad
    device: pc
    external: 0
  TC-AB-003:
    user_id: u_ab_white
    reqId: req-ab-003
    scene_name: game
    device: mobile
    external: 0
  TC-AB-004:
    user_id: u_ab_scene_game
    reqId: req-ab-004
    scene_name: game
    device: mobile
    external: 0
  TC-AB-005:
    user_id: u_ab_no_mapping
    reqId: req-ab-005
    scene_name: game
    device: mobile
    external: 0
  TC-AB-006:
    user_id: u_ab_external_http
    reqId: req-ab-006
    scene_name: game
    device: mobile
    external: 1
  TC-AB-007:
    user_id: u_ab_external_grpc
    req_id: req-ab-007
    scene_name: game
    device: mobile
    external: 1
  TC-AB-009:
    user_id: u_ab_unknown_exp
    reqId: req-ab-009
    scene_name: game
    device: mobile
    external: 0

assertion_rules:
  - pattern: '非兜底、非 external=1 场景'
    template: 'assert resp["code"] == 0'
  - pattern: 'response.body.code == 0'
    template: 'assert resp["code"] == 0'
  - pattern: 'exp 只包含 coarse_rank_exp_game、calibration_exp_game'
    template: 'assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_game", "calibration_exp_game"}'
  - pattern: '不包含 coarse_rank_exp_ad、calibration_exp_ad'
    template: 'assert "coarse_rank_exp_ad" not in resp["experiment_info"] and "calibration_exp_ad" not in resp["experiment_info"]'
  - pattern: 'exp 只包含 coarse_rank_exp_ad、calibration_exp_ad'
    template: 'assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_ad", "calibration_exp_ad"}'
  - pattern: '不包含 coarse_rank_exp_game、calibration_exp_game'
    template: 'assert "coarse_rank_exp_game" not in resp["experiment_info"] and "calibration_exp_game" not in resp["experiment_info"]'
  - pattern: 'exp["coarse_rank_exp_game"] == "cr_off"'
    template: 'assert resp["experiment_info"].get("coarse_rank_exp_game") == "cr_off"'
  - pattern: 'exp["calibration_exp_game"] == "cal_off"'
    template: 'assert resp["experiment_info"].get("calibration_exp_game") == "cal_off"'
  - pattern: 'set(exp.keys())'
    template: 'assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_game", "calibration_exp_game"}'
  - pattern: 'exp 不包含任何 _ad 实验'
    template: 'assert not any(k.endswith("_ad") for k in resp["experiment_info"])'
  - pattern: 'exp == no_exp'
    template: 'assert resp["experiment_info"] == {}'
  - pattern: 'response.body.experiment_info == no_exp'
    template: 'assert resp["experiment_info"] == {}'
  - pattern: 'response.experiment_info == no_exp'
    template: 'assert resp["experiment_info"] == {}'
  - pattern: 'exp["ab_boundary_left"] == "left_hit"'
    template: 'assert resp["experiment_info"].get("ab_boundary_left") == "left_hit"'
  - pattern: 'exp 不包含 ab_boundary_right'
    template: 'assert "ab_boundary_right" not in resp["experiment_info"]'
  - pattern: 'AB 服务启动后同请求返回 code == 0'
    template: 'assert resp["code"] == 0'
```
