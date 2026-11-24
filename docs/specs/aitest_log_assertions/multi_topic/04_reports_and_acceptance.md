# 分片 04 · 多来源结果、兼容和交付验收

本片让测试人员从一条用例的报告中直接看出哪个来源通过、哪个仍在等待，以及最终失败的原因。开发输入为[总体评审稿](../multi_topic_review.md)和[平台 HTTP 增量契约](../../log_capture_platform_delivery/07_observed_topic_handoff.md)。下列测试是候选版本的验收条件。

## 1. 报告契约

沿用 `result.json` 的 `log_validation.schema_version=1`，新增可选字段。一条用例仍产生一个 outcome、一个 JUnit testcase，`summary.pending/failed/error` 按用例计数。多单元任务的根报告和子报告采用相同口径。

| 位置 | 写入和读取要求 |
| --- | --- |
| `cases[].log_validation` | 保留 `immediate_outcome`、`attempt`、`unit_index` 和 `requests[]`。一项代表当前 attempt 的一个 `(request_step, source_id)`。同一业务请求的两项可以有相同 reqId。按 profile 首次声明顺序展示；同一实际来源的多组检查挂在同一项下。 |
| `requests[]` | 保留 `reqId/capture_state/availability/version/rules/cleanup`。增加可选的 `result`（来源行的运行状态转小写）与 `reason`（协调器记录的终态原因，可为 null），便于区分来源超时和内容检查失败。计划中的来源应在等待、提前失败和恢复后可见。补齐计划项时按步骤和来源联合匹配。未绑定 ID 为 null，尚未执行的检查沿用 pending/not_run。 |
| `last_observation` | 最近一次成功解码并匹配本对键的状态结果。包含 `observed_at`（Kit 收到响应时的 UTC RFC 3339 时间）、`result`（FOUND 或 NOT_FOUND）、`capture_state/availability/version/event_count/expected_event_count`。成功返回 NOT_FOUND 时后五项为 null。没有可信状态响应时整个对象为 null，界面显示“未知”。计数 0 与未知分别显示。 |
| `last_poll_error` | 无错误为 null。最近轮询失败记录安全的 `{code, at}`，保留先前成功观测；随后成功轮询时清空。读页错误由取证结果记录。平台就绪的版本与实际完成取证的版本按协调器重查结果更新，不混用跨版本的页。 |
| `rules[]`、`cleanup` | 规则路径保留原 profile 的全局 `group_index` 及检查下标。检查显示结果、原因及现有脱敏摘要。跨分区证据定位同时保留 partition 和 offset（十进制字符串）。沿用来源级 `policy/state/job_id/reason`，显示清理回执对应的来源。 |

即时断言失败、setup/teardown 异常、skip 和从未执行的步骤沿用现有结算优先级。仅当即时阶段以及该例全部必需来源均通过，才允许按来源提交显式 `on_success` 的精确清理。提交失败在 run 级记 issue 并影响退出状态，已通过的断言仍显示通过。

| 情形 | 预期报告及命令行为 |
| --- | --- |
| main 通过，perf COLLECTING（1/2） | 进度报告仅有一条 pending 用例，展示两行来源。main 已通过；perf 显示最近观测时间和 1/2。非终态 `final=false, exit_code=null`。 |
| 显式选择来源的步骤到期，最近有效观测为仍未齐且之后无持续通信错误；或平台明确返回可用记录已采集超时 | 对应来源 `failed`，原因 `LOG_READINESS_TIMEOUT`，`phase=log_evidence`，分类 `ASSERTION_FAILURE`。该例 failed，JUnit 写 failure，命令非零。另一来源的检查结果仍可见，整例零清理。 |
| 无可信观测、持续断网、协议无效、证据过期或缺口 | 沿用取证错误结算，case 为 error，分类 `ENVIRONMENT_ERROR`，终态命令非零。明确鉴权或能力错误可提前终止；发生在运行前的预检失败沿用 `BLOCKED_RUN`。 |
| 两个来源都齐，性能日志的字符串检查失败 | 性能来源展示触发失败的原表达式及安全摘要，`phase=log_assertion`，用例 failed。过期或缺失的正文不能产生内容断言成功。 |
| 0.7.0 用例及旧运行 | 整个步骤的断言组均省略 `source` 时沿用旧超时分类；仅显式选择一个别名也启用新超时语义。旧报告缺少新增字段时仍可打开和重渲染。 |

