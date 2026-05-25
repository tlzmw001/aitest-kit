# AITest Workspace Upgrade Spec

## 背景

`aitest-kit` 升级后，用户可以通过 `pip install -U aitest-kit` 使用新版 CLI、codegen、doctor、run/report 等 Python 代码。

但用户已经通过 `aitest init` 复制到项目中的 workspace 资产不会随 Python 包自动更新，例如：

- `.codex/skills/`
- `.claude/skills/`
- `.agents/skills/`
- `aitest_config/refs/`
- `aitest_config/schemas/`
- `test_workspace/tests/helpers/`
- `AGENTS.md` / `CLAUDE.md` / `README.md`

直接重新执行 `aitest init --force` 有风险，因为会覆盖用户已经适配过的配置、helper 或协作说明。

## 目标

新增安全的 workspace 升级能力：

```bash
aitest upgrade --workspace /path/to/aitest_workspace --check
aitest upgrade --workspace /path/to/aitest_workspace --apply
```

设计原则：

1. 升级 Python 包和升级 workspace 资产是两个独立生命周期。
2. `upgrade` 默认保守，不覆盖疑似用户修改过的文件。
3. `upgrade --check` 只报告，不写文件。
4. `upgrade --apply` 只写入可安全判定的模板文件，并在写入前备份。
5. 不删除用户文件，不删除旧模板文件。

## Workspace Manifest

`aitest init` 以后写入：

```text
.aitest/workspace.json
```

内容包含：

- `schema_version`
- `aitest_kit_version`
- `template_version`
- `created_at`
- `updated_at`
- `template_files`：模板文件相对路径到 sha256 的映射

用途：

- 判断当前文件是否仍然等于上次安装的模板。
- 如果当前文件等于旧模板而新包模板不同，则可安全升级。
- 如果当前文件既不等于旧模板，也不等于新模板，则视为用户本地修改，默认跳过。

历史 workspace 没有 manifest 时，`upgrade` 仍可运行，但只能安全创建缺失文件；已有且与新模板不同的文件默认视为未知冲突。

## 文件策略

### 默认可升级的框架资产

- `.codex/skills/**`
- `.claude/skills/**`
- `.agents/skills/**`
- `aitest_config/refs/**`
- `aitest_config/schemas/**`
- `test_workspace/tests/helpers/**`
- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `.gitignore`
- package template 中的 `.gitkeep` 和 `__init__.py`

### 默认不自动覆盖的项目资产

- `aitest_config/config.yaml`
- `aitest_config/project_config.yaml`
- `test_workspace/tests/conftest.py`
- `test_workspace/knowledge/**`
- `test_workspace/cases/**`
- `test_workspace/casesuites/**`
- `test_workspace/tests/fixtures/**`
- `test_workspace/tests/generated/**`
- `test_workspace/results/**`
- `test_workspace/reports/**`

这些文件可能包含项目专属配置、用例、fixture、profile、generated pytest 或执行产物。

## Upgrade 状态

每个模板文件输出一个状态：

- `OK`：当前文件已是新版模板。
- `NEW`：目标文件不存在，`--apply` 可创建。
- `UPDATE`：当前文件等于 manifest 记录的旧模板，`--apply` 可安全覆盖为新版模板。
- `LOCAL`：当前文件与 manifest 旧模板不同，疑似用户修改，默认不覆盖。
- `MANUAL`：项目资产或高风险文件，默认不自动覆盖。
- `OBSOLETE`：manifest 中存在但新版模板中不存在的文件，只报告不删除。

## 命令行为

### `aitest upgrade --check`

- 不写文件。
- 输出状态摘要。
- 若发现 `LOCAL` 或 `MANUAL`，退出码仍为 0，因为这是升级审计信息，不是运行错误。

### `aitest upgrade --apply`

- 创建 `NEW` 文件。
- 覆盖 `UPDATE` 文件。
- 写入前备份被覆盖文件到：

```text
.aitest/backups/upgrade-YYYYmmdd-HHMMSS/
```

- 不覆盖 `LOCAL` / `MANUAL`。
- 更新 `.aitest/workspace.json` 中已安全同步文件的 hash。

## 验收

1. `aitest init` 会创建 `.aitest/workspace.json`。
2. 新 init 后执行 `aitest upgrade --check` 显示 workspace up to date。
3. 模拟旧模板文件且未被本地修改时，`aitest upgrade --apply` 会更新文件并备份。
4. 模拟用户本地修改时，`aitest upgrade --apply` 不覆盖文件。
5. 删除一个安全模板文件后，`aitest upgrade --apply` 会恢复该文件。
6. `python3 -m pytest tests/test_workspace_template.py -q` 通过。
