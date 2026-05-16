# aitest doctor 规格

## 目标

`aitest doctor` 用于检查 AITest workspace 是否具备运行 codegen 和 generated pytest 的基本条件。它不是自动修复工具，也不启动待测服务。

第一版目标：

```text
快速回答：当前 workspace 结构、配置、profile、generated freshness 和 pytest collect 是否健康？
```

## 非目标

- 不自动创建缺失文件。
- 不自动修改 profile、Markdown、fixture 或 generated pytest。
- 不启动服务。
- 不做网络探测。
- 不替代 `aitest run`。
- 不判断断言失败是否是产品 bug。

## CLI

```bash
aitest doctor
aitest doctor --workspace /path/to/aitest_workspace
aitest doctor --module calibration
```

选项：

| 参数 | 含义 |
|---|---|
| `--workspace` | 从其他目录检查指定 workspace |
| `--module` | 只检查某个模块 |

## 检查项

### 1. Workspace Layout

检查关键路径是否存在：

- `aitest_config/config.yaml`
- `aitest_config/project_config.yaml`
- `test_workspace/cases/`
- `test_workspace/tests/fixtures/`
- `test_workspace/tests/generated/`
- `test_workspace/results/`

缺失关键配置为 `FAIL`；缺少可生成目录为 `WARN`。

`test_workspace/reports/` 是运行产物目录，由 `aitest run` 创建；缺失不作为 doctor 告警。

### 2. Project Config

尝试加载：

- `aitest_config/config.yaml`
- `aitest_config/project_config.yaml`

YAML 或 project config 加载失败为 `FAIL`。

### 3. Module Discovery

从 `test_workspace/cases/` 发现模块。模块目录需要包含：

- `business.md` 或
- `boundary.md`

没有模块时输出 `WARN`，但退出码仍为 0。

### 4. Profile Gate

有模块时运行 profile gate：

```bash
aitest codegen --all --validate-profile
```

或：

```bash
aitest codegen <module> --validate-profile
```

失败为 `FAIL`。

### 5. Generated Freshness

有模块时运行：

```bash
aitest codegen --all --check
```

或：

```bash
aitest codegen <module> --check
```

stale 或 blocked 为 `FAIL`。

### 6. Pytest Collect

如果存在 generated pytest，运行：

```bash
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

或按模块收集对应 generated 文件。

collect 失败为 `FAIL`；没有 generated pytest 为 `WARN`。

### 7. Environment Hint

静态扫描 fixture 中常见环境变量读取方式，例如：

```python
os.environ.get("HTTP_BASE_URL")
os.getenv("DISCOUNT_SYSTEM_BASE_URL")
```

输出 `INFO` 提示可能需要配置的环境变量。不因为环境变量未设置而失败，因为 doctor 第一版不启动服务，也不判断真实运行环境。

## 输出格式

文本输出：

```text
AITest Doctor
Workspace: /path/to/aitest_workspace

[OK] workspace layout
[OK] project config
[WARN] modules: no modules found under test_workspace/cases
[INFO] environment variables referenced by fixtures: HTTP_BASE_URL

Summary: ok=2, warn=1, fail=0, info=1
```

## 退出码

| 情况 | 退出码 |
|---|---|
| 有 `FAIL` | 1 |
| 只有 `OK/WARN/INFO` | 0 |
| CLI 参数错误 | 2 |

## 实现边界

- `doctor` 可以调用现有 codegen CLI 子命令，避免复制 profile gate 和 freshness 逻辑。
- 第一版只做稳定诊断，不生成 report artifact。
- 后续可以扩展 `--json`、Markdown case lint、knowledge lint、connectivity check，但不进入第一版。
