# test-scaffold 格式参考

## API Map 模板

```markdown
# API Map: {module}

path: test_workspace/targets/{target}/api_maps/api_map_{module}.md

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

### 连接层
- {PROJECT}_BASE_URL — 服务地址

### 认证层
- {PROJECT}_USER_TOKEN — 用户 token

### 资源层
- {PROJECT}_INACTIVE_KEY_ID — 已停用的 API Key

## 信息缺口
- {无法从现有来源确认的信息}
```

## Case variables/env 矩阵

```markdown
## Case variables/env 矩阵

| case_id | profile variables | required env | optional env | 缺失行为 |
|---|---|---|---|---|
| TC-XXX-001 | username, password | BASE_URL, USER_EMAIL, USER_PASSWORD | | fail |
| TC-XXX-010 | token_absent=true | BASE_URL | USER_TOKEN | 测试无认证场景 |
```

规则：

- 连接/认证等必需 env 用 `require_env()` fail-fast。
- case 级账号、token、资源 ID 写 suite profile `variables.cases`。
- 负向输入使用 `value`，不要用缺失 env 表达。
- 同一模块不同 case 的差异不得藏进 fixture/Harness 的 case_id 分发。
- profile variables 只记录 env 名或 value，不记录凭证值。

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

## 状态影响与可行性

```markdown
## 状态影响分析

| case_id | 动作类型 | 创建资源 | 唯一值 | cleanup | 幂等 |
|---|---|---|---|---|---|
| TC-XXX-001 | 查询 | 否 | 否 | 否 | 是 |
| TC-XXX-003 | 创建 Key | 是 | name | delete | 否 |

## 自动化可行性判定

| case_id | automation_status | reason_type | required_capability | cleanup_strategy | evidence_ref | resume_condition |
|---|---|---|---|---|---|---|
| TC-XXX-001 | auto_executable | none | public API | none | api_map | executable |
| TC-XXX-008 | skipped_infeasible | no_cleanup | delete API | none | case precondition | cleanup available |
```

`automation_status`：`auto_executable`、`manual_pure`、`manual_semi_auto`、`skipped_infeasible`、`blocked_by_known_issue`。

## Module package

```text
test_workspace/targets/{target}/modules/{module}/
  __init__.py
  module.yaml
  profile.md
  fixture.py
  harness.py
```

`module.yaml`：

```yaml
target: {target}
module: {module}
module_type: multi_endpoint
knowledge_refs:
  l1:
    - test_workspace/knowledge/L1/{module}.md
registered_suites:
  - suite: {suite}
    manifest: {suite_dir}/suite.yaml
    status: active
```

`profile.md`：

```yaml
variables:
  defaults:
    default_scene:
      value: checkout
assertion_rules: []
```

不要在 module profile 写 `module_type`、TC-ID、fixture/object/setup 或路径配置。

## Harness 代码结构

`harness.py`：

```python
from __future__ import annotations

from functools import cached_property

import httpx

from aitest_kit.runtime_variables import require_env


class {Module}Harness:
    def __init__(self) -> None:
        self._http = httpx.Client(transport=httpx.HTTPTransport())

    @cached_property
    def base_url(self) -> str:
        return require_env("{PROJECT}_BASE_URL").rstrip("/")

    def query(self, path: str) -> httpx.Response:
        return self._http.get(f"{self.base_url}{path}")

    def assert_items_active(self, payload: dict) -> bool:
        return all(item["status"] == "active" for item in payload["items"])

    def close(self) -> None:
        self._http.close()
```

`fixture.py`：

```python
from __future__ import annotations

from collections.abc import Iterator

import pytest

from .harness import {Module}Harness


@pytest.fixture
def setup_{module}() -> Iterator[{Module}Harness]:
    harness = {Module}Harness()
    try:
        yield harness
    finally:
        harness.close()
```

fixture 只负责 Harness 生命周期，不提前读取某条用例未使用的环境变量。环境变量在对应 Harness capability 第一次执行时读取。能力较多时按职责拆为 `api.py`、`resources.py` 等，并由 Harness 组合；不要创建宽泛 `actions.py`/`utils.py`。

## Suite profile

```yaml
profile_scope: case_suite
parent_module: {module}
suite: {suite}

variables:
  cases:
    TC-XXX-001:
      token:
        env: PROJECT_TEST_TOKEN

requests:
  TC-XXX-001:
    patches:
      - op: replace
        path: /auth/token
        value_from: token

structured_assertions:
  TC-XXX-001:
    - type: jsonpath_all_equals
      target: resp
      path: $.data.items[*].publishStatus
      equals: 0

case_flows:
  TC-XXX-001:
    description: 查询并验证发布状态
    steps:
      - call: harness.query
        args:
          - /api/v1/items
        save_as: http_resp
      - assign: resp
        expr: http_resp.json()
      - assert: 'assert http_resp.status_code == 200'

case_bodies:
  TC-XXX-002: |
    # reason: 测试函数本身需要并发编排
    results = harness.run_concurrent_requests(5)
    assert len(results) == 5
```

规则：

- flow 不写 fixture/object，根对象固定 `harness`。
- suite profile 不写 `extra_imports`。
- `requests.patches` 支持 `add`、`replace`、`remove`；变量注入用 `value_from`。
- 完整请求引用使用 `{request_ref: self}` 或指定 TC-ID。
- JSONPath、集合、字段存在和长度优先用 structured assertions。
- 循环/条件/等待优先封装 Harness capability；测试函数本身必须控制时才保留 case body。
- module profile 只放 L1 稳定能力；所有 TC-ID 绑定内容放 suite profile。

## 输出摘要模板

```markdown
## test-scaffold 摘要

target：{target}
module：{module}
mode：scaffold-module / scaffold-suite / incremental

module package：
- modules/{module}/module.yaml
- modules/{module}/profile.md
- modules/{module}/fixture.py
- modules/{module}/harness.py
- {其他职责文件或无}

Harness contract：
- setup fixture：setup_{module}
- Harness：{Module}Harness
- public capabilities：{列表}
- env/cleanup：{摘要}

suite assets：
- {suite_dir}/suite.yaml
- {suite_dir}/profile_{suite}_suite.md

route distribution：
- default_http：{N}
- structured_case_flow：{N}
- custom_case_body：{N，附原因}
- manual/skipped：{N}

validation：
- doctor：PASS/FAIL
- validate-profile：PASS/FAIL
- explain/dump-ir binding：setup_{module} -> harness
- codegen/check：PASS/FAIL
- compileall/collect：PASS/FAIL

next：
- 配置运行 env 后执行 `aitest run --suite-file {suite_dir}/suite.yaml`
```
