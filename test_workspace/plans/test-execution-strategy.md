# 测试用例执行策略

> 背景：讨论如何让 AI 从 Markdown 用例走到实际执行，适用于企业级规模（千级用例）。

## 一、核心结论

1. 砍掉 YAML 可执行用例层，Markdown 用例是唯一数据源
2. aitest-kit 不做 DSL 解释器，退化为 `tests/conftest.py` + `tests/helpers/` 的 fixtures 工具层
3. codegen 从 Markdown 生成 `.py` 文件，作为编译产物提交仓库、CI 可跑，但不手动编辑
4. 需求变更时只改 Markdown，重新生成 `.py`

## 二、用例分级

不是所有用例都能做到同等精细度。按可自动化程度分级：

| 级别 | 特征 | 执行方式 | 示例 |
|------|------|---------|------|
| L-Auto | 后端 API 调用，输入输出完全确定 | codegen → pytest 自动执行 | 参数校验、校准计算、库存扣减 |
| L-Semi | 需要检查日志、监控指标等副作用 | codegen 生成请求部分，断言需人工确认或脚本辅助 | 可观测性验证、限流计数器 |
| L-Manual | 前端操作、视觉验证、跨系统交互 | Markdown 用例作为手工测试指引，不生成代码 | 浏览器操作、邮件通知 |

TEST_SPEC 中的用例格式收紧策略只针对 L-Auto 和 L-Semi。L-Manual 保持当前的描述性写法即可。

用例中通过类型标签区分：
```markdown
- **执行级别**：L-Auto / L-Semi / L-Manual
```

## 三、L-Auto 用例格式（收紧后）

### 完整模板

```markdown
### TC-{模块}-{序号}：{一句话描述}
- **关联**：L1/xxx
- **优先级**：P0 / P1 / P2
- **类型**：业务 / 边界 / 异常
- **执行级别**：L-Auto

- **setup**：
  - [redis] SET key value
  - [redis] HSET key field value
  - [file] path/to/file.json
    ```json
    { ... }
    ```
  - [experiment] 实验名: xxx, scene: yyy
    params: { ... }
  - [http] POST /api/v1/admin/xxx
    ```json
    { ... }
    ```

- **request**：
  - [POST] /api/v1/recommend
    ```json
    { "user_id": "u001", ... }
    ```
  或：
  - [gRPC] CouponService.Recommend
    ```json
    { "user_id": "u001", ... }
    ```

- **assert**：
  - response.code == 0
  - response.results[0].calibrated_score == 0.75
  - response.results.length > 0
  - [redis] GET coupon:stock:c001 == "99"
  - [redis] SISMEMBER coupon:user:u001:claimed c001 == true

- **teardown**：
  - [redis] DEL key1 key2
  - [file] DELETE path/to/file.json
```

### setup 标签语法

| 标签 | 格式 | codegen 映射 |
|------|------|-------------|
| `[redis]` | Redis 命令格式：SET/HSET/DEL/SADD 等 | `redis.set()` / `redis.hset()` / `redis.delete()` |
| `[file]` | 文件路径 + JSON/YAML code block | `Path(path).write_text(content)` |
| `[experiment]` | 实验名 + scene + params dict | `httpx.post(ab_service_url + "/api/...", json=...)` |
| `[http]` | METHOD path + JSON body | `client.request(method, path, json=body)` |

### assert 表达式语法

```
# 响应字段断言
response.{jsonpath} == {value}        # 等于
response.{jsonpath} != {value}        # 不等于
response.{jsonpath} > {value}         # 大于
response.{jsonpath} >= {value}        # 大于等于
response.{jsonpath} contains {value}  # 包含
response.{jsonpath}.length == {n}     # 数组/字符串长度

# Redis 断言
[redis] GET {key} == {value}
[redis] EXISTS {key} == true/false
[redis] SISMEMBER {key} {member} == true/false
[redis] TTL {key} > 0

# 两个响应字段比较
response.{path_a} == response.{path_b}
```

