# Suite Runtime / Report / Promotion 支持 Spec

## 背景

当前 `aitest codegen --cases <suite_dir>` 已支持 suite 的 profile 校验、IR dump、生成和 freshness check，但几个后续能力仍偏模块模式：

- `--explain`、`--health-report`、`--analyze-promotion`、`--suggest-promotion-patch` 不支持 `--cases`。
- `aitest run` 只能按模块名定位 `test_{module}_business.py` / `test_{module}_boundary.py`，不能直接运行 suite 生成文件。
- report 的模块统计默认假设分类只有 `business` / `boundary`，suite case file stem 会被隐藏。

## 目标

1. `aitest codegen --cases <suite_dir> --explain <TC_ID>` 可解释 suite 内单条用例。
2. `aitest codegen --cases <suite_dir> --health-report [--write-report]` 可输出 suite 维度 codegen health。
3. `aitest codegen --cases <suite_dir> --analyze-promotion [--write-report]` 可分析 suite profile 中的 `case_bodies` 晋升候选。
4. `aitest codegen --cases <suite_dir> --suggest-promotion-patch` 可输出 suite profile 的 review-only patch 草稿。
5. `aitest run --cases <suite_dir>` 可运行该 suite 对应 generated pytest，并先执行 `codegen --cases <suite_dir> --check`。
6. report 对 suite 生成文件的任意 category/stem 有可见统计，不再只展示 `business` / `boundary`。

## 非目标

- 不自动应用 promotion patch。
- 不改变 module 模式命令行为。
- 不引入 suite 多级继承或 resources 生命周期管理。
- 不重写已有 generated pytest 文件命名规则。

## 影响文件

- `aitest_kit/codegen/cli.py`
- `aitest_kit/codegen/suite_runner.py`
- `aitest_kit/codegen/health.py`
- `aitest_kit/codegen/promotion.py`
- `aitest_kit/report/cli.py`
- `aitest_kit/report/collector.py`
- `aitest_kit/report/renderer.py`
- 对应 `tests/` 单元测试

## 行为定义

### codegen suite modes

`--cases` 与以下模式兼容：

- `--validate-profile`
- `--dump-ir`
- `--explain <TC_ID>`
- `--health-report`
- `--analyze-promotion`
- `--suggest-promotion-patch`
- `--check`
- `--dry-run`
- 默认生成

这些模式仍保持互斥，仍先经过 suite profile gate。

### suite promotion

promotion 分析以 suite 目录中的 suite profile 为主要对象，同时使用 runtime profile 的上下文识别对象名。候选只限当前 suite case files 中出现的 case_id，避免把 module profile 中不属于本 suite 的 `case_bodies` 混入报告。

### run suite

`aitest run --cases <suite_dir>`：

1. 读取 `aitest_suite.yaml` 得到 `module`、`suite`、`case_files`。
2. 定位 generated 文件：`test_{module}_{suite}_{case_file_stem}.py`。
3. freshness check 使用：`python -m aitest_kit.cli codegen --cases <suite_dir> --check`。
4. pytest 只执行该 suite 的 generated 文件。

无 manifest 的 suite 可用 `--module <module>` 补充归属模块。

### report

collector 会从 `source` 中识别 `test_workspace/casesuites/<suite>/...`，在 case 结果中保留 `suite` 字段。renderer 对非 `business` / `boundary` 分类使用动态表格展示，保证 suite file stem 可见。
