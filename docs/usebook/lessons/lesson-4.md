# Lesson 4：Markdown Parser 的输入输出

> 学习目标：理解 `parser.py` 在 codegen 链路中的边界。parser 只负责把 Markdown 用例文件解析成结构化数据，不负责选择生成策略，也不负责生成 pytest。

## parser 在链路中的位置

```text
business.md / boundary.md
  -> parser.py::parse_case_file()
  -> ParseResult
  -> planner.py::build_file_ir()
  -> FileIR
  -> ir_renderer.py
  -> generated pytest
```

parser 的职责：

```text
把 Markdown 文件确定性解析成 Python 数据结构。
```

parser 不负责：

```text
判断这条用例走 default_http 还是 case_flow
生成 pytest
翻译自然语言断言
合并 request_overrides
检查 profile 是否存在
```

## parser 的输入

输入是一个 Markdown 文件，例如：

```text
test_workspace/cases/calibration/boundary.md
```

文件里通常包含：

```markdown
## 共享配置

**接口**：`POST /api/v1/recommend`

**基础请求体（HTTP）**：
```json
{ ... }
```

### TC-CAL-015：校准目录不存在时降级为不校准
- **优先级**：P2 / 异常
- **场景变量**：环境覆盖：`calibration_dir.linear="/tmp/not_exists_cal_linear_011"`，目录不存在
- **断言**：`cal == s`
```

## parser 的输出

输出是一个 `ParseResult`：

```python
ParseResult(
    module="calibration",
    source_file="test_workspace/cases/calibration/boundary.md",
    shared_config=SharedConfig(...),
    cases=[
        TestCase(...),
        TestCase(...),
    ],
    errors=[...],
)
```

核心结果分成四块：

| 字段 | 含义 |
|---|---|
| `module` | 当前模块名，来自 Markdown 文件的父目录名 |
| `source_file` | 当前 Markdown 文件路径 |
| `shared_config` | `## 共享配置` 解析结果 |
| `cases` | 当前文件中的测试用例列表 |
| `errors` | Markdown 结构或 JSON 解析错误 |

## 三个核心 dataclass

### SharedConfig

`SharedConfig` 对应 Markdown 里的 `## 共享配置`：

```python
@dataclass
class SharedConfig:
    interfaces: list[str] = field(default_factory=list)
    base_request_http: dict | None = None
    base_request_grpc: str | None = None
    preconditions: list[str] = field(default_factory=list)
    common_assertions: list[str] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
```

| 字段 | 来自 Markdown 哪里 |
|---|---|
| `interfaces` | `**接口**` |
| `base_request_http` | `**基础请求体（HTTP）**` 的 JSON block |
| `base_request_grpc` | `**基础请求体（gRPC）**` 的 text block |
| `preconditions` | `**标准前置**` |
| `common_assertions` | `**通用断言**` |
| `variables` | `**变量定义**` |

### TestCase

`TestCase` 对应每一个 `### TC-...`：

```python
@dataclass
class TestCase:
    id: str = ""
    title: str = ""
    priority: str = ""
    scenario_vars: dict[str, str] = field(default_factory=dict)
    assertions: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    section: str = ""
```

| 字段 | 来自 Markdown 哪里 |
|---|---|
| `id` | `TC-CAL-015` |
| `title` | `校准目录不存在时降级为不校准` |
| `priority` | `- **优先级**：...` |
| `scenario_vars` | `- **场景变量**：...` |
| `assertions` | `- **断言**：...` |
| `markers` | `- **标记**：...` |
| `section` | 上层二级章节，例如 `目录与文件异常` |

### ParseResult

`ParseResult` 是整个 Markdown 文件的结构化结果：

```python
@dataclass
class ParseResult:
    module: str = ""
    source_file: str = ""
    shared_config: SharedConfig = field(default_factory=SharedConfig)
    cases: list[TestCase] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

可以把它理解成 parser 输出的 AST。

## parse_case_file 主流程

```python
def parse_case_file(path: str | Path) -> ParseResult:
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    module = path.parent.name
    shared_config, config_end, errors = _parse_shared_config(lines)
    cases = _parse_cases(lines, config_end)

    return ParseResult(
        module=module,
        source_file=str(path),
        shared_config=shared_config,
        cases=cases,
        errors=errors,
    )
