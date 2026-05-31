# test-maintain 路由参考

## 症状 → 断裂层映射

| 症状 | 断裂层 | 路由 | 歧义判定 |
|------|--------|------|----------|
| 需求规则未进入知识库 | knowledge | `knowledge-build` | — |
| 缺用例 / 用例过时 | cases | `test-design` | — |
| 单条用例错误 | cases | `test-fix` | — |
| profile not found / validate-profile ERROR | scaffold | `test-scaffold` | — |
| fixture 缺方法 / 缺认证 / 缺 env / 缺 cleanup | scaffold | `test-scaffold incremental` | — |
| `--check` stale | codegen | `test-codegen` | — |
| UNPARSED 过多 | codegen 或 scaffold | 先 `--dump-ir` 看 strategy 来源：emitter 规则缺失 → `test-codegen`；fixture 能力缺失 → `test-scaffold` | 列两候选让用户选 |
| pytest collect 失败 | codegen 或 scaffold | `python -c "import ast; ast.parse(open(f).read())"` 语法错误 → `test-codegen`；ImportError → `test-scaffold` | 按错误类型判定 |
| 测试执行失败 | execution | 读 `report.md` 分流：`ASSERTION_FAILURE` → `test-fix`；`TEST_SCAFFOLD_ERROR` → `test-scaffold`；`PRECONDITION_MISSING` / `ENVIRONMENT_ERROR` → 补 env/服务；SUT bug → 记录 `results/` | — |
| 重复 case_body / case_flow 模式稳定 | emitter | `emitter-build` | — |

## codegen 诊断模式

路由时只需要关心这条诊断链：`--validate-profile`（profile 门禁）→ `--check`（同步性）→ 无参数（生成）→ `--dump-ir` / `--explain`（排查 IR 来源）。

完整模式细节见 `CLAUDE.md` codegen 可移植架构节和 `docs/usebook/codegen_troubleshooting.md`。

## 验证命令序列

修复后按顺序执行到全部通过：

```bash
aitest codegen --suite-file <suite.yaml> --validate-profile
aitest codegen --suite-file <suite.yaml> --check
aitest run --suite-file <suite.yaml> -- --collect-only -q
```

服务就绪时：

```bash
aitest run --suite-file <suite.yaml>
```

聚合验证：

```bash
aitest codegen --target <target> --check
aitest codegen --task-file test_workspace/tasks/<task>.yaml --check
# 最后兜底才使用：
aitest codegen --all --check
```

## 废弃/删除影响面模板

删除或废弃 case 前，填写此清单并提交给用户确认：

```markdown
| 项目 | 值 |
|------|-----|
| case_id | |
| Markdown 源文件 | |
| suite profile 条目 | |
| module profile 条目 | |
| generated pytest 函数 | |
| 删除原因 | |
| 回滚方式 | |
```

默认建议 `retire`（保留历史、标注不再执行），用户明确要求后才 `delete`。
