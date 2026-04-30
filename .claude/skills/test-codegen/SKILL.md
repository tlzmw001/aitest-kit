---
name: test-codegen
description: 从 parser 结构化输出 + emitter 确定性生成 pytest 代码，AI 补写 UNPARSED 部分
when_to_use: 当用户需要将 Markdown 测试用例编译为 pytest 可执行代码时
argument-hint: <target_module> [--dry-run]
arguments: [target_module, dry_run]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# 测试代码生成

将 `$target_module` 模块的 Markdown 用例编译为 pytest 代码。

## 生成策略

采用 **emitter 优先 + AI 补全** 模式：

1. emitter（`aitest_kit/codegen/emitter.py`）确定性生成 .py，通用规则 + codegen_profile 特殊规则覆盖大部分断言
2. AI 只处理 emitter 输出的 `# UNPARSED ASSERTION:` 部分，将其翻译为可执行的 pytest 代码
3. `@pytest.mark.manual` 和 `# SKIPPED` 用例不需要 AI 补写

## 前置：新项目首次使用检查

如果这是一个新项目（没有任何 codegen_profile 存在），执行以下检查：

1. **项目配置** — 检查 `aitest_config/project_config.yaml` 是否存在且匹配当前项目（helper_import、api_path、var_map、module_abbrevs、builtin_assertion_rules）
2. **如果不存在**，参考现有 project_config.yaml 创建一份
3. **project_context.md** — 读取本 skill 目录下的 `project_context.md`，了解当前项目的断言模式表、路径约定、协议偏好、模块分类
4. **提醒用户**：首个模块的 UNPARSED 率可能较高，建议选断言模式最典型的模块作为第一个

## 前置：运行 parser

1. 执行 `python3 -m aitest_kit.codegen.parser test_workspace/cases/$target_module/business.md`，获取结构化输出
2. 如果存在 `boundary.md`，同样执行 parser
3. 读取 parser 输出，理解共享配置和每条用例的结构

如果 `$dry_run` 为 true，只输出可生成/不可生成用例列表，不生成代码。

## 前置：读取 helpers API

读取 `project_context.md`（本 skill 目录下）获取项目路径表，然后读取以下文件了解可用的 fixtures 和 helper 函数签名：

- 全局 conftest.py
- 模块 fixture（如果已存在）
- HTTP/gRPC/Redis helpers

## 第一步：emitter 生成

执行 emitter 生成 .py 文件：

```bash
python3 -m aitest_kit.codegen.emitter $target_module
```

检查输出摘要中的 UNPARSED 数量。

## 第二步：AI 补写 UNPARSED

读取 emitter 生成的 .py 文件，找到所有 `# UNPARSED ASSERTION:` 注释。

对每条 UNPARSED 断言：

1. 读取对应 TestCase 的完整上下文（scenario_vars、assertions、markers）
2. 读取 codegen_profile 中的断言模式表（如果存在）
3. 将 UNPARSED 注释替换为可执行的 pytest 断言代码

补写规则参考下方"断言生成"章节的映射表。自然语言描述无法翻译为代码的，保留 `# UNPARSED ASSERTION:` 不动。

**如果 UNPARSED 为 0**，跳过此步骤。

## 第三步：验证

1. `python3 -c "import ast; ast.parse(open('file').read())"` — 语法检查
2. `pytest --collect-only test_workspace/tests/generated/test_{module}_*.py` — 收集检查
3. 如果模块 fixture 和服务已就绪：`pytest test_workspace/tests/generated/test_{module}_*.py -v`

## 前置：读取 codegen profile

检查 `test_workspace/tests/fixtures/codegen_profile_$target_module.md` 是否存在。

**如果存在**，emitter 会自动加载其中的 YAML 规则段。AI 补写时也应参考 profile 中的断言模式、请求模板、setup 映射。

**如果不存在**：

1. 读取其他模块已有的 profile 作为参考（结构模板 + 通用模式），但不复制模块特有的断言逻辑
2. 生成完毕后在摘要中提示"建议跑通测试后编写 codegen_profile.md"

## emitter 生成规则参考

以下规则已内置于 emitter.py，供 AI 补写 UNPARSED 时参考。

### 文件结构

- `business.md` -> `test_workspace/tests/generated/test_{module}_business.py`
- `boundary.md` -> `test_workspace/tests/generated/test_{module}_boundary.py`

### 类和函数命名

- 类名：`TestCalibrationBusiness`（模块名首字母大写 + Business/Boundary）
- 函数名：`test_tc_cal_001`（TC ID 小写，连字符转下划线）
- docstring：`"""TC-CAL-001：{title}"""`

