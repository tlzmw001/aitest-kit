# Local Console Monaco 编辑器迁移 Spec

> 状态：已实现，当前编辑器运行时权威
> 当前权威范围：Local Console 编辑器运行时、主题应用、诊断标记、补全与文档模型生命周期
> 不改变：Python Application Services、Local Web API、workspace 文件语义、env 权限模型与 Vue 工作台结构

## 1. 背景与决策

现有 Local Console 使用 CodeMirror 6。实际试用暴露出两个与编辑器基础交互直接相关的问题：文本双击后的原生选区反馈不稳定，标签关闭按钮的 hover 表面与预期不一致。前者已经进入编辑器底层选区渲染和主题覆盖范围，继续叠加局部 CSS 会增加维护成本。

本阶段将编辑器内核迁移为 `monaco-editor`，其余界面继续使用 Vue 3。目标是直接获得接近 VS Code 的文本选择、光标、撤销栈、语法着色、诊断标记和编辑器交互，同时避免引入完整 VS Code Workbench。

本 Spec 覆盖以下旧约束：

- `local_console_editor_intelligence_spec.md` 中指定 CodeMirror 6 的实现约束，以及 CodeMirror 专属扩展、lint 和光标定位方式。
- `local_console_editor_theme_settings_spec.md` 中 CodeMirror `Compartment`、CodeMirror theme extension 和“不迁移 Monaco”的约束。

旧 Spec 中与后端校验权威、补全内容来源、主题 id、用户设置格式、标签页产品行为有关的约束继续有效。

## 2. 目标与非目标

### 2.1 目标

1. 保持 `CodeEditor.vue` 对父组件的公开接口不变，父视图不感知底层迁移。
2. 双击字段、拖动和键盘选择均使用 Monaco 原生选区，并在三套主题中清晰可见。
3. 支持 Markdown、YAML、Python 和纯文本，保留当前 AITest 配置键补全。
4. 后端诊断继续作为权威结果，并映射为 Monaco markers。
5. `Cmd/Ctrl+S`、外部内容同步、只读模式和诊断跳转继续工作。
6. 在同一编辑器组件内切换标签时，为每个路径保留独立 model、撤销历史和 view state。
7. 主题热切换不销毁 editor 或 model，不丢失内容、选区、滚动位置和撤销历史。
8. 标签关闭按钮 hover 只出现紧凑圆角表面，不铺满标签高度。
9. 构建后的前端仍由 Python wheel 内的静态资源提供，不新增远程 CDN 依赖。

### 2.2 非目标

- 不引入 VS Code Workbench、Electron 或 Tauri。
- 不实现扩展市场、终端、调试器、Git 面板或 VS Code 插件协议。
- 不改变 workspace 文件读写 API、env 编辑授权和安全边界。
- 不为 YAML/Python 资产开发复杂低代码表单。
- 不同时保留 CodeMirror 和 Monaco 两套运行时，也不增加用户可见的编辑器内核开关。
- 不把前端语法检查提升为业务校验权威。

## 3. 稳定公开接口

`CodeEditor.vue` 必须继续接受：

```ts
modelValue: string
path?: string
language?: string
readOnly?: boolean
diagnostics?: EditorDiagnostic[]
theme?: EditorThemeId
```

必须继续发出：

```ts
update:modelValue(value: string)
save()
```

必须继续暴露：

```ts
focusDiagnostic(diagnostic: EditorDiagnostic): void
```

`EditorView.vue` 和 `EnvironmentView.vue` 不直接导入 Monaco API。

## 4. 运行时设计

### 4.1 依赖与 Worker

- 直接依赖固定版本的 `monaco-editor`，不增加 Vue wrapper 或 loader 依赖。
- 使用 Monaco ESM API和 Vite `?worker` 导入配置本地 editor worker。
- Worker 与主 bundle 一起构建到 `aitest_kit/console/web/assets/`，页面运行不访问公网。
- 本阶段不加载 TypeScript/JavaScript、JSON、CSS 或 HTML language worker。

### 4.2 文档 model 与标签切换

数据流：

```text
EditorView active tab
  -> CodeEditor path/modelValue/language
  -> path 对应 Monaco model
  -> editor.setModel(model)
  -> 恢复该 path 的 view state
```

- 有 path 的文档使用稳定的 `aitest:` URI；无 path 的 env 编辑器使用组件级内存 URI。
- 同一 `CodeEditor` 生命周期内，每个 path 对应一个 model。
- 切换 path 前保存旧 model 的 view state；切回时恢复。
- 父组件传入内容与 model 不同时执行外部同步，但不得回发重复的 `update:modelValue`。
- 组件卸载时释放 editor、监听器、补全 provider、view state 和该组件持有的 models。
- path 切换不重建 editor 实例。

### 4.3 语言

前端 language prop 映射固定为：

| prop | Monaco language id |
|---|---|
| `markdown` | `markdown` |
| `yaml` | `yaml` |
| `python` | `python` |
| 其他 | `plaintext` |

语言只负责语法着色和编辑体验。AITest profile、suite、module、target、task 的正确性仍由后端 validation 决定。

### 4.4 补全

- `completion.ts` 保留框架无关的 AITest key catalog 和上下文判断。
- Monaco provider 根据 model URI 识别当前路径。
- 仅在 YAML key 位置提供建议；Markdown 仅在 YAML fenced block 中提供 profile 建议。
- 补全只插入字段名和 `: `，不得臆造 target、module、账号、token 或业务值。
- provider 被组件卸载时必须 dispose，避免热重载或路由切换后重复建议。

### 4.5 诊断

