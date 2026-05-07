# AITest Project Workspace Template

这是新项目接入 AITest 测试飞轮的空白工作区模板。

它只包含目录结构、通用配置、基础 pytest fixture 和 helper，不包含任何示例项目的业务知识。

## 使用方式

推荐使用初始化命令：

```bash
aitest init --target /path/to/your_project
```

如果你正在 AIAutoTest 源码仓库内开发，也可以手工复制本目录内容到你的项目根目录：

```bash
cp -R templates/project_workspace/. /path/to/your_project/
```

然后在你的项目根目录执行后续流程。

## 初始目录

```text
aitest_config/
  config.yaml
  project_config.yaml
  schemas/codegen_profile.schema.json
docs/
test_workspace/
  knowledge/
  cases/
  tests/
    conftest.py
    fixtures/
    generated/
    helpers/
  results/
  plans/
```

## 首次接入步骤

1. 把开发文档、接口定义、配置样例放入 `docs/`。
2. 根据当前项目修改 `aitest_config/config.yaml`。
3. 根据当前项目修改 `aitest_config/project_config.yaml`。
4. 构建或更新 `test_workspace/knowledge/`。
5. 在 `test_workspace/cases/{module}/` 下生成并 review Markdown 用例。
6. 为模块创建 `test_workspace/tests/fixtures/{module}.py`。
7. 为模块创建 `test_workspace/tests/fixtures/codegen_profile_{module}.md`。
8. 把模块 fixture 注册到 `test_workspace/tests/conftest.py` 的 `pytest_plugins`。
9. 运行 profile gate、dump IR、codegen、pytest collect/run。

## 配置原则

- 不要把旧项目的 URL、端口、Redis key、业务规则复制进新项目。
- 不要在 JSON 基础请求体里写 `{{var}}` 占位符；写合法默认值，case 差异放到 `request_overrides`。
- 新项目 fixture 使用项目专属环境变量，并在缺失时 fail fast。
- generated pytest 是编译产物，优先修改 Markdown/profile/fixture/config 后重新生成。
- gRPC helper 需要按当前项目的 protobuf 自行实现，模板只提供明确报错的 stub。

## 推荐收口命令

```bash
python3 -m aitest_kit.cli codegen {module} --validate-profile
python3 -m aitest_kit.cli codegen {module} --dump-ir
python3 -m aitest_kit.cli codegen {module} --check
python3 -m aitest_kit.cli codegen {module}
python3 -m pytest test_workspace/tests/generated/test_{module}_*.py --collect-only -q
```

如果不想切换目录，可以使用 workspace 参数：

```bash
python3 -m aitest_kit.cli codegen {module} --workspace /path/to/your_project --validate-profile
python3 -m aitest_kit.cli run {module} --workspace /path/to/your_project
```

全量健康检查：

```bash
python3 -m aitest_kit.cli codegen --all --validate-profile
python3 -m aitest_kit.cli codegen --all --check
python3 -m pytest test_workspace/tests/generated --collect-only -q
```
