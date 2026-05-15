# AITest v0.1 Release Spec

## 目标

交付一个可以给新项目试用的 v0.1 版本。用户不需要理解 aitest-kit 示例仓库历史，只需要安装 `aitest-kit`、执行 `aitest init`、放入公开文档、按文档完成最小模块迁移，就能跑通：

```text
公开文档 -> 知识库 -> Markdown 用例 -> profile/fixture -> codegen -> pytest collect/run -> report
```

## 发布边界

### v0.1 支持

- 本地 CLI：`aitest init`、`aitest codegen`、`aitest run`、`aitest report`
- 单一包内 workspace 模板：`aitest_kit/templates/project_workspace/`
- 新项目 workspace 隔离：`--workspace <dir>`
- profile JSON Schema + 语义门禁
- Case IR dump/explain/check/health report
- Markdown 用例到 generated pytest 的确定性生成
- 三套本地 skills：`.codex/skills/`、`.claude/skills/`、`.agents/skills/`
- 文档化迁移 SOP、profile 编写指南、常见错误排查

### v0.1 不支持

- Web UI
- 完全自动迁移新项目
- 自动从已验证 pytest 反向提取 `case_flows`
- 自动应用 promotion patch
- 自动修改待测系统业务代码
- 对所有语言/框架开箱即用；新项目仍需要按文档改 `project_config.yaml`、fixture 和 profile

## 验证对象

### 1. 纯安装态临时项目

使用 `/private/tmp` 下的临时目录验证“用户从零安装后是否能初始化和生成”。该验证不依赖 aitest-kit 当前工作目录，也不依赖 coupon/AB 示例资产。

验收点：

- 从非源码目录执行 `aitest --help`
- `aitest init --target <tmp_project>` 产物完整
- 空 workspace 的提示友好
- 写入最小 demo 模块后，`validate-profile`、`dump-ir`、`codegen`、pytest collect 全部通过

### 2. `discount_system` 外部真实项目

`/Users/zmw/discount_system` 是外部待测系统，可作为真实项目迁移回归目标。它不在 aitest-kit 仓库内，适合检查模板和 playbook 是否会被本仓上下文污染。

使用约束：

- 默认只读取 `/Users/zmw/discount_system/specs/public_api_doc.md` 作为公开行为来源。
- 不读取 `src/`、`tests/` 或非公开 specs，除非用户明确要求做灰盒验证。
- 不直接写入 `/Users/zmw/discount_system`，除非用户明确批准。发布验证优先在 `/private/tmp` 创建独立 workspace，并复制公开文档进入 `docs/`。
- 不复用当前 aitest-kit 的历史迁移产物作为结论；需要从 init 后的干净 workspace 重新验证。

验收点：

- 从公开 API 文档出发，能按新模板建立独立 workspace。
- codegen 产物不依赖 aitest-kit 的 coupon/AB 示例资产。
- 真实服务启动后，generated pytest 可 collect；具备环境时可运行通过。

## P0 任务

| 编号 | 任务 | 产物 | 验收 |
|------|------|------|------|
| P0-1 | 安装态验证设计 | 本 spec 的命令清单 | 明确源码态、安装态、外部项目三类验证 |
| P0-2 | 构建包验证 | wheel/sdist | wheel 中包含模板、schema、refs、AGENTS/CLAUDE、三套 skills、docs 骨架 |
| P0-3 | 从非源码目录安装并运行 CLI | 临时 venv | `aitest --help`、`aitest init` 可执行 |
| P0-4 | 空 workspace 体验 | CLI 输出 | 无模块时提示“暂无模块/下一步创建 cases/profile”，不表现为崩溃 |
| P0-5 | 最小 demo workspace | `/private/tmp` 临时项目 | `validate-profile`、`dump-ir`、`codegen`、pytest collect 通过 |
| P0-6 | Quickstart | `docs/usebook/aitest_quickstart.md` | 新用户按文档能跑通最小模块 |
| P0-7 | Profile Guide | `docs/usebook/codegen_profile_guide.md` | 说明 assertion_rules、case_flows、case_bodies 的使用边界 |
| P0-8 | 常见错误排查 | `docs/usebook/codegen_troubleshooting.md` | 覆盖 E001、profile schema、unknown module_type、stale generated、fixture env |
| P0-9 | 迁移 Playbook 定稿 | `docs/usebook/codegen_new_project_migration_playbook.md` | 与模板、Quickstart、Profile Guide 口径一致 |
| P0-10 | 全量回归 | 命令输出 | compileall、pytest tests、profile gate、codegen check、generated collect 通过 |

