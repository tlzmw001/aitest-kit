# AITest Local Console 前端平台能力 Spec

> 状态：已实现，当前实现权威
> 日期：2026-08-27
> 依赖：`local_console_mvp_spec.md`、`local_console_monaco_editor_spike_spec.md`、`local_console_editor_intelligence_spec.md`
> 不改变：Python Application Services、Local Web API、workspace 文件语义、env 权限模型和确定性执行链路

## 1. 背景与决策

Local Console 已经具备 Vue 3 应用壳、Vue Router 页面路由、Pinia 本地状态、Monaco 编辑器和 Vitest 测试。本阶段不重写现有界面，而是在已确认的冷石墨、紧凑工程工作台方向上补齐以下平台能力：

1. 用 Reka UI 接管需要焦点管理、键盘导航和拖拽语义的复杂交互。
2. 用 `markdown-it` 解析报告 Markdown，并在写入 DOM 前使用 DOMPurify 收窄和清洗输出。
3. 让 Monaco 同时承担源码编辑、只读 JSON 阅读和文件冲突 Diff。
4. 用 Playwright 覆盖真实 Chromium 中的关键用户路径和小范围视觉回归。
5. 修复标签关闭后 Monaco model 和 view state 继续驻留的生命周期债务。

Vue Router、Pinia、Monaco 和 Vitest 继续沿用现有实现，不引入第二套路由、状态、编辑器或单测框架。

## 2. 目标与非目标

### 2.1 目标

- Asset Manager 对话框使用 Reka Dialog，获得焦点锁定、Escape 关闭、恢复焦点和语义化标题。
- 报告的 `report.md`、`result.json` 使用 Reka Tabs，支持方向键和 Home/End 键切换。
- 编辑器与 Inspector 使用 Reka Splitter，可拖拽调整宽度并在本地持久化布局。
- `report.md` 以安全、可读的文档样式预览，不执行原始 HTML，不加载 Markdown 图片。
- `result.json` 使用只读 Monaco JSON 视图，不再使用普通 `pre`。
- 文件保存遇到 `FILE_CONFLICT` 时读取最新磁盘版本，并用只读 Monaco Diff 比较“磁盘版本”和“当前编辑内容”。
- 用户关闭或复用标签时，释放该路径的 Monaco model、markers、undo stack 和 view state。
- Playwright 验证本地会话、报告预览、JSON 标签和编辑器标签关闭交互，并保存一个稳定的小范围视觉基线。

### 2.2 非目标

- 不引入完整 VS Code Workbench、Electron、Tauri 或浏览器内终端。
- 不把 Reka UI 当成视觉主题，不整体改造成通用管理后台组件风格。
- 不迁移原生 `select`、普通按钮和简单表单；只有复杂交互使用 primitives。
- 不实现 Markdown 所见即所得、富文本编辑或任意 HTML 渲染。
- 不允许 Diff 直接覆盖磁盘版本；用户只能继续编辑或明确载入磁盘版本。
- 不实现任意两个文件、任意两次报告之间的通用比较。
- 不引入 TanStack Query、TanStack Table 或 TanStack Virtual。
- 不修改 Console 后端 API，不新增数据库和服务端状态缓存。

## 3. 固定依赖与兼容性

2026-08-27 重新核验 npm metadata 后固定：

| 依赖 | 版本 | 用途 |
|---|---:|---|
| `reka-ui` | `2.10.4` | Dialog、Tabs、Splitter primitives |
| `markdown-it` | `15.0.0` | CommonMark 风格解析 |
| `dompurify` | `3.4.14` | HTML allow-list 清洗 |
| `@types/markdown-it` | `14.2.0` | TypeScript 类型 |
| `@playwright/test` | `1.62.1` | Chromium E2E 与截图断言 |
| `jsdom` | `29.1.1` | 仅用于 Vitest 中执行 DOMPurify 的真实 DOM 安全测试 |

Reka UI 要求 Vue `>=3.4`，当前 Vue `3.5.41` 满足。Playwright 要求 Node `>=20`，当前项目 engines `>=22.18.0` 满足。依赖使用精确版本，不使用 `^` 或 `~`。

Reka UI 自身可能通过传递依赖使用 TanStack Virtual。AITest 不直接导入、配置或依赖该 API；这不构成产品层启用 TanStack Virtual。

## 4. 视觉与交互契约

### 4.1 视觉方向

