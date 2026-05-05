我按 `test-codegen` skill 把实际代码和现有生成物对了一遍。核心结论先放前面：这里不是“AI 直接从 md 写 pytest”，而是一个很明确的编译链路：

```text
test_workspace/cases/{module}/business.md 或 boundary.md
  -> parser.py 解析成 SharedConfig + TestCase[]
  -> planner.py 结合 project_config + codegen_profile 生成 Case IR
  -> emitter.py 调 ir_renderer.py 渲染 Case IR
  -> 生成 test_workspace/tests/generated/test_{module}_{business|boundary}.py
  -> pytest 导入 generated 文件
  -> conftest 注册模块 fixture
  -> 每条测试调用 setup_{module}(case_id=...)
  -> 调 HTTP/gRPC/helper/fixture case object
  -> 执行 assert
```

**一、入口**
用户命令入口是 [aitest_kit/cli.py](/Users/zmw/AIAutoTest/aitest_kit/cli.py:6)，它把 `codegen` 子命令挂到 `aitest` CLI 上。真正的 codegen 命令在 [aitest_kit/codegen/cli.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/cli.py:103)。

常用命令本质如下：

```bash
python3 -m aitest_kit.cli codegen calibration
python3 -m aitest_kit.cli codegen --all
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli codegen calibration --dry-run
python3 -m aitest_kit.cli codegen calibration --dump-ir
python3 -m aitest_kit.cli codegen calibration --explain TC-CAL-025
python3 -m aitest_kit.cli codegen --all --validate-profile --write-report
python3 -m aitest_kit.cli codegen --all --health-report --write-report
```

普通 codegen、`--check`、`--dump-ir`、`--explain` 和 promotion 分析现在都会先跑 profile 硬门禁；profile 有 ERROR 时不会进入 IR/emitter。`--dry-run` 只跑 parser，统计 Auto/Manual/Skipped，不写生成文件，也不要求 profile 通过。`--dump-ir`/`--explain` 用来观察单条用例为什么走 HTTP、gRPC、case_body、case_flow、manual 或 skip；普通 codegen 会调用 `emit_module()` 写入 generated；`--check` 会生成到临时目录，再和现有 generated 做 diff。

日常收口顺序建议固定为：

```bash
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --dump-ir
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli codegen --all
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

其中 `--dump-ir` 主要用于观察策略，不一定每次都人工读完；真正的阻断点是 profile gate 和 `--check`。

**二、parser：只负责把 Markdown 变结构化数据**
parser 的数据模型很简单：`SharedConfig`、`TestCase`、`ParseResult` 定义在 [parser.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/parser.py:14)。它不理解业务语义，只做确定性提取：

- `## 共享配置` 由 `_parse_shared_config()` 解析，提取接口、HTTP JSON 请求体、gRPC 文本请求体、标准前置、通用断言、变量定义，见 [parser.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/parser.py:112)。
- 每条 `### TC-XXX-001：标题` 由 `_parse_cases()` 解析，提取优先级、场景变量、断言、标记，见 [parser.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/parser.py:226)。
- 对外入口是 `parse_case_file(path)`，返回 `ParseResult`，见 [parser.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/parser.py:295)。

拿 calibration 举例，Markdown 里共享请求、通用断言、变量定义在 [business.md](/Users/zmw/AIAutoTest/test_workspace/cases/calibration/business.md:9)，`TC-CAL-001` 的场景变量和断言在 [business.md](/Users/zmw/AIAutoTest/test_workspace/cases/calibration/business.md:58)。parser 只会得到类似：

```python
SharedConfig(
  base_request_http={...},
  common_assertions=["response.code == 0"],
  variables={"s": "...", "cal": "..."}
)

TestCase(
  id="TC-CAL-001",
  title="线性校准按 kx+b 计算并 clamp",
  scenario_vars={"前置操作": "..."},
  assertions=["cal == round(clamp(1.2 * s + 0.1), 4)"]
)
```

**三、profile：每个模块的“生成规则补丁”**
模块 profile 由 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:11) 读取。它只取 `codegen_profile_{module}.md` 里的第一个 YAML 代码块，然后拆出这些配置：

- `assertion_rules`：模块专属断言规则，见 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:31)。
- `request_overrides`：按 case 覆盖请求字段，见 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:52)。
- `extra_imports`：给生成文件追加 import，见 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:66)。
- `case_fixtures`：某些 case 的函数签名不用默认 fixture，见 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:75)。
- `case_bodies`：完全手写某条用例的测试体，见 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:93)。
- `case_flows`：已验证 `case_bodies` 的结构化晋升形态，见 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:125)，校验规则见 [profile.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/profile.py:132)。

