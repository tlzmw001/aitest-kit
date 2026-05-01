# AIAutoTest

AI 驱动的自动化测试工具，基于 Claude Code Skill 编排"文档 → 知识库 → 用例 → 执行"全流程。

## 项目结构

```
coupon_system/          # 待测系统：智能优惠券推荐策略服务（FastAPI + gRPC + Redis）
docs/                   # 开发文档输入目录（skill 的输入源）
test_workspace/         # AI 生成内容的工作目录
  knowledge/            #   测试知识库（L0/L1/L2 + TEST_SPEC）
  cases/                #   测试用例（Markdown，按模块分目录）
  tests/                #   pytest 测试代码
    conftest.py         #     全局 session fixtures
    fixtures/           #     模块 fixture（每模块一个 .py + codegen_profile.md）
    helpers/            #     HTTP/Redis 等测试工具函数
    generated/          #     codegen 生成的 pytest 文件（编译产物）
  results/              #   待测系统 bug 记录
  plans/                #   方案文档
aitest_kit/             # Python 测试工具库（parser、emitter、CLI）
aitest_config/          # 项目级配置
  config.yaml           #   skill 路径配置
  project_config.yaml   #   codegen 项目配置（import 路径、断言规则、模块缩写等）
.claude/skills/         # Claude Code Skill 定义
  doc-gen/              #   设计文档生成（从源码）
  doc-review/           #   设计文档审查
  knowledge-build/      #   测试知识库构建/更新
  test-design/          #   测试用例设计
  test-codegen/         #   Markdown → pytest 代码生成（emitter + AI 补全）
  test-fix/             #   用例修正 + 经验沉淀
  emitter-build/        #   从已验证 .py 提取确定性模板
```

## 常用命令

```bash
# 安装依赖
pip install -e ".[dev,server]"

# 启动待测系统
python -m coupon_system.main

# 运行单测
pytest tests/
```

## 技术栈

- Python 3.9+
- FastAPI + gRPC（待测系统）
- httpx + grpcio（测试客户端）
- Redis（数据层）

## 测试飞轮工作流

七个 skill 构成一条闭环流水线，分为**设计阶段**和**执行阶段**：

```
── 设计阶段 ──

docs/（开发文档）
  ↓
doc-review  ── 审查文档完整性，输出缺口清单
  ↓
doc-gen     ── 从源码补全缺失的设计文档（可选，文档不足时用）
  ↓
knowledge-build ── 从文档构建/更新测试知识库（L0/L1/L2）
  ↓
test-design ── 基于知识库 + TEST_SPEC 生成测试用例（Markdown）
  ↓
人工评审用例
  ↓
test-fix    ── 修正用例错误，沉淀经验到 TEST_SPEC 和相关 skill

── 执行阶段 ──

test-codegen ── Markdown 用例 → pytest 代码
  ↓
pytest 执行
  ↓
失败时分流：
  ├─ 用例问题 → test-fix → 重新 codegen
  └─ fixture/codegen 问题 → 更新 codegen_profile + fixture → 重新 codegen
  ↓
测试全部通过
  ↓
emitter-build ── 从已验证的 .py 提取确定性模板到 emitter
```

### test-codegen 流程细节

1. **parser 解析** — `python3 -m aitest_kit.codegen.parser` 确定性提取 Markdown 结构
   - 如果 JSON 块解析失败，parser 输出诊断信息（E001），不静默返回 None
2. **诊断门控** — parser 输出有 errors 时，codegen 终止并打印诊断 + 修复建议，不生成残缺 .py
3. **读取 profile** — 检查 `tests/fixtures/codegen_profile_{module}.md`，如果不存在则参考其他模块已有 profile 的结构
4. **emitter 生成** — `python3 -m aitest_kit.codegen.emitter` 确定性生成 .py
   - 断言匹配优先级：profile assertion_rules > project_config builtin_assertion_rules > named_templates
   - module_type 校验：profile 声明的模块类型必须满足 project_config 中该类型的 requires 字段
5. **生成后验证** — `ast.parse` + 未定义名检测（_req 等关键名是否存在）
6. **AI 补写 UNPARSED** — emitter 输出的 `# UNPARSED ASSERTION:` 由 AI 翻译为可执行断言（UNPARSED 为 0 时跳过）
7. **端到端验证** — `pytest test_workspace/tests/generated/ -v`
8. **经验沉淀** — 调试经验写入 `codegen_profile_{module}.md`，调用 `/emitter-build` 提取新规则

### 使用指引

- **首次接入新项目**：`/doc-review` → `/doc-gen`（按需）→ `/knowledge-build` → `/test-design`
- **需求迭代**：新文档放入 `docs/` → `/knowledge-build`（增量更新）→ `/test-design`（增量生成）
- **用例出错**：`/test-fix`（修用例 + 记 TEST_SPEC 陷阱 + 更新 skill）
- **生成 pytest**：`/test-codegen <模块名>`
- **只想看文档质量**：`/doc-review`

