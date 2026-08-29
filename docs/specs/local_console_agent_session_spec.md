# AITest Local Console Agent Session Spec

状态：已实现并验证
日期：2026-08-28
依赖：`test_workspace/plans/pi_agent_runtime_integration_spec.md`
前置实现：`docs/specs/local_console_agent_connection_spec.md`
技术调研：`research/console-agent-ux-technical-route/report.md`

## 1. 目标

在现有本地 Console 中增加一个可真实使用的 Pi Agent 工作面，完成以下闭环：

```text
用户选择 approval 或 full_trust。选择 full_trust 时先完成一次显式确认，确认内容展示当前 workspace，并说明该模式继承 Console 进程的本地权限、读取到的文件内容可能进入模型上下文
  -> Console 创建本地 Agent session
  -> Pi Worker 创建 AgentSession
  -> 用户发送 prompt
  -> 浏览器持续接收文本和工具事件
  -> approval 模式下展示权限请求和文件 Diff
  -> 用户 allow_once / allow_session / deny
  -> Pi 原生工具继续或拒绝执行
  -> 工具时间线关联文件、AITest CLI 和报告
  -> 用户可 abort，会话资源被正确释放
```

本阶段实现用户已经确认的七项能力：

1. Agent 对话和 session。
2. 权限模式 UI。
3. 审批卡。
4. 工具时间线。
5. Monaco Diff。
6. editor/report 联动。
7. Python、Node、Vue、Playwright 全链路测试。

## 2. 锁定范围

### 2.1 本阶段实现

- 新增 `/agent` 页面和主导航入口。
- 一个 workspace 可以创建和使用一个当前 Agent session。
- 同一 session 同时只允许一个 prompt。
- session 创建时选择 `approval | full_trust`，运行中不静默切换。
- full_trust 创建前必须完成一次性显式确认；确认只对本次 session 生效，不持久化为默认授权。
- Pi Worker 继续使用原生 read/write/edit/grep/find/ls/bash 和现有 Skill 路径。
- Console 后端拥有 session registry、产品事件、单调 `seq` 和有界 replay。
- 浏览器使用普通 HTTP 发送命令，使用 SSE 接收事件。
- 页面刷新、路由切换和短暂断线后，通过 `after_seq` 恢复事件。
- approval 模式展示权限请求，支持 `allow_once | allow_session | deny`。
- full_trust 模式不产生逐次审批，但保留工具事件。
- 文件 write/edit 请求展示 Monaco Diff 或明确的内容摘要。
- 工具时间线可打开相关文件和最新报告。
- abort、workspace 切换和应用关闭会拒绝 pending approval 并清理 Worker。

### 2.2 本阶段不实现

- 不保证 Console Python 进程或 Pi Worker 重启后的会话继续。
- 不把 Pi session、AITest event log 或聊天历史持久化到磁盘。
- 不引入 OpenHands、AG-UI、WorkerDeck、Cline 或 Vercel AI SDK。
- 不使用 WebSocket。
- 不实现多用户、多 workspace 并行 Agent、多标签会话或远程队列。
- 不实现 Sandbox、Docker/OpenShell 或临时 worktree。
- 不实现 Changeset、多文件原子提交、自动回滚或 Agent 自动 commit。
- 不为每条 AITest CLI 命令新增 typed tool。
- 不在浏览器、workspace、session event 或日志中保存 API Key。
- 不允许前端自行判断工具是否需要审批。

## 3. 当前系统与新增边界

### 3.1 当前调用链

```text
Console AgentConnectionView
  -> FastAPI AgentConnectionService
  -> Python WorkerClient
  -> Node Pi Worker JSONL
  -> Pi AgentSession
```

当前 Worker 已经支持 initialize、prompt、permission_decision、abort 和 shutdown，但 Python `run_prompt()` 是同步消费循环，无法同时承载浏览器 SSE、独立审批请求和 HTTP abort。

### 3.2 新调用链

```text
Vue AgentView
  -> POST commands
  -> FastAPI AgentSessionManager
     -> ConsoleAgentSession
        -> WorkerClient
        -> background reader thread
        -> EventLog(seq, event_id, payload)
  <- GET SSE events?after_seq=N
```

Pi 继续拥有 Agent loop。AITest 只增加一个线程安全的本地会话控制层，不复制 Pi runtime。

### 3.3 所有权

