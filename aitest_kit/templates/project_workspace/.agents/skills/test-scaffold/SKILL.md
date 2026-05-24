---
name: test-scaffold
description: 从 Markdown 用例 + API 文档构建模块 fixture 和 codegen profile，填补 test-design 到 test-codegen 之间的缺口
when_to_use: 当模块已有 Markdown 用例但缺少 fixture 或 codegen profile 时，或首次将新模块接入 codegen 管线时
argument-hint: <target_module> [--incremental]
arguments: [target_module, incremental]
user-invocable: true
allowed-tools: Read Glob Grep Write Edit Bash Agent
effort: high
---

# 测试脚手架构建

为 `$target_module` 模块构建 fixture 和 codegen profile，使其能进入 `test-codegen` 管线。

## 定位

```
test-design 产出 Markdown 用例
  ↓
  test-scaffold ← 本 skill
  ↓
test-codegen 消费 fixture + profile 生成 pytest
```

## 产出

| 文件 | 职责 |
|------|------|
| `fixtures/{module}.py` | Client 类 + setup/teardown fixture |
| `codegen_profile_{module}.md` | module_type、case_flows/case_bodies、assertion_rules、request_overrides |
| `api_map_{module}.md` | API 面 + env 契约 + 可行性判定（scaffold 过程产物，保留供 review） |

所有文件路径相对于 `test_workspace/tests/fixtures/`。

## 哲学

AI 探索：理解 API 面、设计 Client、判断生成路线、写 case_flow。
Skill 保障：分步交互、结构化数据流、验证闭环。
用户 review 每一层设计决策，不面对黑盒最终产物。

## 代码阅读边界

默认不读待测系统源码。docs/、knowledge/、cases/ 不足时，列出缺口请求用户确认后读 API 声明层。

允许读取：路由/端点声明、请求/响应 schema、认证/中间件配置、启动配置。
禁止读取：handler body 业务逻辑、数据库模型/查询、内部服务调用、算法/策略。

读取过的 API 声明层文件记录到 `api_map_{module}.md`。

## Step 0：模式选择

确认：**模块名** + **模式**（full / incremental）。

### full 模式

模块尚无 fixture 和 profile，从头执行 Step 1 到 Step 9。

### incremental 模式

1. 读取现有 fixture + profile
2. 对比 cases/ 与 profile，识别新增 case_id，列出让用户确认
3. 对新增 case 执行 Step 3 + Step 4
4. 如需新端点方法，回到 Step 2 扩展 Client
5. Step 6 → Step 7 追加 profile 条目（不重写已有条目）
6. Step 8 验证闭环

## Step 1：提取 API Map

**子 Agent 适用**：读大量源材料，产出紧凑文档。

提取来源优先级：cases/ 共享配置 → docs/knowledge → 代码 API 声明层（需用户确认）。

产出 `api_map_{module}.md`，格式：

```markdown
# API Map: {module}

## 端点

| Method | Path | 认证 | 用途 |
|--------|------|------|------|

## 认证
- 方式和位置（header/query/cookie）
- 缺失/无效凭证的预期行为

## 请求体参考
### {endpoint}
{合法 JSON 示例}

## 环境变量

### 连接层（必须有才能发请求）
- {PROJECT}_BASE_URL — 服务地址

### 认证层（必须有才能鉴权）
- {PROJECT}_USER_TOKEN — 用户 token

### 资源层（特定 case 需要的已存在资源 ID）
- {PROJECT}_INACTIVE_KEY_ID — 已停用的 API Key

### 业务层（可替换的测试输入）
- （无，或注明来源）

## 信息缺口
- {无法从现有来源确认的信息}
```

环境变量必须分层。分层在此步完成，后续步骤继承。

**用户确认**：端点列表、认证模式、env 分层、信息缺口。

## Step 2：设计 fixture Client

基于已确认的 API Map 设计方法签名。交付物是签名表，不是完整代码：

```
class {Module}Client:
    __init__(base_url, auth_token)     # auth_token: required, 缺失时 fail
    post_messages(model, messages)     → Response  [auth: yes]
    get_usage(start, end)              → Response  [auth: yes]
    get_public_models()                → Response  [auth: no]
    create_api_key(name)               → Response  [auth: yes, 状态变更: 创建]
    delete_api_key(key_id)             → Response  [auth: yes, 状态变更: 删除]
```

每个方法标注：
- **auth 需求**：yes/no。标 yes 的方法，Client 在 `__init__` 中对 auth 参数 fail-fast
- **状态变更**：创建/修改/删除（有则标注，无则省略）

