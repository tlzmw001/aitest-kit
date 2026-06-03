---
name: case-migrate
description: 将外部/历史/公司测试平台用例迁移为 AITest Markdown suite 用例，并保留语义追溯、阻塞分类和人工 review 清单
when_to_use: 当用户已有旧格式测试用例（Excel/CSV/Markdown/Word 导出/测试平台导出/自由文本），需要转换为 AITest Markdown 用例时
argument-hint: <source_cases> <target> <module> [suite_dir]
arguments: [source_cases, target, module, suite_dir]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash
effort: high
---

# 用例迁移

把 `$source_cases` 中的外部/历史测试用例迁移为 AITest Markdown suite 用例。输出目录为 `$suite_dir`；未指定时，建议使用 `test_workspace/suites/{target}/{suite}/`，并由用户确认 suite 名称。

## 定位

```
外部旧用例
  ↓
case-migrate ← 本 skill
  ↓
AITest Markdown suite + 迁移报告
  ↓
人工 review
  ↓
test-scaffold / test-codegen
```

本 skill 只负责“旧用例 → 标准 Markdown 用例”的语义迁移，不生成 pytest，不写 fixture/profile，不修改 generated，不修改待测系统。

## 核心原则

1. **不丢信息**：每条旧用例都必须出现在迁移报告中；无法迁移也要说明原因。
2. **不改语义**：不能把旧用例中没有明确写出的状态码、错误码、字段值、业务规则补成确定断言。
3. **不隐藏阻塞**：缺接口、缺测试数据、缺 fixture 能力、依赖执行顺序、预期模糊等情况必须显式标记。
4. **可追溯**：迁移后的每条用例必须保留原始用例 ID、标题或来源位置。
5. **先 review 再接线**：迁移产物必须经过人工 review 后，再进入 `test-scaffold` / `test-codegen`。

## 输入读取

优先读取用户指定的 `$source_cases`。支持常见形态：

- Excel/CSV/TSV 导出的结构化用例
- Markdown/Word 导出文本
- 测试平台导出内容
- 自由文本测试点、checklist、验收点

同时读取必要的 AITest 上下文：

- `aitest_config/aitest.yaml`：workspace 路径和 codegen 规则
- `aitest_config/refs/case-format.md`：目标 Markdown 格式
- `test_workspace/knowledge/` 中与 `$target/$module` 相关的 L1/L2 文档（存在时）
- 已有 suite 用例（如果是追加迁移）

禁止读取或写入：

- 不读取待测系统业务实现源码，除非用户明确要求
- 不写 `test_workspace/generated/`
- 不写真实 token、账号密码、API key、生产 URL
- 不修改 `.env` 或本地密钥文件

## Step 1：识别原始格式

先判断旧用例字段和结构，不直接转换。

输出字段映射草案：

| 原始字段 | AITest 归属 | 说明 |
|---|---|---|
| 用例编号 | 来源用例 / TC-ID 映射 | 保留原始编号 |
| 用例标题 | 标题 | 必须保留原意 |
| 前置条件 | 标准前置 / 测试资源 / 可行性存疑 | 拆分 env、resource、state |
| 操作步骤 | 场景变量 / 流程 | 不直接写成断言 |
| 测试数据 | 请求覆盖 / variables / 待确认项 | 敏感值必须脱敏 |
| 预期结果 | 断言 / 待确认项 | 不明确则标 `[?]` |
| 自动化状态 | 标记 | manual / skipped / 可行性存疑 |
| 备注/链接/负责人 | 迁移报告 | 默认不进入核心用例正文 |

如果字段含义不确定，先在迁移报告里标记，不猜。

## Step 2：上下文盘点

迁移前确认这些上下文；缺失时列入“待确认项”：

- 目标 `target`
- 目标 `module`
- 目标 `suite`
- 旧用例默认环境或服务入口
- 默认账号、token、测试资源是否来自旧平台上下文
- 是否存在执行顺序依赖
- 是否存在共享测试数据
- 是否有 UI/manual 用例混入 API 用例
- 是否有旧用例与当前知识库冲突

## Step 3：逐条分流

每条旧用例必须分到一个主状态，可附加多个原因标签：

| 状态 | 含义 | 处理 |
|---|---|---|
| `OK` | 语义清楚，可迁移为 AITest Markdown | 写入 Markdown |
| `NEEDS_REVIEW` | 基本可迁移，但有少量待确认 | 写入 Markdown 并标 `[?]` |
| `NEEDS_SCAFFOLD` | 用例清楚，但需要 fixture/helper/profile 能力 | 写入 Markdown 并标 `[!可行性存疑]` |
| `NEEDS_DATA` | 缺测试账号、token、API key、余额、分组、Redis/DB 状态等资源 | 写入 Markdown 并标资源需求 |
| `AMBIGUOUS_EXPECTATION` | 预期结果模糊，如“正确/正常/成功/失败” | 不补确定断言，标 `[?预期不明确]` |
| `AMBIGUOUS_ACTION` | 操作步骤不清楚，不知道应调用什么接口或观察什么状态 | 标待确认 |
| `ORDER_DEPENDENT` | 依赖其他旧用例执行结果 | 建议改为独立流程或人工确认 |
| `MANUAL` | 人工观察、审批、验证码、视觉判断等 | 写入 manual 用例 |
| `UNSUPPORTED` | 当前 AITest 能力暂不支持 | 记录，不强行迁移为自动化 |
| `CONTRACT_CONFLICT` | 与知识库/接口文档/当前规范冲突 | 记录冲突，等待裁决 |
| `SECURITY_REDACTED` | 原用例含敏感值 | 脱敏并记录替代变量名 |

