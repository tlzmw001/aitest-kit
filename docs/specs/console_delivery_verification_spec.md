# Console 交付验收与持久化测量

状态：实现及本地验收完成；六组远程安装与最新 Linux 视觉回归待 push 后由 GitHub 验证。范围由用户确认的三项组成，不包含提交、push、发布或真实模型调用。

## 当前链路与问题

- GitHub Actions 当前在 Ubuntu 跑 Python、Worker 和 Console 测试；Playwright 使用 `{platform}` 截图路径，但仓库只有 Darwin 基线。
- wheel 携带 Worker 安装种子，`agent setup` 在用户 Runtime 目录运行锁定的 npm 安装与原生 self-test；仅检查包内文件不足以证明用户安装后能启动。
- `AgentSession._append` 调用 `AgentEventLog.append`（JSONL + fsync），随后 `_persist` 调用 `AgentSessionStore.save`（临时元数据 + fsync + replace）。目前每事件两次 fsync，先量化成本，不预设 batching。

## 1. Linux 视觉基线

从已核验的 GitHub run 33508507756 的诊断产物恢复两张 Linux PNG，逐图审阅并核对 actual 与 baseline 的哈希。保留 Darwin 图片和现有差异阈值；增加两平台基线存在性/PNG 格式测试及来源说明。新增 Linux 基线不是本轮 Linux 回归通过的证明；最新分支须在 push 后由 GitHub 复测。

## 2. 跨平台安装验收

新增独立 `install-smoke` job，GitHub-hosted Ubuntu/macOS/Windows × Node 22.19.0/24，Python 3.11。既有 Python 3.9/3.11 单元测试矩阵保留。

流程：构建 wheel → 临时隔离 venv 安装 wheel[server] → 仓库外初始化含空格路径的 workspace → doctor → agent setup 两次验证幂等 → 验证用户目录 Runtime 和 Pi self-test → 实际 CLI 启动 Console → 验证认证与打包页面/JS → 关闭进程。

- `scripts/verify_wheel_install.py --wheel-dir DIR --output JSON` 负责隔离环境与安装；`scripts/wheel_install_probe.py` 在新 venv 中运行验收。
- 不复用源码导入、node_modules、用户 Runtime、凭证或真实 workspace；不调用 provider/model。外网只用于 pip/npm 安装依赖。
- 新 venv 从清理后的环境启动，临时 `AITEST_RUNTIME_HOME`、session 目录和 npm cache/config；不覆盖 HOME 或修改用户环境配置。
- 端口由操作系统分配；会话 token 只在进程内消费，不写验收报告/日志。失败报告保存阶段及安全错误类别，不打印原始 Console 输出。
- CI 上传每组合独立的脱敏 JSON 结果；无远程运行结果时明确标注待验证。

## 3. 持久化测量

`scripts/benchmark_agent_persistence.py` 在临时目录使用真实 EventLog 和 Store，按现行 journal append → metadata save 顺序写入合成事件。每轮记录事件延迟 p50/p95/max、吞吐量、fsync 次数/耗时、磁盘字节数与重开回放时间。事件量、payload 字节数和重复次数由参数控制。

测试验证每事件双持久化、重开 seq、统计结构；不设易抖动的耗时断言。报告注明机器、Python、样本和限制：这是持久化阶段，不是 provider/SSE/浏览器端到端延迟，也不代表慢盘表现。只有明确成本证据才另行确定优化和崩溃一致性策略；本阶段默认保留每事件落盘语义。

## 验收与影响

新增脚本及测试、截图与来源说明、工作流和测量记录；不升级依赖，不修改业务 API/运行时持久化策略。运行 Python 全量测试、Worker 测试/类型检查、Vue 测试/构建、macOS Playwright、真实 clean-wheel smoke 和基准。Linux/Windows 真实结果待用户授权 push 后查看 GitHub。

## 官方依据

- [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots)：截图需要审阅入库，并在相同环境比较，平台差异不能靠复制其他平台基线掩盖。
- [GitHub Python CI](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)：采用 setup-python 与 OS matrix 的官方工作流模式。
- 安装架构继续遵循 `docs/specs/pi_worker_distribution_spec.md`，不引入第二套 Runtime 安装实现。

## 本地验收记录

- 原先新增测试复现缺少两张 Linux 基线；补齐后基线与交付脚本测试 10 passed。
- 最终 Python 全量：408 passed、1 个 opt-in 测试 skipped、2 个既有 TestCase 收集警告；compileall 与 git diff --check 均通过。
- macOS / Python 3.9.6 / Node 24.14.0 的 clean-wheel smoke 实跑成功：source=user、setup 幂等、自检、Console 指定 workspace、401 认证、打包 JS 和 Runtime HTTP 查询均通过。
- Vue 110、Worker 20、macOS Playwright 12 个测试通过；前端生产构建成功。
- 持久化测量九轮均重开 seq 一致，p95 小于 0.7 ms；保留原逐事件写入语义。完整数据见 `docs/benchmarks/agent_persistence.md`。
- 不把历史 Linux 图片来源、本机测试或 CI 配置存在表述为最新六组远程绿灯。

## 首次远程验收反馈

run `33944436852` 的 Linux Playwright 13 项已通过；安装验收发现较新 Python
解析到的 FastAPI 不再提供 `add_event_handler`，Console 改用官方 lifespan
（https://fastapi.tiangolo.com/advanced/events/），保留 shutdown 清理，未调整依赖版本。
probe 增加有界且过滤敏感行的错误诊断，子进程提前退出时立即报告，不再只等到
token 队列超时。Windows setup 失败另行按具体诊断定位，不依据 macOS 推断通过。

第二轮 Windows 日志确认 seed `package-lock.json` 字节哈希不匹配。使用
`git -c core.autocrlf=true checkout-index` 在临时目录复现；`.gitattributes`
为 Worker 源和 runtime seed 固定 `eol=lf` 后同一测试通过，不放宽校验、不重算
Windows 专属 bundle hash。Ubuntu/macOS 四组 clean-wheel 已在第二轮通过。
