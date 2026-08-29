# 调研报告：AITest Console 的 Pi Agent 会话、审批与工具时间线技术路线

> 调研锚点：为本地优先的 AITest Console 选择可复用的官方或成熟开源方案，完成 Pi 会话流式传输、人工审批、工具时间线、Monaco Diff、Vue 状态管理和浏览器验证，避免维护自制基础设施。
> 启用来源：GitHub / Web；未启用 X。
> 用户指定方向：Pi 官方 SDK 与 Extension、FastAPI + Vue 3 + Pinia + Monaco + Reka UI + Vitest + Playwright、OpenHands/Cline 成熟实现参考。
> 候选：154 个 | 深度分析：10 个（GitHub 5、Web 5） | 相关但未深验：139 个 | 问题域不同：5 个。
> 证据范围：官方文档、核心源码、测试、Issue、变更记录；没有把搜索摘要当作成熟性证据。

## 一、结论摘要

### 最终判断

- [x] **可以直接使用**：Pi AgentSession/SessionManager/Extension；FastAPI SSE；现有 Pinia、Monaco DiffEditor、Reka UI、Vitest、Playwright。
- [x] **建议组合使用**：Pi 负责 agent loop 与原生工具；pi-permission-system 负责 allow/ask/deny；AITest 负责会话事实、审批桥、事件重放和报告关联；Vue 负责控制面。
- [x] **只借鉴思想后在现有边界内实现**：借 Cline 的 fail-closed 审批语义，借 OpenHands 的 REST 历史 + live tail 与重放去重，借 AG-UI 的生命周期和 ID 关联，借 WorkerDeck 的单调序号与 afterSeq replay。
- [x] **不建议沿用现有路线**：Phase 2 不引入 OpenHands 平台、AG-UI SDK、WorkerDeck gateway、Cline runtime 或 Vercel AI SDK。它们会在已经确定的 Pi + FastAPI + Vue 边界外再增加一层 runtime、协议或 UI 状态机。

### 三个最重要的结论

