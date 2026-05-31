# test-codegen selector 参考

## selector 能力矩阵

| 入口 | 生成 | `--check` | `--dry-run` | `--validate-profile` | `--dump-ir` | `--explain` | `--health-report` | `--analyze-promotion` |
|------|------|-----------|-------------|----------------------|-------------|-------------|-------------------|-----------------------|
| `--suite-file` | 支持 | 支持 | 支持 | 支持 | 支持 | 支持 | 支持 | 支持 |
| `--task-file` | 支持 | 支持 | 支持 | 支持 | 不支持 | 不支持 | 不支持 | 不支持 |
| `--target --module` | 支持 | 支持 | 支持 | 支持 | 不支持 | 不支持 | 支持 | 支持 |
| `--target` | 支持 | 支持 | 支持 | 支持 | 不支持 | 不支持 | 支持 | 支持 |
| `--all` | 支持 | 支持 | 支持 | 支持 | 不支持 | 不支持 | 不支持 | 不支持 |

规则：

1. `--dump-ir` 和 `--explain` 是 suite 级诊断工具，只用于 `--suite-file`。
2. `--health-report` 和 `--analyze-promotion` 支持 suite/module/target，不支持 task/all。
3. `--suggest-promotion-patch` 只用于 suite 级 promotion review，不用于 selector 聚合模式。
4. `--case-id` 不属于 codegen selector。需要单 case 执行时使用 `aitest run --suite-file <suite.yaml> --case-id <TC-ID>`。

## 常用 selector 命令

### suite 级（诊断最完整）

```bash
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --validate-profile
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --dump-ir
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --check
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --explain TC-XXX
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --analyze-promotion --write-report
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --suggest-promotion-patch
python3 -m aitest_kit.cli codegen --suite-file <suite_dir>/suite.yaml --health-report --write-report
```

### task 级

```bash
python3 -m aitest_kit.cli codegen --task-file test_workspace/tasks/<task>.yaml --validate-profile
python3 -m aitest_kit.cli codegen --task-file test_workspace/tasks/<task>.yaml --check
python3 -m aitest_kit.cli run --task-file test_workspace/tasks/<task>.yaml -- --collect-only -q
```

### module/target 级

```bash
python3 -m aitest_kit.cli codegen --target <target> --module <module> --validate-profile
python3 -m aitest_kit.cli codegen --target <target> --module <module> --check
python3 -m aitest_kit.cli codegen --target <target> --module <module> --health-report --write-report
python3 -m aitest_kit.cli codegen --target <target> --module <module> --analyze-promotion --write-report

python3 -m aitest_kit.cli codegen --target <target> --validate-profile
python3 -m aitest_kit.cli codegen --target <target> --check
python3 -m aitest_kit.cli codegen --target <target> --health-report --write-report
python3 -m aitest_kit.cli codegen --target <target> --analyze-promotion --write-report
```

### all 级

```bash
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
```

## 聚合执行与报告

task / module / target / all 是聚合执行维度：

- `aitest run --task-file <task.yaml>` 写入 `test_workspace/reports/tasks/{task}/...`
- `aitest run --target <target> --module <module>` 写入 module 聚合 bucket
- `aitest run --target <target>` 写入 target 聚合 bucket
- `aitest run --all` 写入 all 聚合 bucket

聚合运行不会更新每个 suite 自己的 `latest/`。`aitest report` 重渲染时必须使用同一 selector，不能默认去 suite bucket 或旧顶层 latest。

## 能力缺口判定表

现有模块新增 Markdown 用例时的路由依据：

| 发现 | 处理 |
|------|------|
| 只是缺 `suite.yaml` 或 suite profile | 留在 `test-codegen`：创建 suite 元数据和 `profile_{suite}_suite.md` |
| 只是新增参数组合、断言组合或已有 client 方法的新调用顺序 | 留在 `test-codegen`：补 `variables/case_flows/request_overrides/assertion_rules` |
| 需要调用现有 fixture 没封装的新端点 | 切到 `test-scaffold incremental`：补 client/helper 方法后再回到 codegen |
| 需要新的认证方式、header、cookie、token 来源或 case-scoped env | 切到 `test-scaffold incremental`：补 env 契约和 fixture 注入 |
| 需要创建/清理测试数据或跨步骤状态管理 | 切到 `test-scaffold incremental`：补 setup/cleanup 能力 |
| 需要文件上传、流式响应、WebSocket、mock、外部依赖或复杂生命周期 | 切到 `test-scaffold incremental`，必要时允许 `case_bodies` |
| 只能靠大段 raw `case_body` 绕过 fixture 缺口 | 切到 `test-scaffold incremental`，先补测试能力再决定是否保留 `case_body` |
| generated 需要 import 当前 fixture/helper 中不存在的方法 | 切到 `test-scaffold incremental` |

简化判断：**只是新增用例表达 → test-codegen；需要新增测试调用能力 → test-scaffold incremental。**

## selector 级验证命令

已注册 suite 需追加 module/target selector 验证：

```bash
# module 级
python3 -m aitest_kit.cli codegen --target <target> --module <module> --check
python3 -m aitest_kit.cli run --target <target> --module <module> -- --collect-only -q

# target 级
python3 -m aitest_kit.cli codegen --target <target> --check
python3 -m aitest_kit.cli run --target <target> -- --collect-only -q

# all 级
python3 -m aitest_kit.cli codegen --all --check
python3 -m aitest_kit.cli run --all -- --collect-only -q
```
