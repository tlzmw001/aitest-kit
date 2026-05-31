---
name: test-maintain
description: 测试资产维护分诊台：诊断项目当前状态，定位管线断裂层，路由到正确的 skill 或 CLI 命令
when_to_use: 当用户不确定该用哪个 skill/CLI 命令，或需要对测试资产做维护但不确定从哪入手时
argument-hint: <maintenance_request>
arguments: [maintenance_request]
user-invocable: true
allowed-tools: Read Glob Grep Bash Agent
effort: high
---

# 测试资产维护分诊台

本 skill 是测试维护的分诊入口，不是 codegen 引擎，不直接修改文件。

核心工作模式：

```text
理解用户意图
  → 诊断项目当前状态（确定性命令）
  → 定位最左侧断裂层
  → 路由到对应 skill / CLI
  → 验证修复结果 + 摘要
```

## 参考文档

- `refs/routing.md` — 症状映射、验证命令、废弃影响面模板

## 硬边界

1. **只路由，不直接改文件**：不使用 Write/Edit 修改任何测试资产；修改交给对应 skill。
2. **不直接编辑 generated pytest**：`test_workspace/generated/` 是编译产物，修改必须回到上游源头。
3. **不绕过知识库**：需求变化影响业务规则时，先判断是否需要更新 knowledge。
4. **不自动批量删除**：删除/废弃 case 前列出影响面（模板见 `refs/routing.md`），用户确认后才执行。
5. **不猜业务语义**：断言失败不自动判定为 SUT bug；SUT bug 需人工确认后记录到 `test_workspace/results/`。
6. **歧义路由不默认选择**：路由有多个候选时，列出候选 + 各自判定依据，让用户选择。

## Step 1：理解请求

提取三个要素：

- **范围**：target / module / suite / case_id / 需求名称
- **动作**：add / update / retire / delete / sync / diagnose
- **约束**：用户是否要求只分析不修改

意图不明确时，直接进入 Step 2 诊断，用项目状态帮用户定位问题。

删除、发布、修改 `.env` 或改待测系统代码的请求，必须先停下确认。

## Step 2：诊断项目状态

测试资产管线从左到右：

```text
knowledge → cases → scaffold → codegen → execution → emitter
  L0/L1/L2    Markdown   fixture/profile  generated    report     模式沉淀
```

**按层序检查，找到最左侧断裂层。** 右侧问题可能是左侧断裂的连锁反应。

诊断命令（按需选用）：

| 层 | 命令 | 看什么 |
|----|------|--------|
| knowledge | `ls test_workspace/knowledge/L*/` | 知识库覆盖 |
| cases | `ls test_workspace/suites/{target}/{suite}/` | 用例和 suite.yaml |
| scaffold | `aitest codegen --suite-file <s.yaml> --validate-profile` | fixture/profile 齐备性 |
| codegen | `aitest codegen --suite-file <s.yaml> --check` | generated 与源头同步 |
| execution | `ls test_workspace/reports/{target}/.../latest/` | 最近执行结果 |

不涉及特定模块时，优先用健康检查或显式 task；`--all` 只作为最后兜底，避免在大 workspace 中盲目扫描全部 suites：

```bash
aitest doctor
aitest codegen --task-file test_workspace/tasks/<task>.yaml --check
aitest codegen --all --check
```

**多模块诊断**：scope > 1 module 时委托子 Agent 并行诊断（见子 Agent 策略节），主 Agent 只看聚合结论。

常见症状到断裂层的映射见 `refs/routing.md`。

诊断输出：

```markdown
## 诊断结果

范围：{target} / {module} / {suite}
断裂层：{layer}
症状：{description}
建议路由：{skill / CLI}
```

## Step 3：路由

一条原则：**修最左侧断裂层。**

| 断裂层 | 路由 | 需确认 | 交接信息 |
|--------|------|--------|----------|
| knowledge | `knowledge-build` | 是（影响面大） | 模块名、缺口描述、关联文档 |
| cases | `test-design` / `test-fix` | 否 | 模块+知识库引用 / case_id+错误描述 |
| scaffold | `test-scaffold` | 否 | target、模块、缺口清单 |
| codegen | `test-codegen` | 否 | suite.yaml 路径 |
| execution | `aitest run` | 否 | 无需路由 skill |
| emitter | `emitter-build` | 是（框架级变更） | 已验证 pytest、可沉淀模式 |

"需确认"列为"是"时，向用户说明影响范围，确认后再路由。

特殊路由：

- suite 注册到聚合入口 → `aitest registry register-suite`
- 创建 task manifest → `aitest task create`
- 废弃/删除 → 先列影响面清单（模板见 `refs/routing.md`），用户确认后路由底层 skill

交接时只传底层 skill 需要的最小上下文，不传本 skill 的分析原文。

### 误路由恢复

底层 skill 报告"问题不在本层"时，回退到 Step 2 重新诊断，不重复执行同一路由。连续 2 次误路由后停下，向用户呈现完整诊断数据，请求人工判断。

## Step 4：验证与摘要

底层 skill 完成后，重跑 Step 2 的诊断命令，确认断裂层已修复。验证命令序列见 `refs/routing.md`。

发现新的断裂层（如修了 scaffold 后 codegen 需要重跑）时，继续路由下一层。

验证通过后输出摘要：

```markdown
## 维护摘要

动作：{add/update/retire/delete/sync/diagnose}
断裂层：{layer} → 已修复 / 仍有问题
路由：{skill} → {结果}
资产变化：{简要列表}
后续：{需要人工确认的 / 下一个断裂层}
```

## 子 Agent 策略

| 步骤 | 任务 | 输入 | 输出 | 确认方式 |
|------|------|------|------|----------|
| Step 2 | 多模块并行诊断 | module 列表、诊断命令表 | 每模块（断裂层 / 症状 / 建议路由） | 主 Agent 聚合后呈现 |
| Step 4 | 验证闭环 | 验证命令序列 | pass/fail 摘要 | 失败时阻塞 |

scope ≤ 1 module 或验证命令 ≤ 3 条时主 Agent 直接处理，不委托子 Agent。
