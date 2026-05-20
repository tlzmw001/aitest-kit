# Codex Plugin v0 Spec

## 背景

`aitest-kit` 当前已经具备可发布的确定性内核：

- `aitest init`：初始化干净 workspace。
- `aitest doctor`：检查本地环境和 workspace 基础状态。
- `aitest codegen`：从 Markdown cases、profile、project_config 生成 pytest。
- `aitest run`：执行 generated pytest 并生成结构化报告。
- `aitest report`：从已有结果重渲染报告。
- workspace template：提供 `aitest_config/`、`test_workspace/`、skills、`AGENTS.md`、`CLAUDE.md` 等项目内协作结构。

Codex plugin v0 的目标不是替代这些能力，而是让 Codex 用户更容易走完 AITest 测试飞轮：

```text
开发 / API 文档
  -> 测试知识库
  -> Markdown 用例
  -> fixture/profile
  -> codegen
  -> pytest 执行
  -> report
  -> 失败分流
  -> 规则沉淀
```

核心定位：

```text
Python 包解决“能跑”。
workspace template 解决“有结构”。
Codex plugin 解决“会用”。
```

## 目标

Codex plugin v0 应该让新用户通过自然语言完成以下事情：

1. 初始化 AITest workspace。
2. 检查本地环境和 workspace 健康状态。
3. 基于文档构建测试知识库。
4. 基于知识库生成 Markdown 测试用例。
5. 为模块补齐 fixture/profile 初稿。
6. 调用 `aitest codegen` 生成 pytest。
7. 调用 `aitest run` 执行测试并生成报告。
8. 读取报告并做失败分流。
9. 对已验证的重复模式做 promotion / emitter-build 只读分析。
10. 帮用户交互式学习项目，并把 lesson 记录到文档。

插件 v0 的成功标准不是“完全自动化”，而是：

```text
用户不用先理解全部内部概念，也能按正确顺序完成一次端到端测试接入。
```

## 非目标

plugin v0 不做以下事情：

- 不复制 `aitest_kit` 的 parser、planner、emitter、report 核心逻辑。
- 不在插件中重新实现 codegen。
- 不在插件中重新实现 pytest runner。
- 不做 Web UI / dashboard。
- 不做 MCP server。
- 不自动修改用户业务源码。
- 不自动发布测试报告到外部平台。
- 不自动应用 promotion patch。
- 不自动把 `case_body` 改成 `case_flow`。
- 不替代 workspace template。
- 不绑定某个具体待测系统，例如 `coupon_system` 或 `discount_system`。

这些能力可以作为未来方向讨论，但不进入 v0。

## 核心原则

### 1. 插件是 thin wrapper

插件只做交互式工作流编排：

```text
理解用户意图
  -> 选择正确 workflow
  -> 读取必要上下文
  -> 调用 aitest CLI 或指导用户执行
  -> 解释输出
  -> 给出下一步
```

确定性执行仍由 CLI 完成：

```text
aitest init
aitest doctor
aitest codegen
aitest run
aitest report
```

### 2. AI 做探索，代码做门禁

插件可以让 AI 做：

- 阅读文档。
- 设计知识库初稿。
- 设计 Markdown 用例初稿。
- 生成 fixture/profile 初稿。
- 分析失败原因。
- 判断重复模式是否值得沉淀。
- 给出 promotion 候选和风险说明。

插件必须让代码做：

- profile schema 校验。
- case_id 对齐校验。
- Markdown parser 诊断。
- IR dump。
- generated freshness check。
- pytest collect。
- pytest run。
- report 生成。

### 3. 不让用户第一屏理解内部术语

用户入口应按阶段组织，而不是按内部组件组织。

推荐用户可见阶段：

```text
接入项目
整理测试知识
设计测试用例
生成测试代码
运行测试报告
分析修复失败
沉淀稳定规则
交互式学习项目
```

`Case IR`、`case_flow`、`case_body`、`profile gate`、`emitter` 等概念应在需要排查或进阶优化时解释，不作为初始使用门槛。

## 插件和 CLI 边界

