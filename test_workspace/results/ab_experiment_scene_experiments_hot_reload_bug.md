# ab_experiment 场景实验映射热更新缺失问题记录

## 背景

`ab_experiment` 模块集成测试中，已修复基础请求体解析和 case 级请求覆盖生成问题后，单模块测试仍有 2 条失败：

- `TC-AB-005`：场景无实验映射时返回空实验信息
- `TC-AB-010`：hash 命中区间左闭边界

另外 `TC-AB-011` 当前虽然通过，但属于关联风险：它没有真正验证 `ab_boundary_right` 的右开边界，而是因为该实验没有进入主服务的 scene-experiment mapping，所以响应中自然不包含该实验。

## 复现命令

```bash
python3 -m pytest test_workspace/tests/generated/test_ab_experiment_business.py test_workspace/tests/generated/test_ab_experiment_boundary.py -v --tb=short
```

## 当前结果

```text
12 collected
10 passed
2 failed

FAILED test_workspace/tests/generated/test_ab_experiment_business.py::TestAbExperimentBusiness::test_tc_ab_005
FAILED test_workspace/tests/generated/test_ab_experiment_boundary.py::TestAbExperimentBoundary::test_tc_ab_010
```

`TC-AB-005` 实际响应中仍包含默认 game 场景实验：

```text
resp["experiment_info"] == {
  "calibration_exp_game": "cal_on",
  "coarse_rank_exp_game": "cr_v2_full"
}
```

`TC-AB-010` 实际响应中没有 `ab_boundary_left`：

```text
resp["experiment_info"].get("ab_boundary_left") is None
```

## 期望行为

待测系统应支持运行时热更新 `coupon_system/config/scene_experiments.json` 中的场景到实验映射。

当测试或运维修改 `scene_experiments.json` 后，已运行的主服务应能重新加载最新映射，使后续推荐请求按新映射选择实验。

期望示例：

```json
{
  "scene_experiments": {
    "1001": []
  },
  "default_experiments": []
}
```

修改后，`game/mobile -> scene_id=1001` 的推荐请求应返回：

```json
{
  "experiment_info": {}
}
```

另一个期望示例：

```json
{
  "scene_experiments": {
    "1001": ["ab_boundary_left"]
  },
  "default_experiments": []
}
```

修改后，`scene_id=1001` 的推荐请求应评估 `ab_boundary_left`，从而允许 `TC-AB-010` 验证 hash 区间左闭边界：

```text
exp["ab_boundary_left"] == "left_hit"
```

## 实际行为

当前主服务只在启动阶段加载一次 `scene_experiments.json`：

- `coupon_system/main.py` 中调用 `load_scene_experiment_mapping_config()`
- 读取结果在构造 `CouponBizService` 时注入为 `scene_experiment_mapping`
- 推荐请求执行时使用内存中的 `self.scene_experiment_mapping`

因此运行中修改 `coupon_system/config/scene_experiments.json` 不会影响已启动主服务。

当前默认配置中：

```json
"1001": ["coarse_rank_exp_game", "calibration_exp_game"]
```

所以：

- `TC-AB-005` 即使用例期望空映射，运行中的主服务仍按默认映射评估 game 实验。
- `TC-AB-010` 即使 AB 服务侧可以创建 `ab_boundary_left` 实验，主服务也不会把 `ab_boundary_left` 传给 AB 服务评估，因为该实验名不在内存中的 `scene_id=1001` 映射里。

## 根因判断

这是待测系统能力缺失，不是 pytest 生成代码问题。

根因：主服务缺少 `scene_experiments.json` 运行时热更新机制。配置文件修改后没有 reload、watch、版本检查或管理接口触发刷新。

## 影响范围

- `TC-AB-005` 无法验证“场景实验映射为空时返回空实验信息”。
- `TC-AB-010` 无法验证“将 scene_id=1001 动态映射到新实验后，hash 左闭边界命中”。
- `TC-AB-011` 当前为误通过风险，原因是待验证实验没有进入主服务映射，而不是右开边界逻辑被验证。
- 所有依赖运行时调整 `scene_experiments.json` 的集成测试都会受影响。

## 后续需求建议

建议给主服务补充场景实验映射热更新能力，满足以下任一实现方式：

1. 周期性检测 `scene_experiments.json` 的 mtime 或内容版本，变化后重新加载并原子替换内存映射。
2. 提供测试/运维管理接口，例如 `POST /api/v1/admin/scene-experiments/reload`，显式触发重新加载配置文件。
3. 将 scene-experiment mapping 移到 Redis 或其他动态配置源，由主服务每次请求或按短 TTL 读取最新映射。

无论采用哪种方式，需要保证：

- reload 失败时保留上一份有效配置并记录错误日志。
- reload 对正在处理的请求是线程安全的。
- 支持清空某个 scene_id 的实验列表，即 `scene_experiments["1001"] = []` 应与缺失映射区分清楚。
- 支持新增实验名映射，例如把 `1001` 映射到 `ab_boundary_left`。

## 当前处理结论

在待测系统补齐热更新能力前，不应通过修改测试断言或伪造响应让这几条测试通过。当前 generated 集成测试先不把 `TC-AB-005`、`TC-AB-010` 作为可执行通过项生成；待热更新能力实现后，需要移除 Markdown 中的缺陷标记并恢复执行。

当前应保留失败作为产品/系统缺陷信号，并在后续需求修复完成后重新执行 `ab_experiment` 模块测试验证。
