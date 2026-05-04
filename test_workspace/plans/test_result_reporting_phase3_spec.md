# Phase 3：测试执行结果结构化与报告 MVP

## 状态：DRAFT

## 设计原则

**企业级通用方案**：report 层不硬编码任何项目特定约定（TC ID 格式、目录结构、文件命名）。所有用例身份信息由 emitter 在生成代码中显式声明（`__tc_meta__` / `__codegen_skipped__`），report 层优先消费 metadata，不把 nodeid 正则推导作为主路径。换项目时 report 层零适配。

## 背景

codegen 管线（Phase 1 防御层 + Phase 2 可移植层）已完成，Markdown → pytest 代码路径已打通。
但 pytest 执行结果目前只有终端红绿输出，没有结构化落盘、没有与 Markdown 源用例的正式关联、没有失败归因、没有反哺飞轮的自动化路径。

## 目标

建立"执行结果 → 结构化数据 → 报告 → 飞轮反哺"的闭环，让每次测试执行产出可追溯、可归档、可驱动下一步行动的结构化产物。

## 约束（不可违反）

- 不修改 `coupon_system/` 和 `ab_experiment_sdk/`
- 不引入新的第三方依赖（只用 pytest 内置 JUnit XML + 标准库）
- 不删除已有 `project_config` fallback 逻辑
- 不改变现有 generated pytest 的运行时行为（`__tc_meta__` / `__codegen_skipped__` 是静态 metadata，不影响测试逻辑）
- 不把例行运行报告写进 `test_workspace/results/`（那里是 bug 记录）
- 不采集敏感数据：环境变量值、认证凭证、完整请求体/响应体、内部路径配置
- 不新建 skill，报告功能通过 CLI 命令实现；后续扩展 test-fix 接受 report 作为输入

## 不做的事

- HTML dashboard / Web UI
- 复杂 pytest plugin
- 完整 HTTP 请求/响应采集
- AI 自动判断产品 bug
- 趋势分析 / 历史对比（留给后续 Phase）

---

## 一、用例身份链路：`__tc_meta__` / `__codegen_skipped__`

### 问题

当前 collector 要从 nodeid 和文件名推导 tc_id、module、category、source_md，依赖特定命名约定（`test_tc_cal_001` → `TC-CAL-001`、`test_{module}_{category}.py`）。换项目时这些约定可能不同，report 层就要跟着改。

### 方案

emitter 在每个 test 函数体首行生成显式 metadata 变量：

```python
def test_tc_cal_001(self, setup_calibration):
    """TC-CAL-001：线性校准 k=0.85"""
    __tc_meta__ = {
        "tc_id": "TC-CAL-001",
        "module": "calibration",
        "category": "business",
        "source": "test_workspace/cases/calibration/business.md",
        "title": "线性校准 k=0.85",
        "priority": "P1",
        "markers": [],
    }
    # SETUP: ...
    ...
```

- `__tc_meta__` 是函数局部变量，不影响测试执行（pytest 不关心它）
- collector 通过 AST 解析生成文件提取 `__tc_meta__`，不依赖 TC ID 格式或文件名约定
- 如果 AST 提取失败（比如手写的非 codegen 测试文件），fallback 到 nodeid 正则推导，保证向后兼容

### JUnit XML 与 metadata 的 join 机制

pytest 的 JUnit XML 不稳定提供完整 nodeid，通常只有 `classname`、`name`、`time` 和 failure/error 节点。因此 collector 不能假设 XML 中存在完整的：

```text
test_workspace/tests/generated/test_calibration_business.py::TestCalibrationBusiness::test_tc_cal_001
```

collector 使用以下 join 策略：

1. AST 扫描目标 generated 文件，建立 metadata 索引：
   - `file_path + class_name + function_name -> __tc_meta__`
   - `class_name + function_name -> __tc_meta__`（仅当唯一时作为候选）
2. JUnit XML 解析每个 `<testcase>`：
   - `name` 归一化为 pytest 函数名（如 `test_tc_cal_001`）
   - `classname` 取尾部 class 名（如 `TestCalibrationBusiness`）
   - 如果 XML 包含 `file` 属性，优先用 `file + class + function` 匹配
   - 如果 XML 不含 `file`，用 `class + function` 唯一匹配
