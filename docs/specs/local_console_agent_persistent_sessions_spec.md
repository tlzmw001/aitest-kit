# AITest Local Console Persistent Agent Sessions Spec

状态：已实现并通过本地全量验证
日期：2026-09-01
依赖：`test_workspace/plans/pi_agent_runtime_integration_spec.md`
前置实现：`docs/specs/local_console_agent_session_spec.md`

## 1. 目标

在不改变 AITest 本地优先、BYOK、单 Console workspace 和可审批工具边界的前提下，增加：

- Console/Pi Worker 重启后的会话历史恢复。
- 一个 workspace 下的多个持久 Agent session。
- 多历史 session、单 active Worker。
- 从 Pi 最后持久化位置继续对话。

本阶段不承诺模型流、Shell 或工具调用在进程重启后原地续跑。

## 2. 锁定产品语义

### 2.1 多 session

- 一个 workspace 可以保存多个 session。
- 同一时间最多一个 session 绑定 Worker。
- inactive session 可以查看历史，不能发送 prompt 或处理审批。
- 切换到另一个 session 必须先安全关闭当前 Worker；active prompt 或 pending approval 不得静默切换。
- 新建 session 会关闭当前空闲 Worker，但保留旧 session 历史。
- session 标题默认取第一条用户消息首行，允许以后增加重命名，不调用模型生成标题。

### 2.2 重启恢复

- `succeeded | failed | aborted | created` session 可直接重新激活。
- Console 启动时发现上次为 `running | awaiting_approval` 或 `active_prompt=true`，将其收敛为 `interrupted`。
- pending approval 在重启后全部失效，按 deny 语义处理，不重新提交原工具调用。
- 工具执行中断后结果视为未知；不自动重试。
- 恢复使用用户选中的精确 Pi session 文件，不使用 `continueRecent()` 猜测。
- 历史查看不需要 API Key；重新激活时才检查当前模型连接和 Key。

### 2.3 权限

- `approval` session 重新激活无需额外确认，但旧的 `allow_session` 决定不恢复。
- `full_trust` session 的历史可以直接查看；每次 Console 进程重启后重新激活都必须再次明确确认。
- workspace 内容、Pi session 文件和持久元数据都不能自行开启 `full_trust`。

## 3. Pi 资源隔离

Pi 的运行配置目录和 session 目录必须分开：

```text
临时 agentDir
  -> AITest 权限配置
  -> 固定版本 permission Extension
  -> AITest 显式 Skill 路径
  -> 内存 SettingsManager / BYOK ModelRuntime

持久 sessionDir
  -> Pi 原生 SessionManager JSONL
```

规则：

- 继续使用 AITest 临时 `agentDir`，退出时删除。
- 继续禁止 Pi 自动发现全局 Extension、Skill、Prompt Template 和 Theme。
- 当前 workspace 的 `AGENTS.md | AGENTS.override.md | CLAUDE.md` 继续由 `DefaultResourceLoader` 加载。
- 不自动加载 `~/.pi/agent/AGENTS.md`、`settings.json`、`auth.json`、`models.json`、Skills 或 Extensions。
- 本阶段不增加“完整继承用户 Pi 配置”模式。
- 后续如需个人全局规则，只能通过显式设置加载指定文本 Context File，不能借此启用可执行 Extension。

## 4. 数据权威与磁盘布局

### 4.1 权威边界

| 数据 | 权威来源 |
|---|---|
| 对话消息、Pi tool context、分支和 compaction | Pi session JSONL |
| AITest session id、workspace 关联、标题和终态 | AITest `meta.json` |
| Console 产品事件、审批决定和单调 seq | AITest `events.jsonl` |
| API Key | 当前 Console 进程/环境变量，不持久化 |
| workspace 文件与测试报告 | 用户 workspace |

AITest EventLog 不用于构造下一轮模型上下文；Pi session 不替代 AITest 审批审计。

### 4.2 默认目录

默认根目录为：

```text
~/.aitest/sessions/
```

允许使用 `AITEST_AGENT_SESSION_HOME` 覆盖，测试必须注入临时目录。

```text
<session-home>/
└── <workspace-sha256-prefix>/
    ├── .worker.lock
    └── <aitest-session-id>/
        ├── meta.json
        ├── events.jsonl
        └── pi/
            └── <pi-session>.jsonl
```

