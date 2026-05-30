# ab_experiment module profile

Stable module-level codegen profile. Suite-specific flows stay with suite profiles.

```yaml
assertion_rules:
- pattern: 非兜底、非 external=1 场景
  template: assert resp["code"] == 0
- pattern: response.body.code == 0
  template: assert resp["code"] == 0
- pattern: exp 只包含 coarse_rank_exp_game、calibration_exp_game
  template: assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_game", "calibration_exp_game"}
- pattern: 不包含 coarse_rank_exp_ad、calibration_exp_ad
  template: assert "coarse_rank_exp_ad" not in resp["experiment_info"] and "calibration_exp_ad" not in resp["experiment_info"]
- pattern: exp 只包含 coarse_rank_exp_ad、calibration_exp_ad
  template: assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_ad", "calibration_exp_ad"}
- pattern: 不包含 coarse_rank_exp_game、calibration_exp_game
  template: assert "coarse_rank_exp_game" not in resp["experiment_info"] and "calibration_exp_game" not in resp["experiment_info"]
- pattern: exp["coarse_rank_exp_game"] == "cr_off"
  template: assert resp["experiment_info"].get("coarse_rank_exp_game") == "cr_off"
- pattern: exp["calibration_exp_game"] == "cal_off"
  template: assert resp["experiment_info"].get("calibration_exp_game") == "cal_off"
- pattern: set(exp.keys())
  template: assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_game", "calibration_exp_game"}
- pattern: exp 不包含任何 _ad 实验
  template: assert not any(k.endswith("_ad") for k in resp["experiment_info"])
- pattern: exp == no_exp
  template: assert resp["experiment_info"] == {}
- pattern: response.body.experiment_info == no_exp
  template: assert resp["experiment_info"] == {}
- pattern: response.experiment_info == no_exp
  template: assert resp["experiment_info"] == {}
- pattern: exp["ab_boundary_left"] == "left_hit"
  template: assert resp["experiment_info"].get("ab_boundary_left") == "left_hit"
- pattern: exp 不包含 ab_boundary_right
  template: assert "ab_boundary_right" not in resp["experiment_info"]
- pattern: AB 服务启动后同请求返回 code == 0
  template: assert resp["code"] == 0
module_type: standard_recommend
extra_imports:
- from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
```
