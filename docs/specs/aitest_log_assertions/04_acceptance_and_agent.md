# 分片 4 · 接入验收与 Agent 交付

2026-11-19 · 实现前 Spec

## 1. 目标、依赖与基线

本片验证已安装的 Kit 能完成用例生成、并发调用、后台日志断言、清理及报告交付。依赖 [01 用例与客户端](01_profile_and_client.md)、[02 执行与恢复](02_execution_and_recovery.md)、[03 结果与清理](03_results_and_cleanup.md) 的实现和定向测试通过，契约以对应分片为准。

核对基线为 Kit 工作目录 `729a8d1`、发布标签 `v0.6.0`、Agent `e95fc11`。工作目录包版本为 `0.5.0`，实施前须确定以 `v0.6.0` 为兼容基线的候选提交和新版本号，记录差异，避免将本地分支版本当作云端已安装版本。

Agent 的 `release/cloud-test-requirements.txt` 当前锁定 Kit `0.6.0`、pytest `9.1.1`、httpx `0.28.1`；`release/cloud-test-toolchain.json` 记录 Kit wheel 摘要。用例并发通过 Kit 的 `parallel` extra 安装 `pytest-xdist==3.8.0`，云端依赖锁还须包含 execnet 等解析后的传递依赖。对候选组合执行兼容测试后固定完整锁。

本片交付完整验收样例、自动化门禁、AI 分发验证记录和云端验收清单。模板激活、远程部署、发布包、修改真实环境配置和清理共享测试日志，按本次实际操作授权执行。

## 2. 文件归属与验收材料

以下为本片实现时新增或更新的内容，当前文档不表示这些实现已经存在。

| 位置 | 交付要求 |
| --- | --- |
| `tests/log_assertions_acceptance/` | 集中放置真实 CLI、HTTP 服务、安装包、旧 workspace 和报告一致性验收；复用仓库已有测试辅助能力 |
| `aitest_kit/templates/project_workspace/examples/log_assertions/` | 沿用分片 1 的最小样例，补充多请求与正反场景。wheel 安装后经 init 复制到 workspace 的 `examples/log_assertions/`。验收从该目录取知识输入、Markdown、registry、Harness 和 suite profile，覆盖文本、JSON、多请求和响应派生期望 |
| `docs/usebook/aitest_log_assertions.md` | 从安装、环境变量、生成、运行、恢复到查看报告的一条完整操作路径，复用前 3 片的字段和示例 |
| 包内模板及分发检查 | 校验 Schema、profile 手册、neutral skills 及引用文件进入 wheel 和 sdist；更新范围由 01 片确定 |
| Agent 仓库发布文件 | 核对 Kit wheel、两份工具链锁和候选验收包，沿用现有构建入口 |

运行记录保存在验收输出目录，至少包含候选提交、wheel SHA-256、解释器与依赖版本、命令和退出码、报告路径、通过或待验项。真实 URL 和凭证由环境提供，归档只保留环境变量名和脱敏后的连接标识。

## 3. 本地端到端验收装置

在临时目录安装候选 wheel，测试工作目录位于源码树之外。通过真实 `python -I -m aitest_kit.cli` 子进程执行 init、codegen、run、report 和 resume。HTTP 端使用绑定 loopback 动态端口的本地服务，分别模拟待测业务接口和日志平台，地址通过测试进程环境注入。

业务接口接收请求后登记事件与可控响应。日志端按平台契约提供 sources、ui-settings、status、事件分页、cleanup 和回执，用 HTTP 调用记录核对来源、请求 ID、分页版本、在途读取数和删除幂等键。限额测试将服务端页大小及批量上限设为低于 Kit 默认值。客户端、协调器、SQLite、生成代码、pytest 插件、collector 与 renderer 均走产品入口。配置使用 `aitest_config/log_assertions.yaml`，环境变量默认为 `AITEST_LOG_BASE_URL`、`AITEST_LOG_TOKEN`，测试 Token 由 fixture 生成。

控制端用线程事件、屏障或显式释放指令推进各阶段。服务发回的响应是验收输入，最终结果来自真实 CLI 输出的文件。取消和崩溃只作用于本片创建的进程和临时状态。fixture 结束时释放本片创建的监听器及进程。

### 3.1 生成和 HTTP 契约