| 能力 | CLI 负责 | Plugin 负责 |
|---|---:|---:|
| 初始化 workspace | 是 | 引导和调用 |
| workspace 健康检查 | 是 | 调用并解释 |
| Markdown parser | 是 | 解释诊断 |
| profile JSON Schema 校验 | 是 | 解释修复路径 |
| Case IR 生成 / dump | 是 | 解释 IR 中的 strategy/source_trace |
| pytest 生成 | 是 | 选择正确 codegen 顺序 |
| freshness check | 是 | 解释 stale diff |
| pytest 执行 | 是 | 调用并做失败分流 |
| report 生成 | 是 | 总结和反哺 |
| 文档审查 | 否，或未来可选 CLI | 是 |
| 知识库构建 | 当前主要是 skill | 是 |
| 测试用例设计 | 当前主要是 skill | 是 |
| fixture/profile 初稿 | 否 | 是 |
| promotion 判断 | 不自动判断 | AI 分析 + 人 review |

## 插件和 workspace template 的关系

workspace template 是项目内协作资产源，包含：

```text
AGENTS.md
CLAUDE.md
.codex/skills/
.claude/skills/
.agents/skills/
aitest_config/
test_workspace/
```

Codex plugin 是用户本机 / Codex 环境中的产品入口。

两者关系：

```text
Codex plugin
  -> 引导用户安装 aitest-kit
  -> 调用 aitest init 创建 workspace
  -> 使用 workspace 内的配置、cases、profile、reports
  -> 必要时参考 workspace 内 skills 的项目约束
```

原则：

1. 插件不替代 `aitest init` 生成的 workspace template。
2. 插件不把 workspace template 内容复制到自己的运行逻辑里。
3. 插件可以携带通用 workflow skill，但项目级规则仍以 workspace 内 `AGENTS.md`、`.codex/skills/` 和配置为准。
4. 如果插件 skill 与 workspace skill 有重叠，插件 skill 负责“入口和编排”，workspace skill 负责“项目内细节和约束”。

## 插件目录草案

概念结构：

```text
aitest-kit/
├── .codex-plugin/
│   └── plugin.json
├── skills/
│   ├── onboard/
│   │   └── SKILL.md
│   ├── review-docs/
│   │   └── SKILL.md
│   ├── build-knowledge/
│   │   └── SKILL.md
│   ├── design-cases/
│   │   └── SKILL.md
│   ├── generate-tests/
│   │   └── SKILL.md
│   ├── run-tests/
│   │   └── SKILL.md
│   ├── fix-failures/
│   │   └── SKILL.md
│   ├── promote-rules/
│   │   └── SKILL.md
│   └── learn-project/
│       └── SKILL.md
└── assets/
    ├── logo.png
    └── composer-icon.png
```

`plugin.json` 草案：

```json
{
  "name": "aitest-kit",
  "version": "0.2.0",
  "description": "AI-assisted test design, codegen, execution, and reporting workflow.",
  "skills": "./skills/",
  "interface": {
    "displayName": "AITest Kit",
    "shortDescription": "Generate and run maintainable tests from docs",
    "longDescription": "AITest guides Codex users from project/API docs to test knowledge, Markdown cases, generated pytest, structured reports, and rule promotion review.",
    "developerName": "AITest Kit",
    "category": "Coding",
    "capabilities": ["Interactive", "Read", "Write"],
    "defaultPrompt": [
      "Initialize AITest Kit for this project",
      "Generate tests from my API docs",
      "Run AITest and explain failures"
    ]
  }
}
```

字段以未来真实插件规范为准；本段只描述产品结构和信息架构。

## v0 Skills

### onboard

用户意图示例：

```text
用 AITest 初始化这个项目。
帮我把这个项目接入 AITest。
```

职责：

- 检查 `aitest` 命令是否可用。
- 如果不可用，引导用户安装 `aitest-kit`。
- 运行或建议运行 `aitest doctor`。
- 运行或建议运行 `aitest init --target <workspace>`。
- 检查生成的 workspace 结构。
- 告诉用户下一步需要提供哪些文档。

不做：

- 不生成测试用例。
- 不修改待测系统源码。

### review-docs

用户意图示例：

```text
看看这些接口文档是否足够生成测试。
```

职责：

- 从测试视角审查开发/API 文档。
- 检查 API、字段、错误、状态、配置、可观测性是否足够。
- 输出阻塞项和非阻塞待确认项。

不做：

- 不直接生成 pytest。
- 不从源码猜测文档缺失行为，除非用户明确进入灰盒补文档模式。

