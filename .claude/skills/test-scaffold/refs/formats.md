# test-scaffold 格式参考

## API Map 模板

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

## Case variables/env 矩阵

追加写入 api_map。

```markdown
## Case variables/env 矩阵

| case_id    | profile variables | required env | optional env | 缺失行为 |
|------------|-------------------|--------------|-------------|---------|
| TC-XXX-001 | username, password | BASE_URL, USER_EMAIL, USER_PASSWORD | | fail |
| TC-XXX-010 | token_absent=true | BASE_URL | USER_TOKEN | 测试无认证场景 |
```

分类规则：
- 认证类 env（token、API key、password）：默认 required，除非 case 明确测试"缺失认证"
- 资源标识类 env（key_id、user_id）：required
- 连接类 env（BASE_URL）：始终 required
- 可选功能 env：optional，注明缺失行为
- 同一模块不同 case 需要不同账号、token、URL path、非法值时，优先进入 suite profile `variables`，不要让 fixture 按 case_id 分发
- `variables` 第一版只支持 `env` 和 `value` 两种来源；`env` 会先读进程环境变量，缺失时读当前工作目录 `.env` 或 `AITEST_ENV_FILE` 指定文件；不打印 env 值

suite profile 示例：

```yaml
variables:
  defaults:
    base_url:
      env: SERVICE_BASE_URL
  cases:
    TC-XXX-001:
      username:
        env: TEST_USER_EMAIL
      password:
        env: TEST_USER_PASSWORD
    TC-XXX-010:
      token:
        value: ""
```

## 状态影响表

追加写入 api_map。

```markdown
## 状态影响分析

| case_id    | 动作类型 | 创建资源？ | 唯一值？ | cleanup？ | 幂等？ |
|------------|---------|-----------|---------|----------|-------|
| TC-XXX-001 | 查询     | 否        | 否      | 否       | 是    |
| TC-XXX-003 | 创建 Key | 是        | 是(name)| 是(delete)| 否   |
| TC-XXX-008 | 注册     | 是        | 是(email)| 无API   | 否    |
```

## 可行性判定

追加写入 api_map。非幂等且无 cleanup API 的 case 默认标为可行性存疑。

```markdown
## 自动化可行性判定

可执行：TC-XXX-001, TC-XXX-002, TC-XXX-003, ...
可行性存疑（保持 skipped）：TC-XXX-008
  原因：注册邮箱不可重复且无删除 API
```

## Profile YAML 结构

单 YAML 代码块，所有字段在同一块中。不需要的顶层字段省略。

```yaml
module_type: {type}
extra_imports:
  - "from test_workspace.targets.{target}.fixtures.{module} import setup_{module}"

default_fixture: setup_{module}
default_object: client_factory

# 当每条 case_flow 都需要同一个 factory/setup 时使用。
# 如果 setup_{module} 直接返回 client，不需要 default_case_setup。
default_case_setup:
  call: client_factory
  kwargs:
    case_id: "{case_id}"
  save_as: case

variables:
  defaults:
    base_url:
      env: PROJECT_BASE_URL
  cases:
    TC-XXX-001:
      username:
        env: PROJECT_TEST_USER
      password:
        value: wrong-password

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
      - call: case.method_name
        kwargs:
          username:
            var: username
          password:
            var: password
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

规则：
- `default_fixture/default_object/default_case_setup` 用于减少每条 `case_flow` 重复 setup。
- `default_case_setup` 只在同一批 flow 都需要同一个 factory call 时写；普通 client fixture 不写。
- 单条 `case_flow` 仍可显式声明 `fixture` 或 `object` 覆盖默认值。
- `{case_id}` 会由 codegen 替换成当前用例 ID。

## Fixture 代码结构

```python
from aitest_kit.runtime_variables import require_env


class {Module}Client:
    def __init__(self, base_url: str, auth_token: str, ...):
        self._client = httpx.Client(transport=httpx.HTTPTransport())
        ...

    def {endpoint_method}(self, ...) -> httpx.Response:
        ...

@pytest.fixture
def setup_{module}() -> {Module}Client:
    base_url = require_env("{PROJECT}_BASE_URL")
    return {Module}Client(base_url, ...)
```

## 输出摘要模板

```markdown
## test-scaffold 摘要

target：{target}
模块：{module}
模式：full / incremental
module_type：{type}

创建/修改文件：
- test_workspace/targets/{target}/target.yaml — target 默认目录
- test_workspace/targets/{target}/modules/{module}.yaml — module registry
- test_workspace/targets/{target}/fixtures/{module}.py — Client 类 + setup fixture
- test_workspace/targets/{target}/profiles/profile_{module}.md — module profile
- {suite_dir}/suite.yaml — suite manifest（suite 模式）
- {suite_dir}/profile_{suite}_suite.md — suite profile（suite 模式）
- api_map_{module}.md — API 面 + env 契约 + 可行性判定

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
- 配置环境变量后执行 `aitest run --suite-file <suite_dir>/suite.yaml`
- 或调用 `/test-codegen --suite-file <suite_dir>/suite.yaml` 处理 UNPARSED（如有）
```