1. **Agent 核心不需要自研。** Pi 官方 AgentSession 已经提供创建会话、事件订阅、工具生命周期、abort/dispose、Extension 阻断接缝和 edit patch；AITest 应扩展当前 adapter，不重写 agent loop。证据：`clones/pi/packages/coding-agent/src/core/agent-session.ts`、`clones/pi/packages/coding-agent/docs/sdk.md`、[Pi SDK](https://pi.dev/docs/latest/sdk)。
2. **首期传输应选 SSE + 普通 HTTP，不选 WebSocket。** 浏览器只需要持续接收事件，prompt、abort、permission decision 已天然适合认证 POST。FastAPI 官方 SSE 支持 event id/retry；WebSocket 会额外引入旧连接迟到回调、认证、双向重放和连接 ownership 问题。[FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)、[FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)。
3. **真正需要 AITest 自己拥有的不是“另一套 Agent 框架”，而是一个很薄的、可重放的产品事件层。** 每个 session event 必须有稳定 `event_id` 和单调 `seq`；刷新或断线后以 `afterSeq` 补齐；按 `tool_call_id` 关联并发工具；副作用只对首次事件执行。WorkerDeck、OpenHands 和 Cline 的真实故障都支持这一约束。

### 推荐动作

按用户已同意的 1–7 项继续，但先写 Phase 2 实现 Spec。实现上沿用当前 Python ↔ Pi Worker JSONL，不换 runtime，不引入 AG-UI/Vercel AI SDK。后端新增 session authority、有界事件日志、SSE 订阅和 HTTP command endpoints；前端新增一个 Pinia agent store，用现有 Reka primitives 组织审批/设置，用现有 Monaco DiffEditor 展示文件修改。首期只支持单 workspace、单本地进程、一个 session 内一次只运行一个 prompt；浏览器刷新可恢复事件视图，Console 进程重启后的 Pi 会话恢复作为独立验收项明确决定，不隐式承诺。

## 二、用户指定方向核验

| 方向 | 优先查询来源 | 命中候选 | 当前可用与使用文档 | 核验结果 | 优先级判断 | 证据 |
|---|---|---|---|---|---|---|
| D1：Pi SDK / AgentSession / Extension / pi-permission-system | GitHub + Web | earendil-works/pi | npm 包、SDK/Extension 文档详细，项目已真实接入 | AgentSession、工具事件、abort/dispose、SessionManager 和 Extension 阻断均存在；不需要自研 agent loop | 保持最高优先级 | `cards/github-151.json`、`clones/pi/` |
| D2：FastAPI + Vue 3 + Pinia + Monaco + Reka + Vitest + Playwright | Web + 当前代码 | FastAPI SSE/WebSocket、Monaco、Pinia、Playwright | 官方文档详细；依赖均已锁定并已有组件/测试 | SSE 适合单向事件；Pinia 管跨路由业务状态；Monaco 直接提供 Diff；Playwright 可做真实断线/审批测试；Reka 已用于 Dialog/Tabs | 保持高优先级 | `cards/web-*.json`、`console_web/package.json` |
| D3：OpenHands / Cline 等成熟产品 | GitHub + Issue | OpenHands、Cline、WorkerDeck | 源码和文档可读，但整体接入复杂度高 | 适合作为失败案例与交互规则来源，不适合替换 Pi 或现有 Console | 从“可直接接入”降为“深度借鉴” | `cards/github-026.json`、`github-152.json`、`github-155.json` |

优先级覆盖说明：

- OpenHands 虽然是完整控制面，但当前产品是单机、用户 clone、BYOK，直接采用会重新引入多后端 Agent Server 与 React 控制面，覆盖范围远超 Phase 2。
- AG-UI 是有价值的标准事件词汇，但其 resumable transport 仍没有 sequence/resume wire contract；采用它也无法省掉 Pi → AITest 的权限、patch、Skill、report 映射。
- WorkerDeck 与需求高度重合，但它本身就是另一套 gateway、协议与多客户端产品；本轮只借 seq/replay/capabilities。
- Vercel AI SDK 相关候选未进入深验名额：它擅长模型/流式 UI 抽象，但本项目已由 Pi 产生结构化 agent/tool 事件，再加一层 AI SDK 会形成第二个流式状态来源。

## 三、别人是怎么解决的

### 1. Pi：直接作为 Agent Runtime

- **入选依据**：user_direction、complete_problem。
- **试图解决的问题**：模型调用、agent loop、coding tools、Skills、会话与 Extension。
- **使用的工具**：`createAgentSession`、`AgentSession.subscribe`、`SessionManager`、`DefaultResourceLoader`、原生 read/write/edit/grep/find/ls/bash。
- **执行流程**：创建 ModelRuntime/ResourceLoader → createAgentSession → bindExtensions → subscribe → prompt → tool events → agent settled → abort/dispose。
- **关键技术**：
  - `AgentSession` 直接提供消息和工具执行事件；
  - 工具必须用 `toolCallId` 关联，不能依赖到达顺序；
  - Extension 的 `tool_call` 是阻断点，错误会阻止工具执行；
  - `session_shutdown` 是清理资源的明确生命周期；
  - edit tool 可返回统一 patch，适合交给 Monaco Diff。
- **实际产物**：文本增量、工具调用和结果、session JSONL、edit patch、终态。
- **已经踩过的坑**：并行工具中慢 sibling 会拖住其他已完成 toolResult 的持久化；用户 abort/杀进程后可能留下 orphaned tool calls。AITest 不能把“UI 收到 tool_execution_end”误当作“会话事实已持久”。[Pi issue #7053](https://github.com/earendil-works/pi/issues/7053)。
- **仍未解决的问题**：Pi session 不是 AITest 产品事件日志；当前 Worker 使用 `SessionManager.inMemory`，Worker 退出后无法恢复。
- **当前是否可用**：是，项目已锁定并通过真实模型链路。
- **使用文档与前置条件**：Node.js >=22.19.0、固定 npm 版本、用户 BYOK。
- **接入复杂度**：low；当前 adapter 已存在，Phase 2 是扩展而非重建。
- **能否拿来用**：组合使用。
- **我的评估**：这是唯一应当直接承担 agent runtime 的候选。
- **证据**：`cards/github-151.json`、`clones/pi/`、[Pi SDK](https://pi.dev/docs/latest/sdk)、[Pi Extensions](https://pi.dev/docs/latest/extensions)。

### 2. Cline：审批语义与宿主边界参考

- **入选依据**：user_direction、workflow_gap。
- **试图解决的问题**：coding agent 的工具审批、IDE/CLI 宿主、可恢复会话。
- **使用的工具**：approval policy、ACP permission request、TUI tool dialog、SDK hub。
- **执行流程**：policy 检查 → 自动批准或请求 UI → 展示命令/路径/patch → allow once/always 或 reject → 更新工具状态。
- **关键技术**：无 UI、取消、未知结果全部 fail closed；按工具类型格式化影响范围；requestId/clientId 做关联。
- **实际产物**：审批请求、决定、工具状态和会话事件。
- **已经踩过的坑**：
  - 审批请求未显示工具名，用户无法知道自己批准什么。[Cline issue #8446](https://github.com/cline/cline/issues/8446)。
  - 每个 session event 附完整 transcript 导致内存和流量爆炸；后来改为状态快照与 transcript 分离。
  - replay/live 合并导致重复事件；后来按 event ID 去重。
- **仍未解决的问题**：整套 Cline hub/IDE/runtime 与 AITest 的 Pi + Vue 边界重叠。
- **当前是否可用**：是，但不适合直接引入。
- **接入复杂度**：high。
- **能否拿来用**：只借鉴思想。
- **我的评估**：审批卡必须强制显示 tool name、完整命令/路径、作用域；解析缺失即拒绝。
- **证据**：`cards/github-152.json`、`clones/cline/apps/cli/`、`clones/cline/sdk/CHANGELOG.md`。

### 3. OpenHands：历史与实时流分离参考

- **入选依据**：user_direction、complete_problem。
- **试图解决的问题**：长运行 agent 会话、历史分页、实时事件、重连和离线提交。
- **使用的工具**：REST history、WebSocket live tail、Zustand、TanStack Query。
- **执行流程**：REST 预载历史 → 用历史尾部 timestamp 建 since socket → 重连退避 → event ID 去重 → delta 按帧批处理 → socket 不可用时 REST queue。
- **关键技术**：history/live split、eventIds 集合、stale socket guard、exponential backoff + jitter。
- **实际产物**：可恢复 transcript、连接状态、工具/行动事件和历史分页。
- **已经踩过的坑**：
  - 后台历史 refetch 与 socket gate 互相触发，页面数分钟卡在 Connecting。[OpenHands issue #16733](https://github.com/OpenHands/OpenHands/issues/16733)。
  - 旧 socket 的迟到 close 把已打开的新 socket 标为断开。[OpenHands issue #16842](https://github.com/OpenHands/OpenHands/issues/16842)。
  - reconnect backlog 中重复事件会再次触发非幂等副作用；实现中必须在副作用前先查 event ID。
- **仍未解决的问题**：timestamp anchor 不是严格序号；事件解释器仍很复杂，并有继续拆分的开放议题。
- **当前是否可用**：是，作为独立平台。
- **接入复杂度**：high。
- **能否拿来用**：只借鉴思想。
- **我的评估**：AITest 应借“历史 API + live tail + ID 去重”，不复制 React/OpenHands 控制面。
- **证据**：`cards/github-026.json`、`clones/openhands/src/contexts/conversation-websocket-context.tsx`、`src/hooks/use-websocket.ts`、`src/stores/use-event-store.ts`。

### 4. AG-UI：事件生命周期参考，不作为 Phase 2 依赖

- **入选依据**：workflow_gap、route_diversity。
- **试图解决的问题**：跨 agent/framework 的前端事件协议。
- **使用的工具**：`@ag-ui/core`、`@ag-ui/client`、RxJS、Zod、SSE。
- **执行流程**：RUN_STARTED → message/tool start/delta/end → reducer → RUN_FINISHED/RUN_ERROR；interrupt 通过 resume entries 继续。
- **关键技术**：严格 lifecycle verifier、toolCallId/messageId 关联、JSON Patch state delta、typed reducer。
- **实际产物**：标准 event stream、messages/state 和 interrupt。
- **已经踩过的坑**：.NET 适配层在声明 frontend tool 时曾静默绕过 server tool approval，证明权限不能只靠 UI adapter。[AG-UI issue #2393](https://github.com/ag-ui-protocol/ag-ui/issues/2393)。
- **仍未解决的问题**：resumable capability 仍没有 sequence/resume wire mechanism；BaseEvent 无 sequence，SSE encoder/parser 未利用 id。[AG-UI issue #2105](https://github.com/ag-ui-protocol/ag-ui/issues/2105)。
- **当前是否可用**：协议与 SDK可用。
- **接入复杂度**：moderate，但会增加第二层协议。
- **能否拿来用**：借事件词汇和 verifier 思想。
- **我的评估**：AITest 现阶段不需要跨 runtime 互操作；保持自己的窄 JSONL/SSE schema 更稳。
- **证据**：`cards/github-153.json`、`clones/ag-ui/sdks/typescript/packages/core/src/events.ts`、`packages/client/src/verify/verify.ts`。

### 5. WorkerDeck：seq/replay 与 capability 参考

- **入选依据**：complete_problem、route_diversity。
- **试图解决的问题**：单机 agent gateway、session、approval、事件重放和多客户端。
- **使用的工具**：versioned protocol、REST + WebSocket typed client、session registry。
- **执行流程**：server 创建 session → 每事件分配 seq → attach(afterSeq) replay → live → 重连继续 afterSeq → pending approval 阻断并超时拒绝。
- **关键技术**：monotonic per-session seq、idempotent late results、deny-on-timeout、capabilities、large-result references。
- **实际产物**：可重放 session log、审批、工具时间线、多客户端一致状态。
- **已经踩过的坑**：
  - 数百事件逐条 replay 会造成数百次 render/postMessage，后来增加 replay hold；
  - 大型工具结果和图片不适合完整重放，后来只重放 head/reference，按需 REST 拉完整内容。
- **仍未解决的问题**：项目很新且协议快速演进；整体接入会替换 AITest 现有控制面。
- **当前是否可用**：可 npx 启动，但不建议作为本项目依赖。
- **接入复杂度**：high。
- **能否拿来用**：只借鉴思想。
- **我的评估**：其 `seq + afterSeq + bounded replay + capabilities` 是本轮最值得直接迁移的协议原则。
- **证据**：`cards/github-155.json`、`clones/workerdeck/packages/protocol/src/index.ts`、`packages/client/src/index.ts`、`docs/RELEASING.md`。

### 6. FastAPI SSE：主选浏览器事件传输

- **入选依据**：user_direction、workflow_gap。
- **执行流程**：POST command → GET SSE stream → `id/event/data/retry` → 断线后 afterSeq 重连。
- **能否拿来用**：直接使用。
- **理由**：Phase 2 是“命令低频双向、事件高频单向”的典型形状；命令继续用 REST，事件用 SSE 最薄。
- **限制**：SSE 不保存事件，必须搭配 AITest 有界事件日志。
- **证据**：`cards/web-143.json`、[FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)。

### 7. FastAPI WebSocket：保留但暂不采用

- **入选依据**：user_direction、route_diversity。
- **能否拿来用**：Phase 2 不采用；未来多客户端、双向高频交互再评估。
- **原因**：当前没有需要把 prompt/approval/abort 全塞进同一 socket 的需求；WebSocket 会带来更多 reconnect、stale instance、认证和 replay 状态。
- **证据**：`cards/web-149.json`、[FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)。

### 8. Monaco DiffEditor：直接使用

- **入选依据**：user_direction、workflow_gap。
- **执行流程**：旧内容 + Pi patch/新内容 → original/modified models → DiffEditor → 用户审批。
- **能否拿来用**：直接扩展现有 `DiffEditor.vue`，不实现自定义 LCS/diff renderer。
- **证据**：`cards/web-128.json`、[Monaco createDiffEditor](https://microsoft.github.io/monaco-editor/typedoc/functions/editor_editor_api.editor.createDiffEditor.html)。

### 9. Pinia：直接作为客户端 Agent 投影

- **入选依据**：workflow_gap。
- **状态边界**：
  - store：session summary、events、lastSeq、pending approval、connection status、active run；
  - component local：抽屉开关、折叠项、当前 hover、临时筛选；
  - backend：事件日志、审批事实、Worker/session ownership。
- **能否拿来用**：直接使用。
- **证据**：`cards/web-132.json`、[Pinia Introduction](https://pinia.vuejs.org/introduction.html)、[Pinia Testing](https://pinia.vuejs.org/cookbook/testing.html)。

### 10. Playwright：直接用于真实链路门禁

- **入选依据**：workflow_gap。
- **最低覆盖**：连接后收到 delta、审批 allow/deny、abort、刷新后 afterSeq 补齐、断线重连不重复、Diff 展示、报告跳转。
- **测试原则**：等待事件/响应，不用极短固定 sleep。
- **能否拿来用**：直接使用现有测试基础。
- **证据**：`cards/web-136.json`、[Playwright Network](https://playwright.dev/docs/network)。

## 四、横向评估

| 候选/路线 | 供应形态 | 贴合度 | 当前可用 | 文档 | 接入复杂度 | 技术可信度 | 主要风险 | 判断 |
|---|---|---|---|---|---|---|---|---|
| Pi | 官方 npm + 开源源码 | 极高：已选 runtime | 是 | detailed | low | 核心代码已验、项目已接入 | 并行工具持久化边界、当前 in-memory session | 组合直接用 |
| pi-permission-system | npm Extension | 极高：已选权限 gate | 是 | 项目已有接线 | low | 当前 Phase 1 测试通过 | UI/协议缺字段时必须 fail closed | 直接用 |
| FastAPI SSE | 官方 API | 高：单向事件 | 是 | detailed | low | 官方文档 | 需要自有 replay log | 直接用 |
| FastAPI WebSocket | 官方 API | 中：能力过量 | 是 | detailed | moderate | 官方文档 | stale socket、认证、双向 replay | 暂不采用 |
| Pinia | 官方 Vue store | 高 | 是 | detailed | low | 官方文档、项目在用 | 不能当后端事实源 | 直接用 |
| Monaco Diff | 官方编辑器 API | 高 | 是 | detailed | low | 官方 API、项目在用 | model 生命周期 | 直接用 |
| Reka UI | Vue primitives | 高：Dialog/Tabs/ScrollArea 等 | 是 | 官方组件文档 | low | 项目已有 Dialog/Tabs | 不应把业务状态塞进 primitive | 直接用 |
| Vitest + Playwright | 测试栈 | 高 | 是 | detailed | low | 项目现有门禁 | 网络测试需稳定同步 | 直接用 |
| Cline | 完整 Agent 产品/SDK | 中 | 是 | detailed | high | 源码 + failure evidence | 第二套 runtime/宿主 | 借鉴 |
| OpenHands | 完整控制面 | 中 | 是 | detailed | high | 源码 + tests + issues | 过重、React/多后端 | 借鉴 |
| AG-UI | 标准协议/SDK | 中 | 是 | detailed | moderate | 核心 verifier 已验 | resumable 未定义、额外适配层 | 借鉴事件模型 |
| WorkerDeck | 完整 gateway | 高 | 是但较新 | detailed | high | 核心协议已验 | 与现有控制面重叠、快速演进 | 借 seq/replay |
| Vercel AI SDK | 模型/UI SDK | 低到中 | 是 | detailed | moderate | 本轮未深验 | 与 Pi streaming/tool state 重叠 | Phase 2 不引入 |

### 按流程环节看覆盖

| 流程环节 | 已有解法 | 可直接复用什么 | 仍缺什么 |
|---|---|---|---|
| S1 会话与事件传输 | Pi events + FastAPI SSE | AgentSession subscribe、SSE response | AITest session authority、有界 event log、seq/afterSeq |
| S2 权限审批 | pi-permission-system + Cline 参考 | 现有 allow/ask/deny、超时桥 | Console approval endpoints/card、断线 fail-closed |
| S3 工具时间线 | Pi tool events + AG-UI/WorkerDeck 参考 | toolCallId、显式 lifecycle | update 事件、Skill/命令摘要、event persistence |
| S4 Diff 与工作台联动 | Pi edit patch + Monaco Diff | 现有 DiffEditor.vue | patch/old/new 内容映射、打开文件/报告动作 |
| S5 状态与验证 | Pinia + Reka + Vitest + Playwright | 现有依赖和测试模式 | agent store、reducer tests、断线 E2E |

## 五、前人踩坑与共性未解问题

### 已经发生过的坑

| 坑 | 候选 | 触发条件 | 影响 | 已知规避方式 | 证据 |
|---|---|---|---|---|---|
| UI 显示工具完成，但结果尚未持久 | Pi | 并行批次有慢 sibling | abort 后 orphaned tool call | 按 toolCallId 展示；不要把 UI 终态当 durable 事实；跟踪上游 | [#7053](https://github.com/earendil-works/pi/issues/7053) |
| 审批卡缺工具名 | Cline | 消息解析/字段缺失 | 用户盲批 | 协议字段必填，缺失即拒绝 | [#8446](https://github.com/cline/cline/issues/8446) |
| 每事件携带完整 transcript | Cline | 长会话、状态高频变化 | 内存/流量膨胀 | 事件与 transcript 分离、日志有界 | `clones/cline/sdk/CHANGELOG.md` |
| history refetch 与 live socket 循环 | OpenHands | 后台 refetch 参与建连 gate | 长时间 Connecting | 只 gate 初次无数据；后台 refetch 不拆 live | [#16733](https://github.com/OpenHands/OpenHands/issues/16733) |
| 旧 socket 晚到 close 覆盖新状态 | OpenHands | replacement socket 已 open | UI 假断线 | 每连接实例代次/ownership guard | [#16842](https://github.com/OpenHands/OpenHands/issues/16842) |
| replay 重复触发前端副作用 | OpenHands/Cline | live + backlog 重叠 | 重复通知/动作 | event id/seq 去重后再做副作用 | 对应源码与 changelog |
| mixed tool adapter 绕过审批 | AG-UI .NET | 声明 frontend tool | 未审批执行高风险工具 | enforcement 放 runtime/server；未知分支 deny | [#2393](https://github.com/ag-ui-protocol/ag-ui/issues/2393) |
| replay 逐事件 render | WorkerDeck | 大历史 | UI 抖动与消息洪泛 | replay hold、批处理、虚拟化 | `clones/workerdeck/docs/RELEASING.md` |

### 本轮深验方案中仍未解决的共性问题

| 共性问题 | 涉及候选 | 各自如何缓解 | 为什么仍未完整解决 | 对 AITest 的约束 |
|---|---|---|---|---|
| 断线后的无缝恢复 | OpenHands、AG-UI、WorkerDeck | timestamp+id、保留设计、seq replay | AG-UI 尚无 wire contract；timestamp 非严格序号；持久窗口仍有限 | AITest 用 session-scoped seq + bounded log + afterSeq；窗口缺失时返回明确 resync_required |
| 历史与 live 的竞态 | OpenHands、Cline、WorkerDeck | ID 去重、afterSeq、replay hold | 历史页和实时尾部仍可能重叠 | reducer 必须幂等；副作用在去重后执行 |
| 工具审批的事实归属 | Pi/Cline/AG-UI/WorkerDeck | runtime hook、policy、interrupt、server pending | adapter 错误仍可能 fail open | pi-permission-system/Worker 是唯一 enforcement；Vue 不得决定“是否需要审批” |
| 大结果/长会话成本 | Cline、OpenHands、WorkerDeck | transcript 分离、delta batching、结果引用 | 无界保留仍不可行 | event log 有界；大 stdout/result 只存摘要 + artifact ref |

### 其他待验证风险

- 当前 Pi Worker 使用临时 `agentDir` 和 `SessionManager.inMemory`。如果 Phase 2 要求 Console 进程重启后恢复对话，必须改成持久 session path，并验证 API key 不进入 session。
- Pi 并行工具结果的 durable timing 仍有上游开放问题。首期不应承诺 crash-safe exact-once tool history。
- SSE 经代理时可能被缓冲。AITest 是本地 127.0.0.1 场景，风险较低，但 E2E 仍应验证首个 delta 延迟和断线取消。
- “完全信任”只跳过逐次审批，不是 sandbox；界面需要一直展示当前模式和宿主权限边界。

## 六、参考建议

### 推荐方案

```text
Vue AgentView
  ├─ Pinia agent store：session/events/lastSeq/pending approval
  ├─ Reka UI：Dialog/ScrollArea/Tooltip 等可访问交互 primitive
  ├─ Monaco DiffEditor：文件修改对比
  └─ HTTP client
      ├─ POST /api/agent/sessions
      ├─ POST /api/agent/sessions/{id}/messages
      ├─ POST /api/agent/sessions/{id}/approvals/{requestId}
      ├─ POST /api/agent/sessions/{id}/abort
      ├─ GET  /api/agent/sessions/{id}
      └─ GET  /api/agent/sessions/{id}/events?after_seq=N  (SSE)

FastAPI Agent Control Plane
  ├─ session registry（单进程、本地）
  ├─ bounded event log：event_id + seq + timestamp + correlation ids
  ├─ SSE history replay + live fan-out
  ├─ command validation/auth/redaction
  └─ Pi Worker client
      └─ 现有 versioned JSONL
          ├─ Pi AgentSession / SessionManager
          └─ pi-permission-system
```

关键 ownership：

- Pi：模型、agent loop、原生工具、短期会话。
- pi-permission-system：工具规则与 ask/allow/deny enforcement。
- AITest backend：产品 session、事件序号、审批事实、workspace/report 关联。
- Pinia：后端事件的客户端投影，不是事实源。
- Monaco/Reka：交互控件，不承载权限判断。

### 对 1–7 项的具体路线

1. **Agent 对话与 session**
   - 直接使用 Pi AgentSession；
   - 后端建立 AITest session id ↔ Worker/Pi session id 映射；
   - 同一 session 一次只允许一个 active prompt；
   - 明确 `created/running/awaiting_approval/succeeded/failed/aborted` 状态机；
   - 首期不做多会话并行调度。

2. **权限模式 UI**
   - 模式只有 `approval` 与 `full_trust`；
   - 模式在创建 session 时锁定，运行中不静默切换；
   - full_trust 常驻醒目标记，并说明“继承本机用户权限、不是沙箱”；
   - 不在前端复制权限匹配规则。

3. **审批卡**
   - 直接展示 pi-permission-system 的请求：tool、surface、target、完整路径/命令、规则命中；
   - 按现有协议提供 `allow_once / allow_session / deny`；
   - 无 request id、tool name、target 或 session 已断开时 fail closed；
   - 超时和 session dispose 自动 deny；
   - Reka Dialog/primitive 负责焦点、Esc、可访问性。

4. **工具时间线**
   - 事件按 `tool_call_id` 分组，不按数组顺序配对；
   - 支持 requested/running/finished/error，补映射 `tool_execution_update`；
   - bash 展示完整命令与摘要，write/edit 展示 path 和 diff，read/search 展示范围；
   - 大 stdout/result 只展示截断摘要，完整内容指向 artifact/file；
   - Skill 作为上下文/标签，不伪装成 deterministic runtime API。

5. **Monaco Diff**
   - 复用 `console_web/src/components/DiffEditor.vue`；
   - original 来自审批前磁盘内容，modified 来自 Pi patch 应用结果或工具提供的新内容；
   - 审批前只读，批准后由 Worker 的原生 edit/write 执行；
   - 不实现 Changeset、原子多文件 apply 或自研 diff 算法。

6. **run/report 联动**
   - bash 工具执行现有 `aitest` CLI 后，后端从工具事件或 workspace refresh 识别报告产物；
   - 时间线提供“打开报告”“打开源文件”，通过现有 router/store action，不解析 `report.md` 为权限事实；
   - `result.json` 仍是结构化事实源，`report.md` 是阅读版。

7. **测试门禁**
   - Node：event mapping、update、并发 toolCallId、permission timeout、abort/dispose、session shutdown；
   - Python：session API、token auth、path/workspace scope、event seq/replay、redaction、Worker crash；
   - Vue/Vitest：agent store 幂等 reducer、审批卡、full trust banner、Diff model lifecycle；
   - Playwright：真实浏览器 prompt → delta → tool → approval → finish；deny；abort；刷新后 afterSeq；断线恢复无重复；
   - 全部等待状态/事件，不依赖极短 sleep。

### 可借鉴的思想

1. **toolCallId 关联** — Pi/AG-UI — 并发工具事件可能交错。
2. **fail closed** — Cline/AG-UI failure — 取消、未知、字段缺失、断线都拒绝。
3. **REST history + live tail** — OpenHands — 历史和实时不要混成一个组件生命周期。
4. **seq + afterSeq replay** — WorkerDeck — 比 timestamp anchor 更严格。
5. **副作用在去重之后** — OpenHands/Cline — 重放不能再次触发通知、导航或应用动作。
6. **大结果引用** — WorkerDeck — 事件只保留摘要，完整产物按需获取。
7. **官方 Diff 控件** — Monaco — 不再维护自定义编辑器/diff 逻辑。

### 实施顺序

1. 更新当前连接 Spec 的提交状态，新增 Phase 2 Agent Console Spec，锁定 API、事件 schema、状态机、seq/replay、权限边界和 1–7 验收条件。
2. 先补 Worker/Python 的生命周期与事件层：persistent/ephemeral session 决策、tool update、event log、SSE、commands、abort/dispose。
3. 再做 Pinia store 与 AgentView，先 transcript/tool timeline，再 approval/full trust。
4. 接现有 Monaco DiffEditor 与现有 editor/report 路由。
5. 最后补断线、刷新、超时、Worker crash 和视觉回归，运行全仓门禁。

### 继续验证的问题

- **需要在 Spec 中确认**：刷新浏览器恢复即可，还是 Console 进程重启后也必须恢复 Pi 会话？前者只需 AITest 内存 event log；后者需要持久 SessionManager 和 session metadata。
- **需要 PoC**：Pi edit tool 当前实际事件里 patch/details 的稳定形状，避免通过文本猜 Diff。
- **需要明确上限**：每 session 保留多少事件/字符；超出后是落盘、裁剪还是返回 `resync_required`。
- **需要验证**：permission 请求期间浏览器关闭后，超时 deny 和重新打开页面的 pending approval 是否一致。
- **暂不决定**：达到大量报告行、超大树/日志后是否引入 TanStack Query/Table/Virtual；现阶段 Pinia + 现有列表足够。

## 七、路线不可行与证据边界

本轮没有把任何相关技术路线判定为“普遍不可行”。有两条明确的当前阶段不采用结论：

- **AG-UI 作为 Phase 2 完整 wire protocol**：不是技术上不可行，而是当前收益不足；其 resumable transport 仍缺 sequence/resume contract，且采用后仍要维护 Pi/AITest adapter。[AG-UI #2105](https://github.com/ag-ui-protocol/ag-ui/issues/2105)。
- **WebSocket 作为 Phase 2 主传输**：不是技术上不可行，而是对单向事件 + 低频命令的场景复杂度过高；保留为未来路线。

真正的问题域不同候选已写入 `rejected.json`：手语 OpenHands、像素星球和 Raspberry Pi IO 项目只是名称误命中。

## 附录

### A. 深度分析选择

| 来源 | 排名 | 候选 | 用户方向命中 | selection_basis | 可采用性门槛 | 入选理由 | 覆盖 |
|---|---:|---|---|---|---|---|---|
| GitHub | 1 | earendil-works/pi | D1 | user_direction, complete_problem | 通过 | 当前 runtime 权威 | S1–S4 |
| GitHub | 2 | cline/cline | D3 | user_direction, workflow_gap | 借鉴类 | 成熟审批和 failure evidence | S2,S4 |
| GitHub | 3 | OpenHands/OpenHands | D3 | user_direction, complete_problem | 借鉴类 | 完整 session control plane | S1–S5 |
| GitHub | 4 | ag-ui-protocol/ag-ui | 否 | workflow_gap, route_diversity | 借鉴类 | 标准 lifecycle/verifier | S1,S3 |
| GitHub | 5 | workerdeck/workerdeck | 否 | complete_problem, route_diversity | 借鉴类 | seq/replay/approval 高重合 | S1–S5 |
| Web | 1 | FastAPI SSE | D2 | user_direction, workflow_gap | 通过 | 最薄单向事件流 | S1 |
| Web | 2 | FastAPI WebSocket | D2 | user_direction, route_diversity | 对照 | 双向备选 | S1 |
| Web | 3 | Monaco DiffEditor | D2 | user_direction, workflow_gap | 通过 | 现有依赖直接覆盖 Diff | S4 |
| Web | 4 | Pinia | D2 | workflow_gap | 通过 | 跨路由客户端投影 | S5 |
| Web | 5 | Playwright Network | D2 | workflow_gap | 通过 | 真实断线/审批验证 | S5 |

### B. 用户方向优先级覆盖

| 方向 | 候选 | 处置 | priority_override_reason |
|---|---|---|---|
| D1 Pi | earendil-works/pi | 入选第 1 | 不适用 |
| D2 官方前端栈 | FastAPI/Monaco/Pinia/Playwright | 全部入选 | Reka/Vitest 已是当前依赖和测试基础，限额内优先深验事件、状态、Diff、E2E 四个缺口 |
| D3 成熟 Agent | Cline/OpenHands | 入选 | 整体采用因与当前 Pi/Vue 控制面重叠而降级为借鉴 |

### C. 相关但未深验

- Vercel AI SDK：确认是成熟流式模型/UI SDK，但本轮不对其成熟性和内部机制下新结论；未入选原因是 Pi 已提供 agent/tool event source，新增 AI SDK 会形成重复抽象。
- CopilotKit、AG-UI 各语言适配、OpenHands 子项目、其他本地 coding-agent UI：保留在 cards 中，仅确认相关，不能由本轮报告推断成熟性或可直接采用。
- 其余 139 个候选的范围和未入选原因见 `selection.json` 与对应 cards。

### D. 淘汰项

详见 `rejected.json`。本轮明确淘汰 5 个名称误命中的不同问题域项目，没有用“低 star”或“不喜欢”作为淘汰理由。

### E. 证据索引

`queries.json` → `raw/` → `candidates.json` → `cards/` → `selection.json` → `clones/` → `report.md`
