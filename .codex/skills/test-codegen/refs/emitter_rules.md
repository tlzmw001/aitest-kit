# test-codegen 生成规则参考

## 文件与命名

- `{case_file}.md` -> `test_workspace/generated/{target}/test_{module}_{suite}_{case_file_stem}.py`
- 函数名：TC-ID 小写、连字符转下划线，例如 `test_tc_mod_001`。
- generated 是编译产物；修复应回写 Markdown、profile、Harness 或 codegen。

## ModuleBinding

registry 从 canonical module package 推导：

```text
module package: test_workspace/targets/{target}/modules/{module}/
fixture import: test_workspace.targets.{target}.modules.{module}.fixture
fixture name: setup_{module}
object name: harness
```

策略绑定：

| strategy | pytest fixture | generated object |
|---|---|---|
| default_http | 默认 HTTP fixture | 无 Harness |
| structured_case_flow | `setup_{module}` | `harness` |
| custom_case_body | `setup_{module}` | `harness` |
| manual/skipped | 无 | 无 |

profile 不允许配置 `fixture`、`object`、`default_fixture`、`default_object`、`default_case_setup` 或 `case_fixtures`。suite profile 也不允许 `extra_imports`。

## Harness contract

- `fixture.py` 只公开 `setup_{module}` 并直接 return/yield `{Module}Harness`。
- flow 固定调用 `harness.*` 或前序生成变量。
- Harness 内部可组合 API client、资源管理、复杂计算和私有 fixture。
- suite 不能直接引用 pytest fixture 名，如 `tmp_path`、`caplog`、`monkeypatch`、`mocker`。
- 未使用的 capability 不应在 fixture setup 阶段读取自己的可选 env 或建立连接。
- module 专属能力放 module package；target helpers 只保留已有多 module 复用的纯技术适配；不建立 workspace 顶层 helpers。

## 请求生成

1. 默认 HTTP 从 Markdown 共享基础请求体开始。
2. `requests.<case_id>.overrides` 适合简单字段覆盖。
3. `patches` 用于嵌套替换、列表追加/定位、字段删除和变量注入。
4. patch 支持 `add`、`replace`、`remove`；`value_from` 引用 profile variables。
5. flow 需要请求体时使用 `{request_ref: self}` 或指定 TC-ID，不把 JSON 写成字符串。
6. module profile 只提供稳定 defaults；TC-ID 请求绑定必须在 suite profile。

## case_flow

支持四类 step：

- `call`：调用 `harness` 或前序变量的方法。
- `assign`：用显式表达式生成中间变量。
- `assert`：可执行 Python 断言，必须以 `assert ` 开头。
- `comment`：生成注释，不代表执行能力。

规则：

- flow 顶层只写 `description`、`steps`。
- `args/kwargs` 可使用字面量、`{ref: name}`、`{expr: ...}`、`{var: name}`、`{request_ref: ...}`。
- 非 manual flow 至少包含一个 call/assert。
- pure manual 不写 flow；半自动 manual 可写可执行 flow/body 并保留 marker。
- 不给 YAML 增加 if/for/while/try。复杂控制优先封装 Harness capability。
- 同一个 case_id 不得同时存在于 case flow 和 case body。

## case_body

case body 是复杂运行器控制的逃生通道：并发、进程、mock、复杂文件生命周期或测试函数本身必须保留的分支/循环。

generated 形态固定为：

```python
def test_xxx(self, setup_demo):
    harness = setup_demo
    # profile case_body
```

case body 不能通过额外 fixture 改函数签名，也不应 import module 私有能力绕过 Harness。

## 断言生成

优先级：module/profile `assertion_rules` > `aitest.yaml` builtin rules > UNPARSED。

- JSONPath、列表遍历、字段存在和长度优先用 `structured_assertions`。
- default HTTP 的 structured target 为 `resp`。
- flow 的 structured target 必须是当前 flow 的 `save_as`/`assign` 变量。
- 复杂业务公式或重复遍历可封装为 Harness 方法，flow 断言返回值。
- UNPARSED 必须回写源层，不直接手改 generated。

## 标记处理

- `[manual]` pure manual：manual metadata，不写 comment-only flow。
- `[manual]` 半自动：可生成 flow/body，默认 run 仍排除 manual。
- `[!可行性存疑]`：skipped，保留原因和恢复条件。
- manual/skipped 不能成为 promotion 的业务规则证据。

## Profile 归属

module profile `modules/{module}/profile.md`：

- `assertion_rules`
- `variables.defaults`
- 必要且稳定的 module-level imports

suite profile：

- `variables`
- `requests`
- `structured_assertions`
- `case_flows`
- `case_bodies`

`module_type` 只写 `module.yaml`。测试全部通过且出现重复稳定模式后，使用 `emitter-build` 评估晋升。
