# Registry Maintenance CLI Spec

## 背景

target/module/suite registry 已经成为当前工作流的主入口：

- `target.yaml` 定义目标系统和默认目录。
- `modules/{module}.yaml` 定义模块 fixture、module profile 和 `registered_suites`。
- `suite.yaml` 定义一批 Markdown 用例属于哪个 target/module/suite。
- `task.yaml` 定义一次执行任务包含哪些 suite。

目前 suite 是否进入 `--target`、`--module`、`--all` 聚合执行，依赖人工修改
`module.yaml.registered_suites`。这是确定性的接线动作，适合由 CLI 保证幂等和校验。

同时，`test-maintain` 的定位是测试资产维护管家，应该能根据用户需求辅助完成
suite 注册和 task 创建，但不应该直接手写文件；它应调用确定性 CLI 或路由到
`test-scaffold`。

## 目标

1. 新增 `aitest registry register-suite`，把指定 suite 注册到指定 module。
2. 新增 `aitest task create`，根据明确的 suite 清单创建 task manifest。
3. 更新 `test-maintain` 规则，让它能正确路由：
   - suite 注册 -> `aitest registry register-suite`
   - task 创建 -> `aitest task create`
   - target/module/suite 新建 -> `test-scaffold`
4. 为新增 CLI 增加单元测试。

## 非目标

- 不新增 `create-target` / `create-module` / `create-suite` CLI。
- 不自动推断业务模块、fixture 方法、suite profile 或 case_flow。
- 不自动扫描所有 suite 并批量注册。
- 不保留 YAML 注释。第一版使用 `yaml.safe_dump` 写回 registry/task 文件。
- 不修改 `.env` 或任何外部运行环境。

## 命令设计

### `aitest registry register-suite`

```bash
aitest registry register-suite \
  --target <target> \
  --module <module> \
  --suite-file test_workspace/suites/<target>/<suite>/suite.yaml \
  --status active \
  [--dry-run] \
  [--workspace <workspace_root>]
```

行为：

1. 加载 target registry。
2. 加载 module registry。
3. 加载 suite manifest。
4. 校验：
   - target 存在并可加载。
   - module 存在并可加载。
   - suite manifest 存在并可加载。
   - `suite.target == --target`。
   - `suite.module == --module`。
   - suite case files 全存在。
   - suite profile 存在。
   - module fixture/profile 存在。
5. 如果 module 已注册同名 suite：
   - manifest 相同且 status 相同：输出 already registered，不改文件。
   - manifest 相同但 status 不同：更新 status。
   - manifest 不同：报错，避免同名 suite 指向两个位置。
6. 如果 module 未注册该 suite：追加到 `registered_suites`。
7. 写回 module.yaml 后重新加载并输出验证建议。

输出要包含：

- target
- module
- suite
- manifest
- status
- whether changed
- next commands

### `aitest task create`

```bash
aitest task create \
  --name <task_name> \
  --suite-file test_workspace/suites/<target>/<suite1>/suite.yaml \
  --suite-file test_workspace/suites/<target>/<suite2>/suite.yaml \
  [--description "..."] \
  [--output test_workspace/tasks/<task_name>.yaml] \
  [--overwrite] \
  [--dry-run] \
  [--workspace <workspace_root>]
```

行为：

1. 校验 task name 只包含字母、数字、`_`、`-`。
2. 默认输出到 `test_workspace/tasks/{task_name}.yaml`。
3. 如果输出文件存在且未传 `--overwrite`，报错。
4. 每个 suite_file 必须存在且可加载。
5. 每个 suite 的 case files/profile 必须存在。
6. 生成 task manifest：

```yaml
schema_version: 1
task: nightly_gateway
description: ""
units:
  - name: gateway_smoke
    suite_file: ../suites/sub2api/gateway_smoke/suite.yaml
```

`suite_file` 使用相对 task 文件目录的路径，便于 workspace 移动。

## 维护管家规则

`test-maintain` 只做编排，不直接写文件：

- 用户要求“把某 suite 加到某 module / 让 module 跑到这个 suite”：
  调用 `aitest registry register-suite`。
- 用户要求“创建 task，包含这些 suite”：
  先解析并确认 suite 文件清单，再调用 `aitest task create`。
- 用户要求“新增 target/module/suite”：
  路由到 `test-scaffold`，因为需要业务设计和 fixture/profile 判断。

## 风险

- `yaml.safe_dump` 会丢失原 module.yaml/task.yaml 中的注释。第一版接受这个限制；
  如果后续出现大量注释丢失问题，再考虑局部 patch 写入。
- `registered_suites` 是 module 聚合入口；未注册 suite 仍可通过 `--suite-file`
  单独执行。CLI 输出必须避免用户误解。

## 验证

新增测试覆盖：

- 注册新 suite 成功写入 module.yaml。
- 重复注册同一 suite 幂等。
- 已注册同名 suite 但 manifest 不同时报错。
- suite target/module 与命令不匹配时报错。
- 创建 task 成功写入相对 suite_file。
- task 文件已存在且无 `--overwrite` 时报错。

验证命令：

```bash
python3 -m pytest tests/test_registry_maintenance_cli.py -q
python3 -m pytest tests/test_registry_contexts.py tests/test_report_cli.py tests/test_codegen_suite_profile.py -q
python3 -m compileall aitest_kit/registry aitest_kit/cli.py
```
