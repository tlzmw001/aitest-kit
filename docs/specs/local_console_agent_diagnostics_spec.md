# Local Console Agent 请求诊断

状态：已实现并通过本地验证。2026-09-16。

## 目标与边界

定位“长时间没有回复”发生在请求准备、等待 HTTP、流式返回、Pi 自动重试还是工具审批。
不将之前的慢请求直接归因为审批或上游；目前只证实正常样本的 raw text → Pi text 映射约 1–2 ms，以及自动重试事件未展示。
不改变权限、工具、prompt、模型参数、超时或重试策略；不新增并发会话、依赖、数据库、全局配置或真实模型调用。

## 现状与接线

Vue sendMessage → authenticated HTTP → AgentSession → WorkerClient JSONL prompt → Pi AgentSession。
Pi event → Worker JSONL → AgentSession journal + snapshot → SSE（含 resync）→ Pinia → Vue。
沿用现有隔离 agentDir，只注册内部 inline extension，不加载用户全局扩展。
使用已安装 Pi 0.84.3 的 before_provider_request / after_provider_response hooks；
使用公开 agent.streamFunction 的每请求 fetch 选项，不能 monkeypatch global fetch。
诊断范围为主 Agent streamFunction 调用；Pi 的带外自动压缩等维护请求不归入已完成的请求，也不伪造其指标。
使用官方 `compaction_start` / `compaction_end` 事件标记压缩区间；期间不创建诊断请求、不包装 fetch、忽略 provider 诊断 hooks，结束后恢复普通请求诊断。

## 契约

- POST session messages 的可选 `diagnostics: "basic" | "stream"`，缺省 basic。
  Worker prompt 同字段。旧调用不需要修改；stream 只对下一次被接受的用户消息生效，覆盖该消息产生的模型调用和重试。
- `request_diagnostic` event：完整、可替换的单次模型调用快照。
  payload 含 request_id、message_id、phase、started_at、elapsed_ms、detail、可用的 metrics。
  phase 为 preparing / waiting_response / waiting_text / receiving / thinking / completed / failed / aborted。
  request_id 每次 streamFunction 调用唯一；message_id 保持用户消息关联。
- 基础 metrics：request_ms（相对模型调用开始）、headers_ms、http_status、first_text_ms、complete_ms、error_category。
  缺失字段代表未采集，绝不能用 0 代替未知。请求准备钩子未触发时仍可显示 preparing。
- 详细模式仅支持 model.api=openai-responses；其他 API 明确 detail=unsupported。
  收集 first_byte_ms、first_sse_event_ms、raw_first_text_ms、raw_terminal、raw_eof_ms、raw_event_types（白名单类型的 count/first_ms/last_ms）、解析/超大帧标志。
  request_id 表示 Pi 模型调用；同一调用如 provider 内部发生多次 HTTP fetch，以 `http_attempts` 计数，raw 指标聚合，不冒充独立 Pi 重试。
- `agent_retry` event：phase=start/end、attempt、max_attempts、delay_ms、success（可用时）、安全 error_category。绝不转发任意 errorMessage。
- 只在阶段切换和模型调用结束发送快照，不每 token 写诊断事件。每次模型调用最多发送准备、请求、HTTP、首次 thinking、首次 text、结束这些有限事件。

## 保存与安全

诊断仅保存类型、计数、时长、随机关联 ID、安全错误分类。不保存请求正文、响应正文、思考内容、URL、header、key、原始错误消息。
SSE 观察器使用有界缓冲（单帧约 1 MiB）和类型白名单，异常只记录安全分类并继续转交原始字节；不 fork/tee 预取流，不更改 backpressure、signal、取消和网络错误传播。
后端事件日志保存诊断；内存投影保留最近 20 次调用和最新重试状态，active snapshot / resync 带投影，防止 1000 条事件截断使阶段丢失。
历史加载从现有有界 journal 回放重建最近可见诊断，不增加历史分页；进程重启沿用 interrupted 语义，不让旧请求显示仍在运行。
发送新消息清除上一轮“当前阶段”，已完成请求的诊断保留。基础指标不是网络抓包，各时间点在 UI 清楚标识。