| 状态 | 权威所有者 |
|---|---|
| 模型、Agent loop、tool execution | Pi |
| allow/ask/deny 规则和路径/命令 gate | `pi-permission-system` |
| 当前本地 session、事件 seq、pending approval | AITest Python 后端 |
| 浏览器页面状态 | Pinia 投影 |
| target/module/suite/task/report | AITest workspace/application services |
| API Key | 当前 Console 进程内存或显式环境变量 |

## 4. 技术决策

### 4.1 传输

浏览器命令继续使用认证 HTTP：

- `POST /messages`
- `POST /approvals/{request_id}`
- `POST /abort`
- `DELETE /session`

事件使用 SSE：

- 当前安装的 FastAPI 版本不提供 `fastapi.sse` 模块。
- 本阶段使用 FastAPI/Starlette 官方 `StreamingResponse`，只实现标准 `id/event/data` 编码。
- 不新增 `sse-starlette`，也不在本功能中升级 FastAPI。
- SSE 只是传输层，可靠性来自 AITest EventLog，而不是连接本身。

### 4.2 Replay

每个产品事件包含：

```json
{
  "event_id": "uuid",
  "seq": 17,
  "session_id": "uuid",
  "type": "tool_call_finished",
  "timestamp": "2026-08-28T12:00:00Z",
  "correlation_id": "worker-message-id",
  "payload": {}
}
```

规则：

- `seq` 在单 session 内从 1 单调递增。
- 后端保存最近 1000 个事件，或最多 2 MiB JSON payload，任一先达到就从最旧事件裁剪。
- `GET /events?after_seq=N` 先 replay 所有 `seq > N` 的现有事件，再订阅 live tail。
- 相同事件只分配一次 `event_id` 和 `seq`。
- 前端按 `seq` 去重，`seq <= lastSeq` 不重复归并或触发副作用。
- `after_seq` 早于当前保留窗口时返回一个 `resync_required` 事件，携带当前 session snapshot；不静默制造连续历史。
- 心跳使用 SSE comment，不写入 EventLog，不增加 seq。

### 4.3 Session 状态

```text
created
  -> running
  -> awaiting_approval
  -> running
  -> succeeded | failed | aborted
```

终态后允许再次发送 prompt，状态回到 running；session 本身直到用户新建、删除、切 workspace 或 Console 关闭才销毁。

约束：

- active prompt 存在时再次提交返回 `AGENT_PROMPT_ALREADY_RUNNING`。
- pending approval 存在时 session 状态为 `awaiting_approval`。
- Worker error/exit 必须产生 `error` 和 `agent_finished(status=failed)`，不得永久 running。
- abort 产生 `aborted` 和 `agent_finished(status=aborted)`，重复 abort 幂等。

## 5. Worker 协议扩展

协议版本保持 1，只增加事件字段，不修改现有命令签名。

### 5.1 事件

继续使用：

- `session_started`
- `text_delta`
- `tool_call_requested`
- `permission_requested`
- `permission_resolved`
- `tool_call_finished`
- `agent_finished`
- `aborted`
- `error`

新增：

- `tool_call_updated`

### 5.2 tool event payload

`tool_call_requested`：

```json
{
  "tool_call_id": "call-id",
  "tool_name": "edit",
  "input": {
    "path": "test_workspace/suites/.../cases.md",
    "old_text": "...",
    "new_text": "..."
  }
}
```

`tool_call_updated`：

```json
{
  "tool_call_id": "call-id",
  "tool_name": "bash",
  "partial_result": "bounded redacted summary"
}
```

`tool_call_finished`：

```json
{
  "tool_call_id": "call-id",
  "tool_name": "bash",
  "is_error": false,
  "result": "bounded redacted summary"
}
```

约束：

- 事件始终按 `tool_call_id` 关联，禁止依赖事件顺序。
- 单个 input/result/partial_result 序列化后最多 64 KiB，超出后截断并标记 `truncated: true`。
- bash 保留完整命令，但对输出做截断和脱敏。
- write/edit 输入保留生成 Diff 所需的 path、content 或 old_text/new_text。
- 不把文件完整内容写入长期磁盘日志。本阶段 EventLog 只在内存。

### 5.3 Permission

`permission_requested` 必须提供：

- `request_id`
- `surface`
- `tool_name`
- bash 的 `command`，或文件工具的 `target`
- `summary`

缺少 `request_id`、`tool_name` 或 command/target 时，Python 后端自动 deny，并记录 `permission_invalid` 事件，不把不完整请求交给前端批准。