3. 若仍无法匹配：
   - fallback 到 nodeid / 文件名推导
   - `meta_source` 标记为 `nodeid_fallback`
4. 若 fallback 仍失败：
   - `meta_source` 标记为 `unknown`
   - `tc_id/module/category/source_md` 置空或 `UNKNOWN`，但保留原始 JUnit testcase 信息

### codegen skipped metadata

`[!可行性存疑: ...]` 用例当前不会生成 pytest 函数，因此不会出现在 JUnit XML 中。为了让报告统计这类“设计存在但未进入 pytest”的用例，emitter 在文件尾部生成结构化 file-level metadata：

```python
__codegen_skipped__ = [
    {
        "tc_id": "TC-ROUTE-010",
        "module": "scene_routing",
        "category": "boundary",
        "source": "test_workspace/cases/scene_routing/boundary.md",
        "title": "fallback invalid scene score",
        "priority": "P2",
        "reason": "[!可行性存疑: 当前系统不支持热更新]",
    },
]
```

可以保留现有 `# SKIPPED:` 注释给人读，但 collector 只依赖 `__codegen_skipped__` 统计 `codegen_skipped`。

### emitter 改动

在 `emitter.py` 的 `_render_test_function()` 中，docstring 之后、SETUP 注释之前插入一行。数据来源：

| 字段 | 来源 |
|------|------|
| `tc_id` | `TestCase.id` |
| `module` | `EmitContext.module` |
| `category` | `EmitContext.file_type` |
| `source` | `EmitContext.source_path` |
| `title` | `TestCase.title` |
| `priority` | `TestCase.priority` |
| `markers` | `TestCase.markers` |

这是 Phase 3 中**唯一修改 codegen 层语义的地方**：只增加静态 metadata，不改变测试执行逻辑。metadata 必须覆盖两条生成路径：

- 普通模板路径：由 emitter 渲染请求和断言的测试函数
- `case_bodies` / custom body 路径：由 profile 直接提供测试体的函数

重新 codegen 后，所有 generated pytest 都会出现预期 diff（新增 metadata 行）。验证标准应是“重新生成后 `aitest codegen --all --check` 通过”，而不是要求 metadata 改造前后 generated 文件完全不变。

---

## 二、目录结构

### 报告目录

```
test_workspace/reports/
├── latest/                    # 最近一次运行的副本
│   ├── junit.xml              # 仅 pytest 已执行时存在；BLOCKED_RUN 可不存在
│   ├── result.json
│   └── report.md
└── runs/
    └── {run_id}/              # 格式：YYYYMMDD-HHMMSS
        ├── junit.xml          # pytest 原始 JUnit XML；BLOCKED_RUN 可不存在
        ├── result.json        # 结构化结果（项目数据契约）
        └── report.md          # 人可读 Markdown 报告
```

`latest/` 始终指向最近一次运行，方便 test-fix 等工具固定路径读取。

### 路径配置化

报告输出目录不硬编码，从 `aitest_config/config.yaml` 读取：

```yaml
paths:
  # 已有
  cases_dir: test_workspace/cases
  # 新增
  reports_dir: test_workspace/reports
  generated_dir: test_workspace/tests/generated
```

CLI 的 `aitest run` 和 `aitest report` 从配置读取路径，fallback 到默认值。

### gitignore 策略

`test_workspace/reports/` 是运行产物目录，默认整体不入库：

```gitignore
test_workspace/reports/
```

如果后续需要提交示例报告，应单独放到 `docs/usebook/example_test_report.md`，不要复用 `latest/` 作为文档样例，避免每次执行污染工作区。

---

## 三、result.json Schema（核心数据契约）