## P1 任务

| 编号 | 任务 | 产物 | 验收 |
|------|------|------|------|
| P1-1 | Release note | `CHANGELOG.md` | 写清 v0.1 支持/不支持/实验能力 |
| P1-2 | CLI help 文案统一 | CLI help | `init/codegen/run/report --help` 与文档一致 |
| P1-3 | CI 最小矩阵 | `.github/workflows/ci.yml` | 覆盖 build、init、codegen、pytest、release artifact inspection |
| P1-4 | 安全/隐私说明 | README / Quickstart / template README | 说明 `.env`、凭证、报告脱敏、响应数据风险 |
| P1-5 | API 稳定性标记 | README / Profile Guide / CHANGELOG / template README | 标注 Markdown case、profile schema、workspace layout 的稳定性 |

## P2 任务

| 编号 | 任务 | 产物 | 验收 |
|------|------|------|------|
| P2-1 | 第二个非策略类真实项目演练 | 演练记录 | 验证模板不偏向推荐/策略系统 |
| P2-2 | 自动反向提取 case_flow | 设计 spec | 放到 v0.2，不阻塞 v0.1 |
| P2-3 | 自动应用 promotion patch | 设计 spec | 放到 v0.2，不阻塞 v0.1 |

## 发布前必跑命令

源码态：

```bash
python3 -m compileall aitest_kit
python3 -m pytest tests -q
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
git diff --check
```

安装态：

```bash
python3 -m venv /private/tmp/aitest_release_venv
/private/tmp/aitest_release_venv/bin/python -m pip install build "setuptools>=68.0"
python3 -m build
/private/tmp/aitest_release_venv/bin/python -m pip install dist/aitest_kit-*.whl
cd /private/tmp
/private/tmp/aitest_release_venv/bin/aitest --help
/private/tmp/aitest_release_venv/bin/aitest init --target /private/tmp/aitest_release_project
/private/tmp/aitest_release_venv/bin/aitest codegen --workspace /private/tmp/aitest_release_project --all --validate-profile
```

最小 demo 模块：

```bash
/private/tmp/aitest_release_venv/bin/aitest codegen --workspace /private/tmp/aitest_release_project demo --validate-profile
/private/tmp/aitest_release_venv/bin/aitest codegen --workspace /private/tmp/aitest_release_project demo --dump-ir
/private/tmp/aitest_release_venv/bin/aitest codegen --workspace /private/tmp/aitest_release_project demo
cd /private/tmp/aitest_release_project
/private/tmp/aitest_release_venv/bin/python -m pytest test_workspace/tests/generated --collect-only -q
```

PyPI 发布前检查：

```bash
python3 -m pip index versions aitest-kit
python3 -m build
python3 -m twine check dist/*
```

期望：

- `pip index versions aitest-kit` 在首次发布前返回 `No matching distribution found for aitest-kit`，表示当前包名未被公开占用。
- `twine check dist/*` 返回 `PASSED`，表示 README 长描述和包元数据可被 PyPI 接受。
- `dist/` 中只上传本次要发布的 `aitest_kit-0.1.1.tar.gz` 和 `aitest_kit-0.1.1-py3-none-any.whl`。

TestPyPI 试发布：

```bash
python3 -m twine upload --repository testpypi dist/aitest_kit-0.1.1*
python3 -m venv /private/tmp/aitest_testpypi_install_venv
/private/tmp/aitest_testpypi_install_venv/bin/python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  aitest-kit==0.1.1
/private/tmp/aitest_testpypi_install_venv/bin/aitest --help
```

正式 PyPI 发布：

```bash
python3 -m twine upload dist/aitest_kit-0.1.1*
python3 -m venv /private/tmp/aitest_pypi_install_venv
/private/tmp/aitest_pypi_install_venv/bin/python -m pip install aitest-kit==0.1.1
/private/tmp/aitest_pypi_install_venv/bin/aitest --help
```

发布约束：

