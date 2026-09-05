# AITest Pi Worker Distribution Spec

状态：已实现并完成本地验证
日期：2026-09-01
实现分支：`codex/vue-console-mvp`
上游权威：`test_workspace/plans/pi_agent_runtime_integration_spec.md`
关联实现：`docs/specs/local_console_agent_connection_spec.md`、`docs/specs/local_console_agent_session_spec.md`

## 1. 背景

当前 Pi Agent Runtime 只保证 AITest 源码 checkout：

```text
agent_runtime/pi_worker/
  -> npm ci
  -> Python 通过仓库相对路径启动 src/worker.ts
```

正式 Python wheel 只包含 `aitest_kit*`。安装用户没有顶层 `agent_runtime/pi_worker`，也不应进入
Python `site-packages` 执行 npm 安装。因此现有 Agent 链路无法作为普通 wheel 功能交付。

当前 Worker 源码很小，但展开后的 `node_modules` 约 177 MB、超过一万个文件，并包含 `.node`、
WASM 和多平台资源。首版不能把完整 `node_modules` 塞入 `py3-none-any` wheel。

## 2. 锁定决策

1. Node.js 由用户安装；最低 `22.19.0`，新用户推荐 Node.js 24 LTS。
2. Python wheel 携带 Pi Worker 安装种子，不携带 `node_modules`。
3. 用户通过 `aitest agent setup` 或 Console 明确确认后安装 Runtime。
4. Runtime 安装在用户级目录，不写 workspace，也不修改 Python `site-packages`。
5. 安装使用仓库精确 `package-lock.json` 和 `npm ci --omit=dev --ignore-scripts`。
6. Console、CLI 和 Worker 启动共享同一套 Python Runtime service 与 resolver。
7. 源码 checkout 继续支持现有开发路径；wheel 用户使用已安装 Runtime。
8. 不因分发实现升级 Pi、permission-system 或其他依赖。

## 3. 非目标

本阶段不做：

- 自动下载或安装 Node.js。
- 在 `pip install`、Console 启动或打开 workspace 时静默联网安装。
- 发布独立 `@aitest/pi-worker` npm 包。
- Node SEA、Bun 编译二进制、Electron/Tauri Runtime 打包。
- 离线 Runtime 归档。
- 自动清理旧 Runtime；清理功能另行讨论。
- 把 npm registry token、模型 API Key 或 env 值写入 manifest、日志或 API。
- 持久 session、多 session 或 Capability Registry。

## 4. 用户流程

普通用户：

```bash
python3 -m pip install "aitest-kit[server]"
aitest agent setup
aitest agent doctor --workspace /path/to/workspace
aitest console --workspace /path/to/workspace
```

`aitest agent setup` 与 workspace 无关，一台机器上的同一用户只需为当前 bundle 安装一次。
未安装 Runtime 时，Console 的编辑、codegen、run 和 report 保持可用；Agent 页面和连接测试返回
结构化的 `AGENT_RUNTIME_NOT_INSTALLED`。

## 5. 源与产物边界

唯一手写源：

```text
agent_runtime/pi_worker/
  package.json
  package-lock.json
  src/*.ts
```

wheel 安装种子是确定性生成产物：

```text
aitest_kit/agent/runtime_seed/pi_worker/
  package.json
  package-lock.json
  runtime-manifest.json
  src/*.ts
```

禁止手工修改 `runtime_seed`。生成命令必须：

1. 删除旧 seed 中不再存在的受管文件。
2. 复制允许列表内的源码和 npm metadata。
3. 为每个文件写 SHA-256。
4. 基于路径和文件 hash 计算 `bundle_hash`。
5. 写稳定排序、UTF-8、结尾换行的 manifest。

CI 在生成后执行 `git diff --exit-code -- aitest_kit/agent/runtime_seed`，防止源码与 wheel 产物漂移。

## 6. Runtime manifest

`runtime-manifest.json` 固定包含：