```jsonc
{
  // 运行级元信息
  "run_id": "20260503-143022",
  "status": "COMPLETED",        // COMPLETED | FAILED_RUN | BLOCKED_RUN
  "timestamp": "2026-05-03T14:30:22+08:00",
  "duration_seconds": 12.34,
  "command": "aitest run",
  "project_config_version": "sha256[:8] of project_config.yaml",
  "manual_policy": "excluded",  // excluded | included
  "codegen_check": {
    "status": "passed",         // passed | failed | skipped
    "command": "aitest codegen --all --check",
    "message": ""
  },

  // 聚合摘要
  "summary": {
    "auto_collected": 80,        // 本次进入 pytest 自动执行范围的测试函数数
    "manual_total": 5,           // generated 中标记 manual 的测试函数数
    "manual_executed": 0,        // 本次实际执行的 manual 测试数
    "manual_not_run": 5,         // manual_total - manual_executed
    "codegen_skipped": 2,        // 可行性存疑，未生成 pytest 函数
    "passed": 72,
    "failed": 8,
    "error": 3,
    "pytest_skipped": 0,
    "duration_seconds": 12.34
  },

  // 按模块聚合（由 cases[].module 动态统计，不硬编码模块列表）
  "modules": {
    "calibration": {
      "business": { "auto_collected": 10, "passed": 9, "failed": 1, "error": 0, "pytest_skipped": 0, "manual_total": 1, "manual_not_run": 1, "codegen_skipped": 0 },
      "boundary": { "auto_collected": 6, "passed": 6, "failed": 0, "error": 0, "pytest_skipped": 0, "manual_total": 0, "manual_not_run": 0, "codegen_skipped": 0 }
    }
  },

  // 每条用例结果
  "cases": [
    {
      // 身份信息（优先从 __tc_meta__ 提取，fallback 到 nodeid 推导）
      "nodeid": "test_workspace/tests/generated/test_calibration_business.py::TestCalibrationBusiness::test_tc_cal_001",
      "tc_id": "TC-CAL-001",
      "module": "calibration",
      "category": "business",
      "source_md": "test_workspace/cases/calibration/business.md",
      "meta_source": "tc_meta",      // "tc_meta" | "nodeid_fallback" | "unknown" — 标记身份信息的来源
      "title": "线性校准 k=0.85",
      "priority": "P1",
      "markers": [],
      "is_manual": false,

      // 执行结果
      "outcome": "passed",           // passed | failed | error | pytest_skipped
      "duration_seconds": 0.15,

      // 失败信息（仅 failed/error 时存在）
      "failure": {
        "phase": "call",             // setup | call | teardown | unknown
        "classification": "ASSERTION_FAILURE",
        "exception_type": "AssertionError",
        "message": "assert 0.8532 == 0.8500 ± 1e-4",
        "traceback_summary": "test_calibration_business.py:45: AssertionError"
      }
    }
  ],

  // codegen 跳过的用例：存在于 Markdown，但未生成 pytest 函数
  "codegen_skipped_cases": [
    {
      "tc_id": "TC-ROUTE-010",
      "module": "scene_routing",
      "category": "boundary",
      "source_md": "test_workspace/cases/scene_routing/boundary.md",
      "title": "fallback invalid scene score",
      "priority": "P2",
      "reason": "[!可行性存疑: 当前系统不支持热更新]"
    }
  ]
}
```

### 字段说明

| 字段 | 来源 | 说明 |
|------|------|------|
| `nodeid` | collector 由 file/class/function 重建；fallback 到 JUnit classname/name | 用于复现命令的 pytest 节点标识 |
| `tc_id` | `__tc_meta__["tc_id"]`，fallback: nodeid 正则 | 用例唯一标识 |
| `module` | `__tc_meta__["module"]`，fallback: 文件名提取 | 模块归属 |
| `category` | `__tc_meta__["category"]`，fallback: 文件名提取 | business / boundary |
| `source_md` | `__tc_meta__["source"]`，fallback: 路径推导 | Markdown 源文件 |
| `title` | `__tc_meta__["title"]` | 用例标题，用于报告展示 |
| `priority` | `__tc_meta__["priority"]` | P0 / P1 / P2，用于后续聚合 |
| `markers` | `__tc_meta__["markers"]` + AST decorator | manual / 可行性标记等 |
| `is_manual` | `markers` 或 `@pytest.mark.manual` | 是否为 manual 用例 |
| `meta_source` | collector 自动填充 | 标记身份数据来自 tc_meta、fallback 还是 unknown |
| `phase` | JUnit XML failure/error 节点 message/text 推导 | setup / call / teardown / unknown |
| `classification` | 规则推导 | 失败归因初判 |
| `message` | 异常消息，脱敏+截断 | 不含完整堆栈 |
| `traceback_summary` | 仅文件名+行号+异常类型 | 不含绝对路径 |