超时、session dispose、workspace switch 和 Worker exit 全部 deny。

## 6. Console 后端 API

所有端点继续要求 `X-AITest-Console-Token`，响应使用 `Cache-Control: no-store`。

### 6.1 创建或读取 session

```text
POST /api/agent/sessions
GET  /api/agent/session
```

创建请求：

```json
{
  "permission_mode": "approval",
  "confirmed": false
}
```

创建行为：

- 必须已经打开 workspace。
- 使用当前已保存的非敏感模型连接和当前会话/环境 API Key。
- skill paths 来自当前 workspace 的 `.codex/skills`、`.agents/skills`、`skills` 中实际存在的目录。
- 创建新 session 前关闭旧 session。
- 返回 session snapshot，不返回 Key、Worker pid 或内部环境。
- `permission_mode=approval` 不要求 `confirmed=true`。
- `permission_mode=full_trust` 必须同时提交 `confirmed=true`，否则返回 `FULL_TRUST_CONFIRMATION_REQUIRED`。
- 前端确认 Dialog 必须展示当前 workspace 绝对路径，以及“继承本地权限，文件内容可能进入模型上下文”的风险说明。

Snapshot：

```json
{
  "session_id": "uuid",
  "pi_session_id": "redacted-stable-id",
  "permission_mode": "approval",
  "status": "created",
  "active_prompt": false,
  "pending_approval_ids": [],
  "last_seq": 1,
  "created_at": "...",
  "updated_at": "..."
}
```

### 6.2 发送消息

```text
POST /api/agent/sessions/{session_id}/messages
```

```json
{
  "text": "检查当前 suite 并运行 profile validation"
}
```

限制：

- UTF-8 文本最大 64 KiB。
- 空文本拒绝。
- session id 必须是当前 workspace 的活动 session。
- active prompt 时返回 409。

### 6.3 SSE 事件

```text
GET /api/agent/sessions/{session_id}/events?after_seq=0
```

响应：

```text
id: 17
event: tool_call_finished
data: {"event_id":"...","seq":17,...}

```

SSE URL 无法设置自定义 header 的浏览器限制不适用于本实现，因为前端使用 `fetch()` 读取 stream，而不是原生 `EventSource`；token 继续放在 header，不进入 URL。

### 6.4 审批

```text
POST /api/agent/sessions/{session_id}/approvals/{request_id}
```

```json
{
  "decision": "allow_once"
}
```

规则：

- 决定只接受 `allow_once | allow_session | deny`。
- 重复或过期 request 返回 409，不执行第二次。
- full_trust session 不接受审批决定。

### 6.5 Abort 和关闭

```text
POST   /api/agent/sessions/{session_id}/abort
DELETE /api/agent/sessions/{session_id}
```

- abort 保留 session 和历史事件，允许下一轮 prompt。
- delete 拒绝所有 pending approval，shutdown Worker，并清除内存事件。
- workspace 切换前必须关闭 Agent session；不能只清 Key。
- FastAPI shutdown 时关闭 Agent session。

## 7. 前端状态

新增 `useAgentStore`，仅保存后端事实的客户端投影：

- `session`
- `events`
- `lastSeq`
- `connectionState`
- `pendingApprovals`
- `activeToolCalls`
- `draft`
- `error`

不进入 store：

- approval Diff 的展开状态。
- 当前 hover。
- 工具卡折叠状态。
- 局部 Dialog 开关。

Store action：

- `loadSession()`
- `createSession(mode)`
- `connectEvents()`
- `sendMessage(text)`
- `resolveApproval(requestId, decision)`
- `abort()`
- `closeSession()`
- `disconnectEvents()`
- `applyEvent(event)`

`applyEvent()` 必须幂等，先检查 seq，再更新 transcript/tool/approval 投影，最后才触发 workspace refresh 等副作用。

## 8. 前端页面与视觉规范

### 8.1 参考产品机制

- Cline：审批先展示工具、完整命令和路径，未知决定 fail closed。
- OpenHands：历史和 live tail 分离，重放事件按 ID 去重，token delta 批处理。
- WorkerDeck：session-scoped seq、afterSeq replay、pending approval 和大结果引用。

本项目不复制它们的 React/runtime/gateway，只采用上述机制。

### 8.2 视觉 thesis

