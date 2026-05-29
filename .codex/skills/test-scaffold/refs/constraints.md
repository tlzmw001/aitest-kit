# test-scaffold 约束与校验参考

## Fixture 硬约束

1. **auth fail-fast** — auth 标注为 yes 的方法，对应的 env var 必须用 `aitest_kit.runtime_variables.require_env()` 读取；缺失时报告归类为 `PRECONDITION_MISSING`，不构造空 header
2. **注入模型二选一** — fixture 返回 Client 实例（`object: client`）或 factory（`object: client_factory`），不混用
3. **不做 case_id 分发** — 不生成 `run_case(case_id)` / `assert_case(case_id, resp)` 分发 dict
4. **不 import 待测系统内部模块**
5. **不硬编码 URL、端口、API key、密码**

## 测试数据分类

| 类别 | 处理方式 | 示例 |
|------|---------|------|
| 凭证类 | env var + `require_env()` fail-fast | token, password, API key |
| 唯一资源 | 动态生成（uuid/timestamp） | email, name, request_id |
| 非法输入 | 可固定 | 不存在的模型名 |
| 业务输入 | 可固定，注明来源 | 日期窗口、模型名 |

## Fixture 注入一致性

**方案 A（推荐）**：fixture 返回 Client → `object: client` → fixture 不出现在 steps 里。
**方案 B**：fixture 返回 factory → `object: client_factory` → 第一步 `call: client_factory`。

禁止混用（`fixture: setup_xxx` + `object: client` + steps 首步 `call: setup_xxx` → 双重赋值）。

当多条 flow 都使用同一注入方式时，优先在 profile 顶层写 `default_fixture` / `default_object`。factory 模式再加 `default_case_setup`，例如 `case = client_factory(case_id="{case_id}")`，不要在每条 case_flow 重复同一段 setup。

## case_flow 规则

- steps 只用 `call` / `assign` / `assert` / `comment`
- `assert` 以 `assert ` 开头，是可执行 Python
- 不塞 if/loop/try，复杂逻辑下沉到 fixture/helper
- kwargs/args 值为合法 Python 字面量、`{ref: previous_save_as}`、`{expr: python_expr}` 或 `{var: profile_variable_name}`
- `{var: name}` 只引用 suite/module profile 的 `variables.defaults` 或 `variables.cases.{case_id}`；缺 env 且 `.env` / `AITEST_ENV_FILE` 也无法提供时，会在运行时失败并只显示 env 名，不显示值
- 不用 fixture 按 case_id 选择账号/token；不同 case 的数据差异放到 profile variables
- 单条 case_flow 可以显式写 `fixture` 或 `object` 覆盖顶层默认值；否则必须能从 `default_fixture` 得到 fixture

## auto_fields 判断

判断是否配置 `aitest.yaml.codegen.default_request.auto_fields`。核心规则：只要有一个关键点不确定就不配置。多端点模块优先用 fixture Client + case_flows。只输出判断，不直接修改配置。

## module_type → 路线映射

实际可用的 module_type 从 `aitest.yaml.codegen.module_types` 读取；target/module 在 `modules/{module}.yaml` 声明本模块类型。

| module_type | 基线路线 |
|-------------|----------|
| `standard_http` | 默认模板 |
| `multi_endpoint` | case_flow |
| `isolated_service` | case_flow |

## 逐条 case 路线评估

1. 默认模板够吗？→ 只需 request_overrides
2. 加 assertion_rules 够吗？→ 增加 profile assertion_rules
3. 需要 case_flow？→ 多步骤 / 特定 Client 方法 / 中间变量
4. 需要 case_body？→ 条件分支、循环、mock、并发 → 记录保留原因

**api_map 中标为 skipped 的 case 不参与路线评估。**

## 验证命令与预期

```bash
# 1. target fixture/helper 语法检查
python3 -m compileall test_workspace/targets/{target}/fixtures/{module}.py test_workspace/targets/{target}/helpers

# 2. profile 门禁
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --validate-profile

# 3. Case IR 观测
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --dump-ir

# 4. 生成
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml

# 5. 一致性校验
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --check

# 6. 语法 + 收集
python3 -m compileall test_workspace/generated/{target}
python3 -m aitest_kit.cli run --suite-file <suite_dir>/suite.yaml -- --collect-only -q
```

使用 `python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> ...`；多个 suite 用 `--task-file`。

| 命令 | 预期 | 失败时 |
|------|------|--------|
| collect（suite） | fixture 被发现 | 检查 module.yaml fixture 声明和 generated import |
| `--validate-profile` | 无 ERROR | 修 profile YAML |
| `--dump-ir` | strategy 符合 Step 6 路线 | 修 case_flow/case_body 映射 |
| `codegen` | 生成 .py | 检查 import 路径 |
| `--check` | 无 stale | 重新 codegen |
| compileall | 无语法错误 | 修 Python 片段 |
| collect（模块） | 数量 = 可执行 case 数 | 检查 fixture 注册和 import |

collect 预期数量 = 总 case - skipped - manual，不追求最大化。