### run status 语义

| 状态 | 含义 |
|------|------|
| `COMPLETED` | pytest 已执行，collector 和 renderer 成功产出结果；即使存在 failed/error 用例也仍是 completed |
| `FAILED_RUN` | pytest 启动或 collector/renderer 过程失败，无法形成完整用例结果 |
| `BLOCKED_RUN` | generated freshness check 失败，pytest 未执行 |

### manual 与 skipped 统计语义

报告必须拆分以下概念，不能合并成单一 `skipped`：

| 字段 | 来源 | 含义 |
|------|------|------|
| `pytest_skipped` | JUnit XML `<skipped>` | pytest 已收集但运行时 skip 的测试 |
| `codegen_skipped` | `__codegen_skipped__` | `[!可行性存疑]`，emitter 未生成测试函数 |
| `manual_total` | AST `__tc_meta__.markers` / decorator | generated 中 manual 测试函数总数 |
| `manual_executed` | JUnit XML + metadata | 本次实际执行的 manual 测试数 |
| `manual_not_run` | 计算值 | `manual_total - manual_executed` |

`aitest run` 默认排除 manual 测试（等价于附加 `-m "not manual"`），提供 `--include-manual` 显式执行 manual。报告中必须记录 `manual_policy`：

- `excluded`：默认策略，manual 不进入本次自动化执行结果，但计入 `manual_not_run`
- `included`：用户传入 `--include-manual`，manual 进入 pytest 执行范围

### 安全脱敏规则

- `message` 字段：截断到 200 字符；如果包含 `token`/`password`/`secret`/`key=`/`authorization` 等关键词，替换为 `[REDACTED]`
- `traceback_summary`：只保留文件名（不含绝对路径）+ 行号 + 异常类型
- 不采集：环境变量值、fixture 中的连接字符串、HTTP 请求头/请求体/响应体
- `project_config_version`：只存 sha256 前 8 位，不存文件内容

---

## 四、失败归因规则

基于 `phase` + `exception_type` 组合推导，不做 AI 判断：

| 分类 | 规则 | 含义 |
|------|------|------|
| `ENVIRONMENT_ERROR` | phase=setup 且异常为 `ConnectionError` / `ConnectionRefusedError` / `TimeoutError` / `OSError` | 服务未启动或网络不通 |
| `FIXTURE_ERROR` | phase=setup 且不是连接错误 | fixture/setup 逻辑问题 |
| `CODEGEN_ERROR` | phase=call 且异常为 `NameError` / `TypeError` / `AttributeError` / `SyntaxError` | 生成代码有 bug |
| `ASSERTION_FAILURE` | phase=call 且异常为 `AssertionError` | 断言失败，需人工判断是用例问题还是产品 bug |
| `TEARDOWN_ERROR` | phase=teardown | 清理逻辑问题 |
| `UNKNOWN` | 以上都不匹配 | 需人工检查 |

归因规则表通过 `classifier.py` 实现，规则可配置扩展（后续可通过 config 新增项目特有的异常类型映射）。

注意：`ASSERTION_FAILURE` 不细分为 `PRODUCT_BUG_CANDIDATE` 和 `TEST_CASE_BUG_CANDIDATE`。MVP 阶段断言失败统一归为需人工确认，由报告的反哺清单引导人工分流。

---

## 五、CLI 命令设计

### `aitest run`

执行 generated pytest 并采集结构化结果。

```bash
# 运行全部模块
aitest run

# 运行指定模块
aitest run calibration

# 运行多个模块
aitest run calibration ab_experiment

# 默认不运行 manual；显式运行 manual
aitest run calibration --include-manual

# 调试时跳过 generated freshness check（报告中会标记 codegen_check=skipped）
aitest run calibration --skip-codegen-check

# 透传 pytest 参数（-- 之后）
aitest run calibration -- -x -q
```

内部流程：

