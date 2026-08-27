# AITest Local Console Asset Management Spec

状态：Phase 1.1 实现权威
依赖：`docs/specs/local_console_mvp_spec.md`
范围：本地目录选择，以及 target、module、suite、task 的基础资产管理

## 1. 目标

在不改变 Local Console 本地优先、真实文件为权威、Python 负责业务语义的前提下，补齐首版可用的工作空间入口和测试资产管理能力：

1. 浏览本机目录并选择要打开或初始化的 workspace，同时保留手工输入绝对路径。
2. 创建、查看、编辑、删除 target、module、suite 和 task。
3. 以 suite 为最小结构化用例管理单位。
4. 删除采用 workspace 内可恢复回收站，避免直接永久删除用户资产。

本 spec 仅覆盖上述增量。未被本 spec 改写的 Console 行为继续以 `local_console_mvp_spec.md` 为准。

## 2. 锁定决策

### 2.1 资产和执行边界

- Markdown 用例仍是源数据，generated pytest 仍是派生产物。
- Vue 不拼接 YAML/Python 模板，不直接操作文件系统；所有创建、删除、注册和恢复语义由 Python Application Service 执行。
- 现有文件编辑器承担 update：用户修改配置、Markdown、profile、fixture 或 Harness 后保存。
- 保存后前端重新加载 workspace 快照，使合法的结构变化及时反映在资源树中。
- 不提供 identity rename。需要更改标识时，采用创建新资产、人工迁移、删除旧资产的显式流程。

### 2.2 Suite 是最小用例管理单位

- 创建 suite 固定生成：`suite.yaml`、`cases.md`、`profile_{suite}_suite.md`。
- `cases.md` 只包含 suite 标题和编辑提示，不生成假用例或假 TC-ID。
- 不提供 case 级新建、删除、定位删除、profile 联动清理或结构化表单。
- 用户需要新增、修改或删除某个 case 时，直接编辑 suite 对应 Markdown 文件并保存。
- 现有 case 浏览、单 case 选择和运行能力保持不变。

### 2.3 本地目录选择

- 使用后端目录浏览 API，而不是浏览器 `showDirectoryPicker()`。后者返回浏览器目录句柄，不能可靠提供本地 Python 服务需要的绝对路径。
- API 只返回目录名称、绝对路径、父目录和是否已初始化，不读取或返回普通文件内容。
- 目录路径使用 `expanduser + resolve` 规范化；不存在、非目录或不可读时返回结构化错误。
- 目录选择器默认从当前 workspace 父目录开始；尚未打开 workspace 时从当前用户目录开始。
- 手工路径输入始终保留，目录浏览是辅助入口。

## 3. 创建语义

target 和 module 名称必须是非关键字 Python 标识符 `[A-Za-z_][A-Za-z0-9_]*`，因为 canonical fixture 文件需要形成可导入 Python module；suite 和 task 允许 `[A-Za-z0-9_-]+`。空白、路径分隔符、`.`、`..` 和重名均拒绝。所有写入先检查目标不存在，写完后用现有 registry loader 重新加载；加载产生 error 级诊断或写入失败时回滚本次新建目录/文件。

### 3.1 Target

输入：`name`、可选 `source_root`。

创建 `target.yaml`、target 的 `modules/` 与 `helpers/`，以及该 target 的 suites、generated、reports 目录。`target.yaml` 显式写出 canonical defaults。`source_root` 只记录用户输入路径，不创建或修改待测系统目录。

### 3.2 Module

输入：`target`、`name`、`module_type`。

前置：target 必须存在，`module_type` 必须来自当前 `aitest.yaml.codegen.module_types`。

创建 canonical module package：`__init__.py`、`module.yaml`、`profile.md`、`fixture.py`、`harness.py`。初始 Harness 只提供真实可执行的生命周期骨架 `close()`；fixture 公开 `setup_{module}` 并 yield Harness。不得伪造业务调用能力、响应或测试数据。

### 3.3 Suite

输入：`target`、`module`、`name`、`register`，其中 `register` 默认 true。

前置：target/module 必须存在且 canonical module 资产可加载。创建 `suite.yaml`、`cases.md`、`profile_{suite}_suite.md`。`suite.yaml.case_files` 固定为相对路径 `cases.md`。profile 写入最小合法骨架，不写 case 绑定规则。`register=true` 时同步写入 module 的 `registered_suites`。

### 3.4 Task

输入：`name`、可选 `description`、至少一个已存在 suite manifest。创建 `test_workspace/tasks/{task}.yaml`，suite 路径相对于 task 文件目录保存。Task 不自动发现 suite，不写 env 值。

## 4. 删除与恢复语义

### 4.1 删除预览

删除必须先请求 preview。preview 返回资产身份、将移动的源路径、会修改的 registry 文件、阻断原因和可恢复说明。前端展示结果并要求用户再次确认。

阻断规则：

