# AITest Local Console MVP Spec

## 1. 文档状态

- 状态：已批准，进入实现
- 实现分支：`codex/vue-console-mvp`
- 产品形态：本地优先、单用户、用户自己 clone workspace
- 前端技术：Vue 3、TypeScript、Vite
- 前端构建：Node.js 22.18+，生产 bundle 随 Python wheel 分发
- 后端技术：复用现有 Python/FastAPI 依赖
- 视觉基线：已批准的深色高密度工程工作台
- 与 Pi 的关系：Console MVP 不依赖 Pi，后续通过 AITest 控制面接入

本 Spec 是 Local Console MVP 的实现权威。`test_workspace/plans/pi_agent_runtime_integration_spec.md`
继续作为 Pi Agent Runtime Phase 1 的权威，两条实现线互不混入。

## 2. 背景

AITest 已经具备确定性测试链路：

```text
Markdown cases + target/module/suite/task + profile
  -> profile gate
  -> Case IR
  -> codegen
  -> generated freshness check
  -> pytest
  -> result.json / report.md
```

当前主要入口是 CLI。Local Console 的目标不是在 TypeScript 中复制这套逻辑，而是给本地
workspace 提供可看、可编辑、可执行、可追溯的控制面。

## 3. 第一性原则

1. Vue 负责交互和展示，Python 继续拥有 AITest 语义。
2. Markdown、Profile、配置和 Harness 是源资产；generated pytest 与报告是只读产物。
3. `result.json` 是执行事实源，`report.md` 是阅读版。
4. Console 不依赖 Pi、模型或 API Key，确定性测试链路必须独立可用。
5. 用户可以显式编辑已授权的 env 文件，Agent、日志、报告和普通文件接口不能读取 env 值。
6. 打开 workspace 不执行项目代码；validate、codegen、run 等操作由用户显式发起。
7. 本地优先不等于无限权限。所有路径、命令和进程仍由结构化白名单约束。
8. 首版不使用数据库，workspace 文件系统仍是权威状态。

## 4. MVP 目标

首版完成以下闭环：

1. 通过本地路径打开一个 AITest workspace。
2. 浏览 target、module、suite、case、task 及相关配置和高级资产。
3. 查看和编辑 Markdown、YAML、Python 源文件。
4. 显式保存文件，并使用内容 hash 防止覆盖外部修改。
5. 执行 profile validation、codegen、生成同步检查和 run。
6. 按 case、suite、module 或 task 选择执行范围。
7. 流式查看任务输出、任务状态并终止运行中的子进程。
8. 查看 `result.json`、`report.md` 和历史执行。
9. 展示配置、用例、脚手架、环境、待确认、待测系统和清理错误归属。
10. 创建、查看和编辑 workspace `.env`、`AITEST_ENV_FILE` 和 task `env_files`。

## 5. 非目标

MVP 不做：

- Pi 会话、Agent 对话、Agent 工具调用或 patch 审批。
- 多用户、登录、团队 RBAC、云同步或远程 workspace。
- Electron、Tauri 或桌面安装包。
- 多 workspace 并行执行。
- 低代码 Profile、YAML 或 Harness 表单。
- 任意 Shell 输入或任意命令执行。
- 自动修改 `.gitignore`、`.env` 或 task manifest。
- env 内容历史、云端凭证库或操作系统 Keychain。
- Docker/OpenShell Sandbox。
- generated pytest 的手工编辑。
- 自动把 assertion failure 判定为待测系统 bug。

## 6. 总体架构

```text
System Browser
  -> Vue 3 Local Console
     - workspace explorer
     - source editor
     - run configuration
     - job output
     - reports and history
     - sensitive env editor
        |
        | loopback HTTP + per-process session token
        v
  -> AITest Console API (FastAPI)
     - active workspace state
     - path and source ownership policy
     - safe file/env IO
     - structured command builder
     - subprocess lifecycle and cancellation
     - report index
        |
        v
  -> Existing AITest Python kernel / CLI
     - registry loaders
     - profile gate
     - codegen / freshness
     - run / report
```

不存在反向依赖：AITest codegen/run/report 不 import Console；Pi Runtime 也不 import Console。

正式分发时，Vue 生产构建作为 `aitest_kit.console` 的 package data 进入同一个 Python wheel。
FastAPI 从安装包资源提供前端，不从 active workspace 查找 `console_web/dist`，也不把前端文件
复制到用户 workspace。源码开发仍保留 Vite 流程。未来如增加 Tauri 薄壳，必须复用本 API 与
Vue 构建，不得形成第二套 workspace 文件或执行权限通道。Electron/Tauri 仍不进入 MVP。