```json
{
  "schema_version": 1,
  "runtime": "pi",
  "worker_version": "0.1.0",
  "entrypoint": "src/worker.ts",
  "minimum_node_version": "22.19.0",
  "bundle_hash": "<sha256>",
  "files": {
    "package-lock.json": "<sha256>",
    "package.json": "<sha256>",
    "src/worker.ts": "<sha256>"
  },
  "dependencies": {
    "@earendil-works/pi-coding-agent": "0.84.3",
    "@gotgenes/pi-permission-system": "27.1.1"
  }
}
```

`files` 实际覆盖全部受管 seed 文件。安装前必须重新计算并核对；不一致时拒绝安装。

## 7. 用户级目录

默认根目录：

```text
Path.home() / ".aitest" / "runtimes"
```

显式环境变量覆盖：

```text
AITEST_RUNTIME_HOME
```

最终目录：

```text
<runtime-home>/pi-worker/<bundle-hash>/
```

用户输入不能参与目录拼接。`bundle_hash` 必须是 manifest 中校验后的 64 位小写十六进制。

安装完成后新增 `install-manifest.json`：

```json
{
  "schema_version": 1,
  "runtime": "pi",
  "bundle_hash": "<sha256>",
  "node_version": "v24.14.0",
  "installed_at": "<ISO-8601>"
}
```

不保存 registry token、环境变量内容、workspace 路径或模型配置。

## 8. 安装算法

`aitest agent setup`：

1. 读取并验证 seed manifest 与全部文件 hash。
2. 检查 `node`、`npm`、Node 最低版本和 Runtime 根目录写权限。
3. 如果目标 bundle 已完整安装并通过校验，返回幂等成功。
4. 在同一 Runtime 根目录创建唯一 staging 目录。
5. 将 seed 复制到 staging。
6. 在 staging 执行 `npm ci --omit=dev --ignore-scripts`。
7. 执行 Worker `--self-test`，验证 Pi SDK、permission extension 和 JSON 输出。
8. 写 `install-manifest.json`。
9. 仅在全部成功后把 staging 原子移动到 bundle 目标目录。
10. 失败时删除本次 staging，不改已有可用 Runtime。

如果同 bundle 目标已存在但校验失败，setup 必须先完成新的 staging 与自检，再尝试替换；替换失败时恢复
原目录或保持原目录不变，不能留下半安装目标。

## 9. Worker 自检

Worker 新增：

```bash
node --experimental-strip-types src/worker.ts --self-test
```

成功时只向 stdout 写一行 JSON：

```json
{"runtime":"pi","status":"ok"}
```

失败时向 stderr 写脱敏错误并非零退出。自检不读取 API Key、不发模型请求、不访问 workspace。
普通 JSONL Worker 模式保持现有协议和 stdout 纯净约束。

## 10. Runtime resolver

默认 Worker 查找顺序：

1. 调用方显式传入的 Worker 目录，仅供测试和受控开发入口。
2. Python 包位置能够确定的源码 checkout `agent_runtime/pi_worker`，且依赖完整。
3. 当前 seed `bundle_hash` 对应的用户级 Runtime，且 install manifest、seed 文件和直接依赖完整。
4. 否则抛出 `AGENT_RUNTIME_NOT_INSTALLED`，包含 `aitest agent setup` 提示。

禁止从当前 workspace、全局 `pi`、任意 `PATH` 同名 Worker 或 workspace `node_modules` 猜测 Runtime。

## 11. CLI

新增：

```text
aitest agent setup
```

输出安装阶段、Node/npm 版本、registry、安装目录和直接依赖版本。命令本身是显式安装授权，不再二次确认。

保留并增强：

```text
aitest agent doctor --workspace <path>
```

doctor 依次报告：

- Node 版本。
- Runtime source、bundle hash 和目录。
- seed/install manifest 与依赖完整性。
- workspace Agent 配置。
- API Key 环境变量是否存在，只报告变量名。
- 有 Key 时进行真实 Worker handshake。

