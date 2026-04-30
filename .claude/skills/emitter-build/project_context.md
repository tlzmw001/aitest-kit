# emitter-build 项目上下文

本文件包含当前项目（智能优惠券推荐系统）的 emitter 模板提取专属配置。换项目时重写本文件，不改 SKILL.md。

## 当前项目断言模式清单

### 通用模式（跨项目复用，在 project_config.yaml 的 builtin_assertion_rules 中）

| 模式名 | 匹配文本 | 生成代码 |
|--------|---------|---------|
| status_code | `response.code == {v}` | `assert resp["code"] == {v}` |
| http_status | `response.status_code == {v}` | `assert resp.status_code == {v}` |
| full_body | `response.body == {var}` | `assert resp == {var}` |
| field_equality | `response.{path} == {v}` | `assert resp["{path}"] == {v}` |
| comparison | `response.{path} >= {v}` | `assert resp["{path}"] >= {v}` |
| set_match | `set(response.{path}) == {set}` | `assert {comprehension} == {set}` |
| length | `len({x}) == {n}` | `assert len({x}) == {n}` |

### 项目专属模式（在 project_config.yaml 的 builtin_assertion_rules 中，换项目需替换）

| 模式名 | 匹配文本 | 生成代码 | 专属原因 |
|--------|---------|---------|---------|
| coupon_null | `coupon == null` | `assert resp["coupon"] is None` | coupon 业务概念 |
| coupon_top | `coupon.item_id` + `top_result` | `assert resp["coupon"]["item_id"] == max(...)["item_id"]` | coupon 选最高分 |
| linear_cal | `cal == round(clamp(k*s+b), 4)` | `assert cal == pytest.approx(...)` | 校准公式 |
| no_cal | `cal == s` | `assert cal == pytest.approx(s)` | 不校准场景 |

### Named templates（Python 实现，在 emitter engine 中）

| 模板名 | 用途 | 触发方式 |
|--------|------|---------|
| piecewise_cascade | 分段函数 + 线性串联 | profile assertion_rules 中 `template: piecewise_cascade` |
| piecewise_only | 仅分段函数 | profile assertion_rules 中 `template: piecewise_only` |
| skip | 跳过该断言 | profile assertion_rules 中 `template: skip` |

## 判断规则：通用 vs 模块特有

- 在 2+ 模块出现的断言模式 → 通用，写入 project_config.yaml
- 只在 1 个模块出现的断言模式 → 模块特有，写入该模块的 codegen_profile
- 需要生成 if/elif/else 块的复杂模式 → named_template（Python 实现）
- 简单的"匹配文本 → 替换生成代码" → YAML assertion_rule

## 提取后的验证标准

1. `aitest codegen --all --check` 通过（生成结果不变）
2. `pytest test_workspace/tests/generated/ -v` 全部通过
3. emitter.py 行数 < 500