这里最关键的分叉是：标准模块尽量走“基础请求 + overrides + 断言规则”；复杂生命周期场景继续用 `case_bodies`；重复稳定的多步骤测试晋升为 `case_flows`。例如 calibration profile 主要提供断言规则，见 [codegen_profile_calibration.md](/Users/zmw/AIAutoTest/test_workspace/tests/fixtures/codegen_profile_calibration.md:88)；ab_service 现在用 `case_flows` 表达运行中 API 调用，文件/SDK/mock 场景保留 `case_bodies`，见 [codegen_profile_ab_service.md](/Users/zmw/AIAutoTest/test_workspace/tests/fixtures/codegen_profile_ab_service.md:68)；issuance 只把并发库存用例留在 `case_bodies`，见 [codegen_profile_issuance.md](/Users/zmw/AIAutoTest/test_workspace/tests/fixtures/codegen_profile_issuance.md:27)。

**四、project_config：全局默认生成规则**
全局配置加载在 [project_config.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/project_config.py:182)，最终形成 `DEFAULT_PROJECT`，见 [project_config.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/project_config.py:199)。它决定：

- 默认 HTTP import/call：`http_helper.post`
- 默认 gRPC import/call：`grpc_ops.recommend`
- 默认 API path：`/api/v1/recommend`
- `s`、`cal` 这类短变量如何展开
- 模块缩写如何生成 `u_cal_001` / `req_cal_001`
- 内置断言正则如何生成 pytest 代码

例如 `response.code == 0` 会变成 `assert resp["code"] == 0`；`cal == round(clamp(1.2 * s + 0.1), 4)` 会变成 `pytest.approx(...)`。这些内置规则定义在 [project_config.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/project_config.py:70)。

现在 `ProjectConfig` 会读取 `aitest_config/project_config.yaml` 里的 `modules:` 注册表，profile YAML 也可以声明 `module_type`。profile 体检会用 `module_type` 查 `module_types.requires`，例如 `isolated_service`、`multi_endpoint` 这类模块必须有 `case_bodies` 或 `case_flows` 支撑；没有满足时会在生成前被硬门禁拦住。

**五、emitter：真正写 pytest 文件**
主调用链在 [emitter.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/emitter.py:190)：`emit_module(module)` 依次找 `business.md`、`boundary.md`，每个文件先 `parse_case_file()`，再交给 `emit_file()`。

`emit_file()` 的主要流程在 [emitter.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/emitter.py:64)：

1. 算输出路径：`test_{module}_{file_type}.py`
2. 读取 profile 里的 rules、overrides、imports、case_bodies、case_flows
3. 如果 parser 有错误，返回 diagnostics，不生成残缺文件
4. 如果没有基础 HTTP 请求体，且未被 `case_bodies` 或 `case_flows` 覆盖，报 E002
5. 调 `build_file_ir()` 生成 Case IR，见 [emitter.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/emitter.py:146)
6. 如果 IR planner 有文件级 diagnostics，直接阻断生成
7. 调 `render_file_from_ir()` 渲染 pytest 文本，见 [emitter.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/emitter.py:164)
8. 最后 `write_text()` 写入 generated 文件，见 [emitter.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/emitter.py:175)

真正决定“这条用例走哪条生成路线”的是 [planner.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/planner.py:59) 的 `_strategy_for()`，优先级是：

```text
skipped > custom_case_body > structured_case_flow > manual > default_grpc > default_http
```

真正把 Case IR 写成 pytest 的是 [ir_renderer.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/ir_renderer.py:323) 的 `render_file_from_ir()`。单条用例的核心分叉在 [ir_renderer.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/ir_renderer.py:302) 的 `_render_test_function()`。

第一条路：profile 有 `case_bodies`。  
renderer 不再自动拼请求和断言，而是把 profile 里的 body 原样缩进到测试函数中，见 [ir_renderer.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/ir_renderer.py:152)。ab_service 的文件持久化用例仍是这样：profile 里的 `build_isolated_client(tmp_path, ...)` 直接出现在 [test_ab_service_business.py](/Users/zmw/AIAutoTest/test_workspace/tests/generated/test_ab_service_business.py:252)。