## 12. Console API

所有端点继续使用 Console session token：

### `GET /api/agent/runtime`

返回：

```json
{
  "state": "ready | missing | node_missing | node_unsupported | invalid",
  "source": "source | user | null",
  "message": "human readable status",
  "runtime_dir": "/absolute/path/or/empty",
  "bundle_hash": "sha256 or empty",
  "minimum_node_version": "22.19.0",
  "node_version": "v24.14.0 or empty",
  "npm_version": "11.9.0 or empty",
  "registry": "https://registry.npmjs.org/ or empty",
  "dependencies": [{"name":"...","version":"..."}],
  "setup_command": "aitest agent setup"
}
```

不返回 env 值、npm token 或模型 Key。

### `POST /api/agent/runtime/setup`

请求：

```json
{"confirmed":true}
```

未确认返回 `AGENT_RUNTIME_SETUP_CONFIRMATION_REQUIRED`。存在安装任务时返回 409。存在当前 Agent session 时返回
`AGENT_SESSION_ACTIVE`。成功返回独立 Runtime setup job。

### setup job

```text
GET  /api/agent/runtime/setup/{job_id}
POST /api/agent/runtime/setup/{job_id}/cancel
```

复用现有 Job schema。setup job 与 workspace 测试 job 分开管理，可以在未打开 workspace 时运行。

## 13. Console UX

“设置 → 模型连接”顶部增加 Runtime 卡片：

- ready：展示来源、Node 版本、bundle 短 hash 和目录。
- missing：展示安装会访问的 registry、写入目录、锁定依赖和复制 CLI 命令。
- node_missing/node_unsupported：禁用安装按钮，展示最低版本与 Node 官方下载入口。
- installing：展示可滚动日志、任务状态和取消按钮。
- failed：展示结构化错误和脱敏日志，可再次明确安装。

点击“安装 Agent Runtime”打开 Reka Dialog，明确：

- 将运行 npm 安装。
- 网络访问的 registry。
- 用户级目标目录。
- 不修改 workspace。
- 不读取模型 API Key。

Agent 页面在 Runtime 非 ready 时不展示 session 创建按钮，改为说明并跳转模型连接页。

## 14. 失败语义

至少包含：

| Code | 语义 |
|---|---|
| `AGENT_RUNTIME_NOT_INSTALLED` | 当前 bundle 未安装 |
| `AGENT_RUNTIME_SEED_INVALID` | seed manifest 或文件 hash 不一致 |
| `AGENT_NODE_NOT_FOUND` | Node 不存在 |
| `AGENT_NODE_UNSUPPORTED` | Node 低于最低版本 |
| `AGENT_NPM_NOT_FOUND` | npm 不存在 |
| `AGENT_RUNTIME_INSTALL_FAILED` | npm、自检或原子落盘失败 |
| `AGENT_RUNTIME_INVALID` | 已安装 Runtime 不完整或 hash 不匹配 |
| `AGENT_RUNTIME_SETUP_CONFIRMATION_REQUIRED` | Console 未明确确认 |
| `AGENT_RUNTIME_SETUP_JOB_NOT_FOUND` | setup job 不存在 |

错误可以包含阶段、退出码、路径和脱敏后的有限日志，不能包含凭证值。

## 15. 安全约束

- 安装只写用户 Runtime 根目录下经过验证的目标。
- 不使用 `sudo`，不写全局 npm，不改 workspace、`.env` 或 npm 配置。
- npm 参数固定，不接受浏览器或 workspace 传入任意命令。
- 使用 lockfile integrity；package/lock 不一致时停止。
- npm install scripts 默认禁用；依赖升级必须重新验证该约束。
- API、日志和 install manifest 不含 secret/token/password/key 值。
- Runtime setup 与 Agent approval/full_trust 是不同授权面，不能互相替代。

## 16. 构建与发布