### build-knowledge

用户意图示例：

```text
基于 docs 构建测试知识库。
```

职责：

- 读取用户指定文档。
- 生成或更新 L0/L1/L2。
- 标注 `[?]`。
- 输出待确认项。

不做：

- 不绕过知识库直接写 pytest。

### design-cases

用户意图示例：

```text
为 discount_policy 设计业务和边界用例。
```

职责：

- 基于 L1/L2/TEST_SPEC 生成 Markdown cases。
- 输出覆盖说明和未覆盖原因。
- 区分稳定自动化用例、manual 用例、待确认场景。

不做：

- 不因为文档未定义而脑补稳定断言。

### generate-tests

用户意图示例：

```text
把这个模块的 Markdown 用例生成 pytest。
```

职责：

- 确认模块名和 workspace。
- 检查 fixture/profile 是否存在。
- 缺失时生成初稿或说明缺口。
- 按标准顺序调用 CLI：

```bash
aitest codegen <module> --validate-profile
aitest codegen <module> --dump-ir
aitest codegen <module> --check
aitest codegen <module>
python -m pytest test_workspace/tests/generated --collect-only -q
```

不做：

- 不手改 generated pytest。
- 不绕过 profile gate。

### run-tests

用户意图示例：

```text
运行这些测试并生成报告。
```

职责：

- 调用 `aitest run <module>`。
- 输出报告路径。
- 总结 pass/fail/skip/manual。
- 提醒 freshness blocked 的修复路径。

不做：

- 不自动把断言失败判定为待测系统 bug。

### fix-failures

用户意图示例：

```text
测试失败了，帮我判断问题类型。
```

职责：

- 读取 `test_workspace/reports/latest/result.json` 和 `report.md`。
- 关联 Markdown case、generated pytest、fixture/profile。
- 做失败分流：
  - 文档问题
  - 用例问题
  - fixture/profile 问题
  - codegen 问题
  - 测试环境问题
  - 待测系统 bug
- 给出最小修复路径。

不做：

- 不放宽断言。
- 不 skip 失败用例来制造通过。
- 不默认修改待测系统。

### promote-rules

用户意图示例：

```text
这些测试都通过了，帮我看看哪些模式值得沉淀。
```

职责：

- 只读分析 generated pytest、profile、fixture、Markdown cases。
- 判断是否存在重复稳定模式。
- 输出 promotion candidate report：
  - 证据 case_id
  - 重复结构
  - 建议沉淀层级
  - 风险点
  - 验证命令

不做：

- 不自动应用 patch。
- 不自动修改 profile/fixture/project_config。

### learn-project

用户意图示例：

```text
从小白角度带我理解这个项目，并把课堂笔记写到 usebook。
```

职责：

- 建立学习路线。
- 按章节讲解模块、函数调用和数据流。
- 每节输出图、最小代码地图、关键代码点、理解题。
- 把高价值解释写入 lesson 文档。

不做：

- 不在学习过程中顺手改业务代码。

## 用户流程示例

### 新项目接入

用户：

```text
@aitest 帮我给这个项目建立自动化测试流程。
```

插件行为：

```text
1. 检查 aitest-kit 是否安装。
2. 运行 aitest doctor。
3. 初始化 aitest_workspace。
4. 检查 workspace 结构。
5. 提醒用户提供公开 API 文档。
```

### 从文档生成知识库

用户：

```text
@aitest 基于 docs/public_api_doc.md 构建测试知识库。
```

插件行为：

```text
1. 读取公开文档。
2. 生成 L0/L1/L2。
3. 标注 [?]。
4. 输出待确认项。
```

### 生成并执行测试

用户：

```text
@aitest 为 discount_policy 生成并运行测试。
```

插件行为：

```text
1. 检查 cases/fixtures/profile。
2. 运行 profile gate。
3. dump IR。
4. freshness check。
5. codegen。
6. pytest collect。
7. aitest run。
8. 输出 report 摘要。
```

### 失败分流

用户：

```text
@aitest 这些测试失败了，帮我看原因。
```

插件行为：

```text
1. 读取 latest report。
2. 定位失败 case。
3. 关联 Markdown/profile/generated。
4. 分类失败原因。
5. 给出最小修复建议。
```

## 安装和使用草案

