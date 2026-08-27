# AITest Local Console Editor Theme Settings Spec

状态：已实现，当前实现权威
依赖：`docs/specs/local_console_editor_intelligence_spec.md`
范围：编辑器配色预设、偏好持久化、CodeMirror 运行时主题切换

## 1. 目标

在保持 Local Console 冷石墨深色外壳不变的前提下，让用户从设置中选择更适合自己的编辑器配色：

1. 提供三套经过校准的深色编辑器预设。
2. 选择后立即应用，不刷新页面，不重新打开文件。
3. 切换主题时保留内容、光标、选区、撤销历史和诊断状态。
4. 将主题与现有打开文件方式一起持久化，并兼容旧版偏好数据。
5. 设置入口保持紧凑、克制，不扩张为任意颜色编辑器。

## 2. 锁定决策

### 2.1 只开放编辑器配色

- Console 外壳继续使用当前冷石墨深色 token。
- 不增加全局浅色主题，不增加跟随系统模式。
- 不允许用户逐项编辑十六进制颜色。
- AITest 信号橙继续只表达操作、选中和流水线状态，不作为代码 token 色。

### 2.2 三套固定预设

公开 theme id 固定为：

```text
aitest-dark
vscode-dark-modern
high-contrast-dark
```

预设名称与定位：

| theme id | 界面名称 | 定位 |
|---|---|---|
| `aitest-dark` | AITest 深色 | 当前默认值，冷静的中性石墨背景和熟悉的 IDE 语法色 |
| `vscode-dark-modern` | VS Code Dark Modern | 更接近 VS Code 的深灰表面与蓝紫语法关系 |
| `high-contrast-dark` | 高对比深色 | 更深背景、更亮正文、注释、行号与语法色，优先解决暗色难辨认 |

所有主语法前景色与编辑区背景的对比度必须不低于 4.5:1。selection 颜色不得复用为语法前景色。

### 2.3 CodeMirror 动态重配置

- 使用 `@codemirror/state` 的 `Compartment` 管理主题扩展。
- `CodeEditor` 接收 theme id，不直接读取 Pinia store。
- theme id 变化时只 dispatch `Compartment.reconfigure()`。
- 主题变化不得调用 `EditorView.destroy()` 或重新创建 `EditorState`。
- 未知 theme id 统一回退到 `aitest-dark`。

### 2.4 偏好是一个完整对象

localStorage key 继续使用：

```text
aitest-console-preferences
```

持久化结构：

```json
{
  "editorOpenMode": "tabs",
  "editorTheme": "aitest-dark"
}
```

兼容规则：

- 没有存储值时使用 `tabs` 和 `aitest-dark`。
- 旧数据只有 `editorOpenMode` 时保留该值并补默认主题。
- 未知或非法字段只回退对应字段，不清空其他合法偏好。
- 任一偏好变化时写入完整对象，禁止两个 watcher 互相覆盖。
- 数据仍只保存在当前浏览器本地，不写 workspace 文件，不加入 Git。

## 3. 主题结构

`console_web/src/editor/themeCatalog.ts` 提供 theme id、公开 metadata 和 palette：

```ts
type EditorThemeId = 'aitest-dark' | 'vscode-dark-modern' | 'high-contrast-dark'

interface EditorThemeDefinition {
  id: EditorThemeId
  label: string
  description: string
  palette: EditorPalette
}
```

`console_web/src/editor/theme.ts` 只负责把 catalog 转换为 CodeMirror `Extension`。这样设置面板和偏好 store 不会把 CodeMirror 内核提前打入主 bundle。

主题 catalog 是唯一前端主题来源。设置面板、CodeEditor 和测试从同一 catalog 读取，不分别维护名称和 id。

每套 palette 至少定义：

- background
- gutter
- foreground
- muted
- selection
- tooltip 和 active line 等表面色
- keyword、string、number、function、type、property、comment、control
- error 和 warning

公共工厂负责生成 `EditorView.theme` 与 `HighlightStyle`，避免三套主题复制完整 CodeMirror 配置。

## 4. 设置界面

在现有“编辑器”设置区中保留“打开文件的方式”，并在其后增加“编辑器配色”：

- 使用 radio group，键盘和读屏语义与现有设置一致。
- 每个选项显示名称、短说明和一段小型语法色板。
- 色板只展示 keyword、property、string、function 四个代表色。
- 当前选项使用 AITest 信号橙描边与单选标记。
- 不使用渐变、玻璃效果、大面积彩色背景或装饰动画。
- 设置面板内容超过可视高度时内部滚动，不遮挡关闭按钮。
- 375px 宽度下仍可完整选择三个主题，交互目标不小于 40px。

主题选择立即生效，不设置额外的“保存设置”按钮。

## 5. 数据流

```text
AppShell 设置项
  -> preferences.editorTheme
  -> watch 完整 preferences 对象
  -> localStorage

EditorView
  -> :theme="preferences.editorTheme"
  -> CodeEditor
  -> theme Compartment.reconfigure(extension)
```

设置面板不直接操作 CodeMirror 实例。CodeEditor 不知道设置面板存在，只响应稳定的 theme prop。

## 6. 影响文件

Spec：

- `docs/specs/local_console_editor_theme_settings_spec.md`

前端：

- `console_web/src/stores/preferences.ts`
- `console_web/src/editor/themeCatalog.ts`
- `console_web/src/editor/theme.ts`
- `console_web/src/components/AppShell.vue`
- `console_web/src/components/CodeEditor.vue`
- `console_web/src/views/EditorView.vue`
- `console_web/src/styles/base.css`
- 对应 Vitest 测试
- `aitest_kit/console/web/` 生产构建资产

不修改后端 API、workspace 配置、env 文件或测试资产格式。

## 7. 非目标

- 全局 Console 换肤。
- 浅色主题或跟随操作系统。
- Monaco 或 VS Code 扩展主题导入。
- TextMate theme JSON 导入。
- 用户自定义颜色、字体、字号、行高或字体连字。
- 将主题写入 `aitest.yaml`、workspace 或仓库。
- 跨浏览器、跨设备同步偏好。

## 8. 测试要求

偏好：

- 默认偏好正确。
- 旧版只有 `editorOpenMode` 的数据可以迁移。
- 非法主题只回退主题字段。
- 修改任一字段都会保存完整偏好对象。

主题：

- 三个 theme id 均可解析。
- 未知 id 回退到默认主题。
- 每套主语法色都达到 4.5:1 对比度。
- selection 不出现在 syntax palette 中。

交互：

- 设置面板展示三个主题并更新偏好。
- `EditorView` 将当前主题传给 `CodeEditor`。
- CodeEditor 切换 theme prop 时不销毁编辑器实例。
- 切换后编辑内容保持不变。

## 9. 验收标准

- 用户可以在设置中选择三套编辑器深色配色。
- 主题即时变化，刷新页面后仍保留。
- 旧版多标签偏好不会因升级而丢失。
- 切换主题不丢内容、光标、选区、撤销历史或诊断。
- 高对比主题中的普通文本、行号、注释和语法色明显可辨。
- 设置面板符合现有 `4/6/10/pill` 半径和冷石墨表面体系。
- 桌面与 375px 宽度均无设置项遮挡或页面横向溢出。
- Vue 测试、production build、Python 测试、`compileall` 和 `git diff --check` 全部通过。