实现定位：

- `aitest_kit/log_assertions/projection.py` 目前按 `seen_steps` 补项、按 phase 映射 failure 分类。调整为复合键和对应原因分类。将分片 03 的观测事实读入同一 SQLite 快照，覆盖未终结项、重试历史、根/子报告和 JUnit。当来源因未齐而失败，来源行保留 failed 及原因；尚未执行的 checks 标记 not_run。case.failure 从来源原因生成，与已有逐条内容检查的结果分开。JUnit 沿用现有单独记录 run 级基础设施 issue 的方式。
- `aitest_kit/report/renderer.py` 在“日志验证”中按用例、步骤列出依赖的来源，各行显示来源、最近平台状态、已知条数、验证结果和清理回执。较长内容保留在结构化 JSON。正文、请求输入、Authorization 和 Token 不进入报告、异常或 CLI 输出。
- Console 的 `aitest_kit/console/workspace.py` 已从同一 JSON 生成 Markdown，`console_web/src/views/ReportsView.vue` 已有 Markdown/JSON 标签。复用详情与刷新入口。列表沿用用例级摘要。用旧报告、多来源中间态和终态校验详情与 CLI 一致；`aitest report` 重渲染时保持原 `result.json`，不访问平台。

## 2. 命令行与安装包验收

扩展现有 `tests/log_assertions/`、`tests/log_assertions_acceptance/` 和 `scripts/verify_log_assertions_wheel.py`。使用临时 workspace、动态本地端口和可控的 HTTP 平台；记录业务调用次数、状态请求的键、分页游标、每来源取证次数及清理目标。通过事件或可控时钟驱动收齐/超时。以下门禁分别在定向测试或已安装 wheel 中执行。

| 场景 | 可核验的通过条件 |
| --- | --- |
| AI 从已安装模板写用例 | 新样例涵盖默认来源、仅异步来源、同一步骤两个来源。按 `--validate-profile → --dump-ir → --explain TC-ID → codegen → --check → run` 走通。绑定一次，每个来源的原规则路径正确。别名拼错和同源清理冲突在生成前指出位置。 |
| 批量与分页 | 同平台同凭证、同一轮 30 个 ID 各 3 源、批上限 200，HTTP 记录显示一次 readiness 请求含 90 对，返回各对结果与请求等长同序、键匹配；两源已就绪后仅轮询余下 30 对。超批上限拆分，已齐来源的多组规则共享一份按版本分页的快照。 |
| 平台授权与错误 | 旧平台无批查声明时按同源多个 ID 的 status 取状态；新接口缺项、重复、错序、跨源误配时整批报告协议错误，整批均不得据此推进状态或开始取证；整体 403 直接报告鉴权失败。这些运行中错误均不触发回退。区分一次成功 NOT_FOUND、曾成功后断网、从未收到可用状态和平台明确采集超时。 |
| 快照、断言与清理 | 两页跨分区，相同 offset 位于不同 partition；校验匹配到的原始字符串以及证据定位。翻页遇版本变化后从新版本首页读取。某源超时、错误或内容失败时所有源零清理；通过时仅清理显式选择的 `(source_id,reqId)`，默认保留的同名 ID 仍可读取。 |
| 并发、恢复与报告 | 运行 `--case-concurrency 1 --log-concurrency 1` 与 `4/2`（含多单元 task），分别记录业务在途数与取证在途数。A 等日志期间可执行下一用例；等待不占取证名额。先落盘一源结果，挂起另一源后重启 `aitest run --resume RUN_ID`，核对业务仅调用一次、截止不延期、已验来源不重取、清理幂等键不变。检查 JSON/Markdown/JUnit、退出码和一次用例计数。 |
| 旧安装与分发 | 以真 0.7.0 wheel 生成旧用例和报告；对未完成运行保留有事实的旧 SQLite。候选 basic 与 parallel 安装各执行适用用例，验证单来源 END、无日志套件、旧 pytest freshness、报告只读重渲染和旧库恢复。保留原 0.6.0 无日志 workspace 的兼容回归。候选 wheel/sdist 含模板、Schema 和指南，安装在源码树外，Agent 报告预检使用同一候选解释器。 |

