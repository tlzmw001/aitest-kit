# AITest 外部 Agent 工作台

状态：内置 Pi Agent 已移除并通过本地验证；外部接入方案待讨论。2026-10-17。

## 产品决定

用户准备以独立的 Naiyue Test Agent 作为通用编程与测试操作入口。AITest 保留测试资产、确定性测试流水线和 Console，不再内嵌一套模型连接、Agent 会话与审批运行时。

当前 `main` 为 `1c98669`（v0.5.0）。已创建本地保留分支 `codex/archive-pi-agent-v0.5.0`；实施分支为 `codex/external-agent-workbench`。不回退整个 Console，不丢失 Monaco、资产管理、环境页与测试运行等后续改进。

## 当前链路

```text
Console Agent 页面 / aitest agent
  → AITest 模型配置和会话服务
  → Pi Worker JSONL / Pi SDK / permission extension
  → 本地工具、模型、会话文件

Console 其余页面 / aitest CLI
  → workspace、registry、Profile Gate、Case IR、codegen
  → freshness → pytest → result.json / report.md
```

两条链路在 CLI 注册、Console 应用装配、前端路由/类型/API、打包及交付探针中相连。第二条链路是保留目标。

## 本次移除范围

- 删除 `agent_runtime/pi_worker/` 和 `aitest_kit/agent/` 的已跟踪源文件、安装种子与对应测试。
- 删除 `aitest_kit/console/agent_*.py`、模型连接/Runtime/会话 HTTP 路由及应用装配；移除 `aitest agent` CLI 命令。
- 删除 Vue Agent 页面、模型连接设置、专用组件、store、类型、API/SSE、CSS 与专属测试/截图；保留编辑器设置、通用 Diff 组件和其测试。
- 删除 Pi seed 构建和 Agent 持久化 benchmark 脚本。安装 CI 与探针改为验证独立 Console，无需 Node/npm Runtime。Linux 前端构建和浏览器测试仍使用现有 Node 工具链。
- 更新 README、中英文说明、用户手册、交付说明和打包规则。已发布 CHANGELOG、历史 Spec 和学习记录保留历史事实，以新 Spec 为当前方向。
- 原 `/api/agent/*` 不再注册，`aitest agent` 返回未知命令，前端不再发 Agent 请求。既有 Console 认证、路径验证、env 显式授权、资产操作和执行接口保持原合同。

影响超过 8 个文件，跨 Python、Vue、测试、脚本、CI、文档与生成前端资源；不新增服务或依赖，不升级依赖。

## 数据与兼容边界

只删除仓库跟踪的内置 Agent 功能代码。保留用户 workspace、Markdown、profile、Harness、helper、generated、报告、env 与现有配置文件。

不修改本机 `~/.aitest/sessions/`、`~/.aitest/runtimes/` 或其他凭证/状态目录；保留旧配置中的 `agent` 字段，不自动迁移/清除。旧 Pi 历史不能在新工作台继续，但可使用保留分支及原版本读取。

不改 Naiyue Test Agent 项目的代码、配置或工作区。用户已于 2026-10-17 授权：修复分支审查问题、验证通过后提交到当前实施分支；不推送、不合入 main、不发布。

## 移除后正常与失败链路

- 正常：Console 打开已有 workspace → 认证文件接口 → Monaco 编辑并保存 Markdown → 运行页启动 codegen/run → JobManager → 既有 CLI → 报告页读取 result.json/report.md。
- 失败：profile 错误或 freshness 不通过 → 既有诊断/blocked 结果 → UI 显示来源与分类；不会尝试启动 Agent 或模型连接。
- 旧链接：Agent 页面由现有未找到页面处理；旧 Agent API 返回不存在。打开/切换 workspace 不访问旧 Agent 存储。

## 外部接入建议（本轮仅设计）

```text
用户 → Naiyue Test Agent
          ├─ 读取 AITest skills，按工作流理解任务
          ├─ read/write/edit 修改 Markdown、profile、Harness
          └─ Shell 调用 aitest CLI 完成确定性检查、生成、执行
                                  ↓
                      同一 AITest workspace 文件
                                  ↑
                      AITest Console 查看、编辑与运行
```

首个验证切片复用 Naiyue 当前已有的 workspace skills、通用文件工具及 Shell；不把“测试设计”硬编码为模型必须调用的业务工具。新建 workspace 的 neutral `skills/` 需按 Naiyue 当前发现合同复制至 `.agents/skills/`，复用既有 onboarding 方式。

AITest `result.json` 是执行事实；模型工具成功只说明调用完成。Markdown/profile/Harness 是可编辑源，generated 是编译产物。

如需更稳定的结构化调用，再在 Naiyue 现有 ToolRegistry 中注册少量适配工具，复用 AITest 既有服务/CLI：资产管理、profile 校验、codegen、run、report。工具适配层放在调用方/独立适配包，不让 AITest 依赖 Naiyue/LangChain。

跨 Agent 产品分发后再评估 MCP；当前 Naiyue 源码没有已接线 MCP 客户端。此方案不承诺实时文件监听或跨进程编辑锁，第一轮顺序操作，同一文件的并发编辑使用现有 Console 哈希冲突检查。

