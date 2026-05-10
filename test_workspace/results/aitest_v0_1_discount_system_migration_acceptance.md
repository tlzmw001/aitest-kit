# aitest-kit v0.1 discount_system 新项目迁移验收记录

## 结论

`discount_system` 作为独立目标项目，已完成一次从公开文档到真实 pytest 执行的新项目迁移验收。

验收结论：**通过**。

最终结果：

```text
16 passed in 0.09s
```

本次验证说明：`aitest-kit 0.1.0` 通过本地 release wheel 安装后，可以在目标项目内初始化隔离 workspace，并完成：

```text
公开文档
  -> knowledge-build
  -> test-design
  -> test-codegen
  -> profile/case_flow 回灌
  -> codegen --check
  -> generated pytest
  -> 真实 HTTP 服务执行
  -> emitter-build 冒烟分析
```

## 验收边界

目标项目：

```text
/Users/zmw/discount_system
```

AITest workspace：

```text
/Users/zmw/discount_system/aitest_workspace
```

唯一公开行为输入：

```text
/Users/zmw/discount_system/aitest_workspace/docs/public_api_doc.md
```

迁移阶段禁止读取：

```text
/Users/zmw/discount_system/src
/Users/zmw/discount_system/tests
/Users/zmw/discount_system/reports
/Users/zmw/discount_system/specs/development_session_prompt.md
/Users/zmw/discount_system/specs/implementation_spec.md
/Users/zmw/discount_system/specs/sut_development_spec.md
/Users/zmw/AIAutoTest
```

## 安装与初始化

首次尝试从当前 pip 源安装失败：

```text
ERROR: Could not find a version that satisfies the requirement aitest-kit (from versions: none)
ERROR: No matching distribution found for aitest-kit
```

随后使用本地 release wheel 验证：

```bash
python -m pip install /Users/zmw/AIAutoTest/dist/aitest_kit-0.1.0-py3-none-any.whl
python -m pip show aitest-kit
which aitest
aitest --help
```

安装结果：

```text
Name: aitest-kit
Version: 0.1.0
Location: /Users/zmw/discount_system/.venv/lib/python3.9/site-packages
/Users/zmw/discount_system/.venv/bin/aitest
```

CLI 命令可用：

```text
Commands:
  codegen
  init
  report
  run
```

初始化隔离 workspace：

```bash
aitest init --target /Users/zmw/discount_system/aitest_workspace
```

结果：

```text
Workspace initialized: /Users/zmw/discount_system/aitest_workspace
Created: 50, overwritten: 0
```

初始化资产包含：

```text
AGENTS.md
CLAUDE.md
.agents/skills/*
.claude/skills/*
.codex/skills/*
aitest_config/
test_workspace/
```

未出现旧模板目录：

```text
templates/
project_workspace/
```

空 workspace 体检：

```bash
aitest codegen --all --validate-profile
```

结果：

```text
No modules found under the configured cases directory.
Next step: create test_workspace/cases/<module>/business.md and a matching codegen profile under test_workspace/tests/fixtures.

Profile validation summary: modules=0, errors=0, warnings=0
```

## knowledge-build 验证

输入：

```text
docs/public_api_doc.md
```

生成文件：

```text
test_workspace/knowledge/L0_system_architecture.md
test_workspace/knowledge/L1/discount_policy.md
test_workspace/knowledge/L2/public_api_initial.md
```

验收判断：

- 模块切分为 `discount_policy`，覆盖策略评估、查询、删除。
- 接口契约记录完整：`GET /health`、`POST /api/v1/discount/policy`、`GET /api/v1/discount/decisions/{request_id}`、`DELETE /api/v1/discount/decisions/{request_id}`。
- 不确定点合理标为 `[?]`，包括 validation error body 精确结构、成功 HTTP 状态码、空字符串字段、重复 `request_id`、并发一致性和日志/指标盲区。
- 未混入源码、测试实现、AIAutoTest 旧项目内容。

结论：**通过**。

## test-design 验证

生成文件：

```text
test_workspace/cases/discount_policy/business.md
test_workspace/cases/discount_policy/boundary.md
```

业务用例 8 条：

```text
TC-DP-001 health check
TC-DP-002 black 用户高优先级
TC-DP-003 stock=0 高优先级
TC-DP-004 campaign
TC-DP-005 vip checkout
TC-DP-006 default
TC-DP-007 成功评估后查询
TC-DP-008 删除后查询不存在
```

边界用例 8 条：

```text
TC-DP-009 item_price=0
TC-DP-010 user_level 非法
TC-DP-011 scene 非法
TC-DP-012 item_price<0
TC-DP-013 stock<0
TC-DP-014 缺少必填字段 item_id
TC-DP-015 查询不存在
TC-DP-016 删除不存在
```

验收判断：

- 共享 HTTP 基础请求体是合法 JSON。
- 未使用 `{{placeholder}}` 模板占位符。
- 未生成重复 `request_id`、空字符串、并发、重启后状态这类未定义或不稳定自动化用例。
- validation error body 精确字段未被断言。

结论：**通过**。

## test-codegen 验证