## UI

沿用当前 Vue、Pinia 和 CSS tokens，不换字体或配色。技术用户、克制工作台、没有装饰动画。
状态行在对话流后、输入框前的独立 grid 行；诊断区最多 35vh、内部滚动，确保中止/发送按钮不被挤出视口。
以审批、会话终态、工具执行优先于旧的模型调用状态。
请求阶段展示本阶段已等待时间；没有收到 thinking 事件不显示“思考”。
折叠“请求诊断”显示最近调用、完成耗时、HTTP 状态、首字时间和自动重试信息；缺项写“未采集”。
发送区“仅下一条消息采集详细流诊断”开关，接受成功后复位，失败保留，切换/新建会话清除。
参考开发工具的两层信息组织：VS Code 状态与输出分离、浏览器 Network 的请求级时间详情；只借鉴层级，不复制完整面板。
普通 CSS + scoped CSS，复用现有语义色；原生 details、checkbox 支持键盘，375px 换行不溢出。

## 影响文件

Worker 新增诊断控制器与 SSE 观察器、session/worker 接线和测试；Python client/API/session 新增可选参数与投影模块、测试；
Vue types/API/store、独立诊断组件、AgentView 和测试；用户手册说明；通过现有脚本重建 Worker seed 和前端包。
不手改生成 bundle，不升级依赖；文件超 500 行只拆出相关职责。

## 验证

先失败测试，再最小实现。覆盖基础阶段、延迟首字、工具多轮、自动重试、错误、缺终止帧、取消、SSE 任意分片、超大帧、未知类型与敏感内容不外泄。
本地 fake fetch/HTTP 验证官方 SDK 接线及未改模型请求、signal/取消/背压；不请求真实模型。
Python 覆盖缺省兼容、stream 参数传递、非法模式、journal/replay/截断后 resync；Vue 覆盖一次性开关、阶段优先级、未采集、断线恢复与历史。
运行 Worker、Python、Vitest、前端构建、Playwright、seed 构建及 git diff --check。实际结果在交付时报告。

## 本次验证记录

- `npm test --prefix agent_runtime/pi_worker`：37 passed，包含真实 Pi SDK 对本地模拟 HTTP 服务的成功、重试、截断、中止测试。
  新增 6 项压缩回归先红后绿，覆盖回合后、请求前、overflow 续跑、压缩中止/失败与新消息状态恢复。
- `npm run check --prefix agent_runtime/pi_worker`：退出码 0。
- `npm test --prefix console_web`：26 files / 117 passed。
- `npm run build --prefix console_web`：退出码 0；仍有现存 Monaco 大 chunk 警告，无构建错误。
- `npm run test:e2e --prefix console_web`：15 passed，含 1440px / 375px 诊断视图和一次性开关验证。
  两种尺寸截图已人工查看，现有 Darwin 截图比较通过，未修改或放宽基线；未运行 Linux 浏览器。
- `python3 scripts/build_pi_worker_seed.py`：新 bundle hash 前缀 `b97e5879ed69`；生成 seed 与暂存区一致。
- `python3 -m pytest tests -q`：418 passed / 1 skipped；2 条原有 TestCase collection warning。
- `codegen --all --validate-profile` 与 `codegen --all --check`：通过；generated pytest collect：188 tests。
- 从暂存区导出的干净源码执行 `python3 -m build --no-isolation`：wheel 与 sdist 构建成功。
- `python3 -m compileall -q aitest_kit/agent aitest_kit/console` 与 `git diff --check`：退出码 0。
- 实现验证阶段不修改真实配置或凭证，没有真实模型 HTTP 请求；保留已有 research 与学习笔记。提交和 push 由后续显式授权执行。