- target 下仍有 module 或 suite时禁止删除 target。
- module 下仍绑定或拥有 suite 时禁止删除 module。
- suite 被任意 task 引用时禁止删除 suite。
- 资产不存在、身份与 manifest 内容不一致或 workspace 当前存在运行中 job 时禁止删除。
- 删除 suite 时自动从所属 module 的 `registered_suites` 移除；不级联删除 task。

### 4.2 回收站

- 删除不是永久删除，而是把受管源资产移动到 `.aitest/trash/{entry_id}/assets/` 下的原相对路径。
- 对删除过程修改的 registry 文件，在 `.aitest/trash/{entry_id}/backups/` 保存删除前副本。
- `manifest.json` 记录 entry id、时间、kind、identity、移动路径、修改文件和修改后 sha256，不记录敏感内容。
- reports、results 和 generated 始终保留。
- 恢复前要求原目标路径不存在；若曾修改的 registry 文件已在删除后再次编辑，sha256 冲突会阻止恢复。
- 恢复成功后删除对应 trash entry；不提供 Console 内永久清空回收站。

## 5. HTTP API

所有 API 继续要求本地 Console session token。

- `GET /api/directories?path=<absolute-or-~>`
- `GET /api/assets/options`（读取当前 workspace 可用的 module_type）
- `POST /api/assets/targets`
- `POST /api/assets/modules`
- `POST /api/assets/suites`
- `POST /api/assets/tasks`
- `POST /api/assets/delete-preview`
- `POST /api/assets/delete`
- `GET /api/trash`
- `POST /api/trash/{entry_id}/restore`

创建和删除成功返回更新后的 `WorkspaceSnapshot`。删除请求携带 `confirmed: true`，且只能按结构化资产身份删除，不能传任意文件路径。

目录响应包含当前绝对路径、父目录、初始化状态，以及直接子目录的名称、路径和初始化状态。目录 API 不返回文件内容。

## 6. 前端交互

### 6.1 Workspace 打开

- 路径输入框旁增加“浏览目录”。
- 目录选择器以内嵌面板展示 breadcrumb、返回上级、子目录列表、初始化状态和“选择此目录”。
- 选择后只回填路径；真正打开仍由用户点击“打开”。
- 未初始化目录继续沿用现有“初始化并打开”二次确认。

### 6.2 Explorer 资产管理

- Explorer 顶部提供单一 `+` 入口，打开紧凑的资产创建面板。
- 创建类型根据层级呈现 target/module/suite/task，并只显示必要字段。
- target 配置文件和 task 文件必须在 Explorer 可见、可打开编辑。
- 每个 target/module/suite/task 提供删除动作；删除前展示 preview 和阻断原因。
- 设置页不承载资产 CRUD；编辑器多标签仍由已有设置管理。
- 成功创建 suite 后自动打开 `cases.md`；其他资产打开其主要配置文件。
- 错误使用结构化 code + message 原样展示，不静默忽略。

视觉继续沿用当前冷石墨高密度工作台、信号橙和 VS Code 风格编辑区，不引入新的 UI 依赖。

## 7. 错误分类

新增错误码：`DIRECTORY_INVALID`、`DIRECTORY_READ_FAILED`、`ASSET_NAME_INVALID`、`ASSET_ALREADY_EXISTS`、`ASSET_NOT_FOUND`、`ASSET_PARENT_NOT_FOUND`、`MODULE_TYPE_INVALID`、`ASSET_VALIDATION_FAILED`、`ASSET_CREATE_FAILED`、`ASSET_DELETE_BLOCKED`、`ASSET_DELETE_CONFIRMATION_REQUIRED`、`ASSET_DELETE_FAILED`、`TRASH_ENTRY_NOT_FOUND`、`TRASH_RESTORE_CONFLICT`、`TRASH_RESTORE_FAILED`。

## 8. 验收标准

- 目录 API 只列目录，能识别初始化状态，并对非法目录返回结构化错误。
- 四类资产创建后可被现有 loader 和 workspace snapshot 读取。
- suite 创建生成三件套，默认注册到 module，且不生成任何假 case。
- task 创建只接受真实 suite。
- 四类资产删除阻断规则有测试；suite 删除能取消注册、恢复并检测 registry 冲突。
- 路径遍历、重名和未确认删除均被拒绝。
- 用户可以从 UI 浏览目录，创建四类资产，打开 target/task 配置，并完成预览后删除。
- suite 内不出现 case 级新增或删除按钮；空 workspace 不显示示例数据。
- 现有 session、文件保存、env、job、report、case 浏览与运行不回归。
- Python 测试、Vue 单元测试和 Vue production build 全部通过。

## 9. 非目标

- Electron、Tauri 或原生安装器。
- 浏览器持久化目录句柄。
- case 级结构化 CRUD。
- identity rename。
- target 级联删除、task 自动改写或跨资产批量迁移。
- 为每个 YAML/Python 字段开发低代码表单。
- 永久清空回收站或操作系统 Trash 集成。
- 自动删除 reports、results、generated 或外部源文件。