### 首次自然指令结果

真实用户式首次指令后，AI 倾向于直接生成 generated pytest，未完成 codegen 链路回灌。

失败信号：

```text
test_workspace/tests/fixtures/discount_policy.py 不存在
test_workspace/tests/fixtures/codegen_profile_discount_policy.md 不存在
[WARNING] W501: codegen profile not found
dump-ir 中 api_path 仍为 /api/v1/replace-me
aitest codegen discount_policy --check 显示 generated stale
```

验收判断：首次自然指令 **未通过**。这符合“AI 可先探索，但不能停留在手写 generated”的项目设计。

### 二次反馈回灌结果

用户将失败现象反馈给 AI 后，AI 将探索结果回灌到正式 codegen 链路。

新增文件：

```text
test_workspace/tests/fixtures/discount_policy.py
test_workspace/tests/fixtures/codegen_profile_discount_policy.md
```

最终 profile 状态：

```text
16 条用例全部使用 structured_case_flow
case_bodies: 0
UNPARSED: 0
```

fixture 关键质量点：

```text
服务地址读取 DISCOUNT_SYSTEM_BASE_URL，兼容 HTTP_BASE_URL
缺少服务地址时 pytest.fail
httpx.Client 使用 httpx.HTTPTransport()
只调用公开 HTTP API
```

验证命令：

```bash
aitest codegen discount_policy --validate-profile
aitest codegen discount_policy --dump-ir
aitest codegen discount_policy
aitest codegen discount_policy --check
python3 -m compileall test_workspace/tests/fixtures/discount_policy.py test_workspace/tests/generated
python3 -m pytest test_workspace/tests/generated --collect-only -q
```

结果：

```text
Profile validation summary: modules=1, errors=0, warnings=0
All generated files are up to date.
16 tests collected in 0.04s
```

结论：二次反馈回灌后 **通过**。

## 真实服务执行

启动服务时目标项目环境缺少运行依赖：

```text
ModuleNotFoundError: No module named 'uvicorn'
```

该问题归类为目标项目运行环境准备，不属于 `aitest-kit` codegen 问题。补齐目标服务依赖后，服务启动成功。

健康检查：

```bash
curl -sS http://127.0.0.1:18081/health
```

结果：

```json
{"status":"ok"}
```

真实 pytest 执行：

```bash
cd /Users/zmw/discount_system/aitest_workspace
source /Users/zmw/discount_system/.venv/bin/activate
env DISCOUNT_SYSTEM_BASE_URL=http://127.0.0.1:18081 python3 -m pytest test_workspace/tests/generated -q
```

结果：

```text
................                                                                                                 [100%]
16 passed in 0.09s
```

结论：**通过**。

## emitter-build 冒烟验证

输入边界：

```text
test_workspace/tests/generated/
test_workspace/tests/fixtures/codegen_profile_discount_policy.md
test_workspace/tests/fixtures/discount_policy.py
test_workspace/cases/discount_policy/
test_workspace/knowledge/
```

结论：

```text
当前模块 16 条用例全部由 case_flows 覆盖。
未发现 case_bodies。
没有 case_bodies -> case_flows 晋升对象。
未修改任何文件。
```

识别出的后续沉淀方向：

1. `policy decision` 成功决策断言模板。
2. `validation failure does not persist` 验证失败不落库流程模板。
3. `decision not found` 404 / `DECISION_NOT_FOUND` 断言块。
4. 纯 `structured_case_flow` generated 文件中默认 HTTP boilerplate 噪音优化。
5. profile 说明区中的 base URL 环境变量描述与 fixture 保持一致。

结论：**通过**。

## 产品发现

### P1：安装口径

本轮迁移验收时，`pip install aitest-kit` 在本机默认 pip 源不可用。v0.1 当时通过本地 release wheel 验证通过。

2026-05-10 已完成 PyPI 发布：`aitest-kit==0.1.1` 已发布到 TestPyPI 和正式 PyPI，并分别通过干净 venv 安装验证、`aitest --help`、`aitest init` 和空 workspace profile gate。

### P1：test-codegen skill 需要强调探索回灌

真实用户自然指令第一次停留在手写 generated，未生成 fixture/profile。已将经验同步到：

```text
.codex/skills/test-codegen/SKILL.md
.claude/skills/test-codegen/SKILL.md
.agents/skills/test-codegen/SKILL.md
aitest_kit/templates/project_workspace/.codex/skills/test-codegen/SKILL.md
aitest_kit/templates/project_workspace/.claude/skills/test-codegen/SKILL.md
aitest_kit/templates/project_workspace/.agents/skills/test-codegen/SKILL.md
```

核心规则：

```text
AI 可先手写探索，但最终必须回灌到 fixture + codegen_profile + case_bodies/case_flows，并通过 aitest codegen --check。
```

### P2：纯 structured_case_flow generated boilerplate

当一个 generated 文件全部用例都是 `structured_case_flow`，且不使用默认 HTTP helper 时，当前仍可能生成：

```text
http_helper import
BASE_REQUEST
_req()
```

