# AITest Workspace Template Spec

## 背景

当前 `AIAutoTest` 仓库同时承担三种职责：

1. 框架研发：`aitest_kit/`、codegen、Case IR、profile gate、health/promotion。
2. 示例待测系统：`coupon_system/`、`ab_experiment_sdk/`。
3. 当前项目测试资产：`docs/`、`aitest_config/`、`test_workspace/knowledge`、`test_workspace/cases`、`test_workspace/tests`、`test_workspace/results`。

这种结构适合我们研发和演练，但不适合直接交给新用户。用户拉下仓库后，如果想给自己的项目设计测试，会看到已有知识库、历史用例、生成代码和示例系统混在一起，容易误以为这些都是必须复用的项目资产。

## 目标

把协作模型整理成三层：

| 层级 | 内容 | 换项目时是否复用 |
|---|---|---|
| 框架层 | `aitest_kit/`、codegen、profile schema、CLI、通用 workflow | 复用，不写项目业务规则 |
| 项目工作区模板 | 空白 `aitest_config/`、`test_workspace/`、基础 helper、模板说明 | 新项目从这里复制或初始化 |
| 示例层 | coupon、discount 等完整迁移案例 | 只用于学习和对照，不作为默认工作区 |

最终用户体验应该是：

```bash
pip install aitest-kit
cd /path/to/user_project
aitest init
```

本轮按阶段推进到可用状态：先保留可人工复制的干净模板，再补齐 `aitest init` 和 `--workspace`，示例层先做索引隔离，不物理搬迁现有示例资产。

## 非目标

本阶段不做以下事情：

- 不移动现有 `coupon_system/`、`ab_experiment_sdk/`。
- 不搬迁当前根目录下的 `test_workspace/`。
- 不把当前 coupon/discount 的知识库、用例、profile 复制进模板。
- 不拆成多个仓库。
- 不修改被测系统代码。

## 目标结构

第一阶段新增：

```text
templates/
└── project_workspace/
    ├── README.md
    ├── .gitignore
    ├── .codex/
    │   └── skills/
    │       └── README.md
    ├── aitest_config/
    │   ├── config.yaml
    │   ├── project_config.yaml
    │   └── schemas/
    │       └── codegen_profile.schema.json
    ├── docs/
    └── test_workspace/
        ├── knowledge/
        │   ├── TEST_SPEC.md
        │   ├── L1/
        │   └── L2/
        ├── cases/
        ├── tests/
        │   ├── __init__.py
        │   ├── conftest.py
        │   ├── fixtures/
        │   ├── generated/
        │   └── helpers/
        ├── results/
        └── plans/
```

模板必须保持空白项目属性：

- 不包含当前示例项目的模块名、API path、Redis key、业务断言公式。
- 不包含 `coupon_system` / `ab_experiment_sdk` 的导入。
- `generated/` 作为编译产物，只保留包初始化文件和占位目录。
- `.codex/skills` 只说明 skill 分发方式，不把项目经验硬编码进模板。

## 关键规则

### 1. 用户不要直接复用当前根 `test_workspace`

当前根 `test_workspace/` 是 AIAutoTest 示例和研发现场。新项目应从 `templates/project_workspace/` 创建干净工作区，再逐步生成知识库、用例、profile 和 fixture。

### 2. 项目差异只进入配置层和工作区

换项目时优先修改：

- `aitest_config/config.yaml`
- `aitest_config/project_config.yaml`
- `test_workspace/knowledge/`
- `test_workspace/cases/`
- `test_workspace/tests/fixtures/{module}.py`
- `test_workspace/tests/fixtures/codegen_profile_{module}.md`

不要因为项目不同就修改 `aitest_kit/codegen` engine 或通用 skill，除非确认是框架能力缺失。

### 3. 模板不应携带旧项目默认地址

模板中的 pytest fixture 使用环境变量 fail fast：

```python
base_url = os.environ.get("AITEST_HTTP_BASE_URL")
if not base_url:
    pytest.fail("AITEST_HTTP_BASE_URL is required for generated HTTP tests")
```

模块级 fixture 迁移时应进一步改成项目专属变量，例如 `DISCOUNT_SYSTEM_BASE_URL`。不能回退到旧项目的 `HTTP_BASE_URL` 或硬编码 localhost。

### 4. Markdown 是源文件，generated 是编译产物

模板中的 `.gitignore` 默认忽略 generated 测试产物，只保留目录结构。项目是否提交 generated pytest 由用户仓库自行决定。

### 5. profile schema 随模板交付