`pyproject.toml` 将 seed 作为 `aitest_kit.agent` package data。wheel/sdist 验收必须证明：

1. seed 文件全部存在。
2. 不包含 `node_modules` 和 Worker tests。
3. wheel 仍为纯 Python 通用 wheel。
4. 从干净 wheel 安装后能运行 `aitest agent setup`。
5. setup 可在任意 cwd 执行。
6. Console 和 CLI 解析到同一个用户 Runtime。

## 17. 测试矩阵

### Python 单元测试

- manifest 生成稳定且源变化会改变 bundle hash。
- seed hash 被篡改时拒绝安装。
- Node/npm 缺失和版本不足。
- setup 幂等、失败清理、已有目标替换保护。
- Runtime resolver 的 source/user/missing 顺序。
- doctor 不输出 secret。
- Console 状态、确认、任务查询、取消和 session 冲突。

### Node 测试

- `--self-test` 成功且只输出一行 JSON。
- 普通 JSONL Worker 测试保持通过。

### Vue/Vitest/Playwright

- ready/missing/node error/failed/installing 状态。
- Dialog 展示 registry、路径和“不修改 workspace”。
- 未确认不启动安装。
- setup job 终态后刷新 Runtime 状态。
- Agent 页面在 Runtime 缺失时不允许创建 session。

### 发布验证

- Python 3.9 与 3.11。

## 18. 实现与验证结果

实现保持本 Spec 的所有权边界：Worker 手写源仍只在 `agent_runtime/pi_worker/`；构建脚本生成
wheel seed；`aitest_kit.agent.runtime` 是 CLI、doctor、Console 和 Worker resolver 的唯一
Runtime service。Console setup 复用现有有界输出与进程组取消机制，但使用独立用户级 job manager，
不依赖已打开的 workspace。

2026-09-01 本地验收结果：

- Pi Worker：17 个 Node 测试通过，`--self-test` 会真实加载 permission extension。
- Python Agent/Console：126 passed、1 个 opt-in 真实模型 smoke skipped；全量 Python 为 370 passed、1 skipped。
- Vue：24 个测试文件、89 个测试通过；生产构建成功。
- Playwright：Chromium 10/10 通过，包括既有视觉回归。
- wheel/sdist 构建成功；wheel 为 `py3-none-any`，包含 seed，不包含 `node_modules` 或 Worker tests。
- 从新建虚拟环境只安装 wheel 后，在 `/tmp` 运行 setup 成功；resolver 报告 `source=user`。
- 在另一个 cwd 对同一 Runtime 再次 setup 返回幂等成功。

远程 Python 3.9/3.11 CI 仍由提交后的 GitHub Actions 验证；本地完成不替代远程绿灯。
- Node 22.19 与当前 Node 24 LTS。
- Ubuntu、macOS、Windows 至少各完成一次 seed setup/self-test；真实模型 smoke 仍保持 opt-in。

## 18. 完成条件

后续交付验收接入：`.github/workflows/ci.yml` 的 `install-smoke` 矩阵覆盖三种
GitHub-hosted OS × Node 22.19.0/24，通过真实 clean-wheel 安装、两次 setup、
self-test 和 Console HTTP 验证以上路线。脚本和本地复现见
`docs/usebook/console_delivery_verification.md`。配置存在不等于六组远程已通过，
实际状态以对应提交的 GitHub run 为准。

- wheel 用户无需 AITest 源码 checkout 即可安装并启动 Pi Worker。
- `aitest agent setup` 不依赖 cwd/workspace，失败不破坏已有 Runtime。
- Console 安装入口真实接线，非静态演示。
- Runtime 缺失时错误可行动，不暴露 `Cannot find module`/`worker.ts not found`。
- seed、wheel、CLI、Console、doctor 与 Worker 自检完成 L1 存在、L2 实质、L3 接线验证。
- Python、Node、Vue、Playwright、wheel 内容和 `git diff --check` 全部通过。
