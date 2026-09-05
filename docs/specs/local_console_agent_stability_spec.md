# Console / Pi 稳定性修复

状态：已实现并通过本地全量验证
日期：2026-09-04
前置：`local_console_agent_persistent_sessions_spec.md`、`local_console_agent_session_spec.md`

## 范围与现有数据流

用户已批准审查中的 7 个核心问题及前端打磨项。保持 Vue/Pinia/Monaco、Pi SDK、原生工具和 permission Extension，不升级依赖、不增加沙箱、不改用户环境配置。

当前链路：浏览器操作 → HTTP → Python Session/Worker → JSONL → Pi/工具；产品事件写入 events.jsonl/meta.json，再经 SSE 投影到 Pinia。普通文件和 env 保存均由 HTTP 返回新的内容/hash。

## 修复契约

1. 原生 grep 的递归搜索只按入口目录授权，不能用 path deny 推导出逐文件保护。审批模式将 grep 改为 ask，复用现有审批扩展；用户拒绝前不运行原生搜索。直接敏感文件 read 的 deny 保持。明确：批准 grep/bash 后仍继承本地权限，可能读取敏感内容，此处不是沙箱，也不声称逐文件强制过滤。full_trust 不变。
2. 保存响应更新文档已保存基线/hash，但不得覆盖等待期间的新输入；响应只作用于原文档实例，重复保存同一实例应串行/去重。隐藏、关闭或切换后不得被旧响应重新显示内容。覆盖冲突路径共用保存规则。
3. 对持久 session 的恢复、激活、归档遵循同一 workspace OS lease。其他进程持有 lease 时，历史读取不执行恢复写入；归档/激活返回已有冲突码。获取锁后重新读元数据，避免用锁前快照恢复。锁须覆盖恢复写入及 Worker 生命周期。
4. JSONL 只读加载容忍并记录不完整尾行，不修改磁盘。下一次由持有 lease 的写入者追加时，先修复有效字节边界；完整但缺换行的尾行追加分隔符。中间损坏仍报错。持久化成功后才推进内存 seq。
5. Worker 握手任何异常都终止并等待子进程退出。Session 初始化后续失败也必须清理 Worker，再释放 lease；初始化完成前不启动产品事件读取线程。
6. HTTP snapshot 和 SSE 事件采用相同 session id / 单调 seq 规则。旧 HTTP 不回退新 SSE 状态；事件游标独立于快照版本，不能跳过未消费的事件。历史加载有请求归属，旧会话响应不得覆盖新选择。
7. resync_required 在同一 Session 锁下取得 snapshot、保留事件及完整 pending approvals；浏览器原子替换有界时间线与待审批数据。无需全量历史分页，不恢复已失效审批。流中发生窗口溢出同样 resync。

前端打磨：报告详情采用最新请求归属；中文输入法确认 Enter 不发送（isComposing / composition 状态 / 229 兼容）；write Diff 读取失败明确提示并可重试，只有明确 FILE_NOT_FOUND 才视为空文件；外部路径不伪造完整磁盘 Diff；空字符串删除可展示 Diff。

## 文件与接口

- Worker：permissions.ts 与真实 Extension/native grep 集成测试；按已有脚本重建 wheel seed。
- Python：agent/client.py、console/agent_sessions.py、agent_event_log.py、agent_session_api.py，必要时将恢复职责拆到独立模块以遵守 500 行限制；对应 pytest。
- Vue：EditorView、EnvironmentView、ReportsView、AgentView、AgentApprovalCard、stores/agent 及对应 Vitest；按 Vite 重建包内前端。
- SSE 增量 payload：`resync_required.payload.events: AgentEvent[]`、`pending_approvals: object[]`；snapshot 与 events 在同一锁内截取。不改变 HTTP 路由、公开方法签名或协议版本。
- history 响应增量携带同批 `session` snapshot；active history 同时携带 pending approvals，避免“列表快照旧、历史游标新”造成状态永久滞后。保留旧客户端字段。
- 同步当前用户文档中的权限边界和恢复说明。磁盘性能批处理、跨平台安装验收、发布与新能力均不在本次实现范围。

## 验证

每项先运行失败回归，再最小修复并运行对应测试。并发测试使用可控 Promise、真实 OS lease、事件同步，不用极短 sleep。

- Python 全套 pytest / compileall。
- Worker npm test / npm run check，seed 构建与一致性验证。
- Vue npm test / npm run build / Playwright，diff --check。
- 无真实模型请求、密钥或实际 env 文件写入；研究目录不动；未经用户要求不 commit/push。

## 实现与验证结果

7 项核心修复与前端打磨项均已接线。恢复写入的 OS lease 逻辑独立放在 `agent_session_recovery.py`，避免继续扩充 Session 生命周期文件超过 500 行。原生 grep 继续由固定版本 permission Extension 审批，不引入自写搜索器。

2026-09-04 本地验证：

- 修复前正式回归分别复现前端 8 处失败、IME/Diff 5 处失败、后端 12 处失败；后续同类路径检查又补充 history snapshot 与 Worker 无进程清理测试。
- `python3 -m pytest tests -q`：398 passed，1 skipped（原有），2 个原有 TestCase collection warning。
- `python3 -m compileall -q aitest_kit`：退出码 0。
- Worker `npm test && npm run check`：20 passed，check 退出码 0；包含真实 permission Extension 与原生 grep 的拒绝/允许测试，无模型请求。
- Vue `npm test`：25 files、110 passed；`npm run build`：退出码 0，保留原有 Monaco chunk warning。
- Playwright `npm run test:e2e`：12 passed（macOS Chromium），包含已有视觉基线、新增保存竞态、resync 审批恢复、Diff 重试与空文件删除展示。
- IME 已通过组件与浏览器事件级测试；没有自动操纵系统输入法候选窗，不把合成事件验证表述为所有平台原生 IME 验收。
- Runtime seed 已按 canonical 源重建并校验：`8166cf5f9522bbf0356a404a828b28c96d9d21a07f5afccde953961298ef8bd1`。
- `git diff --check`：通过。无依赖升级、真实 env 修改、研究资产修改或 commit/push。

回归覆盖扩展到同类路径：send/approval/abort 的 HTTP 快照、list/get/history/activate/archive 的 lease 边界、普通文件/env 保存、初始 replay 与流中窗口溢出。包内前端与 Worker seed 均由原构建流程更新，不手改生成产物。

后续交付工作已落地：Linux 视觉基线、跨平台安装 CI 和持久化测量见 `docs/specs/console_delivery_verification_spec.md`。最新 Linux 回归及六组安装验收以对应提交的 GitHub CI 结果为准；本地验证不替代远程绿灯。测量结论是保留逐事件落盘，而不是还有批处理优化未完成。

仍按规模触发后再评估：状态/表格/虚拟列表库，不列为本阶段交付缺口。

提交前补充回归：history snapshot 的同步不得把其他运行会话误标为 inactive；切换后按最新 history snapshot 而不是旧列表项决定是否重连 SSE。两条测试先复现 active 标记丢失及零次 stream 调用，再修正同一 store 的同步逻辑。

提交前最终验收：Python 408 passed / 1 skipped；Vue 112 passed；Worker 20 passed；macOS Playwright 13 passed（新增活跃但空闲会话 → 历史 → 返回后的事件流验证，保留运行中禁止切换规则）。11 个 suite profile/freshness 检查通过，188 个 generated 测试 collect 成功；前端、wheel/sdist 构建及包内容检查通过。
