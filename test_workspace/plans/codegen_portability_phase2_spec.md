# Codegen 可移植层 Phase 2 Spec

## 背景

`aitest_kit/codegen/emitter.py` 同时包含通用生成引擎和本项目专属配置：

- helper import、API path、变量映射、模块缩写硬编码在 `ProjectConfig`。
- 内置断言规则通过 `_match_*` / `_render_*` Python 函数硬编码。
- named template 可用名称硬编码。

这些内容切换项目时应通过配置替换，通用 emitter 不应承载项目专属规则。

## 目标

1. 新增 `aitest_config/project_config.yaml`，承载项目级 codegen 配置。
2. emitter 从 YAML 加载 `ProjectConfig`；YAML 不存在时保留 Python fallback。
3. 内置断言规则使用与 profile `assertion_rules` 兼容的规则对象，支持：
   - `pattern` 子串匹配。
   - `regex` 正则匹配和命名分组插值。
   - `template` 多行 Python 模板。
   - `params` 传递给 named templates。
4. 断言解析优先级固定为：profile rules > project_config builtin rules > named templates。
5. profile 支持 `module_type`，按 project config 的 `module_types[*].requires` 做生成前校验。
6. `emitter.py` 保持小于 500 行；通用渲染工具拆入独立模块。

## 文件影响

- 新增 `aitest_config/project_config.yaml`
- 新增 `aitest_kit/codegen/project_config.py`
- 新增 `aitest_kit/codegen/profile.py`
- 新增 `aitest_kit/codegen/render_utils.py`
- 修改 `aitest_kit/codegen/emitter.py`

## 非目标

- 不改变合法 Markdown 的 parser 行为。
- 不改变正常模块生成出的 pytest 内容。
- 不引入新依赖。
- 不调整各模块测试语义。

## 验证

1. `python3 -m compileall aitest_kit/codegen`
2. `python3 -m aitest_kit.cli codegen --all --check`
3. 临时非法 JSON 模块应输出 E001 且 blocked。
4. 临时移走 `aitest_config/project_config.yaml` 后，`python3 -m aitest_kit.cli codegen --all --check` 仍通过 fallback。
5. `wc -l aitest_kit/codegen/emitter.py` 小于 500。