```
1. 从 config.yaml 读取 generated_dir 和 reports_dir
2. 确定目标文件列表
   - 无参数：{generated_dir}/test_*.py
   - 指定模块：test_{module}_business.py + test_{module}_boundary.py
3. 创建 run_id = 当前时间 YYYYMMDD-HHMMSS
4. 创建 {reports_dir}/runs/{run_id}/
5. 执行 generated freshness check：
   - 无参数：等价于 `aitest codegen --all --check`
   - 指定模块：只检查目标模块
   - check 失败：生成 `BLOCKED_RUN` 的 result.json + report.md，不执行 pytest
   - 用户传入 `--skip-codegen-check`：跳过 check，并在 result.json 记录 `codegen_check.status=skipped`
6. 执行 pytest：
   python3 -m pytest {files} \
     --junitxml={run_dir}/junit.xml \
     -v -m "not manual" {extra_args}
   - 用户传入 `--include-manual` 时不追加 `-m "not manual"`
7. AST 解析目标 .py 文件，提取所有 `__tc_meta__` 和 `__codegen_skipped__`
8. 解析 junit.xml + 合并 tc_meta → 构建 result.json
9. 从 result.json 生成 report.md
10. 复制 run_dir/* 到 {reports_dir}/latest/
11. 终端输出摘要
```

退出码：

| 退出码 | 含义 |
|--------|------|
| 0 | pytest 全部通过 |
| 1 | pytest 有失败 |
| 2 | pytest 执行错误或 collector/report 阶段错误 |
| 3 | pytest interrupted |
| 4 | pytest usage error |
| 5 | pytest no tests collected |
| 10 | `BLOCKED_RUN`，generated freshness check 失败，pytest 未执行 |

### `aitest report`

从已有的 result.json 重新生成报告（不重新执行测试）。

```bash
# 从最近一次运行生成
aitest report

# 从指定运行生成
aitest report 20260503-143022
```

用途：修改报告模板后重新渲染，或手动检查历史运行。

---

## 六、report.md 模板

```markdown
# 测试执行报告

- **运行 ID**：{run_id}
- **运行状态**：{status}
- **时间**：{timestamp}
- **耗时**：{duration}s
- **命令**：`{command}`
- **Codegen Check**：{codegen_check.status}
- **Manual 策略**：{manual_policy}

## 执行摘要

### 自动化结果

| 状态 | 数量 |
|------|------|
| 通过 | {passed} |
| 失败 | {failed} |
| 错误 | {error} |
| pytest skipped | {pytest_skipped} |
| **本次自动化收集** | **{auto_collected}** |

### 未进入本次自动化执行

| 类型 | 数量 |
|------|------|
| manual 总数 | {manual_total} |
| manual 已执行 | {manual_executed} |
| manual 未执行 | {manual_not_run} |
| codegen skipped | {codegen_skipped} |

## 按模块统计

| 模块 | business | boundary | 通过率 |
|------|----------|----------|--------|
| calibration | 9/10 | 6/6 | 93.8% |
| ... | ... | ... | ... |

## 失败详情

### ENVIRONMENT_ERROR（{n} 条）

> 服务未启动或网络不通。处理方式：检查服务状态后重新执行。

| TC ID | 模块 | 异常摘要 |
|-------|------|---------|
| TC-XXX-001 | xxx | ConnectionRefusedError: ... |

### FIXTURE_ERROR（{n} 条）

> fixture/setup 逻辑问题。处理方式：检查对应模块的 fixture 文件。

（同上表格式）

### CODEGEN_ERROR（{n} 条）

> 生成代码有 bug。处理方式：检查 codegen profile 或 emitter 规则。

### ASSERTION_FAILURE（{n} 条）

> 断言失败，需人工判断是用例问题还是产品 bug。

| TC ID | 模块 | 断言摘要 | 复现命令 |
|-------|------|---------|---------|
| TC-CAL-003 | calibration | assert 0.85 == 0.83±1e-4 | `pytest {nodeid} -v` |

### TEARDOWN_ERROR / UNKNOWN

（如有）

## 反哺清单

基于失败归因自动生成的下一步动作建议。

### 需要 test-fix（用例或断言可能有误）

- TC-XXX-001：{断言摘要}，源文件：{source_md}

### 需要修 fixture / codegen profile

- TC-YYY-002：{异常摘要}

### 人工确认后可记录到 results/ 的待测系统 bug

- TC-ZZZ-003：{断言摘要}

### 需要人工判断

- TC-AAA-004：{异常摘要}

### 环境问题（重启服务后重试）

- {n} 条 ENVIRONMENT_ERROR，重试命令：`aitest run {modules}`

## BLOCKED_RUN

当 generated freshness check 失败时，pytest 不执行，报告只输出阻断原因：

- **Codegen Check**：failed
- **原因**：generated pytest 与 Markdown/profile 不一致
- **下一步**：先运行 `aitest codegen {modules}`，再运行 `aitest run {modules}`
```