本轮只读验证：Naiyue 当前 `application/skills.py` 的发现器实际识别本仓 `.agents/skills/` 和 `.claude/skills/` 共 20 条 skill 元数据，diagnostics=0；这不等于真实模型已经正确执行测试工作流。现有 `tools/registry.py` 使用 LangChain BaseTool + Pydantic 的 ToolSpec/ToolRegistry，可作为后续适配接点。官方工具合同参考 [LangChain tools](https://reference.langchain.com/python/langchain-core/tools)。

## 验证

- 先加失败测试：CLI 不再暴露 agent；Console 没有 Agent API/服务；旧 Agent 状态未被触碰；UI 无 Agent 导航、设置或请求，编辑器设置仍可用。
- 移除专属功能测试；在混合测试文件保留全部 Console/编辑器、认证、文件、运行、报告验证，不以删测试掩盖仍保留能力的失败。
- Python 全量测试、Vitest、Vue 构建、Playwright、profile validation、freshness、generated collect。
- wheel/sdist 从干净跟踪源码构建，检查 Console 与 skills 完整、不含 Pi 安装种子；安装探针验证在无 Agent Runtime 条件下启动 Console、认证和 JS 资源。
- 不调用真实模型，不操作真实待测服务；报告本机验证与未运行平台的区别。

### 分支审查修正合同

- 已复现：setuptools 复用旧 `build/lib` 时会将已删除的 Agent 模块和页面资源带回 wheel；原安装探针只验证 Agent API 404，不能证明包内无残留。
- 在现有 `scripts/verify_wheel_install.py` 增加 `verify_archive(path)`，只用标准库读取 wheel/sdist 文件清单，不解压、不执行、不清理用户缓存。拒绝旧 Agent Python 包、Console Agent 模块、Worker/seed、Agent 页面产物和 node_modules。
- 安装验收先检查 wheel 内容，失败时在 `inspect_wheel` 阶段退出且不创建 venv/执行安装；结构化报告提供不含归档文件名或文件正文的修复提示。仅通过内容检查后才报告 `embedded_agent=absent`，HTTP 探针另报告 `agent_api=absent`。
- CI 的 wheel/sdist 检查与发布构建检查复用此函数，避免仅安装入口修复、实际产物上传入口仍漏检。只修改检查，不改变发布触发条件、权限、版本或上传目标。
- 交付文档说明：新 outdir 不等于干净构建目录；正式构建使用已提交代码的干净 checkout/worktree，不自动删除现有 build、缓存、Runtime、会话或 workspace。
- 同步修正仓库与 init 模板配置手册的 Agent 字段归属；添加 CHANGELOG 未发布记录，保留 v0.5.0 历史。
- 先增加污染 wheel、带前缀 sdist、正常包、失败报告和文档一致性回归测试，确认旧代码失败再修复；随后执行完整 Python、Vue、浏览器、构建、profile/freshness/collect 和隔离安装验证。
- 提交仅包含本次 Pi 移除及其审查修正、Spec、回归测试与完整前端产物；排除其他 research/lesson/讨论稿。

### 本地结果

- 新 CLI/API 缺席测试及导航设置测试先失败，移除后通过。
- `python3 -m pytest tests -q`：339 passed，2 条既有 collection warning；含审查修正新增的 27 条回归验证，已删除功能的专属测试同步移除。
- `npm test --prefix console_web`：19 files / 72 passed。
- `npm run test:e2e --prefix console_web`：9 passed；保留编辑器/运行/报告场景，新增无 Agent 导航/设置/请求场景。
- `npm run build --prefix console_web`：退出码 0；现存 Monaco 大 chunk 警告仍在。
- `codegen --all --validate-profile`、`codegen --all --check` 通过；generated collect：188 tests。
- 干净跟踪源码快照构建 wheel/sdist 成功；包内 Console 和 skills 存在，Pi Python 模块、Worker seed 和 Agent 页面资源均不存在。
- `scripts/verify_wheel_install.py`：Darwin / Python 3.9.6 隔离安装 passed；wheel_contents、workspace doctor、Console HTTP、JS 成功，未认证返回 401，embedded_agent=absent、agent_api=absent。未运行 Linux/Windows 原机验证或远程 CI。
- 交付回归：修复前污染 wheel 验收误判及两份配置手册、CHANGELOG 断言共 4 条失败；修复后 `tests/test_delivery_verification.py` 为 35 passed。原“子进程异常脱敏”测试的空文件改为有效 ZIP fixture，以继续验证 venv 失败分支，不放宽原断言。
- 复用旧构建缓存生成的 wheel 含 26 个旧 Agent Python 文件和 7 个旧 Agent 页面资源；修正后的安装验收返回退出码 1，stage=inspect_wheel，不再误判通过。
- 干净 wheel/sdist 构建和 `twine check` 通过；CI、publish 两个工作流中的归档检查 Python 片段均在本地对实际产物执行通过。这不是远程 workflow 或发布执行证据。
- 安全和架构提交前只读复核未发现阻断项。提交边界：仅当前实施分支，不推送、不合入 main、不发布；其他研究和学习文件保持原状。

## 回退

恢复旧功能可使用保留分支或 v0.5.0；本次不修改历史会话/Runtime 数据，无需反向数据迁移。新工具接入另行确认 Spec 与最小验收任务后实施。