设计原则：
- 每个端点一个方法，方法名反映动作，不做 `run_case(case_id)` 分发
- 返回 `httpx.Response`，断言在 profile/test 层
- `httpx.Client(transport=httpx.HTTPTransport())`
- 环境变量驱动，不硬编码

首次创建前读其他模块 fixture 参考项目惯例。

**用户确认**：方法粒度、命名、auth 标注。

## Step 3：环境变量契约

**子 Agent 适用**：扫描 case 文件提取 env 需求。可与 Step 2 并行。

输入：api_map 的分层 env 定义 + cases/ 全部文件。
产出：case → env 矩阵，**追加写入 api_map_{module}.md**。

```markdown
## Case 环境变量矩阵

| case_id    | required env          | optional env | 缺失行为 |
|------------|-----------------------|-------------|---------|
| TC-XXX-001 | BASE_URL, USER_TOKEN  |             | fail    |
| TC-XXX-010 | BASE_URL              | USER_TOKEN  | 测试无认证场景 |
```

分类规则：
- 认证类 env（token、API key、password）：默认 required，除非 case 明确测试"缺失认证"
- 资源标识类 env（key_id、user_id）：required
- 连接类 env（BASE_URL）：始终 required
- 可选功能 env：optional，注明缺失行为

矩阵写入 api_map 后，Step 5 生成 fixture 时显式引用此矩阵生成 env check 代码。

**用户确认**：哪些变量是真实凭证、CI 中能否自动获取。

## Step 4：状态影响与可行性判定

**子 Agent 适用**：扫描 case 的请求动作和前置条件。可与 Step 3 并行。

产出两部分，**追加写入 api_map_{module}.md**：

### 状态影响表

```markdown
## 状态影响分析

| case_id    | 动作类型 | 创建资源？ | 唯一值？ | cleanup？ | 幂等？ |
|------------|---------|-----------|---------|----------|-------|
| TC-XXX-001 | 查询     | 否        | 否      | 否       | 是    |
| TC-XXX-003 | 创建 Key | 是        | 是(name)| 是(delete)| 否   |
| TC-XXX-008 | 注册     | 是        | 是(email)| 无API   | 否    |
```

### 可行性判定

非幂等且无 cleanup API 的 case 默认标为可行性存疑。

```markdown
## 自动化可行性判定

可执行：TC-XXX-001, TC-XXX-002, TC-XXX-003, ...
可行性存疑（保持 skipped）：TC-XXX-008
  原因：注册邮箱不可重复且无删除 API
```

可行性判定是 Step 7 的显式输入——skip_list 中的 case 不生成 case_flow/case_body。

**用户确认**：非幂等 case 是否可接受、cleanup 策略、是否需要测试专用资源、固定值是否改为动态生成。用户可以将可行性存疑的 case 移入可执行或确认保持 skipped。

## Step 5：生成 fixture + conftest 接线

基于已确认的 Step 2（Client 签名 + auth 标注）和 api_map 中的 env 矩阵生成 `fixtures/{module}.py`。

### 数据流

- `__init__` 参数和 fail-fast 逻辑 → 从 Step 2 的 auth 标注 + api_map 的 env 分层生成
- cleanup 方法 → 从 Step 4 的状态影响表中 cleanup=是 的条目生成
- env check 粒度 → 从 Step 3 的 case 矩阵生成（哪些方法需要哪些 env）

### 结构

```python
class {Module}Client:
    def __init__(self, base_url: str, auth_token: str, ...):
        self._client = httpx.Client(transport=httpx.HTTPTransport())
        ...

    def {endpoint_method}(self, ...) -> httpx.Response:
        ...

@pytest.fixture
def setup_{module}() -> {Module}Client:
    base_url = os.environ.get("{PROJECT}_BASE_URL")
    if not base_url:
        pytest.fail("{PROJECT}_BASE_URL is required")
    return {Module}Client(base_url, ...)
```

### 硬约束

1. **auth fail-fast** — auth 标注为 yes 的方法，对应的 env var 缺失时 `pytest.fail()`，不构造空 header
2. **注入模型二选一** — fixture 返回 Client 实例（`object: client`）或 factory（`object: client_factory`），不混用
3. **不做 case_id 分发** — 不生成 `run_case(case_id)` / `assert_case(case_id, resp)` 分发 dict
4. **不 import 待测系统内部模块**
5. **不硬编码 URL、端口、API key、密码**

### 测试数据分类