- 主题关键词：克制、精确、耐久。
- 保留现有 OKLCH 冷石墨表面、信号橙、`4/6/10/pill` 半径尺度和 Avenir Next/PingFang UI 字体栈。
- Reka primitives 使用现有 class 和 CSS token，不引入 Tailwind、CSS Modules 或第二套图标库。
- 层级继续依赖背景亮度步进和细分隔线；只在对话框使用现有深层阴影。
- 交互动画只使用 opacity/transform，遵守 `prefers-reduced-motion`。

### 4.2 可访问性

- Dialog 必须有可感知标题，打开后焦点进入，关闭后回到触发控件。
- Tabs 使用 `tablist/tab/tabpanel` 语义和完整键盘导航。
- Splitter handle 可聚焦，提供清晰 focus-visible 和足够命中区域。
- 图标按钮保留 `aria-label`，不以 `div` 模拟按钮。
- 375px 窄屏继续隐藏 Inspector，Splitter handle 同时隐藏，不阻挡源码编辑。

## 5. Reka UI 接入边界

### 5.1 Dialog

`AssetManager.vue` 使用以下 primitives：

```text
DialogRoot
  -> DialogPortal
     -> DialogOverlay
        -> DialogContent
           -> DialogTitle
           -> DialogClose
```

现有 `openCreate/openDelete/openTrash` 公开方法和业务状态不变。Dialog 的 open 状态仍由 `mode` 派生；关闭时只清空 `mode`，不额外写 workspace。

文件冲突使用独立 Dialog，内容为 Diff、说明和明确操作。载入磁盘版本会丢弃当前未保存内容，因此按钮必须写明结果，并只在该 Dialog 内提供。

### 5.2 Tabs

`ReportsView.vue` 使用受控 `TabsRoot`。两个固定值为：

- `report`：安全 Markdown 预览。
- `json`：只读 Monaco JSON。

切换报告时保留当前 tab。没有 `report.md` 时显示真实空状态，不构造示例内容。

### 5.3 Splitter

`EditorView.vue` 将源码区与 Inspector 放入水平 Splitter：

- 源码区默认约 76%，最小 55%。
- Inspector 默认约 24%，最小 18%，最大 40%。
- 使用稳定 `autoSaveId` 写入浏览器 localStorage。
- 1024px 以下隐藏 Inspector 和 resize handle，源码区占满剩余宽度。

Problems 面板高度本阶段保持固定，不增加第二层嵌套 splitter。

## 6. 安全 Markdown 预览

数据流固定为：

```text
report.md 原文
  -> markdown-it({ html: false, linkify: false, typographer: false })
  -> DOMPurify.sanitize(严格 allow-list)
  -> Vue v-html sink
```

约束：

- 原始 HTML 永远不交给 Markdown parser 执行。
- allow-list 只包含标题、段落、列表、表格、引用、链接、代码、强调和分隔线等文档标签。
- 允许的属性只包含链接的 `href/title/target/rel` 与 fenced code 的 `class`。
- 不允许 `img`、`svg`、`style`、`iframe`、表单控件、事件属性和未知协议。
- 外部链接由 renderer 在清洗前添加 `target="_blank"` 和 `rel="noopener noreferrer"`；不得在 DOMPurify 之后再修改 HTML 字符串。
- 空 Markdown 显示调用方提供的真实空状态。

## 7. Monaco 三种职责

### 7.1 源码编辑

沿用 `CodeEditor.vue`。新增公开方法：

```ts
disposeDocument(path: string): void
reloadDocument(): void
```

关闭标签或 reuse 模式替换干净标签前，`EditorView` 调用该方法。被释放文档必须清空 `aitest` markers、dispose model 并删除 view state。当前 model 被释放时先从 editor detach，随后由新的 active path 接管。

### 7.2 只读 JSON

- Monaco environment 增加 JSON language 和本地 JSON worker。
- `CodeEditor` 接受 `language="json"` 并以 `readOnly` 模式显示格式化后的 `result.json`。
- JSON worker 与静态 bundle 一同进入 Python package，不访问 CDN。

### 7.3 文件冲突 Diff

保存失败数据流：

```text
PUT /api/files
  -> 409 FILE_CONFLICT
  -> GET /api/files 读取最新磁盘版本
  -> DiffEditor(original=磁盘, modified=当前未保存内容)
```

`DiffEditor.vue` 使用 `monaco.editor.createDiffEditor`，两侧都只读，跟随当前编辑器主题。关闭时释放 diff editor 与两侧 models。

用户操作：

