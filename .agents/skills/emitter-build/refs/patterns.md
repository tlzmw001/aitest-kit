# emitter-build 模式与晋升参考

## 通用断言模式

跨模块复用的断言模式写入 `aitest_config/aitest.yaml` 的 `codegen.builtin_assertion_rules`。

| 模式 | 匹配正则 | 生成模板 |
|------|----------|----------|
| 状态码 | `` `response.code == {v}` `` | `assert resp["code"] == {v}` |
| 状态码(HTTP) | `` `response.status_code == {v}` `` | `assert resp.status_code == {v}` |
| 完整响应体 | `` `response.body == {var}` `` | `assert resp == {var}` |
| 字段等值 | `` `response.{path} == {v}` `` | `assert resp{["path"]} == {v}` |
| 集合匹配 | `` `set(response.{path}) == {set}` `` | `assert {comprehension} == {set}` |
| 长度 | `` `len({x}) == {n}` `` | `assert len({x}) == {n}` |
| 近似相等 | `` `{x} == round(clamp({expr}), 4)` `` | `assert {x} == pytest.approx(max(0, min(1, {expr})), abs=1e-4)` |
| 恒等 | `` `{x} == {y}` ``（两个变量） | `assert {x} == pytest.approx({y})` |

特殊状态不是晋升结果：

- `[manual]` pure manual：生成 manual 标记和人工检查说明，不写 comment-only `case_flow`
- `[manual]` 半自动：可以保留可执行 `case_flow` / `case_body`，但仍保留 manual marker
- `[!可行性存疑]`：跳过或进入 `__codegen_skipped__`，不写执行 flow
- UNPARSED：待补断言规则或待人工补写，不直接视为可沉淀模式

项目专属模式的完整清单见 `aitest_config/aitest.yaml` 的 `codegen.builtin_assertion_rules`。

## 模块特有断言模式

当断言代码无法用通用模式覆盖，但属于某个 module 的 L1 稳定能力时，写入 module profile 的 `assertion_rules`：

```yaml
assertion_rules:
  - name: rounded_score
    regex: "^score == round\\((?P<expr>.+), 4\\)$"
    template: |
      assert score == pytest.approx(round({expr}, 4), abs=1e-4)

  - name: publish_status_all_zero
    pattern: "response.data.items 中每条记录的 publishStatus == 0"
    template: |
      client.assert_all_publish_status(resp, 0)
```

规则：

- `pattern`、`regex`、`template`、`extract_vars`、`params`、`name` 是 schema 支持字段。
- 模块特有 assertion_rules 写 module profile。
- 具体 TC-ID 的执行流程写 suite profile，不写 module profile。
- 复杂循环/分支断言优先抽成 fixture/helper 方法，再由 `case_flow` 调用。

## 断言模式分类

| 出现范围 | 归属 |
|---|---|
| 2+ 模块，语义与项目无关 | `aitest.yaml.codegen.builtin_assertion_rules` |
| 只在当前 module，L1 稳定能力 | module profile `assertion_rules` |
| 只服务当前 suite / TC-ID | suite profile `case_flows` 或 `case_bodies` |
| 需要循环、分支、复杂遍历 | 先抽 fixture/helper，再由 `case_flow` 调用 |

## case_bodies 提取规则

`case_bodies` 是复杂场景逃生通道，不是默认路线。只从已验证通过的 pytest 提取。

提取步骤：

1. 从 generated pytest 函数中去掉 emitter 自动生成部分，例如 docstring、`__tc_meta__`、`# SETUP:` 注释。
2. 保留真正业务执行代码，写入 suite profile 的 `case_bodies.{tc_id}`。
3. 从函数签名提取 fixture 参数（去掉 `self`），写入 suite profile 的 `case_fixtures.{tc_id}`。
4. 与 suite profile 已有 `case_bodies` diff：
   - 一致：无需更新。
   - generated 中有验证通过的修正：回写 suite profile 后重新 codegen。
   - suite profile 中没有：新增为首次提取。
5. 如果 3+ 个 body 结构相似，输出晋升候选；不自动晋升，不静默改写 profile。

晋升为 `case_flow` 时，必须同时删除对应旧 `case_body`。同一个 case_id 同时存在于 `case_bodies` 和 `case_flows` 会被 profile gate 视为错误。

保留 `case_body` 的合理场景：

- 线程池、子进程、服务生命周期管理
- 复杂 `for` / `while` / `if` 控制流
- monkeypatch、mock transport、日志 handler 注入
- 文件持久化和临时目录生命周期本身就是测试主体
- 高风险资源创建、扣费、真实账号状态修改等需要人工门禁的流程

## case_flow 提取规则

`case_flow` 适合稳定的 Arrange / Act / Observe / Assert 多步骤流程。当前支持：