第二条路：profile 有 `case_flows`。
planner 会把它标成 `structured_case_flow`，renderer 按步骤生成“调用 helper -> 保存变量 -> 派生变量 -> 断言/注释”，见 [ir_renderer.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/ir_renderer.py:198)。目前 `validation_ratelimit` 已全部迁移到 `case_flows`；`rough_ranking` 的 23 条 recommend flow 已迁移；`issuance` 迁移 17 条并保留并发 `case_body`；`ab_service` 迁移 26 条运行中 API flow，并保留文件、subprocess、Remote SDK 生命周期和 mock 相关 body。schema 422 这组用 `assign` step 把 `locs = [item["loc"] for item in resp.json()["detail"]]` 结构化表达出来；manual 日志核查用 `comment` step 渲染为注释，见 [codegen_profile_validation_ratelimit.md](/Users/zmw/AIAutoTest/test_workspace/tests/fixtures/codegen_profile_validation_ratelimit.md:33)。

第三条路：默认推荐接口模板。
renderer 自动生成函数签名、setup 调用、请求体、HTTP/gRPC 调用、断言，见 [ir_renderer.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/ir_renderer.py:243)。calibration 的生成结果就是这样：Markdown 的 `TC-CAL-001` 被编译成 [test_calibration_business.py](/Users/zmw/AIAutoTest/test_workspace/tests/generated/test_calibration_business.py:32)，其中 `_req("u_cal_001", "req_cal_001")`、`http_helper.post(...)`、`assert cal == pytest.approx(...)` 都是 renderer 生成的。

**六、断言是怎么翻译的**
断言翻译集中在 [render_utils.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/render_utils.py:176) 的 `resolve_assertion()`。优先级非常重要：

```text
profile assertion_rules
  -> project_config builtin_assertion_rules
  -> named_templates
  -> # UNPARSED ASSERTION
```

比如 calibration 的分段校准不是一行 assert 能表达，所以 profile 用 `piecewise_cascade` 命名模板，见 [codegen_profile_calibration.md](/Users/zmw/AIAutoTest/test_workspace/tests/fixtures/codegen_profile_calibration.md:89)。真正把模板渲染成 `if/elif/else + pytest.approx` 的逻辑在 [render_utils.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/render_utils.py:103)。生成结果就是 [test_calibration_business.py](/Users/zmw/AIAutoTest/test_workspace/tests/generated/test_calibration_business.py:53) 里的分段计算。

如果规则都匹配不上，就会写 `# UNPARSED ASSERTION`，见 [render_utils.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/render_utils.py:197)。当前主要残留在 e2e 和 calibration boundary：e2e business 有 6 个，e2e boundary 有 8 个，calibration boundary 有 2 个。

**七、profile 格式门禁**
profile 仍然写在 `codegen_profile_{module}.md` 的 YAML 代码块里，但格式契约已经由中心 JSON Schema 管住：

```text
aitest_config/schemas/codegen_profile.schema.json
```

它负责检查顶层字段、基础类型、未知字段、`case_flow` step 形状；随后 Python 语义校验继续检查 case_id 是否存在、`case_bodies`/`case_flows` 是否冲突、`assert` step 是否显式以 `assert ` 开头、`ref` 是否引用前面保存过的变量、`module_type` 是否满足项目配置。格式错误不要等 pytest 执行时再查，先用：

```bash
python3 -m aitest_kit.cli codegen --all --validate-profile --write-report
```

这会在 `test_workspace/reports/codegen/latest/` 下写出每个模块的 profile validation Markdown/JSON。

**八、各模块现在的生成策略**
我按现有 profile 和 generated 统计了一下，模块大致分四类：

| 模块 | 当前生成方式 | 为什么这样 |
|---|---|---|
| `calibration` | 默认推荐接口 + profile 断言规则 | 主要是响应字段和校准公式断言，适合规则化 |
| `ab_experiment` | 默认推荐接口 + request_overrides + 断言规则 | 通过主服务推荐接口观察 AB 命中策略 |
| `feature_scoring` | 默认推荐接口 + request_overrides，部分 manual/skip | 特征和打分链路有些日志/故障注入无法纯黑盒自动化 |
| `scene_routing` | 默认推荐接口 + request_overrides + Redis fixture | 场景/兜底主要可通过请求字段和 Redis 状态控制 |
| `e2e` | 默认推荐接口 + request_overrides + 断言规则，但仍有 UNPARSED | 跨主服务、AB、Redis、发放记录，断言语义更复合 |
| `ab_service` | `case_flows` + `case_bodies` | 运行中 API CRUD 已结构化；文件持久化、Remote SDK 生命周期、mock 保留 body |
| `issuance` | `case_flows` + 1 条 `case_body` | 发放后查库存/查用户券/gRPC 查询已结构化；并发库存用例保留 body |
| `logging` | `case_bodies` | 需要启动隔离服务并采集日志 |
| `rough_ranking` | `case_flows` | 隔离主服务 + recording scoring gRPC proxy 留在 fixture，测试体已结构化 |
| `validation_ratelimit` | `case_flows` | 覆盖 HTTP schema、gRPC 字段、限流；可执行用例已结构化，存疑用例仍 skip |

