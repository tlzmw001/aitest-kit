# Profile 路径硬收敛 Spec

## 背景

当前 module profile 和 suite profile 同时存在“按命名约定推导”和“配置文件显式声明”两种入口：

- module profile：`module.yaml.profile.file` 与 `{target.defaults.profile_dir}/profile_{module}.md`
- suite profile：`suite.yaml.profile` 与 `{suite_dir}/profile_{suite}_suite.md`

这会造成配置重复、AI scaffold 易写错、doctor/codegen/registry 对路径来源理解不一致。后续统一采用硬约定路径，移除显式 profile 路径配置。

## 目标规则

### module profile

唯一合法路径：

```text
{target.defaults.profile_dir}/profile_{module}.md
```

`modules/{module}.yaml` 不允许出现 `profile` 字段。出现即诊断错误。

### suite profile

唯一合法路径：

```text
{suite_dir}/profile_{suite}_suite.md
```

`suite.yaml` 不允许出现 `profile` 字段。出现即诊断错误。

## 非目标

- 不改变 module profile 与 suite profile 的 YAML 内容结构。
- 不改变 runtime profile merge 语义。
- 不改变 `target.defaults.profile_dir` 目录级配置。
- 不改变 suite Markdown `case_files` 机制。

## 影响范围

### 代码

- `aitest_kit/registry/loader.py`
  - module profile 只按 target defaults + module 名推导。
  - suite profile 只按 suite dir + suite 名推导。
  - `module.yaml.profile` 和 `suite.yaml.profile` 作为非法字段诊断。

- `aitest_kit/codegen/suite.py`
  - suite profile 只使用默认推导。
  - `suite.yaml.profile` 进入 forbidden manifest fields。
  - module profile 只使用 `preferred_module_profile_path`。

- `aitest_kit/codegen/profile.py`
  - 更新 module profile path helper 文案，保留兼容函数仅作为 canonical wrapper 或移除未使用路径。

- `aitest_kit/doctor.py`、`aitest_kit/registry/cli.py`
  - 应自然通过 `ModuleContext.profile_path` / `SuiteManifestContext.profile_path` 使用 canonical path。
  - 错误文案如有 “profile.file is required” 需改为 canonical profile path 语义。

### 当前测试资产

- 删除 `test_workspace/targets/**/modules/*.yaml` 中的 `profile:` 字段。
- 删除 `test_workspace/suites/**/suite.yaml` 中的 `profile:` 字段。
- 不移动 profile 文件；现有文件名已经符合 canonical 命名。

### 文档与 skill

- 更新 `aitest_config/refs/config-files.md`。
- 同步模板 `aitest_kit/templates/project_workspace/aitest_config/refs/config-files.md`。
- 更新核心 skill 中涉及 `suite.yaml.profile` / `module.yaml.profile.file` 的描述。
- 更新 `AGENTS.md` / `CLAUDE.md` 中的配置边界描述。

### 测试

- 更新 registry、suite codegen、doctor、report 相关测试夹具，移除显式 `profile` 字段。
- 新增或调整测试，验证：
  - `suite.yaml.profile` 会产生诊断。
  - `module.yaml.profile` 会产生诊断。
  - 未写 profile 字段时仍能加载 canonical profile。

## 验证命令

```bash
python3 -m pytest tests/test_registry_contexts.py tests/test_codegen_suite_profile.py tests/test_codegen_suite_target.py tests/test_doctor.py tests/test_registry_maintenance_cli.py -q
python3 -m aitest_kit.cli doctor
python3 -m aitest_kit.cli codegen --target coupon_system --module calibration --validate-profile
python3 -m aitest_kit.cli codegen --target coupon_system --module calibration --check
```