建议后续优化 emitter：文件内不存在 `default_http` / `default_grpc` case 时，不生成默认请求模板和相关 import。

### P2：可选 named flow/template

`discount_policy` 中重复模式明显：

- 成功策略评估并断言决策字段。
- 验证失败后查询记录不存在。
- 查询不存在决策的 404 / `DECISION_NOT_FOUND` 断言块。

这些模式暂时保留为 `case_flows` 即可。等更多新项目或模块出现相同模式后，再考虑沉淀为 profile/emitter 层的 named flow/template。

### P3：profile 说明一致性

`discount_policy` profile 说明区曾出现 base URL 描述与 fixture 实际读取逻辑不完全一致的问题。后续 test-codegen 生成 profile 时，应确保说明区和 fixture 真实行为一致。

## 总体判断

本次验收覆盖了 `aitest-kit v0.1` 的新项目核心飞轮：

```text
安装 release wheel
  -> init workspace
  -> knowledge-build
  -> test-design
  -> test-codegen
  -> codegen gate
  -> pytest collect
  -> 真实服务执行
  -> emitter-build 冒烟分析
```

最终结论：**v0.1 新项目迁移主链路成立，可以作为后续 PyPI 发布和 v0.1.1/v0.2 规划的基线。**

## PyPI 发布前检查

执行日期：2026-05-10

本次新增发布准备：

- `pyproject.toml` 补充 README 长描述、MIT SPDX license、license file、作者、关键词、classifiers 和项目链接。
- `README.md` 安装说明改为 PyPI 安装，并保留本地 release wheel 安装方式。
- `CHANGELOG.md` 记录 PyPI-ready metadata。
- `test_workspace/plans/aitest_v0_1_release_spec.md` 补充 PyPI/TestPyPI 发布步骤、不可逆约束和发布后验证命令。

验证结果：

```text
python3 -m compileall aitest_kit
结果：0 错误

python3 -m pytest tests -q
结果：80 passed, 2 warnings in 2.83s

python3 -m aitest_kit.cli codegen --all --validate-profile
结果：modules=11, errors=0, warnings=0

python3 -m aitest_kit.cli codegen --all --check
结果：All generated files are up to date.

python3 -m pytest test_workspace/tests/generated --collect-only -q
结果：198 tests collected in 0.09s

python3 -m pip index versions aitest-kit
结果：ERROR: No matching distribution found for aitest-kit

python3 -m build
结果：Successfully built aitest_kit-0.1.1.tar.gz and aitest_kit-0.1.1-py3-none-any.whl

python3 -m twine check dist/*
结果：PASSED for wheel and sdist

本地 wheel 干净 venv 安装
结果：aitest-kit-0.1.1 installed successfully

aitest --help
结果：CLI 可用，展示 init/codegen/run/report

aitest init --target /private/tmp/aitest_release_pypi_verify_project --force
结果：Created: 50, overwritten: 0

aitest codegen --workspace /private/tmp/aitest_release_pypi_verify_project --all --validate-profile
结果：modules=0, errors=0, warnings=0，并输出下一步创建 cases/profile 的提示
```

TestPyPI 发布验证：

```text
twine upload --repository testpypi dist/aitest_kit-0.1.1*
结果：上传成功
View at: https://test.pypi.org/project/aitest-kit/0.1.1/

python3 -m pip index versions aitest-kit --index-url https://test.pypi.org/simple/
结果：aitest-kit (0.1.1), Available versions: 0.1.1

pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ aitest-kit==0.1.1
结果：Successfully installed aitest-kit-0.1.1

aitest --help
结果：CLI 可用，展示 init/codegen/run/report

aitest init --target /private/tmp/aitest_testpypi_project_011 --force
结果：Created: 50, overwritten: 0

aitest codegen --workspace /private/tmp/aitest_testpypi_project_011 --all --validate-profile
结果：modules=0, errors=0, warnings=0，并输出下一步创建 cases/profile 的提示
```

正式 PyPI 发布验证：

```text
twine upload dist/aitest_kit-0.1.1*
结果：上传成功
View at: https://pypi.org/project/aitest-kit/0.1.1/

python3 -m pip index versions aitest-kit
结果：aitest-kit (0.1.1), Available versions: 0.1.1

pip install aitest-kit==0.1.1
结果：Successfully installed aitest-kit-0.1.1

pip show aitest-kit
结果：Name: aitest-kit, Version: 0.1.1

aitest --help
结果：CLI 可用，展示 init/codegen/run/report

aitest init --target /private/tmp/aitest_pypi_project_011 --force
结果：Created: 50, overwritten: 0

aitest codegen --workspace /private/tmp/aitest_pypi_project_011 --all --validate-profile
结果：modules=0, errors=0, warnings=0，并输出下一步创建 cases/profile 的提示
```

最终发布结论：

- PyPI 页面：https://pypi.org/project/aitest-kit/0.1.1/
- TestPyPI 页面：https://test.pypi.org/project/aitest-kit/0.1.1/
- 新用户安装命令：`pip install aitest-kit==0.1.1`
- release 版本与 GitHub tag `v0.1.1` 一致。