### 反哺清单生成规则

| 失败分类 | 归入清单 | 说明 |
|----------|---------|------|
| `ENVIRONMENT_ERROR` | 环境问题 | 不进入其他清单 |
| `FIXTURE_ERROR` | 需要修 fixture / codegen profile | — |
| `CODEGEN_ERROR` | 需要修 fixture / codegen profile | — |
| `ASSERTION_FAILURE` | 需要人工判断 | 人工分流后移入 test-fix 或 bug 记录 |
| `TEARDOWN_ERROR` | 需要修 fixture / codegen profile | — |
| `UNKNOWN` | 需要人工判断 | — |

---

## 七、实现文件清单

### 新建文件

| 文件 | 职责 | 行数估算 |
|------|------|---------|
| `aitest_kit/report/__init__.py` | 包初始化 | ~1 |
| `aitest_kit/report/collector.py` | 解析 JUnit XML + AST 提取 tc_meta/codegen_skipped → result.json | ~180 |
| `aitest_kit/report/renderer.py` | result.json → report.md（含反哺清单） | ~150 |
| `aitest_kit/report/classifier.py` | 失败归因规则引擎 | ~60 |
| `aitest_kit/report/sanitizer.py` | 脱敏工具 | ~40 |
| `aitest_kit/report/cli.py` | `aitest run` + `aitest report` 命令 | ~120 |
| `tests/test_collector.py` | collector 单元测试 | ~100 |
| `tests/test_classifier.py` | classifier 单元测试 | ~60 |
| `tests/test_sanitizer.py` | sanitizer 单元测试 | ~40 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `aitest_kit/codegen/emitter.py` | 生成 `__tc_meta__` / `__codegen_skipped__` 静态 metadata |
| `aitest_kit/cli.py` | 注册 `run` 和 `report` 子命令 |
| `aitest_config/config.yaml` | paths 段新增 `reports_dir` 和 `generated_dir` |
| `.gitignore` | 添加 `test_workspace/reports/`（报告产物不入库）|
| `CLAUDE.md` | 更新工作流，补充 `aitest run` 和 `aitest report` 说明 |
| `AGENTS.md` | 更新工作流，补充报告阶段约定 |
| `README.md` | 更新命令列表和项目结构 |

### 不修改的文件

- `aitest_kit/codegen/` 除 emitter.py 外的所有文件
- `coupon_system/` 和 `ab_experiment_sdk/`
- `test_workspace/results/` 下的 bug 记录

---

## 八、实施步骤

### Phase 3A：tc_meta + 结果落盘

1. **emitter 改造**：普通模板路径和 `case_bodies` 路径都在 docstring 后生成 `__tc_meta__` 行
2. **codegen skipped metadata**：文件尾部生成 `__codegen_skipped__` 列表，覆盖 `[!可行性存疑]` 未生成函数的用例
3. **重新生成全部模块**：`aitest codegen --all` + `aitest codegen --all --check` 验证 metadata diff 已落盘且生成结果一致
4. 创建 `aitest_kit/report/` 包
5. 实现 `collector.py`：AST 提取 `__tc_meta__` / `__codegen_skipped__` + 解析 JUnit XML + join 构建 result.json
6. 实现 `classifier.py`：phase + exception_type → classification
7. 实现 `sanitizer.py`：message 截断 + 敏感词替换 + traceback 精简
8. 实现 `cli.py` 中的 `aitest run` 命令，默认排除 manual，支持 `--include-manual` 和 `--skip-codegen-check`
9. 更新 `aitest_config/config.yaml`：新增 `reports_dir` 和 `generated_dir`
10. 单元测试：用手写的 JUnit XML fixture + mock .py 文件测试 collector + classifier + sanitizer
11. 集成验证：`aitest run calibration` 生成 result.json，检查 schema 正确性