- workspace key 来自 canonical workspace path 的 SHA-256，不把任意路径直接拼入目录。
- `meta.json` 使用临时文件 + `os.replace()` 原子更新。
- `events.jsonl` 和 Pi session 使用 append-only JSONL。
- session 目录与文件使用仅当前用户可访问的权限。
- `.worker.lock` 使用操作系统文件锁，保证同一 workspace 即使由多个 Console 进程打开，也最多只有一个 active Worker；进程退出后由操作系统释放。
- 不引入 SQLite 或远程数据库。

### 4.3 元数据

`meta.json` 至少包含：

- `schema_version`
- `session_id`
- `pi_session_id`
- `pi_session_file`
- `workspace_path`
- `permission_mode`
- `title`
- `status`
- `active_prompt`
- `pending_approval_ids`
- `last_seq`
- `created_at`
- `updated_at`
- `archived`

不包含 Key、Authorization、env 值、Worker pid 或完整模型请求。

### 4.4 持久事件

- 内存 EventLog 继续保留最近 1000 个事件或 2 MiB，并维持当前 SSE replay 契约。
- 磁盘 `events.jsonl` 保存经过 `redact()` 的产品事件，用于重启后恢复对话和工具时间线。
- write/edit 的 `content | old_text | new_text` 只供当前 live Diff 使用，写盘前移除；历史页显示路径、摘要和审批结果，不恢复完整 Diff。
- 不把未脱敏工具输出、凭证值或完整文件副本写入 AITest 事件日志。
- malformed 最后一行必须记录诊断并忽略该尾行；中间损坏不得静默跳过整个文件。

## 5. Worker 协议与 Pi SessionManager

协议版本保持 1，`initialize` 增加可选字段：

```json
{
  "session_dir": "/absolute/aitest/session/pi",
  "session_file": "/absolute/aitest/session/pi/session.jsonl"
}
```

- 有 `session_file`：验证其位于 `session_dir` 内，再调用 `SessionManager.open()`。
- 只有 `session_dir`：调用 `SessionManager.create()`。
- 两者都没有：保持现有 `SessionManager.inMemory()`，兼容 CLI connection test 和既有调用。
- `ready` 增加 Pi `session_file`，只在 Python/Worker 内部使用，不返回浏览器。
- Pi session 文件尚未产生时，恢复按同一 AITest session 创建新的 Pi 文件并更新元数据。

## 6. Console API

保持现有 API，并增量增加：

```text
GET  /api/agent/sessions
GET  /api/agent/sessions/{session_id}
GET  /api/agent/sessions/{session_id}/history?after_seq=N
POST /api/agent/sessions/{session_id}/activate
POST /api/agent/sessions/{session_id}/archive
```

- `GET /api/agent/session` 继续返回当前 active session；没有 active Worker 时返回 `null`。
- `POST /api/agent/sessions` 创建并立即激活新 session。
- `activate` 请求包含 `confirmed`；full trust 必须为 true。
- message、approval、abort 只接受当前 active session。
- history 对 active/inactive session 都可读取，不创建 Worker。
- 现有 `DELETE /sessions/{id}` 兼容为归档语义：关闭 Worker、标记 archived，不永久删除文件。
- workspace 切换和 FastAPI shutdown 只停止 Worker，不归档或删除历史。

Snapshot 增加：

```json
{
  "title": "检查 coupon suite",
  "is_active": false,
  "status": "interrupted"
}
```

`status` 新增 `interrupted`。

## 7. Console UI

- Agent 页面增加 workspace-scoped session 列表和“新建会话”。
- 列表展示标题、更新时间、权限模式和最后状态。
- 选择 inactive session 只加载历史，主操作为“继续会话”。
- full trust 的“继续会话”必须打开与创建时同等级别的确认 Dialog。
- active session 继续使用 SSE；inactive session 使用 history API。
- active prompt 或 pending approval 时切换必须先显式中止；本阶段可以禁止切换并给出明确提示。
- 归档后从默认列表移除，不提供永久删除。
- `interrupted` 明确提示“已恢复到最后持久化位置，最后工具结果可能未知”。

## 8. 非目标

- 不做多个并行 Worker。
- 不做后台 daemon、进程重连或 Shell 进程托管。
- 不自动重放 prompt、工具调用或审批。
- 不做跨设备同步、云端 session 或团队共享。
- 不做 Pi session tree 编辑 UI。
- 不做结构化长期 Memory。
- 不加载用户全局 Pi Extension/Skill/auth/settings。
- 不做自动过期、配额和永久清空回收站。

## 9. 文件影响

预计新增：

- `aitest_kit/console/agent_session_store.py`
- `docs/specs/local_console_agent_persistent_sessions_spec.md`
- 对应 Python、Node、Vue 测试。