后端 `EditorDiagnostic` 的一基坐标直接转换为 Monaco `IMarkerData`：

- `error` -> `MarkerSeverity.Error`
- `warning` -> `MarkerSeverity.Warning`

坐标必须夹紧到当前 model；空范围至少覆盖一个可见字符位置。marker owner 固定为 `aitest`。切换 model 或更新 diagnostics 后只更新当前文档的 markers。

`focusDiagnostic` 将光标移动到诊断起点，居中显示并聚焦编辑器。

### 4.6 主题

保留已发布的设置值和顺序：

1. `aitest-dark`
2. `vscode-dark-modern`
3. `high-contrast-dark`

`themeCatalog.ts` 继续作为设置 UI 与编辑器的共同主题来源。Monaco 主题从 catalog 注册，至少映射背景、前景、行号、活动行、选区、光标、浮层和诊断颜色。语法 token 颜色沿用 catalog 的语义色。

主题变化调用 Monaco theme API，不创建新 editor，不创建新 model。

### 4.7 基础交互

- 编辑器自适应容器尺寸。
- 关闭 minimap，保留行号、折叠、诊断 glyph 和查找能力。
- `scrollBeyondLastLine` 关闭。
- `Cmd/Ctrl+S` 发出 `save`，不触发浏览器保存页面。
- 只读变化通过 `updateOptions` 生效，不重建 editor。
- 选区完全交给 Monaco 原生渲染，不再用应用层 `::selection` 补丁模拟。

## 5. 标签关闭按钮

关闭按钮仍是独立的语义化 `button`，点击范围保持可用，但 hover 背景由内部 22px × 22px 圆角表面承担。按钮根节点在 hover、active 和 focus 状态下始终透明，避免出现覆盖整列的方形背景。

## 6. 影响文件

计划修改：

- `console_web/package.json`
- `console_web/package-lock.json`
- `console_web/src/components/CodeEditor.vue`
- `console_web/src/components/CodeEditor.test.ts`
- `console_web/src/editor/completion.ts`
- `console_web/src/editor/completion.test.ts`
- `console_web/src/editor/diagnostics.ts`
- `console_web/src/editor/diagnostics.test.ts`
- `console_web/src/editor/theme.ts`
- `console_web/src/editor/theme.test.ts`
- `console_web/src/editor/monacoEnvironment.ts`
- `console_web/src/styles/views.css`
- 两份被覆盖的旧 editor Spec
- `aitest_kit/console/web/` 构建产物

迁移通过后移除 CodeMirror 依赖；不保留未接线的兼容实现。

## 7. 测试与验收

### 7.1 自动化

至少覆盖：

1. path 与 language 映射。
2. AITest 补全 catalog 和 YAML/fenced YAML 上下文。
3. 后端诊断到 Monaco marker 的严重级别和坐标夹紧。
4. 主题注册包含三个稳定 id，选区对比度达标。
5. 切换 theme 不销毁 editor/model，内容不变。
6. 切换 path 复用 editor，并保存和恢复 model/view state。
7. 外部内容同步不产生回声更新。
8. 只读与诊断跳转更新已有 editor。
9. 标签关闭 hover 根节点透明，内部表面尺寸固定。

### 7.2 构建与真实运行

必须通过：

```bash
cd console_web
npm test -- --run
npm run build
```

随后通过本地 `aitest console` 会话验证：

- 页面没有 Monaco worker 或 CSP 控制台错误。
- 打开 YAML、Markdown、Python、env 文本均可编辑。
- 双击字段出现清晰选区，输入后可替换选中内容。
- 多标签切换后内容、光标、滚动位置和撤销历史仍在。
- 切换三套主题不丢内容。
- validation diagnostics 可显示并跳转。
- 关闭按钮 hover 为紧凑圆角表面。

记录构建产物大小。体积增加可以接受，但不得因为误引入完整 VS Code Workbench、非目标 language workers 或重复编辑器运行时而异常膨胀。

## 8. Spike 决策门槛与回退

满足以下条件即完成迁移：

- 自动化测试和构建全绿。
- 静态产物完全本地化。
- 真实页面无 worker 错误。
- 现有保存、补全、诊断、主题和多标签行为无回归。
- 原生选区和关闭按钮问题通过可见验收。

若 Monaco 无法在当前 Vite/Python 静态分发链路内稳定加载，或必须引入完整 Workbench 才能满足现有功能，则回退本次 Monaco 代码与依赖变更，保留 Vue 工作台和已确认的产品行为，另行评审编辑器方案。回退不得修改后端 API 或 workspace 数据。

## 9. 实现核验记录

- 固定依赖：`monaco-editor@0.56.0`；其锁定的 `dompurify@3.4.8` 通过 npm override 提升为已修复的 `3.4.14`，不改变 Monaco API。
- CodeMirror 与 Lezer 运行时依赖已移除。
- 生产构建只包含本地 editor worker，以及 Markdown、YAML、Python 的轻量语言定义 chunk；没有 TypeScript、JSON、CSS 或 HTML worker。
- Monaco 主 chunk：3,811.93 kB，gzip 974.68 kB；editor worker：300.37 kB。
- Vitest 覆盖 model/view state、主题热切换、外部同步无回声、只读更新、marker 映射、补全上下文和父视图持续挂载。
- 本地 Python Console 真实页面已验证：无 Worker/控制台错误；双击选区可见；打开两个标签后仍只有一个 Monaco editor 实例；切回标签后选区恢复；三套主题热切换不改变内容；关闭按钮根节点保持透明，hover 表面为 22px × 22px。