| 场景 | 必须验证的结果 |
| --- | --- |
| 文本、JSON、多事件、响应派生 expected | 真实请求后冻结期望，正文按原类型交给检查，成功与故意不符均有对应报告 |
| 请求前登记、响应后绑定、请求失败 | 声明日志的调用发出前已有计划，允许响应后绑定。未声明日志的旧调用保留原业务报文，响应没有关联字段也可执行。已声明的步骤缺少关联值有明确错误 |
| 来源与 ID | 同 ID 不同 source、特殊路径段、同例多次请求均定位正确，清理使用精确 ID |
| 分页 | 覆盖多页、空筛选结果、大整数和 false/null；分页完整后执行检查，顺序符合接口契约 |
| 版本和可用性 | 中途 409 后丢弃旧页，重查状态，从最新可用版本首页取全量，所有参与断言的页版本一致；410、缺失结束能力、过期、不完整均形成规定错误 |
| 网络与授权 | 401/403、限流、暂时 5xx、断连及截止时间；重试有界，业务请求不会因日志重试而重发 |
| profile 失败 | 不存在的 request_step、后台引用 reply、非法代码及不支持操作在发业务请求前被 gate 拦截 |

### 3.2 两个并发数

测试至少提供六条独立用例、两个 suite。通过 pytest 生命周期记录以及 HTTP 服务账本共同证明上限，避免只凭总耗时推断并发。

| 配置 | 受控过程与验收 |
| --- | --- |
| `1 / 1` | A 完成即时阶段后将日志维持为采集中，观察 B 已发业务请求；任何时刻 setup 至 teardown 在途实例数不超过 1；同时验证的就绪请求不超过 1 |
| `4 / 2` | 阻塞四条用例的即时阶段，确认四条均进入且第五条未进入；释放后使至少三个请求就绪，阻塞事件读取，确认两条验证在途、第三条等待；释放后全部收敛 |
| 跨 suite | suite B 的业务调用与 suite A 剩余日志验证重叠，全 run 的用例和日志上限仍为 4 与 2 |
| 身份隔离 | 参数化实例、重复 case ID、同一 suite 被 task 多次选择及不同请求步骤各自归属正确；恢复沿用原身份 |
| 错误配置 | 0、负数、缺少 parallel extra、冲突的透传 `-n/--numprocesses` 等按 02 片拒绝，记录生效配置 |
| worker 与规则异常 | 终止一个 worker 后没有自动重发业务；规则执行超限按 02 片终止计算进程，验证名额被释放，其他请求继续完成 |

等待中的请求不占日志验证名额。测试用屏障保证至少两个请求确实并发验证，同时以计数器证明始终不超限。用例内自行发出的多个业务调用遵守 Harness 的能力约定。

### 3.3 最终结果、清理与恢复

| 场景 | 必须验证的结果 |
| --- | --- |
| 即时通过、日志失败 | case 最终失败；result.json、report.md、JUnit 与退出码一致 |
| teardown 失败 | 日志已通过仍保留请求，最终结果反映收尾失败 |
| on_success 与 retain | 清理场景显式配置 on_success，成功且结果保存后才提交；省略配置采用 retain，失败、错误、中断请求无清理调用 |
| 清理受理 | 202 记录任务 ID 后可结束本轮，不等待物理删除；回执状态按已知事实显示 |
| 仅清理提交失败 | 业务 case 保持 passed；整轮 exit=1；JUnit 增加独立基础设施 testsuite，三种报告均展示清理异常 |
| 清理重试 | 模拟服务已受理但响应丢失，重试复用相同幂等键和请求集合；其他用例日志不会被误删 |
| 短 TTL 与积压 | A 的证据保存后让平台过期，最终仍保留 A 的已完成结论；积压达到上限得到确定反馈 |
| 中断和恢复 | 在登记、读取、断言落盘和清理受理处分别中断，再 resume；沿用原期限、规则与 ID，已完成业务请求不重发 |
| latest 与互斥 | 恢复旧 run 不覆盖较新 latest；同 run 双恢复者按 02 片拒绝或互斥；取消保留已完成结果 |
| 报告安全与资源 | 报告有界摘要，无 Token/完整原始日志；SQLite 位于 `.aitest/runs/<run_id>/`，未进入报告交付目录 |

前两条命令分别验证两组并发上限。第三条使用专门中断的测试 run ID 验证恢复，并检查业务请求计数。

```bash
"$CANDIDATE_PY" -I -m aitest_kit.cli run --workspace "$ACCEPTANCE_WORKSPACE" --suite-file "$ACCEPTANCE_SUITE" --case-concurrency 1 --log-concurrency 1
"$CANDIDATE_PY" -I -m aitest_kit.cli run --workspace "$ACCEPTANCE_WORKSPACE" --suite-file "$ACCEPTANCE_SUITE" --case-concurrency 4 --log-concurrency 2
"$CANDIDATE_PY" -I -m aitest_kit.cli run --workspace "$ACCEPTANCE_WORKSPACE" --resume "$ACCEPTANCE_RUN_ID"
```