### Phase 3B：Markdown 报告

1. 实现 `renderer.py`：从 result.json 渲染 report.md（含反哺清单）
2. 实现 `cli.py` 中的 `aitest report` 命令
3. 验证：对照模板检查生成的 report.md

### Phase 3C：飞轮对接 + 文档更新

1. 更新 CLAUDE.md 工作流，补充 `aitest run` → 报告 → 反哺路径
2. 更新 AGENTS.md 工作流，补充报告阶段约定
3. 更新 README.md 命令列表和项目结构
4. 更新 .gitignore

---

## 九、验证标准

### 功能验证

- [ ] `aitest run calibration` 执行测试并生成 `junit.xml` + `result.json` + `report.md`
- [ ] `aitest run` 不带参数执行全部模块
- [ ] `aitest run` 默认排除 manual，并在 result.json/report.md 记录 `manual_total/manual_executed/manual_not_run`
- [ ] `aitest run --include-manual` 执行 manual，并在 result.json/report.md 记录 `manual_policy=included`
- [ ] generated 过期时 `aitest run` 生成 `BLOCKED_RUN` 报告，不执行 pytest
- [ ] `aitest run --skip-codegen-check` 跳过 freshness check，并记录 `codegen_check.status=skipped`
- [ ] `aitest report` 从 `latest/result.json` 重新渲染 `report.md`
- [ ] `aitest report {run_id}` 渲染指定历史运行
- [ ] result.json 中 `meta_source` 为 `tc_meta`（非 fallback）
- [ ] result.json 的 `tc_id` 能正确映射回 Markdown 源文件
- [ ] result.json 中 `codegen_skipped` 来自 `__codegen_skipped__`，不依赖 JUnit XML
- [ ] 失败用例的 `classification` 符合归因规则表
- [ ] `latest/` 被正确更新为最新运行的副本

### 通用性验证

- [ ] collector 不依赖特定 TC ID 格式（通过 `__tc_meta__` 而非正则）
- [ ] collector 不依赖特定文件名约定（通过 `__tc_meta__` 而非文件名解析）
- [ ] collector 能在 JUnit XML 无完整 nodeid 时，通过 `classname + name` 与 AST metadata join
- [ ] `__tc_meta__` 覆盖普通模板路径和 `case_bodies` / custom body 路径
- [ ] 路径从 config.yaml 读取，不硬编码
- [ ] fallback 逻辑能处理不含 `__tc_meta__` 的手写测试文件

### 安全验证

- [ ] result.json 的 `message` 字段不超过 200 字符
- [ ] 包含 `token`/`password`/`secret`/`key=`/`authorization` 的消息被替换为 `[REDACTED]`
- [ ] `traceback_summary` 不含绝对路径
- [ ] result.json 中无环境变量值、连接字符串

### 质量验证

- [ ] `pytest tests/test_collector.py tests/test_classifier.py tests/test_sanitizer.py` 全部通过
- [ ] `aitest_kit/report/` 下每个文件不超过 500 行
- [ ] 不引入标准库以外的新依赖（除已有的 click、pyyaml）
- [ ] `aitest codegen --all --check` 通过（重新生成 metadata 后结果一致）
- [ ] `.gitignore` 忽略 `test_workspace/reports/`，运行报告不污染 git status

---

## 十、后续展望（不在本 Phase 范围）

- test-fix 接受 `report.md` 作为输入，自动读取失败清单并定位问题
- 归因规则可配置化：`project_config.yaml` 新增 `classification_rules` 段，支持项目特有异常类型
- 历史趋势：多次 result.json 对比，生成通过率变化曲线
- 请求/响应采集（带脱敏）用于失败复现
- 批量归因：跨模块失败模式识别（如同一 fixture 导致多模块失败）