## Step 4：迁移为 AITest Markdown

按 `aitest_config/refs/case-format.md` 生成 Markdown。每条迁移用例必须保留来源：

```markdown
### TC-XXX-001：用例标题
- **来源用例**：`OLD-CASE-ID`
- **迁移状态**：OK
- **优先级**：P0
- **场景变量**：
  - 接口：`POST /api/example`
  - 请求覆盖：`{"field":"value"}`
- **断言**：`response.code == 0`
```

如果旧预期不明确：

```markdown
- **断言**：访问失败；错误语义表示无权限
- **待确认**：[?预期不明确: 原用例未说明具体 HTTP 状态码、业务错误码或响应字段]
```

如果需要测试资源或 fixture 能力：

```markdown
- **标记**：[!可行性存疑: 需要 low_balance_user 测试资源和余额查询能力]
- **场景变量**：
  - 测试资源：`low_balance_user`
  - 前置状态：用户余额不足
```

如果是 manual：

```markdown
- **标记**：manual
- **说明**：原用例依赖人工视觉确认，当前不进入默认自动化执行
```

## Step 5：迁移报告

必须生成迁移报告，建议路径：

`test_workspace/reports/case_migration/{suite}_migration_report.md`

报告包含：

```markdown
# 用例迁移报告

## 输入

- 原始用例：...
- 目标 target：...
- 目标 module：...
- 目标 suite：...

## 汇总

| 状态 | 数量 |
|---|---:|
| OK | 0 |
| NEEDS_REVIEW | 0 |
| NEEDS_SCAFFOLD | 0 |
| NEEDS_DATA | 0 |
| AMBIGUOUS_EXPECTATION | 0 |
| AMBIGUOUS_ACTION | 0 |
| ORDER_DEPENDENT | 0 |
| MANUAL | 0 |
| UNSUPPORTED | 0 |
| CONTRACT_CONFLICT | 0 |
| SECURITY_REDACTED | 0 |

## 字段映射

| 原始字段 | AITest 归属 | 说明 |
|---|---|---|

## 用例映射

| 来源用例 | 新 TC-ID | 状态 | 说明 |
|---|---|---|---|

## 信息保留说明

- 已迁移到 Markdown 的信息：
- 仅保留在报告中的信息：
- 已脱敏的信息：
- 无法确认的信息：

## 待确认项

- ...

## 未迁移/不自动化项

| 来源用例 | 原因 | 建议 |
|---|---|---|
```

报告必须能回答：是否有旧用例被丢弃、是否有断言被 AI 补写、哪些信息只保留在报告中。

## 信息不丢失规则

逐条检查旧用例中的信息，按以下归属处理：

- 影响执行或断言的内容 → 迁移到 Markdown
- 影响追溯但不影响执行的内容 → 放迁移报告
- 敏感值 → 替换为环境变量名或资源 alias，并在报告中说明已脱敏
- 无法解释的字段 → 放报告“无法确认的信息”
- 与当前规范冲突的内容 → 放 `CONTRACT_CONFLICT`

禁止静默删除字段。确实不迁移到 Markdown 时，必须在报告中说明原因。

## 语义保守规则

以下情况必须标 `[?]` 或阻塞分类，不能脑补：

- “返回正确”“保存成功”“展示正常”“扣费正确”等没有字段级证据
- 未说明具体状态码、错误码、响应字段
- 未说明测试数据准备方式
- 未说明前置账号、token、key、余额、分组、订阅状态来源
- UI 视觉判断无法映射到 API/状态验证
- 旧用例依赖其他用例执行顺序
- 与知识库或接口文档冲突

## 完成标准

1. 目标 suite Markdown 已生成或更新
2. 迁移报告已生成
3. 每条旧用例在报告中有映射或不迁移原因
4. 所有敏感值已脱敏
5. 所有 `[?]`、`[!可行性存疑]`、manual、unsupported、contract conflict 已汇总
6. 没有生成 pytest、fixture、profile 或修改 generated

## 输出摘要

完成后向用户输出：

```markdown
## 用例迁移摘要

来源：$source_cases
目标：$target / $module
输出 suite：$suite_dir

### 生成文件
| 文件 | 说明 |
|---|---|

### 状态汇总
| 状态 | 数量 |
|---|---:|

### 高风险迁移点
- 原预期不明确：
- 原前置不完整：
- 依赖执行顺序：
- 含敏感值并已脱敏：
- 与知识库冲突：

### 下一步
1. 人工 review Markdown 和迁移报告
2. 确认待确认项
3. 通过后进入 test-scaffold / test-codegen
```