## 7. 目录与实现单元

```text
console_web/
  package.json
  package-lock.json
  vite.config.ts
  tsconfig*.json
  index.html
  src/
    api/
    components/
    stores/
    views/
    App.vue
    main.ts
    styles.css

aitest_kit/console/
  __init__.py
  app.py
  cli.py
  files.py
  jobs.py
  workspace.py
  web/                 # Vue production build, included in wheel

tests/console/
  test_console_api.py
  test_console_files.py
  test_console_jobs.py
```

单文件不超过 500 行；职责出现三次前不再抽象新的框架层。

## 8. Workspace 模型

### 8.1 打开

`POST /api/workspace/open` 接收本地绝对或相对路径。后端规范化真实路径并验证：

- 路径存在且是目录。
- 包含 `aitest_config/aitest.yaml`。
- 包含 `test_workspace/`。
- 配置能够由现有 loader 解析。

打开只读取配置和目录，不 import 或执行 fixture、Harness、helper、generated pytest。

当路径存在且是目录，但 `aitest_config/aitest.yaml` 与 `test_workspace/` 均不存在时，返回
`WORKSPACE_NOT_INITIALIZED`，不写入任何文件。前端保留用户刚选择的路径，展示初始化将写入的
资产范围，并等待用户点击“初始化并打开”。只有 `POST /api/workspace/initialize` 收到
`confirmed: true` 才调用既有 `init_workspace(..., force=False)`；不暴露 force。模板文件冲突、
部分初始化结构或运行中的 job 都阻止初始化。成功后才把该目录设为 active workspace。

首版进程中只保存一个 active workspace。最近路径只保存路径引用，不保存文件内容或 env 值。

### 8.2 快照

`GET /api/workspace` 返回：

- workspace 名称、规范化路径和 Git branch。
- target、module、suite、task 层级。
- suite case 文件、Profile、module 高级资产。
- case id、标题、优先级和 source line。
- registry diagnostics。
- 最近运行摘要。

target/module/suite/task 语义优先调用现有 registry loader。前端不解析这些配置形成第二份权威。

## 9. 文件所有权与编辑规则

### 9.1 可编辑源文件

- Markdown 用例与知识文件。
- `aitest_config/`、target/module/suite/task YAML。
- module/suite Profile。
- fixture、Harness、helper 及其他 workspace 内 Python 测试资产。

### 9.2 只读文件

- `test_workspace/generated/`。
- `test_workspace/reports/`。
- `test_workspace/results/` 默认只读，MVP 不提供 SUT bug 写入流程。
- Git 元数据和 workspace 外未授权文件。

普通文件接口明确拒绝 `.env` 和任何识别为 env source 的文件，env 只能通过敏感接口访问。

### 9.3 读取和保存

读取返回 UTF-8 内容、相对路径、owner、read-only 状态和 SHA-256。

保存必须携带读取时的 SHA-256。后端在写入前再次比较；不一致返回冲突，不覆盖磁盘新内容。
保存使用同目录临时文件与原子替换，并保留现有文件 mode。新建普通源文件不在 MVP 范围。

## 10. Env 权限

### 10.1 允许的 env source

- `{workspace}/.env`。
- 当前 Console 选择的 `AITEST_ENV_FILE`。
- task manifest 的 `env_files`。
- 用户通过敏感授权接口逐文件授权的其他 env 文件。

Shell env 只展示变量名和存在状态，不能通过 Console 修改父进程。CI Secrets 不展示。

### 10.2 敏感接口

Env 元数据默认只返回：

- 文件路径或 shell 来源。
- 变量名。
- 是否存在。
- Git tracked/ignored/untracked 状态。
- 文件是否位于 workspace 外。

读取 env 内容必须显式传入敏感访问确认。响应禁止缓存。env 内容不能进入普通文件接口、
job output、日志、异常、报告、localStorage 或 Agent 上下文。

### 10.3 编辑

Env 使用原始 dotenv 文本编辑器，保留注释、顺序、引号、`export` 和空行。保存前复用
`aitest_kit.runtime_variables` 的同一 parser 校验；非法内容不写入。

保存同样使用 SHA-256 冲突检查和原子替换。新建 `.env` 默认 mode 为 `0600`；现有文件
保留 mode。不创建 `.env.bak` 等永久密钥副本。

外部 env 文件必须先按解析后的真实文件路径授权。任意路径字符串不能直接获得读取权限。

### 10.4 运行优先级