- **Visual thesis**：冷石墨、低装饰、高信息密度的本地测试工程工作面，信号橙只用于当前动作与权限焦点。
- **Content plan**：顶部定向与模式状态，中部对话和工具时间线，右侧或内联审批细节，底部输入和 abort。
- **Interaction thesis**：新事件轻微 opacity/translate 进入；审批态通过背景层级和信号橙聚焦；按钮按压 scale 0.96，尊重 reduced motion。

### 8.3 UI 结构

桌面宽度：

```text
AgentView
├─ session header：模型、模式、状态、新建/关闭
├─ activity stream
│  ├─ user message
│  ├─ assistant text
│  ├─ tool group
│  └─ permission card + optional Diff
└─ composer：输入、发送、abort
```

不增加通用卡片网格。消息、工具和审批使用不同结构，不通过同一个圆角卡片模板表达。

### 8.4 组件

- `AgentView.vue`：页面编排，控制在 500 行以内。
- `AgentSessionHeader.vue`：状态与 permission mode。
- `AgentActivityStream.vue`：事件和空状态。
- `AgentToolEvent.vue`：工具生命周期。
- `AgentApprovalCard.vue`：权限决定与 Diff。
- `AgentComposer.vue`：prompt 与 abort。
- 复用 `DiffEditor.vue`。
- Reka UI 只用于确实需要 focus lock 的确认 Dialog；审批默认内联，不用 Modal 阻断整个页面。

### 8.5 Tokens 与交互

- 继续使用现有 `--canvas/--surface/--raised/--signal/--danger/--success`。
- 继续使用 `--r1:4px`、`--r2:6px`、`--r3:10px`、pill。
- 深度只使用现有 background steps 和细分隔线，不新增玻璃、渐变或重阴影。
- 所有按钮最小点击区域 40×40px。
- icon-only button 必须有 `aria-label`。
- hover 只在可 hover 设备生效；focus-visible 使用现有信号橙 outline。
- 动画只使用 transform/opacity，不使用 `transition: all`。

### 8.6 响应式

- >= 1100px：完整 stream 和宽 Diff。
- 760px 到 1099px：审批详情在时间线内联，Diff 使用 inline layout。
- < 760px：单列；header actions 换行；composer 固定在内容底部但不覆盖事件；工具命令可横向滚动。
- 375px 无横向页面溢出，所有核心按钮保持 40px 高。

## 9. Editor 和 Report 联动

工具事件可提供 UI action：

- 文件 path：跳转 `/editor?path=<encoded>`。
- report path：跳转 `/reports?path=<encoded>`。
- bash 命令结束后，如果命令包含 AITest run/report/codegen/freshness，则调用一次 workspace refresh。

限制：

- 前端只根据后端提供的已验证 workspace-relative path 跳转。
- 不从自由文本中正则猜任意文件路径并直接打开。
- 不把 assistant 文本当成 run/report 成功事实。

## 10. 文件影响

预计新增：

- `docs/specs/local_console_agent_session_spec.md`
- `aitest_kit/console/agent_sessions.py`
- `tests/console/test_console_agent_sessions.py`
- `console_web/src/stores/agent.ts`
- `console_web/src/stores/agent.test.ts`
- `console_web/src/views/AgentView.vue`
- `console_web/src/views/AgentView.test.ts`
- `console_web/src/components/agent/*.vue`
- `console_web/src/components/agent/*.test.ts`
- `console_web/src/styles/agent.css`
- Playwright Agent flow tests。

预计修改：

- `docs/specs/local_console_agent_connection_spec.md`
- `agent_runtime/pi_worker/src/session.ts`
- Worker 测试。
- `aitest_kit/agent/client.py`
- `aitest_kit/console/app.py`
- `aitest_kit/console/agent_connections.py`
- `tests/agent/test_client.py`
- `console_web/src/types.ts`
- `console_web/src/api/client.ts`
- `console_web/src/router.ts`
- `console_web/src/components/AppShell.vue`
- `console_web/src/styles/base.css`
- 构建产物 `aitest_kit/console/web/`。

任何单个生产代码文件不得超过 500 行。新职责优先放独立模块，不把 session manager 继续塞进 `app.py`。

## 11. 测试门禁

### 11.1 Node

- tool start/update/end 映射和 64 KiB 截断。
- 并发 tool call 按 ID 独立。
- permission payload 完整性。
- timeout/abort/dispose deny pending approval。
- full_trust 不产生 permission request。
- error、abort 和 agent settled 终态。

### 11.2 Python