### request 补充说明

- HTTP 请求必须写出 method + path + 完整 JSON body
- gRPC 请求必须写出 service.method + 完整 message JSON
- 如果知识库未给出完整字段定义，标注 `[!请求体待补全]`，第二轮读代码后补全

## 四、L-Semi 用例格式

setup 和 request 部分与 L-Auto 相同（可自动执行的部分尽量自动化）。

assert 部分允许包含非程序化断言，用 `[manual]` 标签标注：

```markdown
- **assert**：
  - response.code == 0
  - [manual] 检查应用日志包含 "calibration skipped, experiment off"
  - [manual] Grafana 面板 api-latency P99 < 100ms
```

codegen 生成代码时：
- 程序化断言正常生成 assert
- `[manual]` 断言生成注释 `# MANUAL CHECK: 检查应用日志包含 ...`，pytest 不会因此失败

## 五、质量保障链路

| 环节 | 谁负责 | 质量靠什么 |
|------|--------|-----------|
| 知识库 → Markdown 用例 | AI 生成 + 人 review | AI 判断力 + TEST_SPEC 红线 |
| Markdown 格式正确性 | AI 生成时自检 | 标签语法校验（可写 linter） |
| Markdown → .py codegen | AI 或模板引擎 | 确定性模板映射，不依赖 AI 创意 |
| .py 能跑通 | pytest | 语法错误、import 错误、fixture 缺失都是硬报错 |
| 断言逻辑正确 | 根源在 Markdown 用例 | 人 review Markdown，不需要 review .py |

### 变更流程

```
需求变更 → 更新知识库 → 重新生成/修改 Markdown 用例 → 重新 codegen → pytest 跑一遍
```

人只需要 review Markdown 用例的变更 diff。.py 的 diff 不需要看。

## 六、codegen 实现方式

两种选择，可以从方案 A 起步，规模大了再切方案 B：

**方案 A：AI codegen（起步阶段）**
- test-codegen skill 读 Markdown 用例 + conftest fixtures API → 生成 pytest 代码
- 优点：灵活，能处理格式不完全规整的用例
- 缺点：非 100% 确定性，大批量时可能有不一致

**方案 B：模板引擎 codegen（规模化阶段）**
- 写一个 Python 脚本，解析结构化 Markdown → 填充 pytest 代码模板
- 优点：100% 确定性，速度快，不依赖 AI
- 缺点：需要 Markdown 格式严格统一，开发模板引擎有一次性成本

## 七、fixtures 工具层（替代 aitest-kit）

不做独立 pip 包，放在项目的 `tests/` 目录下：

```
tests/
├── conftest.py          # pytest fixtures：client, redis, experiment 等
├── helpers/
│   ├── http.py          # httpx 封装（自动记录耗时、重试、日志）
│   ├── grpc.py          # gRPC reflection 客户端
│   ├── redis.py         # Redis 操作 + 自动追踪清理
│   └── assertion.py     # 收集模式断言（可选）
└── generated/           # codegen 生成的测试文件
    ├── test_calibration.py
    ├── test_validation.py
    └── ...
```

conftest.py 提供的核心 fixtures：

```python
@pytest.fixture
def client():
    """HTTP 客户端，base_url 从 config 读取"""

@pytest.fixture
def grpc_client():
    """gRPC 客户端，地址从 config 读取"""

@pytest.fixture
def redis(request):
    """Redis 客户端，自动追踪本次测试写入的 key，teardown 时清理"""

@pytest.fixture
def experiment():
    """AB 实验配置器，提供 set/reset 方法"""
```

## 八、待确认项

1. experiment 的 setup 具体怎么做——取决于 AB 实验服务是否提供管理 API
2. 日志断言（L-Semi）是否值得做半自动化——比如 tail 日志文件 grep 关键字
3. codegen 起步用方案 A（AI）还是直接上方案 B（模板引擎）
4. generated/ 目录是否提交 git，还是 CI 时实时生成