### setup 处理

场景变量 -> `# SETUP:` 注释 + `setup_{module}(case_id="TC-XXX")` 调用。

fixture 由 `test_workspace/tests/fixtures/{module}.py` 提供，通过 conftest.py 的 `pytest_plugins` 注册。

新增模块时需要：
1. 创建 `test_workspace/tests/fixtures/{module}.py`
2. 在 `conftest.py` 的 `pytest_plugins` 列表中添加

### fixture 编写检查清单

编写新模块的 `setup_{module}` fixture 前，确认：

1. **部署拓扑** — 服务间调用关系，确认环境变量（AB_SERVICE_URL、REDIS_URL 等）
2. **可用 API** — fixture 需要调用的管理接口（白名单 CRUD、库存初始化等）
3. **隔离策略** — 每条用例的数据如何隔离（tmp_path、唯一 user_id、teardown 恢复）
4. **teardown** — 所有副作用都能恢复（实验配置、白名单、Redis key）
5. **`_CASE_CONFIGS` 结构** — 参考 codegen_profile 的 setup 映射章节

### 断言生成

断言匹配优先级：profile assertion_rules > project_config builtin_assertion_rules > named_templates。

通用断言模式（框架内置）：

| 断言模式 | 生成方式 |
|---------|---------|
| `response.code == 固定值` | `assert resp["code"] == 固定值` |
| `response.xxx == 固定值` | `assert resp["xxx"] == 固定值` |
| `set(response.results[*].item_id) == {集合}` | `assert {r["item_id"] for r in resp["results"]} == {集合}` |
| `len(xxx) == N` | `assert len(xxx) == N` |
| `[manual]` 标记 | `# MANUAL CHECK: {原文}` |
| 无法翻译 | `# UNPARSED ASSERTION: {原文}` |

项目专属断言模式见 `project_context.md` 的"项目断言模式表"。

`round(..., 4)` -> `pytest.approx(..., abs=1e-4)`。`clamp(x)` -> `max(0, min(1, x))`。

### 请求生成

1. 从共享配置取基础请求体，场景变量 `请求覆盖` 合并
2. gRPC 用例通过场景变量中的 `协议：gRPC` 标识，具体处理方式见 `project_context.md` 的"协议偏好"
3. `{{user_id}}` -> `u_{module}_{tc_number}`，`{{req_id}}` -> `req_{module}_{tc_number}`

### 标记处理

- `[manual]` -> `@pytest.mark.manual` + 断言为注释
- `[!可行性存疑: ...]` -> 跳过不生成，末尾 `# SKIPPED:`

## 质量要求

1. 生成的代码必须通过 `ast.parse`
2. 每个 test 函数独立，不依赖执行顺序
3. 不 import 待测服务内部模块
4. 不硬编码端口，通过 fixture 获取 base_url
5. 不发明用例中没有的断言

## 输出

```
## codegen 摘要

模块：{module}
生成文件：
- test_{module}_business.py — N 条（emitter X 条，AI 补写 Y 条）
- test_{module}_boundary.py — N 条

跳过（可行性存疑）：
- TC-XXX：原因

仍未解析：
- TC-XXX：断言原文

TODO：
- （fixture 不存在时）setup_{module} fixture 需要手写
- （有 gRPC 用例时）gRPC helper 需要补充
- （无 codegen_profile 时）建议跑通测试后编写 codegen_profile
- （测试全部通过后）调用 /emitter-build 提取确定性模板
```

## 后续：编写 codegen profile

测试调通后编写 `test_workspace/tests/fixtures/codegen_profile_{module}.md`，必须包含：

| 章节 | 内容 |
|------|------|
| **fixture 依赖** | fixture 名称、来源、调用方式 |
| **setup_{module} 做了什么** | fixture 内部操作步骤 |
| **新增用例时如何扩展** | dict/map 添加条目格式 |
| **请求模板** | 固定字段、差异字段、helper 用法 |
| **断言模式** | 断言 -> pytest 映射表 |
| **setup 映射** | 场景变量 -> _CASE_CONFIGS 映射 |
| **已知阻塞项** | 无法自动化的用例及原因 |
| **调试经验** | 模块特有排错经验 |
| **emitter 规则** | YAML code block，模块特有断言规则 |

参考：`test_workspace/tests/fixtures/codegen_profile_calibration.md`

## 后续：emitter-build

测试全部通过且 profile 编写完成后，调用 `/emitter-build` 提取确定性模板。