| 类别 | 处理方式 | 示例 |
|------|---------|------|
| 凭证类 | env var, fail-fast | token, password, API key |
| 唯一资源 | 动态生成（uuid/timestamp） | email, name, request_id |
| 非法输入 | 可固定 | 不存在的模型名 |
| 业务输入 | 可固定，注明来源 | 日期窗口、模型名 |

### conftest 接线（原子步骤）

生成 fixture 文件后，立即检查 `test_workspace/tests/conftest.py`：
- 如果项目使用 `pytest_plugins` 注册机制，确认新模块已在列表中
- 如果不在，追加注册
- 运行 `pytest --collect-only` 验证 fixture 可被发现

fixture 生成和 conftest 接线是同一步骤的两个子步骤，不分开。

## Step 6：Profile 模式确认

### auto_fields 判断

判断是否配置 `project_config.yaml` 的 `default_request.auto_fields`。核心规则：只要有一个关键点不确定就不配置。多端点模块优先用 fixture Client + case_flows。只输出判断，不直接修改配置。

### 路线决策

**第一级：module_type 定基线**

实际可用的 module_type 从 `project_config.yaml` 的 `module_types` 读取。

| module_type | 基线路线 |
|-------------|----------|
| `standard_http` | 默认模板 |
| `multi_endpoint` | case_flow |
| `isolated_service` | case_flow |

**第二级：逐条 case 从简到繁评估**

1. 默认模板够吗？→ 只需 request_overrides
2. 加 assertion_rules 够吗？→ 增加 profile assertion_rules
3. 需要 case_flow？→ 多步骤 / 特定 Client 方法 / 中间变量
4. 需要 case_body？→ 条件分支、循环、mock、并发 → 记录保留原因

**api_map 中标为 skipped 的 case 不参与路线评估。**

### 挑选代表性 case

从可执行 case 中挑 1-2 条最有代表性的（标准是代表性，不是路线覆盖），展示完整 profile 片段：路线理由、fixture/object、steps、断言。说明选择原因。

### profile 结构规则

单 YAML 代码块，所有字段在同一块中。不需要的顶层字段省略。

```yaml
module_type: {type}
extra_imports:
  - "from test_workspace.tests.fixtures.{module} import setup_{module}"

fixture: setup_{module}
object: client

request_overrides:
  TC-XXX-001:
    field_name: value

assertion_rules:
  - name: "..."
    regex: "..."
    template: "..."

case_flows:
  TC-XXX-001:
    steps:
      - call: client.method_name
        save_as: http_resp
      - assign: resp
        expr: http_resp.json()
      - assert: 'assert http_resp.status_code == 200'

case_bodies:
  TC-XXX-002: |
    # reason: 需要 mock transport
    resp = client.call(...)
    assert resp.status_code == 200
```

### fixture 注入一致性

**方案 A（推荐）**：fixture 返回 Client → `object: client` → fixture 不出现在 steps 里。
**方案 B**：fixture 返回 factory → `object: client_factory` → 第一步 `call: client_factory`。

禁止混用（`fixture: setup_xxx` + `object: client` + steps 首步 `call: setup_xxx` → 双重赋值）。

### case_flow 规则

- steps 只用 `call` / `assign` / `assert` / `comment`
- `assert` 以 `assert ` 开头，是可执行 Python
- 不塞 if/loop/try，复杂逻辑下沉到 fixture/helper
- kwargs 值为合法 Python 字面量或 ref 引用

**用户确认**：路线选择、step 结构、断言充分性。

## Step 7：生成全量 profile

**子 Agent 适用**。

子 Agent 输入（全部为已确认的结构化文档）：
- Step 6 确认的 profile 模式样本
- cases/ 全部文件
- Client 方法签名（Step 2）
- api_map 中的 env 矩阵（Step 3）
- **api_map 中的 skip_list（Step 4）**— skip_list 中的 case 不生成 case_flow/case_body

输出：完整 `codegen_profile_{module}.md`。

路线选择记录附在 profile 末尾或输出摘要中：

```
TC-XXX-001: structured_case_flow — 多步骤
TC-XXX-004: manual — 需要人工检查
TC-XXX-008: skipped — 可行性存疑（非幂等，无 cleanup）
```

**用户确认**：路线分布统计 + 特殊标注的 case。

## Step 8：验证闭环

