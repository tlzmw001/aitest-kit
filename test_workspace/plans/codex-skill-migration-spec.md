# Codex Skill 迁移 Spec

## 背景

仓库当前已有 Claude 版本地 skills：

- `.claude/skills/doc-review/SKILL.md`
- `.claude/skills/doc-gen/SKILL.md`
- `.claude/skills/knowledge-build/SKILL.md`
- `.claude/skills/test-design/SKILL.md`
- `.claude/skills/test-fix/SKILL.md`

其中 Codex 版仅完成了 `test-design`，其余 4 个 skill 仍未迁移到 `.codex/skills/`。

## 目标

把剩余 4 个 skill 迁移为 Codex 可用的本地 skill：

- `.codex/skills/doc-review/SKILL.md`
- `.codex/skills/doc-gen/SKILL.md`
- `.codex/skills/knowledge-build/SKILL.md`
- `.codex/skills/test-fix/SKILL.md`

## 迁移约束

1. 保持 skill 名称与原 Claude 版一致。
2. Frontmatter 只保留 Codex 必需字段：
   - `name`
   - `description`
3. 不额外生成 README、CHANGELOG、agent metadata 或其他辅助文件。
4. 正文保留原 SOP 的核心执行顺序、输入边界、输出模板和质量约束。
5. 正文收敛为 Codex 风格：
   - 不保留 Claude 专用元数据字段
   - 不依赖 `$argument` 语法才能理解
   - 用占位描述用户输入和默认输出位置
6. 与已落地的 `.codex/skills/test-design/SKILL.md` 保持风格一致。

## 不在本次范围

- 不删除 `.claude/skills/` 原文件
- 不新增 `agents/openai.yaml`
- 不修改 `test-design`
- 不同步调整其他仓库流程文档

## 验收标准

1. 4 个目标 `SKILL.md` 文件全部存在。
2. 每个 skill 都能独立说明：
   - 何时使用
   - 读取哪些输入
   - 按什么步骤执行
   - 产出什么结果
   - 有哪些质量边界
3. 迁移后的内容不依赖 Claude 专有字段也能执行。