可以用健康报告查看这些状态是否继续成立：

```bash
python3 -m aitest_kit.cli codegen --all --health-report --write-report
```

报告会统计每个模块的 case 总数、`case_flow` 数、`case_body` 数、UNPARSED 数、profile 错误数和成熟度。当前成熟度最高自动计算到 L3；L4 作为未来人工审计标记暂不自动产生。它不是新的源文件，只是 codegen 的体检产物。

一个容易踩的点：HTTP/gRPC 分流不是看标题，也不是看共享配置里的接口，而是 Case IR planner 检查场景变量的 value 是否包含 `"gRPC"`，见 [planner.py](/Users/zmw/AIAutoTest/aitest_kit/codegen/planner.py:52)。所以新增 gRPC 用例时，Markdown 的场景变量里要明确出现 `协议：gRPC` 这类内容，否则会走 HTTP 生成路径。你也可以用 `--explain TC-XXX` 看 `protocol.source` 到底来自哪个场景变量。

**九、pytest 执行时发生什么**
pytest 执行 generated 文件时，先加载 [conftest.py](/Users/zmw/AIAutoTest/test_workspace/tests/conftest.py:10)，这里注册了所有模块 fixture plugin，并提供 `http_base_url`、`grpc_target`、`ab_base_url`、`redis_url`，这些都能通过环境变量覆盖，见 [conftest.py](/Users/zmw/AIAutoTest/test_workspace/tests/conftest.py:26)。

默认 HTTP 请求走 [http.py](/Users/zmw/AIAutoTest/test_workspace/tests/helpers/http.py:10)，它用 `httpx.Client(transport=httpx.HTTPTransport())` 绕过系统代理，`post()` 会 `raise_for_status()` 并返回 JSON；需要断言 422 的场景用 `post_response()` 返回原始 `httpx.Response`，见 [http.py](/Users/zmw/AIAutoTest/test_workspace/tests/helpers/http.py:17)。

gRPC 请求走 [grpc_ops.py](/Users/zmw/AIAutoTest/test_workspace/tests/helpers/grpc_ops.py:28)，它把 dict 请求转成 protobuf request，再把响应转回 dict。issuance 这种模块则通过 fixture 返回领域操作对象，例如 `IssuanceCase.post_recommend()`、`grpc_recommend()`、`query_coupons()`，见 [issuance.py](/Users/zmw/AIAutoTest/test_workspace/tests/fixtures/issuance.py:121)。rough_ranking 更复杂，会启动 recording scoring server 和隔离主服务，见 [rough_ranking.py](/Users/zmw/AIAutoTest/test_workspace/tests/fixtures/rough_ranking.py:221)。

**十、执行命令**
完整跑测试前要先启动 Redis、AB 服务、打分 mock、主服务；这个流程在 [test_execution_guide.md](/Users/zmw/AIAutoTest/docs/usebook/test_execution_guide.md:103)。真正跑 pytest 的命令在 [test_execution_guide.md](/Users/zmw/AIAutoTest/docs/usebook/test_execution_guide.md:141)：

```bash
python3 -m pytest test_workspace/tests/generated/ -v
python3 -m pytest test_workspace/tests/generated/test_calibration_business.py -v
python3 -m pytest test_workspace/tests/generated/test_calibration_business.py::TestCalibrationBusiness::test_tc_cal_001 -v
python3 -m pytest test_workspace/tests/generated/ -v -m "not manual"
```

我这次没有启动外部服务跑全量集成测试，但做了两个不依赖服务的验证：

```bash
python3 -m aitest_kit.cli codegen --all --check
# All generated files are up to date.

python3 -m pytest test_workspace/tests/generated --collect-only -q
# 185 tests collected in 0.06s
```

所以当前可以确认两件事：Markdown/profile 到 generated 的编译结果是同步的；pytest 能成功导入并收集全部 185 条 generated 测试。真正执行这些测试时，失败排查顺序就是：先看是服务/环境连接失败，还是 fixture 前置不对，还是断言规则/profile 生成不对，最后才考虑 Markdown 用例本身要修。