- `继续编辑`：关闭 Diff，不改变 tab 内容。
- `载入磁盘版本`：用最新文档替换 tab 的 document/content，清除该 tab 旧 model，并为同一路径重新挂载新 model 后关闭 Diff。

不提供“强制覆盖磁盘”按钮，避免在冲突处理中静默丢失 Console 外修改。

## 8. Playwright 策略

- 使用固定 Chromium project；测试通过 Vite `webServer` 启动前端。
- E2E 通过 `page.route` 提供最小、真实结构的 Console API 响应，不新增生产后端测试模式，也不允许固定生产 session token。
- 端口来自 `AITEST_CONSOLE_E2E_PORT`，配置文件提供仅用于测试的默认值。
- 行为覆盖：fragment token 清理、workspace 加载、打开编辑器文件、报告 Markdown、JSON tab。
- 视觉回归只截取稳定且有历史缺陷的标签关闭按钮 hover 区域，避免把整页字体与操作系统差异变成脆弱基线。
- screenshot path 不包含宿主平台名；固定 Chromium 版本、隐藏 caret、禁用动画，并设置极小像素容差。
- CI 在 Node `22.18.0` 下安装 Chromium 后运行 Playwright。

## 9. TanStack 延后门槛

只有满足下列可测规模条件后，才单独写 Spec 并评审引入：

- TanStack Query：至少 3 类跨页面共享的服务端资源需要缓存失效，或至少 2 个页面存在轮询、去重和重新聚焦刷新。
- TanStack Table：报告明细稳定超过 100 行，并且真实需要排序、筛选、列显隐、固定列中的至少 3 项。
- TanStack Virtual：资源树、日志或结果列表稳定超过 1000 个可见节点，且浏览器性能测量确认 DOM 数量是瓶颈。

未达到门槛时继续使用 Pinia、局部请求状态、普通语义表格和原生滚动。不得仅为“技术栈完整”提前安装。

## 10. 影响文件

预计新增或修改：

- `console_web/package.json`、`package-lock.json`
- `console_web/vite.config.ts`
- `console_web/src/components/SafeMarkdown.vue`
- `console_web/src/components/DiffEditor.vue`
- `console_web/src/components/AssetManager.vue`
- `console_web/src/components/CodeEditor.vue`
- `console_web/src/editor/monacoEnvironment.ts`
- `console_web/src/views/EditorView.vue`
- `console_web/src/views/ReportsView.vue`
- `console_web/src/styles/base.css`、`views.css`
- 对应 Vitest 测试
- `console_web/playwright.config.ts`
- `console_web/e2e/console.spec.ts` 与视觉基线
- `.github/workflows/ci.yml`
- `.gitignore`
- `aitest_kit/console/web/` 构建产物

后端 Python 文件和公开 API 不在修改范围。

## 11. 测试与验收门禁

### 11.1 Vitest

至少覆盖：

1. Markdown 中原始 HTML、script、事件属性、图片和 `javascript:` URL 不进入 DOM。
2. 标题、列表、表格、fenced code 和安全链接正常渲染。
3. Reka Dialog open/close 与删除 blocker 行为不回归。
4. Reka Tabs 的两个 panel 与 Monaco JSON 参数正确。
5. 文件冲突会读取磁盘版本并打开 Diff；两个用户操作分别保留本地内容或载入磁盘版本。
6. 标签 close/reuse 释放对应 Monaco model 和 view state。
7. DiffEditor 在 props 更新时复用实例，在卸载时释放所有资源。

### 11.2 Playwright

至少覆盖：

1. 本地 token 从 URL fragment 移除且不出现在后续地址。
2. 真实浏览器可加载 workspace 并打开文件。
3. 报告 Markdown 安全预览可见，危险节点不存在。
4. 键盘切换到 `result.json` 后显示只读 Monaco。
5. 标签关闭按钮 hover 截图与基线一致。

### 11.3 全量验证

必须通过：

```bash
python3 -m pytest tests -q
cd console_web
npm audit --audit-level=high
npm test
npm run test:e2e
npm run build
cd ..
git diff --exit-code -- aitest_kit/console/web
git diff --check
```

同时核验 wheel 或干净 sdist 构建中的 Console 资产只包含当前 hashed bundle，不发布本机旧 `build/lib` 缓存混合出的 wheel。

## 12. 完成条件