```

关键点：

- `path.read_text(...).splitlines()` 把 Markdown 文件读成行列表。
- `module = path.parent.name` 表示模块名来自目录结构，不来自 Markdown 标题。
- `_parse_shared_config(lines)` 解析共享配置。
- `_parse_cases(lines, config_end)` 从共享配置结束之后开始解析用例。
- 最终返回 `ParseResult`。

## parser 的边界

parser 只做确定性结构提取。

它会识别：

```text
共享配置
接口
HTTP JSON 请求体
gRPC text 请求体
标准前置
通用断言
变量定义
TC 标题
优先级
场景变量
断言
标记
章节
```

它不会做：

```text
不会判断 HTTP/gRPC 该用哪个
不会把断言翻译成 Python assert
不会判断某个 case 是否应该 case_flow
不会合并 request_overrides
不会生成 pytest
不会检查 profile 是否存在
```

如果 parser 解析出来的 `scenario_vars` 还是自然语言字符串，这是正常的。

后面要么 profile 接管，要么 planner/emitter 的规则接管，要么 AI 补写。

## parser 可以单独运行调试

`parser.py` 可以作为模块直接运行：

```bash
python3 -m aitest_kit.codegen.parser test_workspace/cases/calibration/boundary.md
```

它会打印：

```text
Module
Source
Shared Config
Cases
```

示例输出：

```text
Module: calibration
Source: test_workspace/cases/calibration/boundary.md

=== Shared Config ===
  Interfaces: ['POST /api/v1/recommend', 'gRPC coupon.CouponService/Recommend']
  HTTP body keys: ['user_id', 'scene_name', 'device', 'policy_id', 'external', 'reqId', ...]
  gRPC body: yes
  Preconditions: 4
  Common assertions: ['`response.code == 0`']
  Variables: {'s': '`response.results[0].score`', 'cal': '`response.results[0].calibrated_score`', ...}
```

逐条 case 会打印：

```text
TC-CAL-022: 分段区间配置非法时跳过该段
  Priority: P2 / 异常
  Section: 分段边界
  Scenario vars: {
    '请求覆盖': '第一段 ...',
    '请求覆盖_2': '请求命中条件'
  }
  Assertions: ['`cal == s`']
```

所以如果怀疑 Markdown 没被正确解析，第一步可以直接跑：

```bash
python3 -m aitest_kit.codegen.parser <某个 md 文件>
```

先确认 parser 输出是不是符合预期。

注意：

```text
parse_case_file() 返回 ParseResult，是代码接口。
python -m aitest_kit.codegen.parser 输出文本，是调试视图。
```

后续 codegen 不会解析这个文本输出。后续代码拿的是内存对象 `ParseResult`。

## parser errors 如何进入 profile validator

`profile_validator.py` 也会调用 parser。

核心逻辑：

```python
def _collect_markdown_cases(report: ProfileValidationReport, module_dir: Path) -> None:
    ...
    parse_result = parse_case_file(md_path)
    for parser_error in parse_result.errors:
        _error(report, "E001", parser_error, str(md_path))
    report.case_ids.update(tc.id for tc in parse_result.cases)
```

它的目的有两个：

第一，收集 Markdown 里的 case_id：

```python
report.case_ids.update(tc.id for tc in parse_result.cases)
```

这样才能检查 profile 里写的 case_id 是否真的存在。

第二，把 parser error 转成 profile validation error：

```python
_error(report, "E001", parser_error, str(md_path))
```

所以：

```bash
aitest codegen --all --validate-profile
```

也能发现 Markdown JSON 错误。

这点很重要：

```text
profile gate 不只是检查 profile 本身，也会检查 Markdown 源用例是否有 parser error。
```

## parser errors 如何进入 Case IR

`planner.py` 会把 `ParseResult` 转成 `FileIR`。

如果 parser 有错误，会进入 `FileIR.diagnostics`：

```python
file_ir = FileIR(
    module=parse_result.module,
    category=category,
    source_file=parse_result.source_file,
    diagnostics=[
        DiagnosticIR(code="E001", layer="parser", message=error)
        for error in parse_result.errors
    ],
)
```

如果运行：

```bash
aitest codegen calibration --dump-ir
```

parser 错误会进入 FileIR 的 diagnostics：

```json
{
  "diagnostics": [
    {
      "code": "E001",
      "layer": "parser",
      "message": "..."
    }
  ]
}
```

这就是 `--dump-ir` 的价值之一：

```text
不仅能看每条 case 的策略，还能看 parser/planner 诊断在哪一层出现。
```
