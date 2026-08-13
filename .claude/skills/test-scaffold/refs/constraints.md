# test-scaffold 约束与校验参考

## Module Harness 硬约束

1. module package 固定为 `test_workspace/targets/{target}/modules/{module}/`。
2. `fixture.py` 只公开一个 pytest fixture：`setup_{module}`。
3. `setup_{module}` 直接 return/yield `{Module}Harness`，不返回 factory。
4. generated 对象固定命名为 `harness`；profile 不配置 fixture/object/setup。
5. fixture 不按 case_id 选择请求、账号、配置、资源或业务分支。
6. module-local 私有 fixture 必须以下划线开头，不对 profile 暴露。
7. 业务动作、复杂计算和资源 ownership 放 Harness 或同 package 的职责模块。
8. 必需 env 使用 `require_env()`/`require_envs()`；未使用的 capability 不提前读取其可选 env。
9. 不 import 待测系统内部实现，不硬编码 URL、端口或凭证。
10. 资源必须可追踪并 cleanup；只清理当前 Harness 实际创建的资源。

## Helper 归属

| 作用域 | 放置位置 | 条件 |
|---|---|---|
| 单 module | `modules/{module}/*.py` | 默认归属 |
| 同 target 多 module | `targets/{target}/helpers/` | 已有至少两个真实调用者 |
| 跨 workspace 框架能力 | `aitest_kit.helpers` | 稳定、项目无关、需发布维护 |

- 不建立 `test_workspace/helpers/`。
- target helper 只承载协议、认证、序列化等纯技术适配，不承载业务动作、测试数据或断言。
- 不为首次出现的代码提前抽公共 helper。

## 测试数据分类

| 类别 | 处理方式 |
|---|---|
| 凭证 | profile `variables` 声明 env 名，运行时 `require_env()` fail-fast |
| case 级资源/账号 | `variables.cases` + `{var: name}` |
| 请求体差异 | `requests.<case_id>.patches`，简单顶层覆盖可用 `overrides` |
| 唯一资源 | suite 显式传入 namespace/request id，Harness 创建并记录 cleanup |
| 非法输入 | suite profile 固定 value |
| 复杂准备 | Harness capability，参数由 suite flow 显式传入 |

运行时 case context 只用于 capture/log 归因，不得作为请求差异或业务分支输入。

## case_flow 规则

- flow 顶层只允许 `description` 和 `steps`。
- steps 只用 `call`、`assign`、`assert`、`comment`。
- 根调用只能是固定 `harness` 或前序 `save_as`/`assign` 变量。
- 不直接引用 `tmp_path`、`caplog`、`monkeypatch`、`mocker` 等 pytest fixture。
- `assert` 必须以 `assert ` 开头。
- args/kwargs 使用字面量、`{ref: name}`、`{expr: ...}`、`{var: name}` 或 `{request_ref: ...}`。
- 不在 YAML 中增加 if/for/while/try；复杂控制封装为 Harness capability。
- 非 manual flow 至少有一个 `call` 或 `assert`；pure manual 不写 flow。
- suite profile 禁止 `extra_imports`；需要的新能力先进入 module package。
- case body 作为逃生通道，但 generated 也只注入 `harness`。

## module profile 与 suite profile

module profile 只允许模块级稳定内容：

- `assertion_rules`
- `variables.defaults`
- 确有必要的 module-level imports

suite profile 承载：

- `variables`
- `requests`
- `structured_assertions`
- `case_flows`
- `case_bodies`

TC-ID 绑定内容不得写回 module profile。`module_type` 只在 `module.yaml` 中声明。

## 路线选择

1. 默认 HTTP + request patches 足够：使用 default_http。
2. JSONPath/集合/长度断言：使用 structured assertions。
3. 多步骤或调用 module capability：使用 case_flow。
4. 循环、条件、等待、mock 可封装：增加 Harness capability，再由 flow 调用。
5. 测试函数本身必须保留复杂运行器控制：使用 case_body，并记录原因。

不把 case_flow 扩展成通用编程语言，也不为减少 YAML 行数把业务差异藏进 case_id 分发表。

## 验证命令与预期

```bash
# 1. workspace 与 Harness contract
python3 -m aitest_kit.cli doctor

# 2. module package 语法
python3 -m compileall test_workspace/targets/{target}/modules/{module}

# 3. profile gate 与 IR
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --explain <TC-ID>

# 4. 生成与 freshness
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --check

# 5. collect
python3 -m compileall test_workspace/generated/{target}
python3 -m aitest_kit.cli run --suite-file <suite_dir>/suite.yaml -- --collect-only -q

# 6. 已注册 suite 的聚合接线
python3 -m aitest_kit.cli codegen --target <target> --module <module> --check
python3 -m aitest_kit.cli run --target <target> --module <module> -- --collect-only -q
```

| 门禁 | 预期 | 失败归属 |
|---|---|---|
| doctor | Harness contract 无 FAIL | module package/registry |
| validate-profile | 0 ERROR | profile |
| dump-ir/explain | fixture=`setup_{module}`，object=`harness` | binding/planner |
| check | up to date | generated freshness |
| compileall | 0 error | Python 代码 |
| collect | 可执行 case 数正确 | import/fixture/generated |

collect 数量按 manual/skipped 规则计算，不通过 skip 或放宽断言伪造成功。
