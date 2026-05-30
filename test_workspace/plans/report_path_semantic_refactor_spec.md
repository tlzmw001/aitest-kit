# Report Path Semantic Refactor Spec

## 背景

当前 `aitest run --target/--module/--case-id` 会复用 task runner，并把 selector 聚合报告写入：

```text
test_workspace/reports/tasks/{selector_name}/
```

这暴露了内部实现：用户没有显式跑 task，却需要到 `tasks/` 下找 module、target 或 case 报告。与此同时，聚合运行会为 aggregate 和每个 suite unit 分别创建独立 run_id，用户难以判断哪些 run_id 属于同一次命令。

## 目标

1. report 目录按用户语义组织，而不是按内部 runner 实现组织。
2. 去掉 `reports/{target}/modules/{module}` 中的 `modules/` 层，直接使用 `reports/{target}/{module}`。
3. suite case 与 module selector case 统一写入 `reports/{target}/{module}/cases/{case_id}`。
4. 采用方案 B：聚合运行只更新聚合 bucket 的 `latest`；unit 结果保存在同一个 aggregate run_id 的 `units/` 下，不更新 suite 自己的 `latest`。
5. 一次 `aitest run` 命令只有一个用户可见 invocation run_id；聚合 run 下保存 unit 明细。
6. `aitest report` 和 `aitest run` 必须使用同一个 report bucket resolver。

## 新目录结构

```text
test_workspace/reports/
├── all/
│   ├── runs/{run_id}/
│   └── latest/
├── tasks/
│   └── {task_name}/
│       ├── runs/{run_id}/
│       └── latest/
└── {target}/
    ├── target/
    │   ├── runs/{run_id}/
    │   └── latest/
    └── {module}/
        ├── module/
        │   ├── runs/{run_id}/
        │   └── latest/
        ├── suites/
        │   └── {suite}/
        │       ├── runs/{run_id}/
        │       └── latest/
        └── cases/
            └── {case_id}/
                ├── runs/{run_id}/
                └── latest/
```

每个 bucket 内保持不变：

```text
runs/{run_id}/result.json
runs/{run_id}/report.md
runs/{run_id}/junit.xml      # 进入 pytest 后才有
latest/result.json
latest/report.md
latest/junit.xml             # 进入 pytest 后才有
```

聚合 bucket 额外保存 unit 明细：

```text
runs/{run_id}/units/{unit_name}/result.json
runs/{run_id}/units/{unit_name}/report.md
runs/{run_id}/units/{unit_name}/junit.xml
latest/units/{unit_name}/...
```

## 命令到 bucket 的映射

| 命令 | 报告 bucket |
|---|---|
| `aitest run --suite-file <suite.yaml>` | `reports/{target}/{module}/suites/{suite}` |
| `aitest run --suite-file <suite.yaml> --case-id TC-X-001` | `reports/{target}/{module}/cases/tc_x_001` |
| `aitest run --target T --module M` | `reports/{target}/{module}/module` |
| `aitest run --target T --module M --case-id TC-X-001` | `reports/{target}/{module}/cases/tc_x_001` |
| `aitest run --target T` | `reports/{target}/target` |
| `aitest run --all` | `reports/all` |
| `aitest run --task-file task.yaml` | `reports/tasks/{task_name}` |

## 聚合运行规则

直接 suite run：

- 写入 suite 或 case bucket。
- 更新该 bucket 的 `latest`。

task/target/module/all 聚合运行：

- 只更新聚合 bucket 的 `latest`。
- 每个 suite unit 写入当前 aggregate `runs/{run_id}/units/{unit_name}/`。
- 不更新 suite 自己的 `latest`。
- aggregate `result.json.task.units[]` 记录每个 unit 的 `result_path`、`report_path`、`junit_path`。

## 命名规则

- `target`、`module`、`suite`、`case_id` 均使用 safe-name。
- `case_id` 转小写，`-` 转 `_`，例如 `TC-CAL-001` -> `tc_cal_001`。
- `{target}/target` 是保留目录；第一版不额外实现 module 名保留字校验，后续可由 `doctor` 检查 module 名是否为 `target`。
- 同一 module 下 case_id 应唯一；第一版沿用现有 selector 过滤行为，后续可由 `doctor` 检查重复。

## 影响范围

| 文件 | 修改点 |
|---|---|
| `aitest_kit/report/paths.py` | 新增统一 report bucket resolver |
| `aitest_kit/report/cli.py` | direct suite run/report 使用 resolver；支持 unit report dir override |
| `aitest_kit/report/task_runner.py` | 聚合 bucket 使用 resolver；unit 结果写入 aggregate run 的 `units/` |
| `tests/test_report_cli.py` | 更新路径断言；补聚合单 run_id + units 断言 |
| `README.md` / `README.en.md` | 更新 report 目录说明 |

## 不做

1. 不迁移旧 report 目录。
2. 不做旧路径 fallback 查询。
3. 不把所有 unit 明细塞进一个巨大 `result.json`。
4. 不改变 pytest 执行、collector、failure classifier 的语义。
5. 不改变 generated pytest 的路径。

## 验证矩阵

1. `--suite-file` 写入 `reports/{target}/{module}/suites/{suite}/latest`。
2. `--suite-file --case-id` 写入 `reports/{target}/{module}/cases/{case_id}/latest`。
3. `--target T --module M` 写入 `reports/{target}/{module}/module/latest`。
4. `--target T --module M --case-id` 写入 `reports/{target}/{module}/cases/{case_id}/latest`。
5. `--target T` 写入 `reports/{target}/target/latest`。
6. `--task-file` 写入 `reports/tasks/{task_name}/latest`。
7. 聚合 run 的 `latest/units/{unit_name}/result.json` 存在。
8. 聚合 run 的 unit 不更新 suite bucket latest。
9. `aitest report` 对 suite/module/target/case/task 能找到对应 latest 并重渲染。