对用户推荐路径：

```bash
pip install aitest-kit
```

然后在 Codex 中安装 AITest plugin。

首次使用：

```text
@aitest 初始化这个项目。
```

如果用户没有安装 Python 包，插件应提示：

```bash
pip install aitest-kit
aitest doctor
```

原则：

- plugin 不应隐式安装依赖，除非用户明确同意。
- plugin 不应隐式修改 `.env` 或业务配置文件。
- plugin 可以生成 workspace 内测试资产，但应遵守项目 `AGENTS.md`。

## 验证标准

plugin v0 实现后，应至少验证：

1. 新项目空目录中可以引导安装和 `aitest init`。
2. 已初始化 workspace 中可以识别 `aitest_config/` 和 `test_workspace/`。
3. 可以调用 `aitest doctor` 并解释失败项。
4. 可以基于文档生成知识库。
5. 可以基于知识库生成 Markdown cases。
6. 可以生成 fixture/profile 初稿。
7. 可以运行 `aitest codegen --validate-profile`。
8. 可以运行 `aitest codegen --dump-ir`。
9. 可以运行 `aitest codegen --check`。
10. 可以运行 `aitest codegen`。
11. 可以运行 pytest collect。
12. 可以运行 `aitest run` 并读取报告。
13. 可以对失败报告做分类说明。
14. promotion 分析默认为只读，不修改 profile。

## 风险和约束

### Skill 漂移

风险：

```text
workspace template 中已有 .codex/.claude/.agents skills；
plugin 也会携带 skills；
两边可能逐渐不一致。
```

控制方式：

- 插件 skill 只做通用入口和编排。
- workspace skill 保留项目内约束。
- 修改核心 workflow 时，明确是否需要同步 template 和 plugin。
- 后续可以增加 skill sync checklist，但 v0 不做自动同步工具。

### 过度自动化

风险：

```text
用户希望一键从文档到全部测试通过；
但真实项目中文档缺失、环境缺失、接口未定义、状态不可控都很常见。
```

控制方式：

- 插件明确区分“可自动生成”和“需要确认”。
- 对 `[?]` 不脑补。
- 对失败不直接判断为系统 bug。
- 对 promotion 不自动应用 patch。

### 版本漂移

风险：

```text
插件里的说明和 PyPI 版本 CLI 行为不一致。
```

控制方式：

- 插件尽量调用 CLI 自身输出。
- 关键能力以 `aitest --help`、`aitest doctor`、`aitest codegen --validate-profile` 为准。
- 插件文档中避免复制复杂 CLI 内部行为。

## 里程碑

### v0.1 spec-only

- 写本 spec。
- 更新 roadmap。
- 不实现插件。

### v0.2 local plugin prototype

- 已使用 Codex plugin scaffold 创建本地插件。
- v0.2 阶段只包含 `plugin.json` 和 3 个入口 skill：
  - `onboard`
  - `generate-tests`
  - `run-tests`
- 已在本地 Codex 中完成 discovery / install / skill loading smoke test：
  - 输入 `@AITest Kit` 后能触发安装提示。
  - 安装后能选择并调用插件入口 skill。
  - 本阶段只验证插件接入，不替代 CLI 级 `validate-profile`、`codegen`、`run` 验证。

### v0.3 workflow complete

- 已补齐全部 v0 skill 入口：
  - `review-docs`
  - `build-knowledge`
  - `design-cases`
  - `fix-failures`
  - `promote-rules`
  - `learn-project`
- 外部项目端到端接入验证仍沿用 CLI/workspace 验证路径；plugin v0.3 当前只完成 skill 覆盖，不声明公开发布就绪。
- plugin skill 与 workspace skill 的同步策略：plugin skill 只做通用入口和编排；workspace skill 保留项目内细节、模板和约束。

### v1.0 publish candidate

- 完成插件安装说明。
- 完成截图 / demo 文档。
- 完成失败分流示例。
- 完成 promotion review 示例。

## 当前结论

Codex plugin v0 应该是薄插件，不是第二套 `aitest-kit`。

它的价值是把用户带进正确测试流程：

```text
让 AI 帮用户理解、设计、解释和判断；
让 aitest CLI 负责校验、生成、执行和报告。
```

这个边界能最大化上手体验，同时避免核心能力分裂。