### 关键约定

- 测试知识库是用例设计的唯一输入源，不绕过知识库直接写用例
- Markdown 用例是唯一数据源，test-codegen 生成 pytest 代码执行
- TEST_SPEC 是所有 skill 的行为准则，经验教训统一沉淀在此
- 用例存放在 `test_workspace/cases/{模块名}/` 下，未指定时先询问用户
- 模块 fixture 按模块拆分到 `test_workspace/tests/fixtures/{module}.py`，conftest.py 只放全局 fixture
- codegen_profile 存放在 `test_workspace/tests/fixtures/codegen_profile_{module}.md`，与 fixture 文件同目录
- 项目结构或流程发生变更时，检查是否需要同步更新 `CLAUDE.md` 和 `README.md`，并询问用户是否需要更新 `docs/usebook/` 下的文档

## 测试执行注意事项

### 部署拓扑先行

设计 fixture 前必须确认服务的实际部署模式：
- 确认 `AB_SERVICE_URL`、`REDIS_URL`、`HTTP_BASE_URL` 等环境变量的实际值
- 确认服务间调用关系（本地 SDK vs 远程服务）
- 优先用运行时 API 操作（如 AB 白名单 CRUD），而非启动时环境变量注入

### httpx 系统代理

httpx 0.28+ 会自动读取 macOS 系统代理，`proxy=None` 无效。测试 helper 中必须用显式 transport：
```python
httpx.Client(transport=httpx.HTTPTransport())
```

### 测试角色边界

AI 的角色是测试工程师，不是被测系统的开发者：
- `coupon_system/`、`ab_experiment_sdk/` 下的源码和配置文件不得修改
- 只改测试代码：`test_workspace/`、`aitest_kit/`、`.claude/skills/`
- 通过被测系统已有的 API、环境变量、磁盘数据文件来构造测试条件
- 现有接口无法满足测试需求时，记录为"测试基础设施需求"让用户决定

## codegen 可移植架构

codegen 管线分三层，换项目时只改配置层，不改框架层：

```
┌─────────────────────────────────────────────────────┐
│  框架层（换项目不改）                                  │
│  - parser engine (parser.py)                        │
│  - emitter engine (emitter.py)                      │
│  - CLI (cli.py)                                     │
│  - 通用 helpers (http.py, redis_ops.py)              │
│  - skill 框架模板 (SKILL.md)                         │
├─────────────────────────────────────────────────────┤
│  项目配置层（换项目重写，YAML 格式）                    │
│  - aitest_config/config.yaml                        │
│  - aitest_config/project_config.yaml                │
│  - grpc_ops.py（项目专属 protobuf 封装）              │
├─────────────────────────────────────────────────────┤
│  模块配置层（每模块一份）                              │
│  - codegen_profile_{module}.md                      │
│  - fixtures/{module}.py                             │
└─────────────────────────────────────────────────────┘
```

### 首次接入新项目的 codegen 配置

1. 创建 `aitest_config/config.yaml`：声明路径映射、服务地址、协议偏好、已知限制
2. 创建 `aitest_config/project_config.yaml`：声明 helper import 路径、API 路径、变量映射、模块缩写、内置断言规则、模块映射
3. 每个模块创建 `codegen_profile_{module}.md`：声明 module_type、assertion_rules、request_overrides 等
4. 每个模块创建 `fixtures/{module}.py`：实现 setup/teardown 逻辑

### module_type 分类

codegen_profile 头部必须声明 module_type，emitter 根据类型校验必需字段：

| module_type | 适用场景 | 必需字段 |
|-------------|---------|---------|
| `standard_recommend` | 标准推荐接口模块 | 无额外要求 |
| `multi_endpoint` | 多端点服务模块 | case_bodies 或 endpoint_map |
| `subprocess_capture` | 需要隔离进程捕获输出 | case_bodies |
| `isolated_service` | 需要隔离服务实例 | case_bodies |

### Markdown 用例格式规范

Markdown 用例的共享配置格式是框架标准，所有项目统一使用以下 section 名（不可自定义）：

```markdown
## 共享配置
**接口**：`POST /api/v1/xxx`
**基础请求体（HTTP）**：
```json
{合法 JSON，不允许 {{var}} 占位符}
```
**基础请求体（gRPC）**：
```text
{protobuf 文本格式}
```
**标准前置**：
- 前置条件列表
**通用断言**：`response.code == 0`
**变量定义**：
- `var_name` = 定义
```

**关键规则**：
- `json` 代码块必须是严格合法 JSON，`json.loads` 必须能解析
- 变化字段用合法默认值填充（如 `"external": 0`），case 级差异通过 codegen_profile 的 request_overrides 声明
- 禁止 `{{var}}` 模板占位符出现在 JSON 块中

### 待测系统 bug 记录

测试发现的待测系统 bug 记录到 `test_workspace/results/`，不跳过、不放宽断言、不伪造成功响应。等待系统修复后重新执行验证。