## 4. 安装包、旧 workspace 与 AI 入口

验收分为基础安装和带 `[parallel]` 安装两个干净环境。基础安装运行旧 suite 和 `1 / 1`；并发安装运行 `4 / 2`。云端需要并发时，其锁文件包含已验证的完整依赖。使用支持的 Python 版本矩阵，并至少覆盖 Windows 与 Linux 的 CLI、进程退出和恢复。以下解释器分别来自本片创建的两个临时 venv。

```bash
"$BASIC_PY" -m pip install "$KIT_WHEEL"
"$PARALLEL_PY" -m pip install "${KIT_WHEEL}[parallel]"
"$BASIC_PY" -m pip check
"$PARALLEL_PY" -m pip check
```

旧 workspace 由 `v0.6.0` 创建，包含原 profile、generated、历史 result.json、用户修改过的 Schema/skill 和自定义 Harness。在副本上执行候选 `upgrade --check/--apply`，核对安全更新与冲突列表，自定义内容保留。随后核对旧生成新鲜度、旧报告重渲染和无日志配置的运行。新日志语法需同步到 AI 实际读取的指南和 Schema，再通过 gate。

新增 AI 验收只向 Agent 提供候选 wheel 初始化后的 workspace、样例知识/需求和已知 Harness 能力，隐藏本仓源码、开发 Spec 和人工答案。安装后的文件可供 Agent 自行发现。按当前 Agent 工具提示，将 neutral skills 放到临时 workspace 的 `.claude/skills/`；也验证文档支持的 `.agents/skills/` 发现路径。已有用户目录按升级冲突处理。

要求 Agent 独立写出四类日志规则，包含纯文本、JSON 字段、多事件和响应派生期望，再完成以下真实命令。记录首次产物、诊断及修正，成功条件是最终 profile 和运行结果符合需求。

```bash
"$CANDIDATE_PY" -I -m aitest_kit.cli codegen --workspace "$ACCEPTANCE_WORKSPACE" --suite-file "$ACCEPTANCE_SUITE" --validate-profile
"$CANDIDATE_PY" -I -m aitest_kit.cli codegen --workspace "$ACCEPTANCE_WORKSPACE" --suite-file "$ACCEPTANCE_SUITE" --dump-ir
"$CANDIDATE_PY" -I -m aitest_kit.cli codegen --workspace "$ACCEPTANCE_WORKSPACE" --suite-file "$ACCEPTANCE_SUITE" --explain "$ACCEPTANCE_CASE_ID"
"$CANDIDATE_PY" -I -m aitest_kit.cli codegen --workspace "$ACCEPTANCE_WORKSPACE" --suite-file "$ACCEPTANCE_SUITE"
"$CANDIDATE_PY" -I -m aitest_kit.cli codegen --workspace "$ACCEPTANCE_WORKSPACE" --suite-file "$ACCEPTANCE_SUITE" --check
```

再故意将后台表达式改为引用 `reply`，要求 gate 定位 TC-ID 和规则，Agent 按分发指南改成 expected；恢复合法写法后，通过 run 产生成功及故意失败报告。修改日志规则后，旧 generated 必须被 freshness check 拒绝。真实模型暂不可用时，记录 AI 验收待执行，自动化 schema 测试单独计为通过。

## 5. 本地质量门禁

下列命令在实现完成的 Kit 候选 checkout 执行，采用已有构建和 CI 入口。用例依赖通过该候选的安装说明准备。端到端测试以 `tests/log_assertions_acceptance/` 为本片约定的发现入口。

```bash
python3 -m pytest tests/log_assertions_acceptance -q
python3 -m pytest tests -q
python3 -m compileall -q aitest_kit
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m pytest test_workspace/generated --collect-only -q
npm --prefix console_web run build
python3 -m build
git diff --check
```

构建后检查 wheel/sdist 成员并在源码树外安装真实 wheel，执行 `pip check`、init、doctor、旧 suite、新样例、report。测试报告记录所有命令的实际退出码。Console 的等待、失败和终态展示按 03 片补定向组件或端到端验证，并运行仓库既有前端门禁。

## 6. Agent 云端交付

Agent 的 Python 报告预检直接导入 `collect_result` 和 `render_markdown`，使用现有参数并读取 `summary.passed`。在候选 Kit 上执行该预检使用的真实 pytest XML 路径，确认兼容。[预检入口](../../../../naiyue-test-agent/naiyue_test_agent/cloud_runner/preflight.py)

按以下顺序准备交付材料，实际远程步骤由已授权的环境执行者完成。