沿用现有规则：

```text
Shell environment
  > explicit task env_files / AITEST_ENV_FILE
  > workspace .env
```

Console 为一次运行选择 env 文件时，只给该子进程设置 `AITEST_ENV_FILE`，不修改 Shell、
`.zshrc`、`aitest.yaml` 或 task manifest。

## 11. Job 与命令边界

Console 只接受结构化 operation 和 selector，不接受 Shell 字符串。

允许的 operation：

| operation | CLI 映射 | 写入 |
|---|---|---|
| `validate_profile` | `aitest codegen <selector> --validate-profile` | 否 |
| `codegen` | `aitest codegen <selector>` | generated |
| `freshness` | `aitest codegen <selector> --check` | 否 |
| `run` | `aitest run <selector>` | reports |

允许的 selector：

- suite：`--suite-file <manifest>`。
- case：suite selector 加一个或多个 `--case-id`，仅用于 run。
- module：`--target <target> --module <module>`。
- target：`--target <target>`。
- task：`--task-file <manifest>`。

路径必须解析到 active workspace 内的已存在 manifest。target/module/case 字符串必须由当前
registry/workspace 快照解析。任何未注册参数、额外 pytest 参数或 `--skip-codegen-check` 都拒绝。

### 11.1 生命周期

每个 workspace 同时只允许一个 active job：

```text
queued -> running -> succeeded
                  -> failed
                  -> cancelled
```

job 保存安全的命令摘要、时间、退出码和有界 stdout/stderr 文本。输出必须经过通用敏感值
redaction。取消先 terminate，超时后 kill，并等待子进程退出。

redaction 覆盖 Console 已读取的 env 值和常见敏感 Shell 变量，是纵深防护而不是任意编码的
秘密检测器；测试、fixture、Harness 和待测系统日志仍不得主动输出凭证。

Run 保留现有内置 freshness gate。Console 普通路径不暴露跳过开关。

## 12. 报告与错误归属

Console 从配置解析得到的 reports 路径递归读取历史 `result.json`，排除 `latest` 重复项，并按
timestamp 排序。报告详情返回原始 `result.json`、同目录 `report.md` 和规范化摘要。

UI 同时保留原始 failure classification 和展示归属：

| 展示归属 | 典型证据 |
|---|---|
| CONFIG | YAML、registry、Profile shape 和 suite context |
| CASE | parser、Case IR 或人工确认的用例意图错误 |
| SCAFFOLD | fixture、Harness、helper、生成接线和 codegen |
| ENV | PRECONDITION_MISSING、ENVIRONMENT_ERROR |
| REVIEW | 尚未人工归因的 ASSERTION_FAILURE |
| SUT | 人工确认并记录的待测系统行为 |
| CLEANUP | TEARDOWN_ERROR 和 restoration failure |

`ASSERTION_FAILURE` 默认进入 REVIEW，不自动归为 SUT。

## 13. 本地安全

- HTTP 只允许绑定 loopback 地址。
- 每次启动生成随机 session token，API 请求必须携带。
- CORS 只允许 localhost/127.0.0.1 开发和当前静态站点来源。
- API token 可放 sessionStorage，env 内容不得持久化。
- 所有用户路径在使用前 `resolve()`，并执行 root/授权文件检查。
- 不提供任意 Shell、eval、Python module import 或任意绝对路径读取。
- 打开 workspace 不执行代码，执行操作必须由用户显式点击。
- env、Authorization、token、password 等值不进入日志和报告。

MVP 假设用户运行的是自己信任的本地 workspace。打开不可信仓库并执行其 Python 测试需要
外部 Sandbox，不由本 Spec 声称解决。

## 14. 前端信息架构

主导航：工作台、用例、运行、报告、诊断、环境、设置。

固定 App Shell：

```text
58px primary rail
  + 272px resource explorer
  + flexible work area
  + 54px context/pipeline bar
  + 26px status bar
```

顶部流水线中文文案：用例、Profile 校验、生成 pytest、生成同步、执行、报告。

主路径：

- 工作台：真实 workspace 数量、模块列表、最近执行、错误所有权图例。
- 用例：文件 tabs、CodeMirror 源编辑、保存状态、只读 generated/report 提示。
- 运行：case/suite/module/task selector、命令预览、env source、启动与取消。
- 报告：历史列表、summary、cases、原始 `result.json` 和 `report.md`。
- 诊断：原始分类、展示归属、证据链和 source 跳转。
- 环境：来源优先级、key presence、显式 reveal、敏感编辑和 Git 状态。

