---
name: test-codegen
description: 从 parser 结构化输出 + helpers API 生成 pytest 代码
when_to_use: 当用户需要将 Markdown 测试用例编译为 pytest 可执行代码时
argument-hint: <target_module> [--dry-run]
arguments: [target_module, dry_run]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# 测试代码生成

将 `$target_module` 模块的 Markdown 用例编译为 pytest 代码。

## 前置：运行 parser

1. 执行 `python3 -m aitest_kit.codegen.parser test_workspace/cases/$target_module/business.md`，获取结构化输出
2. 如果存在 `boundary.md`，同样执行 parser
3. 读取 parser 输出，理解共享配置和每条用例的结构

如果 `$dry_run` 为 true，只输出可生成/不可生成用例列表，不生成代码。

## 前置：读取 helpers API

读取以下文件，了解可用的 fixtures 和 helper 函数签名：

- `test_workspace/tests/conftest.py` — pytest fixtures
- `test_workspace/tests/helpers/http.py` — HTTP 客户端
- `test_workspace/tests/helpers/redis_ops.py` — Redis 操作

## 前置：读取 codegen profile（如果存在）

检查 `test_workspace/cases/$target_module/codegen_profile.md` 是否存在。如果存在，读取并应用其中的模块特有规则：

- **fixture 依赖**：生成代码中使用 profile 指定的 fixture 名称和参数
- **请求模板**：用 profile 中的 items、字段差异覆盖通用规则
- **断言模式**：profile 中的模块特有断言翻译规则优先于下方通用断言表
- **setup 映射**：按 profile 中的"场景变量描述 → _CASE_CONFIGS 映射"生成 setup 注释

如果不存在 profile，使用下方通用规则生成。生成完毕后在摘要中提示"建议跑通测试后编写 codegen_profile.md"。

## 生成规则

### 文件结构

每个 Markdown 文件生成一个 pytest 文件：
- `business.md` → `test_workspace/tests/generated/test_{module}_business.py`
- `boundary.md` → `test_workspace/tests/generated/test_{module}_boundary.py`

文件头部固定：

```python
# Auto-generated from {source_path}
# DO NOT EDIT — regenerate with: /test-codegen {module}
import pytest
from test_workspace.tests.helpers import http as http_helper
```

### 类和函数命名

- 类名：`TestCalibrationBusiness`（模块名首字母大写 + Business/Boundary）
- 函数名：`test_tc_cal_001`（TC ID 小写，连字符转下划线）
- docstring：`"""TC-CAL-001：{title}"""`

### setup 处理

场景变量中的前置操作、环境覆盖等 → 生成为 `# SETUP:` 注释，然后调用模块 fixture：

```python
# SETUP: 前置操作：线性校准文件规则 conditions={"device":"mobile"}, k=1.2, b=0.1
setup_calibration(case_id="TC-CAL-001")
```

fixture 名称为 `setup_{module}`，由 conftest.py 提供。如果 conftest 中还没有该 fixture，在生成文件末尾添加 TODO 注释提醒。

### 请求生成

1. 从共享配置取基础请求体
2. 场景变量中的 `请求覆盖` → 合并到基础请求体（JSON merge）
3. 场景变量中的 `协议` 决定调用方式：
   - `HTTP` 或无协议字段 → `http_helper.post(http_base_url, path, json=body)`
   - `gRPC` → 生成 `# TODO: gRPC call` 注释（第一版不实现 gRPC helper）
4. `{{user_id}}` 替换为 `u_{module}_{tc_number}`（如 `u_cal_001`）
5. `{{req_id}}` 替换为 `req_{module}_{tc_number}`

### 断言生成

按断言内容分派：

| 断言模式 | 生成方式 |
|---------|---------|
| `response.code == 固定值` | `assert resp["code"] == 固定值` |
| `response.xxx == 固定值` | `assert resp["xxx"] == 固定值` |
| `cal == s` | `assert cal == pytest.approx(s)` |
| `cal == round(clamp(k * s + b), 4)` | `assert cal == pytest.approx(max(0, min(1, k * s + b)), abs=1e-4)` |
| `coupon == null` | `assert resp["coupon"] is None` |
| `coupon.item_id == top_result.item_id` | `assert resp["coupon"]["item_id"] == max(resp["results"], key=lambda r: r["score"])["item_id"]` |
| `set(response.results[*].item_id) == {集合}` | `assert {r["item_id"] for r in resp["results"]} == {集合}` |
| `len(xxx) == N` | `assert len(xxx) == N` |
| 包含 `[manual]` 或自然语言描述 | `# MANUAL CHECK: {原文}` |
| 无法翻译为代码 | `# UNPARSED ASSERTION: {原文}` |

关系断言中引用共享配置的变量定义时，在函数体中先提取变量：

```python
s = resp["results"][0]["score"]
cal = resp["results"][0]["calibrated_score"]
```

`round(..., 4)` 映射为 `pytest.approx(..., abs=1e-4)`。
`clamp(x, 0, 1)` 或 `clamp(x)` 映射为 `max(0, min(1, x))`。

### 标记处理

- `[manual]` → 函数加 `@pytest.mark.manual`，所有断言生成为 `# MANUAL CHECK:` 注释
- `[!可行性存疑: ...]` → **跳过该用例不生成**，在文件末尾添加注释：`# SKIPPED: TC-XXX — [!可行性存疑: 原因]`

### 通用断言

共享配置的通用断言自动插入每个 test 函数（标记为 manual 的除外）。

## 质量要求

1. 生成的代码必须是合法 Python，能通过 `python3 -c "import ast; ast.parse(open('file').read())"`
2. 每个 test 函数必须是独立的，不依赖其他 test 的执行顺序
3. 不要在生成代码中 import 待测服务的内部模块
4. 不要硬编码 localhost 端口，通过 fixture 获取 base_url
5. 不要发明用例中没有的断言

## 输出

生成完毕后输出摘要：

```
## codegen 摘要

模块：{module}
生成文件：
- test_{module}_business.py — N 条用例
- test_{module}_boundary.py — N 条用例

跳过（可行性存疑）：
- TC-XXX：原因

不可解析断言：
- TC-XXX：断言原文

TODO：
- setup_{module} fixture 需要手写
- gRPC 用例需要补充 helper
- （无 codegen_profile.md 时）建议跑通测试后编写 codegen_profile.md
```
