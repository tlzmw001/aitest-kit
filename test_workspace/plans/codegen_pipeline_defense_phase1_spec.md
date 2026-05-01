# codegen 管线防御层 Phase 1 Spec

## 目标

让 Markdown 基础请求体 JSON 非法、请求体缺失、生成文件语法错误等问题在对应边界直接报错并停止，不再漂移到 pytest 运行期才暴露为 `_req` 未定义。

## 修改范围

- `aitest_kit/codegen/parser.py`
  - `_extract_json_block` 返回 JSON 解析错误信息。
  - `_parse_shared_config` 收集诊断。
  - `parse_case_file` 填充已有 `ParseResult.errors`。
  - parser `__main__` 打印诊断。

- `aitest_kit/codegen/emitter.py`
  - `EmitResult` 增加 `diagnostics`。
  - `emit_file` 在生成前检查 parser errors。
  - `emit_file` 在缺少基础 HTTP 请求体且存在未被 `case_bodies` 覆盖的非 skip 用例时阻断生成。

- `aitest_kit/codegen/cli.py`
  - `codegen` 命令打印 diagnostics，标记 BLOCKED。
  - 对成功生成文件做 `ast.parse` 语法校验。
  - 最终统计区分 generated / blocked。
  - `--check` 临时生成时也应把 diagnostics 视为不一致。

## 不做

- 不改变合法 JSON 的解析结果。
- 不改变正常模块 generated 代码内容。
- 不引入新依赖。
- 不修改待测系统源码。

## 验证

1. `python3 -m aitest_kit.cli codegen calibration`
2. `python3 -m aitest_kit.cli codegen --all --check`
3. 临时构造非法 JSON 模块，确认 codegen 打印 `E001` 并拒绝生成。
4. 非 e2e generated 全量 pytest 回归。
