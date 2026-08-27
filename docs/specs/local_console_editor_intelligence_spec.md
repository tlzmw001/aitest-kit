# AITest Local Console Editor Intelligence Spec

状态：已批准，进入实现
依赖：`docs/specs/local_console_mvp_spec.md`、`docs/specs/local_console_asset_management_spec.md`
范围：CodeMirror 编辑体验、保存前诊断、AITest 配置提示、Console 视觉收敛

## 1. 目标

在不把 Local Console 扩张为浏览器 IDE 的前提下，补齐首版编辑器的可读性和基础智能：

1. 使用高对比度的深色语法主题，解决 YAML、Markdown、Python 深蓝文本难以辨认的问题。
2. 对未保存内容执行只读、无副作用的语法与基础结构校验。
3. 为 AITest 常见 YAML 和 Profile 字段提供上下文提示。
4. 在编辑器内和 Problems 面板显示同一组诊断，并支持定位到对应行。
5. 收敛现有 Console 的色彩、文字层级和交互状态，使整体更克制、精确、耐看。

本 spec 只覆盖编辑体验和视觉一致性。资产管理、env 权限、确定性执行与报告语义继续以前述 spec 为权威。

## 2. 锁定决策

### 2.1 保留 CodeMirror 6

- Phase 1 继续使用 CodeMirror 6，不迁移 Monaco。
- 当前问题的根因是深色外壳叠加 CodeMirror 面向浅色背景的默认 HighlightStyle，不是编辑器内核能力不足。
- Monaco 的 diff、models、workers 和 IDE 级语言服务当前不是首版必要能力，其体积和生命周期复杂度不进入本阶段。
- 当产品同时出现至少三项 IDE 级刚需时再复核 Monaco：完整 Python LSP、definition/reference/rename/code action、语义 token、内置 diff、独立多 model undo/view state、outline/sticky scroll。

### 2.2 Python 是校验权威

- Vue 和 CodeMirror 只负责编辑交互、字段提示与诊断渲染。
- 未保存内容通过结构化 API 发送给本地 Python Console 做只读校验。
- API 不写磁盘、不执行 workspace 代码、不 import fixture/Harness/helper、不启动 codegen 或 pytest。
- 编辑器实时诊断是快速反馈，不替代 `profile validation`、`codegen --check` 和 `aitest run` 的确定性门禁。

### 2.3 提示不是第二份 schema 权威

- 前端提示目录只包含稳定、公开且高频的 AITest 字段和简短说明。
- 提示可以减少拼写错误，但不能据此判定文件有效。
- 真正的字段合法性由后端校验和现有 loader/profile gate 决定。
- 不引入低代码表单，也不自动重写用户 YAML、Markdown 或 Python。

## 3. 编辑器主题

主题基于 VS Code Dark Modern 的可读性逻辑，但保留 AITest 的冷石墨外壳和信号橙。

### 3.1 语法色

| 角色 | 颜色 | 深色背景上的用途 |
|---|---|---|
| 主文本 | `#D4D4D4` | 普通文本与标点 |
| keyword | `#C586C0` | Python 关键字 |
| string | `#CE9178` | YAML/Python 字符串 |
| number/bool | `#B5CEA8` | 数字、布尔值、常量 |
| function | `#DCDCAA` | 函数和可调用项 |
| type/class | `#4EC9B0` | 类型和类 |
| property/variable | `#9CDCFE` | YAML key、属性和变量 |
| comment | `#6A9955` | 注释 |
| control blue | `#569CD6` | link、label 等辅助语义 |

背景固定为 `#1E1E1E`，主语法色与背景的目标对比度不低于 4.5:1。选区 `#264F78` 只表示 selection，不作为语法色。AITest 信号橙不参与代码 token 配色，避免操作语义和语法语义混淆。

### 3.2 编辑器表面

- 行号区使用比编辑区更低一级的石墨色。
- 当前行仅做轻微亮度提升，不使用彩色整行背景。
- diagnostic error/warning 使用波浪下划线与行内提示，不覆盖 token 前景色。
- autocomplete、tooltip 和 lint tooltip 使用同一套石墨表面、细边框和固定圆角。
- 编辑区继续使用等宽字体栈，不下载网络字体。

## 4. 实时诊断

### 4.1 API

新增：

```text
POST /api/editor/validate
```

请求：

```json
{
  "path": "test_workspace/suites/demo/smoke/suite.yaml",
  "content": "target: demo\n..."
}
```

响应：

```json
{
  "diagnostics": [
    {
      "severity": "error",
      "code": "YAML_SYNTAX",
      "message": "...",
      "line": 4,
      "column": 3,
      "end_line": 4,
      "end_column": 4,
      "source": "yaml"
    }
  ]
}
```

约束：

- `path` 必须通过现有 workspace 内路径和普通文件访问策略，env 文件仍被拒绝。
- 请求体内容上限为 2 MiB，超限返回结构化错误。
- 所有位置使用 1-based line/column，前端转换为 CodeMirror offset。
- 诊断按 error、warning、行号稳定排序。
- API 返回零条诊断代表当前快速校验通过，不代表完整执行门禁通过。

### 4.2 校验范围

YAML：

- 使用后端现有 PyYAML 做语法校验。
- AITest 配置根节点必须是 mapping。
- `suite.yaml` 检查 `target/module/suite/case_files`、`case_files` 类型，以及禁止出现的生成和执行字段。
- `target.yaml` 检查 `target`。
- `module.yaml` 检查 `target/module/module_type`，并校验当前 workspace 已声明的 module type。
- task YAML 检查 `schema_version/name/units` 的基础类型。
- `aitest.yaml` 与 `capture.yaml` 只做语法和 mapping root 检查，完整语义继续由现有 loader/doctor 负责。