- EventLog seq、裁剪、replay、wait 和 resync_required。
- Worker 后台 reader、prompt concurrency、approval、abort 和 close。
- session API token、输入上限、错误码和 no-store。
- workspace switch/app shutdown 清理 session。
- Worker exit 收敛为 failed。
- Secret 不进入 snapshot、event、error 或日志。

### 11.3 Vue/Vitest

- store event reducer 幂等和乱序 tool ID。
- SSE chunk parser、断线退避和 afterSeq。
- approval/full trust UI。
- Diff original/modified model。
- send/abort/terminal state。
- file/report 跳转。
- 375px 结构不依赖桌面专用 DOM。

### 11.4 Playwright

- 创建 approval session。
- prompt -> text delta -> tool -> approval -> finish。
- deny 和 abort。
- 刷新后 afterSeq replay，无重复。
- 断线后恢复，无丢失和重复副作用。
- full_trust 常驻风险标记。
- full_trust 创建前的一次性确认包含当前 workspace 与模型上下文风险。
- Diff 和报告/源文件跳转。

### 11.5 验证命令

```bash
python3 -m pytest tests -q
cd agent_runtime/pi_worker && npm test && npm run check && npm audit --audit-level=high
cd ../../console_web && npm test && npm run build && npm audit --audit-level=high
npm run test:e2e
cd .. && git diff --check
```

## 12. 完成条件

- 用户可以在 Console 内创建真实 Pi Agent session 并连续对话。
- approval/full_trust 两种模式真实接线，不是静态 UI。
- 权限请求缺字段、超时、断线和 session 清理全部 fail closed。
- 文本、工具和审批事件通过 SSE 实时显示。
- 页面刷新或短暂断线后可从 last seq 恢复，事件不重复。
- write/edit 审批可查看 Monaco Diff 或明确说明无法构造 Diff。
- Agent 可以通过原生 bash 调用 AITest CLI，并从时间线打开真实文件或报告。
- API Key 和其他凭证不进入浏览器存储、配置、事件、日志或错误。
- 无 Agent Key 或不使用 Agent 时，现有 workspace、editor、run、report 完全不受影响。
- Python、Node、Vue、build、Playwright 和 audit 全部通过。

## 13. 实现与验证结果

实现已按本 Spec 接线：

- Pi Worker 增加 `tool_call_updated`、受限工具输入、受限结果和完整终态事件。
- Python Worker client 增加不消费事件队列的 prompt、approval、abort、shutdown 控制方法，并用写锁保护并发 JSONL 写入。
- Console 增加内存 session registry、有界 EventLog、`seq/after_seq` replay、SSE、审批、abort、关闭和 workspace 切换清理。
- full_trust 同时由 API `confirmed=true` 门禁和 Reka UI 一次性确认 Dialog 保护。
- Vue 增加 `/agent`、Pinia 投影、断线重连、对话流、工具时间线、内联审批和 Monaco Diff。
- 工具路径只有通过后端 workspace 边界验证后才生成编辑器链接；识别到的 AITest run/report 命令可跳转报告页。
- 生产前端已重新构建到 `aitest_kit/console/web/`。

2026-08-28 验证结果：

- `python3 -m pytest tests -q`：348 passed，1 skipped。
- `python3 -m compileall -q aitest_kit`：通过。
- `cd agent_runtime/pi_worker && npm test`：16 passed。
- `cd agent_runtime/pi_worker && npm run check`：通过。
- `cd agent_runtime/pi_worker && npm audit --audit-level=high`：0 vulnerabilities。
- `cd console_web && npm test`：23 files、81 tests passed。
- `cd console_web && npm run build`：通过，产物已写入包内 Console web 目录。
- `cd console_web && npm audit --audit-level=high`：0 vulnerabilities。
- `cd console_web && npm run test:e2e`：10 passed。
- `git diff --check`：通过。

构建仍会报告 Monaco 相关 chunk 超过 500 kB 的 Vite warning；这是已有 Monaco 按路由加载后的体积提示，不是构建错误，也未在本阶段通过自定义拆包扩大实现范围。

## 13. 后续阶段

以下内容必须根据真实使用再决定：

- Console/Worker 重启后的持久 session 恢复。
- 多 session 和会话列表。
- typed AITest tools。
- 大型日志虚拟化和 TanStack Virtual。
- 多文件 Changeset、hash 校验和原子 apply。
- Sandbox/worktree/Docker/OpenShell。