- Vue Router、Pinia、Monaco、Reka UI、markdown-it、DOMPurify、Vitest 和 Playwright 都有真实接线，不存在只安装未使用的依赖。
- Reka primitives 没有改变已确认的业务语义和视觉风格。
- Markdown sink 只有经过 DOMPurify 的输出。
- JSON 和 Diff worker 全部本地分发。
- 关闭标签不遗留该文档的 Monaco model。
- Python、Vitest、Playwright、build、bundle drift 和安全审计全部通过。
- TanStack 三件套没有直接依赖和产品代码引用。

## 13. 实现核验记录

- Vue Router、Pinia 和 Vitest 沿用既有接线；新增 `reka-ui@2.10.4`、`markdown-it@15.0.0`、`dompurify@3.4.14`、`@playwright/test@1.62.1` 和 DOMPurify 单测所需 `jsdom@29.1.1`，均为精确版本。
- Reka Dialog 已用于 Asset Manager 和文件冲突，Tabs 已用于报告文件，Splitter 已用于源码区与 Inspector。真实 Chromium 已验证 Dialog 焦点恢复、Tabs 方向键和 Splitter 键盘调整。
- SafeMarkdown 使用 `html: false` 与严格 DOMPurify allow-list；jsdom 单测和真实 Chromium 都确认 script、图片与危险 URL 不成为活动 DOM。
- Monaco 新增本地 JSON worker、只读 `result.json` 与保存冲突 Diff。关闭/reuse 标签释放 model；同路径载入磁盘版本会释放旧 model 并立即重新挂载新 model。
- Vitest 收集范围固定为 `src/**/*.test.ts`，避免把 Playwright spec 误当作单元测试。
- Playwright 共 7 条真实浏览器路径，并提交标签关闭 hover 的小范围像素基线；其中轮询瞬时失败恢复、失败终态刷新、诊断 source 定位和关闭最后标签均在真实 Chromium 验证。
- 生产构建的 `assets/` 共 29 个文件，另有入口 `index.html`。主要体积：`editor.api` 2,654.36 kB（gzip 682.20 kB）、`CodeEditor` 1,167.17 kB（gzip 298.29 kB）、JSON worker 429.59 kB、editor worker 300.37 kB。
- 验证结果：Python 301 passed；Vitest 19 files / 66 tests passed；Playwright 7 passed；generated pytest 188 collected；11 个 suite profile validation 和 freshness check 全部通过；npm audit 0 vulnerabilities。
- 从干净 sdist 构建 wheel 后，wheel 中 30 个 Console 文件（29 个 assets 加 `index.html`）与当前源码目录逐一一致，missing 和 stale 均为空。未使用本机旧 `build/lib` 缓存产物作为发布证据。

## 14. 交互与执行链路加固

本节约束 Console 在短暂后端错误、失败执行和未保存编辑场景下的行为。实现不得把临时请求失败误判为任务终止，也不得因导航或标签关闭静默丢失用户输入。

### 14.1 Job 轮询

- Job 轮询采用串行调度，不允许同一个 job 的轮询请求重叠。
- 单次轮询失败只显示错误并继续轮询；下一次成功后连续失败计数归零。
- 连续 5 次轮询失败后停止自动轮询，并明确告诉用户自动轮询已停止；不得把 job 伪装成终态。
- `succeeded`、`failed`、`cancelled` 都是终态。任何终态都必须刷新 workspace snapshot，使最近执行和报告索引与磁盘一致。

### 14.2 导航与未保存内容

- 诊断页只有在能够解析失败 case 的 Markdown source path 时才显示“定位 source”，并把 path 作为 editor query 传递。
- 没有实现的快捷键不得出现在 UI 中；第一阶段不实现命令面板，因此顶栏不显示 `Command-K` 承诺。
- Environment 页面存在未保存 env 内容时，路由离开、切换 env source 或隐藏敏感值都必须请求确认；拒绝后保留当前页面和内存内容。
- 关闭脏编辑标签必须允许用户明确选择“继续编辑”或“放弃修改并关闭”，不得只显示不可操作的错误。
- 用户显式关闭最后一个标签后，编辑器保持空状态；只有首次进入且没有 path 时才自动打开第一个 case。

### 14.3 恢复与状态一致性

- DirectoryPicker 的显式初始路径不可用时，自动回退到用户 home 目录；home 目录也不可用时才显示阻断错误。
- 取消旧标签的待校验定时器或请求时，必须把旧标签从 `waiting` / `validating` 恢复为 `idle`，避免永久显示伪进行态。
- 报告页刷新列表时必须重新读取当前选中报告的详情；若报告已不存在，选择新的第一项；若列表为空，清空选择和详情。
- 面包屑的渲染 key 必须包含位置索引，支持路径中出现重复目录名。