1. 固定 Kit wheel 的版本和 SHA-256，更新 Agent 的两份工具链锁；加入 parallel 完整依赖并核验 pytest 兼容。运行 Agent 的 `test_template_preparation.py`、`test_acceptance_bundle.py`、`test_task_capabilities.py`、`test_aitest_kit_tool.py`。
2. 沿用 Agent `scripts/build_release.py` 生成平台 wheel，并用 `scripts/build_cloud_acceptance.py` 打候选包。该入口当前要求 macOS ARM64、Linux x86_64/ARM64、Windows x86_64 四个同源 wheel；候选目录、版本、wheel 清单和两份锁一致。
3. 在已批准的构建环境准备新 Runner 模板，`nyt cloud release prepare` 自动执行 full preflight。记录真实 image ID、工具链摘要和 TemplateReceipt，随后按既有流程登记、激活并创建验收任务。
4. 从实际 Runner 的 AITest 工具运行版本检查、doctor、样例和 pip check。分别覆盖无项目 `.venv` 与有 `.venv`；后者必须安装候选 Kit 和 parallel，缺依赖应暴露所选环境的错误。
5. 取得 `task_output_directory` 返回的本轮路径，CLI 完成后复制最终报告和必要的脱敏验收证据；待云端快照完成，下载文件并比对 SHA-256。任务状态 SQLite、环境文件及凭证不作为交付文件。

```bash
# 在 Agent 仓库，环境变量均指向本轮明确选择的候选文件
"$AGENT_PY" -m pytest tests/cloud/test_template_preparation.py tests/cloud/test_acceptance_bundle.py tests/cloud/test_task_capabilities.py tests/test_aitest_kit_tool.py -q
"$AGENT_PY" -m scripts.build_cloud_acceptance --root "$AGENT_ROOT" --output "$CANDIDATE_BUNDLE_DIR" --wheel "$AGENT_MACOS_ARM_WHEEL" --wheel "$AGENT_LINUX_X86_WHEEL" --wheel "$AGENT_LINUX_ARM_WHEEL" --wheel "$AGENT_WINDOWS_WHEEL" --kit "$KIT_WHEEL"
# 仅在已授权的 Linux 构建环境执行，配置由环境执行者提供
"$AGENT_PY" -m naiyue_test_agent.cli cloud release prepare "$CANDIDATE_RELEASE_ID" --settings "$TEMPLATE_BUILD_SETTINGS"
```

云端工具实际以所选解释器的 `-I -m aitest_kit.cli` 执行。通过 Shell 在同一环境核验以下内容，并在 AITest 工具中运行 `doctor` 与上述样例，避免只测 Coordinator 的解释器。

```bash
python -I -c 'import sys,importlib.metadata as m; print(sys.executable); print({n:m.version(n) for n in ("aitest-kit","pytest","pytest-xdist","httpx")})'
python -I -m pip check
```

## 7. 真实平台与隧道待验项

从 Runner 容器使用配置中的日志 base URL 调用接口。隧道以该容器看到的入口核验，业务服务与日志服务分别验证可达。实际 Token 仅由运行环境注入，HTTP 请求复用 Kit 的认证和客户端行为。

| 验收项 | 通过证据 |
| --- | --- |
| 来源与字段 | 实际来源可见，completion_supported 正确；Harness 关联值、`module.yaml.log_capture.source_id` 和平台映射一致 |
| 真实 Kafka 完成 | 经业务请求产生事件和 end；COMPLETE 后事件可读且有序，分页与版本满足客户端契约 |
| 成功/失败 | 真实服务各跑一条通过与故意不符，核对事件、结果、JUnit、退出码 |
| 清理 | 仅使用本轮专用前缀和精确 reqIds，on_success 得到 202；失败与 retain 仍可读至 TTL |
| 隧道异常 | 在专用验收连接模拟短断连，恢复有界重试；环境不允许断连时该项待验 |
| 报告下载 | Runner 得到终态后，用户或 Agent 从现有云端文件链路下载并核对摘要 |

日志平台不可访问时，完成本地 HTTP、安装包和 AI 可执行门禁，并将本节逐项标为待验，记录阻塞环境、所需来源/入口及应执行的场景。已有 Mock 通过记录只证明 Kit 对给定契约的处理，真实平台和云端验收分别保留实际结果。

## 8. 完成条件

本片验收表覆盖前述场景并逐项填入 pass、fail 或 pending，附对应产物。发布候选须通过本地质量门禁和安装包验证；面向云端启用还需通过真实模板、Runner、隧道和产物下载验证。每个 pending 明确所缺环境及后续执行者，保留待验状态至取得真实证据。