- 调用 fixture/helper 对象方法
- `args` / `kwargs` 传入字面量、`ref` 引用或显式 `expr`
- `save_as` 保存中间变量
- `assign` 用显式 `expr` 派生中间变量
- `assert` 使用可执行 Python 断言，必须以 `assert ` 开头
- `comment` 渲染受控注释

边界：

- 自然语言断言不要直接写进 `case_flow.assert`；先转为 assertion_rule、helper 方法或人工确认的 Python assert
- 复杂循环断言优先抽 helper，例如 `client.assert_all_publish_status(resp, 0)`
- 循环/分支逻辑本身就是测试主体时，保留 case_body
- 不要用 comment-only flow 代表 manual；pure manual 不写 profile entry

## 晋升分类

| 晋升目标 | 适用场景 | 写入位置 |
|----------|----------|----------|
| `promote_to_assertion_rule` | 请求/flow 已稳定，只有断言可模板化 | module profile 或 `aitest.yaml` |
| `promote_to_case_flow` | 多步骤流程稳定，差异主要是参数和期望值 | suite profile |
| `promote_to_helper` | 多个 body/flow 重复 Python 逻辑 | fixture/helper |
| `promote_to_default_template` | 可退回 default_http/default_grpc，且默认模板真实适配 | suite profile request_overrides |
| `promote_to_named_template` | 需要受控 if/elif/else，且跨模块稳定 | emitter/renderer |
| `keep_case_body` | 少见、复杂、并发、mock 等暂不晋升 | suite profile |

推荐顺序：assertion_rule → case_flow → fixture/helper → keep_case_body → emitter/renderer 规则最后。

不要因为 default_http/default_grpc 已存在就强行退回默认模板；多端点项目通常应优先使用 fixture Client + case_flow。

## 晋升条件

建议晋升必须满足：

1. 至少 3 条已验证通过的 case_body 或 flow 结构相似。
2. 差异主要是参数、期望值、case_id 或 profile variables。
3. 使用 fixture/helper 暴露的公开测试能力。
4. 晋升后比原 case_body 更可读、更可解释。
5. 晋升后 `--validate-profile`、`--check`、collect 能通过。

不满足时保留 case_body，并在输出摘要中说明原因。

## IR 对齐项

| 对齐项 | IR/profile/parser 输出 | generated pytest |
|---|---|---|
| case identity | `case_id/module/suite/source_file` | `__tc_meta__` |
| 断言文本 | `TestCase.assertions` / `AssertionIR.source` | `assert ...` / manual check / UNPARSED 注释 |
| 执行策略 | `CaseIR.strategy` | 默认模板、case_flow、case_body、manual skip |
| fixture | `CaseIR.fixtures` / profile defaults | 函数参数、fixture import、对象创建 |
| flow steps | `case_flows.{tc_id}.steps` | call / assign / assert / comment 代码 |
| skipped | `__codegen_skipped__` / strategy skipped | 未生成 test 函数或显式 skip |

## 分类产出规则

- 在 2+ 模块出现的断言模式 → 通用，写入 `aitest.yaml.codegen.builtin_assertion_rules`
- 只在 1 个模块出现、且属于 L1 稳定能力 → 模块特有，写入 module profile
- 只服务当前 suite 或当前 TC-ID → 写入 suite profile
- 多个 case 重复 Python 动作 → 抽 fixture/helper
- 需要生成 if/elif/else 块且跨模块稳定 → named_template 或 emitter/renderer
- 简单"匹配文本 → 替换生成代码" → YAML assertion_rule

## 验证命令

### suite 级

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --check
python3 -m aitest_kit.cli run --suite-file <suite.yaml> -- --collect-only -q
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --health-report --write-report
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --analyze-promotion --write-report
python3 -m aitest_kit.cli codegen --suite-file <suite.yaml> --suggest-promotion-patch
```

### module / target 聚合

```bash
python3 -m aitest_kit.cli codegen --target <target> --module <module> --check
python3 -m aitest_kit.cli codegen --target <target> --module <module> --health-report --write-report
python3 -m aitest_kit.cli codegen --target <target> --module <module> --analyze-promotion --write-report

python3 -m aitest_kit.cli codegen --target <target> --check
python3 -m aitest_kit.cli codegen --target <target> --health-report --write-report
python3 -m aitest_kit.cli codegen --target <target> --analyze-promotion --write-report
```

约束：

- `--suggest-promotion-patch` 只建议 suite 级使用
- target/module 聚合适合发现趋势和候选组，不适合直接生成可应用 patch
- `promotion_report.md/json` 用于解释和工具消费
- `promotion_patch.md/diff` 是 review-only 草案，默认不自动修改 profile