Markdown：

- 普通用例 Markdown 检查未闭合 fenced code block。
- YAML fenced block使用 PyYAML 校验语法。
- Profile Markdown 的 fenced block 外结构不做低代码限制，YAML fenced block 额外检查已知顶层字段和基础类型。
- 不尝试在实时请求中执行完整 suite profile gate，因为完整 gate 依赖磁盘上多个关联文件；保存后仍使用现有 Profile 校验操作。

Python：

- 使用 `ast.parse` 做语法校验。
- 不 import、不执行、不做类型检查和 LSP 分析。

其他文本：返回空诊断。

### 4.3 请求与竞态

- 内容或路径变化后等待 350ms 再校验。
- 新请求发出前取消旧请求；旧响应不得覆盖新内容的诊断。
- 文件读取中、没有打开文件或文件超过限制时不发请求。
- 网络或 API 失败作为编辑器级错误展示，不伪装成文件语法错误。

## 5. Completion

CodeMirror 使用官方 autocomplete 扩展。建议项按文件上下文提供：

- `suite.yaml`：`target`、`module`、`suite`、`case_files`、`knowledge_refs`。
- `target.yaml`：`target`、`source_root`、`docs`、`knowledge_refs`、`defaults` 及目录字段。
- `module.yaml`：`target`、`module`、`module_type`、`knowledge_refs`、`registered_suites`。
- task YAML：`schema_version`、`name`、`description`、`defaults`、`units` 和 unit selector 字段。
- Profile YAML fenced block：`profile_scope`、`parent_module`、`parent_profile`、`suite`、`knowledge_refs`、`assertion_rules`、`structured_assertions`、`variables`、`requests`、`case_bodies`、`case_flows`。

提示只在 YAML 行首或缩进后的 key 位置出现。插入内容保持普通 YAML 文本，不自动填入假 target、module、suite、case id 或密钥值。

## 6. Problems 面板

- 移除当前不可操作的 Validation 和 Output 假标签，只保留真实 Problems 入口和实时校验状态。
- 面板显示 error/warning 数量、code、message、source、line/column。
- 点击诊断将焦点移到对应行并滚动到可见区域。
- 无问题时显示“快速校验未发现问题”，并明确完整门禁仍需保存后运行。
- 未保存时提示“当前诊断基于编辑器内容”；已保存时提示“内容与磁盘版本一致”。
- API 错误与文件诊断分开展示，避免把 Console/网络错误误判为用户文件错误。

## 7. 视觉收敛

视觉主题：冷静、精确、克制。界面是本地测试工程控制台，不是营销页，也不是装饰型 dashboard。

### 7.1 保留

- 冷石墨多级表面、细分隔线、紧凑工作台布局。
- AITest 信号橙用于主操作、选中态和当前流水线位置。
- owner provenance、运行状态和错误分类使用语义色。
- 无图片、无渐变、无玻璃效果、无装饰性阴影。

### 7.2 收敛

- 提高辅助文字、路径、行号和小徽标的最低对比度。
- 同一层级只保留一个视觉强调，避免标题、橙色按钮和高亮边框同时争抢注意力。
- 编辑器 inspector 的“进入确定性执行”改为次级操作样式，主操作仍留给用户当前页面的核心任务。
- 统一按钮、输入、面板和 tooltip 的半径为现有 `4/6/10/pill` 命名尺度。
- 所有 icon-only 控件保留 aria-label 和清晰 focus-visible。
- 窄屏不强行保留 inspector；Problems 面板和标签栏允许横向或垂直收缩，不遮挡代码。

## 8. 影响文件

后端：

- `aitest_kit/console/editor_validation.py`
- `aitest_kit/console/app.py`
- `tests/console/test_console_editor_validation.py`

前端：

- `console_web/src/editor/theme.ts`
- `console_web/src/editor/completion.ts`
- `console_web/src/editor/diagnostics.ts`
- `console_web/src/components/CodeEditor.vue`
- `console_web/src/views/EditorView.vue`
- `console_web/src/api/client.ts`
- `console_web/src/types.ts`
- `console_web/src/styles/base.css`
- `console_web/src/styles/views.css`
- 对应 Vitest 测试与生产构建资产

CodeMirror 的 `language`、`autocomplete`、`lint` 和 `@lezer/highlight` 已由现有 CodeMirror 包间接安装。实现会把直接 import 的包以当前锁文件版本声明为直接依赖，不升级版本，不引入新的编辑器框架。

## 9. 非目标

- Monaco 迁移。
- Python LSP、类型检查、definition/reference/rename/code action。
- 完整 YAML language server 或任意 JSON Schema 引擎。
- 格式化、自动修复、自动保存。
- diff editor、minimap、outline、sticky scroll。
- 浏览器内运行 fixture、Harness、helper、codegen 或 pytest。
- case 级结构化增删改查。
- 低代码 YAML/Profile 表单。

## 10. 验收标准

- Markdown、YAML、Python 的关键 token 在编辑器背景上达到可读对比度，深蓝 token 不再出现。
- 修改内容后 350ms 左右可看到快速诊断，旧响应不会覆盖新内容。
- YAML 和 Python 语法错误同时出现在编辑器和 Problems 面板，点击可定位。
- Profile/YAML key 在合法 key 位置出现 AITest 提示，不插入假业务值。
- env 文件仍不能通过普通 editor validation API 读取或校验。
- Problems 面板不再出现不可用标签。
- 工作台、编辑器、运行、报告、诊断、环境页在桌面宽度保持统一视觉层级。
- 900px 以下布局无关键操作遮挡；375px 宽度可完成导航、打开文件和查看诊断。
- Python 测试、Vue 测试、Vue production build、`compileall` 和 `git diff --check` 全部通过。
