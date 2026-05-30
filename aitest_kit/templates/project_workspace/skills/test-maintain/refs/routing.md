# test-maintain 路由参考

## 症状 → 断裂层映射

| 症状 | 断裂层 | 路由 |
|------|--------|------|
| 需求规则未进入知识库 | knowledge | `knowledge-build` |
| 缺用例 / 用例过时 | cases | `test-design` |
| 单条用例错误 | cases | `test-fix` |
| profile not found / validate-profile ERROR | scaffold | `test-scaffold` |
| fixture 缺方法 / 缺认证 / 缺 env / 缺 cleanup | scaffold | `test-scaffold incremental` |
| `--check` stale | codegen | `test-codegen` |
| UNPARSED 过多 | codegen | `test-codegen`（可能回退到 scaffold） |
| pytest collect 失败 | codegen 或 scaffold | 语法问题 → `test-codegen`；fixture 接线 → `test-scaffold` |
| 测试执行失败 | execution | 分流：用例问题 → `test-fix`；fixture → `test-scaffold`；SUT → 记录 `results/` |
| 重复 case_body / case_flow 模式稳定 | emitter | `emitter-build` |

## codegen 模式速查

详细口径以 `CLAUDE.md` 和 `docs/usebook/` 为准；需要细节时先读取这些文档。

| 模式 | 用途 | 适用范围 |
|------|------|----------|
| `--dry-run` | 只解析 Markdown，不进 profile gate，不写 generated | suite/task/target/module/all |
| `--validate-profile` | 校验 profile schema、case_id 对齐、语义 | suite/task/target/module/all |
| `--check` | diff generated 与当前源头，不写 generated | suite/task/target/module/all |
| 无特殊参数 | 正式生成 pytest | suite/task/target/module/all |
| `--dump-ir` | 输出 Case IR JSON，排查 strategy 来源 | 仅 `--suite-file` |
| `--explain <TC-ID>` | 单条 case 的 IR 解释 | 仅 `--suite-file` |
| `--health-report` | 成熟度和健康度报告 | suite/target/module |
| `--analyze-promotion` | case_bodies 晋升分析 | suite/target/module |
| `--suggest-promotion-patch` | review-only 晋升草案 | 仅 `--suite-file` |

模块级沉淀先用 `--health-report` 和 `--analyze-promotion` 获得聚合证据，修改 profile/helper 前仍需路由 `emitter-build` 和人工 review。

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