预计修改：

- `aitest_kit/console/agent_sessions.py`
- `aitest_kit/console/app.py`
- `agent_runtime/pi_worker/src/session.ts`
- `agent_runtime/pi_worker/src/worker.ts`
- `console_web/src/types.ts`
- `console_web/src/api/client.ts`
- `console_web/src/stores/agent.ts`
- `console_web/src/views/AgentView.vue`
- `console_web/src/styles/agent.css`
- 包内前端构建产物。

任何生产代码文件不得超过 500 行；持久存储不继续堆入 `agent_sessions.py`。

## 10. 测试门禁

### Node

- `create` 使用指定 sessionDir 并返回 session file。
- `open` 恢复同一 Pi session id 和历史上下文。
- session file 越界或非法路径被拒绝。
- 未提供持久字段时仍为 in-memory。
- 临时 agentDir 和全局资源隔离不回归。

### Python

- 元数据原子写入、workspace 隔离和 secret 不落盘。
- EventLog 重启加载、seq 连续、裁剪和敏感 write/edit 字段不落盘。
- 多 session 列表、查看、激活、归档和单 active Worker。
- running/awaiting approval 重启后收敛为 interrupted。
- full trust 重新激活必须确认。
- workspace 切换和 app shutdown 只停止 Worker，不删除 session。
- 损坏尾行有日志；损坏元数据只影响对应 session。

### Vue

- session 列表加载和选中。
- inactive history 不连接 SSE。
- activate 后连接 SSE 并允许发送。
- full trust 恢复确认。
- interrupted 提示和归档后的选择回退。
- 现有审批、Diff、abort 和 replay 不回归。

### 验证命令

```bash
python3 -m pytest tests -q
python3 -m compileall -q aitest_kit
cd agent_runtime/pi_worker && npm test && npm run check && npm audit --audit-level=high
cd ../../console_web && npm test && npm run build && npm audit --audit-level=high
npm run test:e2e
cd .. && git diff --check
```

## 11. 完成条件

- Console 重启后仍能列出并查看当前 workspace 的历史 Agent session。
- 重新激活后 Pi 使用同一持久 session 上下文继续对话。
- 多历史 session 相互隔离，同时只有一个 Worker。
- 执行中断不会自动重放副作用。
- AITest 继续隔离 Pi 用户全局资源，只加载 workspace Context File 和显式资源。
- API Key、敏感 env 值和完整审批 Diff 不进入 AITest 持久事件日志。
- 现有 Agent、Console 和确定性测试链路全部通过。

## 12. 实现与验证结果

2026-09-01 已完成：

- Pi Worker 使用显式 `session_dir/session_file` 创建或打开精确的 Pi JSONL session；未提供字段时保持 in-memory 兼容。
- AITest 使用 workspace-scoped 文件目录保存 `meta.json`、脱敏 `events.jsonl` 和 Pi 原生 session；元数据原子更新，归档不永久删除。
- Console 支持多历史 session、单 active Worker、inactive history、显式继续和重启后 `interrupted` 收敛。
- workspace 级文件锁把“单 active Worker”约束扩展到多个本地 Console 进程。
- full trust 在创建和重新激活时都要求明确确认；用户全局 Pi 配置与第三方 Extension 仍保持隔离。
- Vue Agent 页面提供会话列表、新建、历史查看、继续与归档；active session 仍使用 SSE。
- wheel Runtime seed 已通过 `scripts/build_pi_worker_seed.py` 从 canonical Worker 源确定性重建，bundle hash 为 `4dd492943bf2b7f7a1c27e7f48062ed73697be5942862feed61b94115750f044`。

验证结果：

- `python3 -m pytest tests -q`：382 passed，1 skipped。
- `python3 -m compileall -q aitest_kit`：通过。
- `cd agent_runtime/pi_worker && npm test && npm run check`：19 passed，check 通过。
- `cd agent_runtime/pi_worker && npm audit --audit-level=high`：0 vulnerabilities。
- `cd console_web && npm test && npm run build`：24 files、95 tests passed，build 通过。
- `cd console_web && npm audit --audit-level=high`：0 vulnerabilities。
- `cd console_web && npm run test:e2e`：10 passed；Agent 会话列表的 macOS 视觉基线已审阅并更新。
- `git diff --check` 与 Runtime seed 校验：通过。

Vite 仍报告已有的 Monaco 大 chunk warning；它不影响构建成功，本阶段未扩大范围处理编辑器拆包。