现有验收脚本的 `--baseline-wheel` 只安装一份基线，原验收用它跑 0.6.0 无日志工作区。实现时保留该参数及原测试，增补可选 `--baseline-070-wheel`：独立安装 0.7.0，用其 CLI 创建有日志的旧 workspace、旧报告和可恢复 SQLite。候选交付门禁同时传入两个基线，验收记录分别列出版本、执行数量及结果。下列命令用于分片实现后的独立构建目录，`$AGENT_ROOT` 指向可读取的 Agent 源码。将候选 SHA-256、操作系统、Python 版本、依赖、运行命令、退出码及脱敏报告收录在验收记录。

```sh
python3 -m pytest tests -q
npm --prefix console_web test
npm --prefix console_web run build
python3 -m build --outdir "$CANDIDATE_DIST"
python3 scripts/verify_log_assertions_wheel.py --wheel-dir "$CANDIDATE_DIST" \
  --baseline-wheel "$BASELINE_060_WHEEL" --baseline-070-wheel "$BASELINE_070_WHEEL" \
  --agent-root "$AGENT_ROOT" --output "$ACCEPTANCE_DIR"
```

## 3. 云端 Agent 与 Windows 隧道联调

核对基线为 `naiyue-test-agent` 提交 `493bb43`。其 `release/cloud-test-requirements.txt` 锁定 Kit 0.7.0。`naiyue_test_agent/cloud_runner/kernel.py` 把当轮 `command.services` 放入模型上下文，`naiyue_test_agent/tools/aitest_kit.py` 接收 CLI 参数和 timeout，优先使用项目 `.venv/bin/python`。换包后应在实际执行解释器中确认候选版本。一次 Bash 中导出的变量只对其后代进程生效。

1. 准备两个独立 Runner 任务和各自已获授权的日志平台入口。由 Agent 使用工作区写文件能力，将当轮路由的 `connect_host:connect_port` 与原服务基础路径写入本任务 `aitest_config/log_assertions.yaml` 的 `platform.base_url`。保留已有 YAML 配置及 `token_env` 引用。权限受项目写权限/审批控制，工具没有自动将路由写入 YAML 的步骤。
2. 从同一 Runner 的运行环境经隧道访问带认证的 `/v1/sources`、`/v1/ui-settings`，执行一条需要两来源的用例。从平台侧脱敏访问记录确认状态、事件页、获准的精确清理均到达该任务入口。分别用 suite 和 task 发起运行，交换运行次序，验证两个工作区的地址独立。
3. 记录当前明文 HTTP 的 Host 验收条件、实际项目解释器、任务 ID、用例结果和脱敏请求记录。旧 Agent 仍能读取既有报告、运行无日志用例。需使用原 Host/HTTPS SNI 的部署单独核对路由条件；实测未通过应记录具体阶段与错误。

本地 loopback 验证 HTTP 客户端、路由选择和打包结果。真实 Kafka 收齐、Windows 转发、容器可达性及线上权限单列为部署环境验收项，由该环境的维护方执行后记录结果。

## 4. 交给编写用例的 Agent

更新 `aitest_config/refs/config-files.md` 和 `aitest_config/refs/log-assertions.md`，同步包内唯一 workspace 模板的同名手册。在 `docs/usebook/aitest_log_assertions.md` 贯穿一个只等主链路和性能的例子。把同一例子的字段归属、验收命令和超时读法同步到相关的 `test-scaffold` 与 `test-codegen` skill，仓库三份本地副本语义一致，模板仅维护 `skills/` 一份。

以 `aitest init` 生成的干净工作区为验收输入。只给 Agent 模块的 Harness 能力、平台来源 ID 与一条业务检查要求，让它按随包说明写出分片 02 的 profile、通过 gate 并产出正确 IR。核对它能从失败报告定位具体来源。fixture 只承担业务请求与绑定，平台收齐阈值和隧道地址各自只出现在所属配置里；用例仍可用 `len(events)` 检查已收齐证据中的业务条数。

## 5. 整体审查回归

- HTTP 响应解析和规则进程启动移出协调器事件循环。快照交给规则执行器前复核取证截止时间，取消时回收规则进程。
- 恢复时凭证文件缺失应给出 CLI 错误。如果仅有清理待办，保存无法确认原身份的结果并结算报告。
- 以 pytest 收集结果绑定报告节点与生成文件路径。子单元保留阻断原因及实际退出码，跨分区证据保存 partition 和 offset，跳过的敏感表达式执行相同脱敏。
- 清理采用独立的有限排队预算和首次提交后的重试预算。后台默认最多四个清理请求在途，同一意图的提交继续复用原幂等键。