`codegen_profile.schema.json` 属于结构契约。新项目本地应有一份 schema，避免 profile gate 在脱离 AIAutoTest 仓库后找不到校验文件。

### 6. skill 尽量稳定

通用 skill 表达流程，不携带具体项目业务规则。项目经验沉淀优先进入：

- `TEST_SPEC.md`
- `project_config.yaml`
- `codegen_profile_{module}.md`
- fixture/helper
- `case_flows`

## 分阶段计划

### Phase 1：模板化工作区

本阶段完成：

- 新增 `templates/project_workspace/`。
- 新增模板 README，说明如何从空白工作区接入新项目。
- 新增空白 `aitest_config/config.yaml` 和 `project_config.yaml`。
- 新增基础 pytest 目录、fail-fast `conftest.py` 和通用 HTTP/Redis helper。
- 新增 gRPC helper stub，明确 gRPC 项目必须自行实现 protobuf 适配。
- 更新迁移 playbook，明确不要复用当前根 `test_workspace`。
- 更新用例格式文档，去掉 HTTP JSON 中 `{{placeholder}}` 的旧描述。

验收标准：

- `templates/project_workspace` 不包含 coupon/discount 业务内容。
- 模板 Python 文件能 compile。
- 文档明确三层结构：框架层、项目模板层、示例层。

### Phase 2：初始化命令

本阶段实现：

```bash
aitest init --target /path/to/project
```

- 复制 `templates/project_workspace`。
- 已有文件时默认拒绝覆盖。
- 提供 `--force` 覆盖模板管理文件；不实现自动 merge。
- 初始化后输出下一步命令清单。
- 同步 setuptools package data，确保模板和 schema 随 `aitest-kit` 安装。

验收标准：

- `aitest init --target <dir>` 能在空目录或已有项目目录中创建 AITest 工作区。
- 目标文件已存在时默认失败，不覆盖用户内容。
- `--force` 明确覆盖模板文件并输出覆盖数量。
- 初始化后的工作区包含 profile JSON Schema。

### Phase 3：workspace 参数

本阶段实现：

```bash
aitest codegen discount_policy --workspace /path/to/project
```

或约定：

```bash
cd /path/to/project
aitest codegen discount_policy
```

需要支持的路径：

- `aitest_config/config.yaml`
- `aitest_config/project_config.yaml`
- `test_workspace/cases`
- `test_workspace/tests/fixtures`
- `test_workspace/tests/generated`
- `test_workspace/reports/codegen/latest`

验收标准：

- `codegen` 在 `--workspace` 下读取目标工作区的 config/cases/profile/schema。
- generated 文件写入目标工作区。
- `run` 和 `report` 支持同样的 `--workspace` 参数。
- 在项目目录内直接执行命令时仍保持兼容。

### Phase 4：示例目录隔离

本阶段先做非破坏性的示例索引隔离。当前示例资产仍保留在原位置，并新增：

```text
examples/
├── coupon_system/
└── discount_policy/
```

索引文档记录每个示例的当前位置、边界和参考价值。物理移动会影响大量文档、测试路径和导入，不在本轮执行；若未来要移动，单独写迁移 spec。

### Phase 5：拆仓评估

本阶段完成评估结论，不执行拆仓。候选拆分形态是：

```text
aitest-kit
aitest-template
aitest-examples
```

当前结论：暂不拆仓。原因是框架仍在快速演进，拆仓会放大模板、schema、skill、示例之间的同步成本。先用 `aitest init`、`templates/project_workspace` 和 `examples/` 索引把边界钉稳。

## 风险与控制

| 风险 | 控制 |
|---|---|
| 模板过重，变成第二个示例项目 | 模板只放空白结构和通用 helper，不放业务数据 |
| 模板过轻，用户不知道怎么开始 | README 写清第一条链路和必须配置项 |
| skill 和项目经验继续混杂 | skill 只描述流程，业务差异进入 TEST_SPEC/profile/config |
| CLI 仍依赖当前工作目录 | Phase 2/3 支持 init/workspace，并保留 `cd project` 的兼容路径 |
| 当前示例资产被误删或误搬 | Phase 1 不移动示例资产 |

## 当前结论

迁移演练已经证明测试飞轮可以迁移到新系统。下一步不是继续加项目规则，而是把仓库整理成：

```text
核心框架 + 干净模板 + 示例参考
```

本轮先把 `templates/project_workspace`、`aitest init`、workspace 参数和 examples 索引落地。拆仓只保留评估结论，等框架稳定后再决定。
