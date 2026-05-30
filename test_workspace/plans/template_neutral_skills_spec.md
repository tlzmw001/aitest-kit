# 模板 skills 中立化改造 Spec

## 背景

当前 `aitest init` 的项目模板在初始化 workspace 时同时写入三套 agent 专属 skill 目录：

- `.codex/skills/`
- `.claude/skills/`
- `.agents/skills/`

三套目录内容语义相同，但会带来两个问题：

1. 模板体积和维护成本膨胀，同一个 skill 修改需要复制三份。
2. 新用户还没决定使用哪个 agent 时，workspace 被预置多个隐藏目录，容易误解为必须同时维护三套。

用户希望模板只保留一份通用 `skills/`，由用户根据实际使用的 agent 自行复制到 `.codex/skills`、`.claude/skills` 或 `.agents/skills`。

## 目标

1. `aitest_kit/templates/project_workspace/` 下只保留一份 `skills/` 作为 agent-neutral skill 源。
2. `aitest init` 默认只写入 `skills/`，不再写入 `.codex/`、`.claude/`、`.agents/`。
3. 文档明确说明：
   - `skills/` 是通用源目录，不是某个 agent 的运行目录。
   - Codex/Claude/agents 用户需要按需复制 `skills/` 到对应隐藏目录。
4. package data 只打包模板根目录的 `skills/`。
5. `init` / `upgrade` 相关测试覆盖新模板形态。

## 非目标

1. 不修改仓库根目录当前正在使用的 `.codex/skills/`、`.claude/skills/`、`.agents/skills/`。
2. 不实现自动识别当前 agent 并自动复制 skill。
3. 不改变 skill 内容语义；本次只改模板组织方式和文档说明。
4. 不改变 `aitest codegen/run/report` 的业务逻辑。

## 目标目录结构

```text
aitest_kit/templates/project_workspace/
  skills/
    README.md
    doc-gen/SKILL.md
    doc-review/SKILL.md
    emitter-build/SKILL.md
    knowledge-build/SKILL.md
    test-codegen/SKILL.md
    test-design/SKILL.md
    test-fix/SKILL.md
    test-maintain/SKILL.md
    test-scaffold/SKILL.md
```

初始化后的 workspace 默认形态：

```text
<workspace>/
  skills/
  AGENTS.md
  CLAUDE.md
  README.md
  aitest_config/
  test_workspace/
```

用户按需安装到 agent：

```bash
# Codex
mkdir -p .codex/skills
cp -R skills/. .codex/skills/

# Claude Code
mkdir -p .claude/skills
cp -R skills/. .claude/skills/

# agents workflow
mkdir -p .agents/skills
cp -R skills/. .agents/skills/
```

## 影响范围

### 模板文件

- 移除模板内 `.codex/`、`.claude/`、`.agents/`。
- 新增模板根目录 `skills/`。
- 更新模板 `README.md`、`AGENTS.md`、`CLAUDE.md` 对 skill 使用方式的描述。

### 包配置

- 更新 `pyproject.toml` 的 package data：
  - 删除 `.codex/.claude/.agents` skill 打包规则。
  - 新增 `skills/README.md`、`skills/*/SKILL.md`、`skills/*/refs/*`。

### CLI 文案

- 更新 `aitest init` docstring 和 Next steps，明确初始化后需要按 agent 复制 `skills/`。

### 测试

- `init` 测试应断言：
  - `skills/test-codegen/SKILL.md` 存在。
  - `.codex/skills`、`.claude/skills`、`.agents/skills` 默认不存在。
- 已存在 `.claude/` 不应影响 init，因为模板不再写入 `.claude/`。
- 若目标路径中 `skills` 是文件，应报目录冲突。
- `upgrade --apply` 恢复缺失模板文件时应使用 `skills/...` 路径。

## 兼容性与迁移行为

1. 新 workspace：只得到 `skills/`。
2. 老 workspace：如果已存在 `.codex/.claude/.agents`，`upgrade` 不应因为模板删除这些目录而主动删除用户已有内容。
3. 老 workspace 缺失 `skills/` 时，`upgrade --apply` 应能新增模板托管的 `skills/` 文件。
4. 用户本地修改过的模板托管文件仍遵循现有 manifest 保护逻辑，不被静默覆盖。

## 验证计划

```bash
python3 -m pytest tests/test_workspace_template.py -q
python3 -m pytest tests -q
python3 -m build
```

包内容验证：

```bash
python3 - <<'PY'
import glob, zipfile
wheel = sorted(glob.glob("dist/aitest_kit-*.whl"))[-1]
with zipfile.ZipFile(wheel) as z:
    names = z.namelist()
print(any("templates/project_workspace/skills/test-codegen/SKILL.md" in n for n in names))
print(any("templates/project_workspace/.codex/skills/test-codegen/SKILL.md" in n for n in names))
PY
```

预期第一行 `True`，第二行 `False`。