- 上传 PyPI 属于不可逆发布动作，必须先确认版本号、dist 文件清单和目标仓库。
- 同一版本号在 PyPI/TestPyPI 上传后不能覆盖；如果上传后发现问题，只能发布新版本。
- 不在 `twine upload` 命令中写入 token；使用环境变量、keyring 或交互式输入。
- 发布成功后，再更新验收记录中“PyPI 不可用”的历史说明，并用真实 `pip install aitest-kit==0.1.1` 结果补充最终验证。

## 当前验证记录

2026-05-08 已完成 P0 安装态主链路验证：

- wheel/sdist 不包含 `coupon_system` 或 `ab_experiment_sdk`。
- wheel 包含 workspace 模板、schema、refs、AGENTS/CLAUDE 和三套 skills。
- 从 `/private/tmp` 非源码目录执行 `aitest --help` 成功。
- `aitest init --target /private/tmp/aitest_release_project --force` 成功。
- 空 workspace 执行 `--validate-profile` 输出下一步创建 `cases/<module>` 和 profile 的提示。
- 最小 demo 模块通过 `--validate-profile`、`--dump-ir`、正式 codegen、`--check` 和 pytest collect。
- 发现并修正运行期依赖：`pytest` 已纳入基础依赖，因为 `aitest run` 和 generated collect 是产品主路径。

2026-05-08 已完成 `discount_system` 外部真实项目最小验证：

- 只读取 `/Users/zmw/discount_system/specs/public_api_doc.md` 作为行为来源。
- 使用安装态 `aitest init` 创建 `/private/tmp/aitest_discount_release_project`。
- 在独立 workspace 内建立 `discount_policy` 最小模块，覆盖默认规则和 VIP checkout 规则。
- `--validate-profile`、`--dump-ir`、正式 codegen、`--check`、pytest collect 全部通过。
- 启动 `/Users/zmw/discount_system` 后，以 `HTTP_BASE_URL=http://127.0.0.1:18081` 执行 generated pytest，结果 `2 passed`。
- 迁移口径补充：Markdown 场景变量中的“请求覆盖”用于人类 review 和 trace；当前确定性 codegen 的真实请求体差异以 profile `request_overrides` 为准。

2026-05-08 已完成 P1 发布收口：

- 新增 `CHANGELOG.md`，记录 v0.1 支持范围、不支持项、实验能力、安全隐私说明。
- 统一 `aitest --help`、`aitest init --help`、`aitest codegen --help`、`aitest run --help`、`aitest report --help` 的产品化文案。
- 新增 `.github/workflows/ci.yml`，覆盖 Python 3.9/3.11 下的 compileall、unit tests、profile gate、codegen check、generated collect、empty workspace init 和 package build。
- README、Quickstart、Profile Guide 和 template README 均补充安全/隐私与稳定性边界。
- 修正 package data，确保 wheel/sdist 中包含 `aitest_kit/templates/project_workspace/README.md`。
- 安装态复验：从 wheel 重新安装后执行 `aitest init --target /private/tmp/aitest_p1_project --force` 成功，空 workspace `--validate-profile` 输出友好下一步提示。

2026-05-08 已完成人工 release review 收口：

- README 第一主路径调整为新项目 `aitest init` 接入，本仓 `coupon_system`/`ab_experiment_sdk` 明确作为示例回归资产。
- 新项目迁移 Playbook 和 workspace 模板补充黑盒首轮信息边界，避免从目标系统源码或已有测试推断业务规则。
- `aitest run --help` 补充 `MODULE`/`PYTEST_ARGS` 参数展示和示例。
- CI package build 后增加 artifact inspection，检查 wheel 包含 workspace 模板关键文件，且 wheel/sdist 不包含 `coupon_system`、`ab_experiment_sdk`、`discount_system`。

## 完成定义

v0.1 release 可以发布的最低标准：

1. P0 全部完成。
2. P1 全部完成。
3. 安装态验证不依赖 aitest-kit cwd。
4. 新 workspace 不包含 coupon/AB/discount 历史资产。
5. Quickstart、Profile Guide、Troubleshooting、Playbook、CHANGELOG 存在且互相引用。
6. `discount_system` 外部真实项目演练有明确结论：通过、阻塞项或待补测试基础设施。