```bash
# 1. conftest 接线验证
python3 -m pytest test_workspace/tests/generated/ --collect-only -q 2>&1 | head -5

# 2. profile 门禁
python3 -m aitest_kit.cli codegen $target_module --validate-profile

# 3. Case IR 观测
python3 -m aitest_kit.cli codegen $target_module --dump-ir

# 4. 生成
python3 -m aitest_kit.cli codegen $target_module

# 5. 一致性校验
python3 -m aitest_kit.cli codegen $target_module --check

# 6. 语法 + 收集
python3 -m compileall test_workspace/tests/fixtures/{module}.py test_workspace/tests/generated
python3 -m pytest test_workspace/tests/generated/test_{module}_*.py --collect-only -q
```

| 命令 | 预期 | 失败时 |
|------|------|--------|
| collect（全量） | fixture 被发现 | 检查 conftest pytest_plugins 注册 |
| `--validate-profile` | 无 ERROR | 修 profile YAML |
| `--dump-ir` | strategy 符合 Step 6 路线 | 修 case_flow/case_body 映射 |
| `codegen` | 生成 .py | 检查 import 路径 |
| `--check` | 无 stale | 重新 codegen |
| compileall | 无语法错误 | 修 Python 片段 |
| collect（模块） | 数量 = 可执行 case 数 | 检查 fixture 注册和 import |

collect 预期数量 = 总 case - skipped - manual，不追求最大化。

## Step 9：跨模块 review（第 2+ 模块时）

检查跨模块可复用模式，只标记和建议，不自动提取：
- Client 重复模式（auth header）→ helpers/ 或 base Client
- 相同 assertion 模式 → project_config builtin_assertion_rules
- 相似 case_flow 结构 → named flow template 候选

## 子 Agent 策略

| 步骤 | 任务 | 输入 | 输出 |
|------|------|------|------|
| Step 1 | 提取 API Map | cases/、docs/、代码 API 层 | api_map（~1 页） |
| Step 3 | 扫描 env var | cases/、api_map env 分层 | case env 矩阵（追加到 api_map） |
| Step 4 | 扫描状态影响 | cases/、api_map | 状态影响表 + skip_list（追加到 api_map） |
| Step 7 | 生成全量 profile | cases/、确认的模式、签名、skip_list | profile 文件 |

并行：Step 1 确认后，Step 2（主 Agent）与 Step 3 + 4（子 Agent）可并行。
case < 10 条时主 Agent 直接处理也可。

api_map 是全流程的结构化中间文档。Step 3、Step 4 的产出追加写入 api_map，后续步骤从 api_map 读取，不依赖 AI 跨步骤记忆。

## 边界

允许：读 docs/knowledge/cases/、经确认读 API 声明层、读其他模块 fixture/profile、读 project_config、创建/修改 fixtures/ 和 api_map、运行验证命令、更新 conftest.py 的 pytest_plugins 列表。

禁止：读业务逻辑、改 generated/、改 .env、硬编码凭证、编造 API 行为、import 待测系统、改待测系统代码、生成 case_id 分发表。

## 完成标准

1. `fixtures/{module}.py` 存在且 `compileall` 通过
2. `codegen_profile_{module}.md` 存在且 `--validate-profile` 无 ERROR
3. `--dump-ir` 中每条 case 的 strategy 符合预期
4. `codegen --check` 通过
5. conftest 已注册，`pytest --collect-only` 收集数 = 可执行 case 数
6. api_map 包含 env 分层 + case 矩阵 + 可行性判定
7. 可行性存疑 case 已经用户确认处理方式

scaffold 完成意味着"能进入 codegen 管线"，不意味着"测试通过"。真正连服务跑测试是 `aitest run` 的职责。

## 输出摘要

```markdown
## test-scaffold 摘要

模块：{module}
模式：full / incremental
module_type：{type}

创建/修改文件：
- fixtures/{module}.py — Client 类 + setup fixture
- codegen_profile_{module}.md — profile
- api_map_{module}.md — API 面 + env 契约 + 可行性判定
- conftest.py — pytest_plugins 注册（如需）

Client 方法：
- {method_name}({params}) [auth: yes/no]

路线分布：
- default_http/grpc：{N} 条
- structured_case_flow：{N} 条
- custom_case_body：{N} 条（附保留原因）
- manual：{N} 条
- skipped（可行性存疑）：{N} 条

环境变量（分层）：
- 连接层：{VAR} — required
- 认证层：{VAR} — required
- 资源层：{VAR} — required
- 业务层：{VAR} — optional

验证结果：
- validate-profile: {PASS/FAIL}
- codegen --check: {PASS/FAIL}
- collect: {N} / {可执行 case 数}

下一步：
- 配置环境变量后执行 `aitest run {module}`
- 或调用 `/test-codegen {module}` 处理 UNPARSED（如有）
```