界面没有真实数据时展示空状态，不使用假 target、case、报告或用户数据。

## 15. 视觉设计

- 主题：深色、高密度、可追溯工程工作台。
- 视觉材料：冷石墨背景层级，不使用装饰渐变或玻璃拟态。
- 主色：`oklch(0.72 0.14 55)` 信号橙，只用于当前操作和关键动作。
- 成功、失败、警告仅用于真实语义。
- 字体：Avenir Next / PingFang SC，代码使用 SFMono-Regular。
- 圆角系统：4px、6px、10px、pill。
- 深度：背景亮度层级和一像素分隔，不使用普通卡片阴影。
- 动效：只动画 transform/opacity，按钮按下 scale 0.96，支持 reduced motion。
- 目标尺寸：1440x900；1280px explorer 缩窄；1024px 以下 explorer drawer；移动编辑不在范围。

## 16. API 错误

所有失败返回稳定 code 和可读 message，不返回敏感 details。至少包括：

- `WORKSPACE_INVALID`
- `WORKSPACE_NOT_INITIALIZED`
- `WORKSPACE_INIT_CONFIRMATION_REQUIRED`
- `WORKSPACE_INIT_CONFLICT`
- `WORKSPACE_INIT_FAILED`
- `WORKSPACE_ALREADY_INITIALIZED`
- `WORKSPACE_NOT_OPEN`
- `PATH_OUTSIDE_WORKSPACE`
- `FILE_READ_ONLY`
- `FILE_CONFLICT`
- `FILE_ENCODING_ERROR`
- `ENV_ACCESS_REQUIRED`
- `ENV_PATH_NOT_AUTHORIZED`
- `ENV_INVALID`
- `JOB_ALREADY_RUNNING`
- `JOB_NOT_FOUND`
- `SELECTOR_INVALID`
- `UNAUTHORIZED`

## 17. 测试与验收

### 17.1 后端自动测试

- 打开有效/无效 workspace。
- 未初始化目录只返回可初始化状态且不写文件；确认后复用 packaged template 初始化并打开。
- 初始化不提供 force，模板冲突和部分初始化结构不会被覆盖。
- wheel 包含 Vue `index.html` 与静态 assets，启动位置与 active workspace 相互独立。
- 防路径遍历和 symlink 越界。
- 普通源文件读写、只读目录拒绝、hash 冲突。
- env 普通接口拒绝、显式 reveal、外部授权、非法 dotenv、原子保存和 mode。
- Shell env 覆盖文件值不被 Console 改写。
- 每个 operation/selector 构造正确 argv，无 Shell 拼接。
- 单 active job、输出收集、cancel/terminate/kill。
- report 历史排除 latest 重复项并保持 result.json 权威。
- API token 与 CORS 边界。

### 17.2 前端自动测试

- TypeScript 检查和生产构建通过。
- workspace 空态、真实树和错误态。
- 文件 dirty/save/conflict 状态。
- env 默认隐藏、显式 reveal、离开页面清理内容。
- run selector 和 job 状态。
- report/history 读取。

### 17.3 手工视觉验收

- 1440x900 和 1280x800 无横向溢出。
- 1024px explorer 可收起。
- 中文长标题、长路径和长诊断不会破坏布局。
- 键盘焦点可见，跳到主内容可用，icon-only button 有 aria-label。
- env 值不出现在页面 URL、普通网络响应、日志、报告和 localStorage。
- reduced motion 生效。

### 17.4 验证命令

```bash
python3 -m pytest tests/console -q
python3 -m pytest tests -q
python3 -m compileall aitest_kit
npm --prefix console_web test
npm --prefix console_web run build
python3 -m pip wheel . --no-deps --wheel-dir <temporary-wheel-dir>
python3 -m aitest_kit.cli codegen --all --check
```

## 18. 实现顺序

1. FastAPI app、token、active workspace、packaged frontend 和统一错误。
2. workspace snapshot、安全文件接口和显式初始化流程。
3. env 授权、读取、校验和保存。
4. 结构化 job、CLI 子进程和取消。
5. report index/detail。
6. Vue App Shell、workspace、editor、run、report、diagnostics、environment。
7. 后端/前端测试、生产构建和浏览器视觉校准。

## 19. 最终判断

Local Console 是 AITest 确定性测试内核的本地控制面，不是第二套测试框架。它允许用户直接
管理自己的 workspace 与 env，但不把这种用户权限扩散给 Agent、任意命令或远程服务。
Console 与 Pi 通过未来的 AITest 控制面组合，任何一方都不成为另一方的运行前提。
