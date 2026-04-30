# 测试执行全流程指南

本文档面向第一次接触本项目的使用者，从零讲解"Markdown 用例 → pytest 代码 → 执行 → 调试"的完整流程。

## 总览

一句话概括：**Markdown 测试用例是唯一的数据源，通过 codegen 工具编译成 pytest 代码，然后用 pytest 执行。**

整个流程可以拆成 4 步：

```
Markdown 用例           codegen 编译           pytest 执行          结果处理
(人写/AI 生成)   ──→   (确定性生成 .py)  ──→  (跑测试)      ──→  (通过/调试)

test_workspace/         test_workspace/        ↑                   ↑
  cases/模块名/           tests/generated/     需要先启动           失败时分两类：
  ├── business.md         ├── test_*_business.py  所有依赖服务      ├── 用例问题 → test-fix
  └── boundary.md         └── test_*_boundary.py                   └── codegen/fixture 问题 → 改 profile
```

## 第一步：理解文件布局

```
test_workspace/
├── cases/                      ← Markdown 用例（输入）
│   └── calibration/
│       ├── business.md         ← 业务测试用例
│       ├── boundary.md         ← 边界测试用例
│       └── mismatch.md         ← 文档不一致记录（不参与 codegen）
│
├── tests/                      ← pytest 测试代码
│   ├── conftest.py             ← 全局 fixture（地址、Redis tracker）
│   ├── fixtures/               ← 模块级 fixture
│   │   ├── calibration.py      ← calibration 模块的前置/清理逻辑
│   │   └── codegen_profile_calibration.md  ← codegen 生成规则配置
│   ├── helpers/                ← 测试工具函数
│   │   ├── http.py             ← HTTP 客户端封装
│   │   ├── grpc_ops.py         ← gRPC 客户端封装
│   │   └── redis_ops.py        ← Redis 操作 + 自动清理
│   └── generated/              ← codegen 生成的 pytest 文件（编译产物）
│       ├── test_calibration_business.py
│       └── test_calibration_boundary.py
```

**关键原则**：
- `generated/` 下的 `.py` 文件是编译产物，不要手动编辑——改了也会被下次 codegen 覆盖
- 要改测试逻辑，改 `cases/` 下的 Markdown 源文件，然后重新 codegen
- 要改前置操作 / 清理逻辑，改 `fixtures/` 下的模块 fixture

## 第二步：codegen 编译（Markdown → pytest）

### codegen 做了什么

codegen 内部分两步：**parser 解析** → **emitter 生成**。

```
business.md  ──→  parser  ──→  结构化数据（SharedConfig + TestCase列表）
                                    │
                                    ↓
                               emitter  ──→  test_calibration_business.py
                                    │
                         codegen_profile 提供模块专属规则
```

- **parser**（`aitest_kit/codegen/parser.py`）：确定性地从 Markdown 提取共享配置（接口、请求体、变量）和每条用例（ID、断言、场景变量）
- **emitter**（`aitest_kit/codegen/emitter.py`）：把结构化数据转成 pytest 代码。通用断言用内置规则匹配，模块专属断言从 `codegen_profile` 的 YAML 规则匹配
- 如果某条断言既不匹配内置规则也不匹配 profile 规则，emitter 会输出 `# UNPARSED ASSERTION:` 注释，由 AI 补写

### 怎么跑 codegen

```bash
# 编译单个模块
aitest codegen calibration

# 编译所有模块
aitest codegen --all

# 只看解析结果，不生成文件
aitest codegen calibration --dry-run

# 检查 generated/ 里的文件是否和源 Markdown 一致
aitest codegen --all --check
```

### codegen 的输出

运行后会显示每个文件的统计：

```
============================================================
Module: calibration
============================================================

  test_workspace/tests/generated/test_calibration_business.py
    Cases:    14        ← 生成了 14 条测试方法
    Manual:   0         ← 标记为手动验证的用例
    Skipped:  2         ← 标记为"可行性存疑"被跳过的用例
    Unparsed: 0         ← emitter 无法自动生成断言的条数（0 最好）
```

如果 `Unparsed > 0`，需要手动打开生成的 `.py` 文件，搜索 `UNPARSED ASSERTION` 注释，补写断言代码。

## 第三步：启动服务 → 执行 pytest

### 3.1 启动依赖服务

pytest 是集成测试，需要被测系统及其依赖全部在本地跑起来。**启动顺序**：

```bash
# ① Redis（如果已在运行可跳过）
redis-server

# ② AB 实验服务
env AB_SERVICE_HOST=127.0.0.1 python3 -m ab_experiment_sdk.service

# ③ 内部 gRPC 打分服务
python3 -m coupon_system.scoring_server.mock_server

# ④ 外部 HTTP 打分服务
python3 -m coupon_system.scoring_server.external_mock_server

# ⑤ 待测主服务（注意代理绕过）
env AB_SERVICE_URL=http://127.0.0.1:8100 \
  NO_PROXY=localhost,127.0.0.1 \
  no_proxy=localhost,127.0.0.1 \
  python3 -m coupon_system.main
```

每个服务需要独立的终端窗口（或用 `&` 放后台）。

**快速验证所有服务就绪**：

```bash
redis-cli ping                                    # 期望: PONG
curl -sS http://127.0.0.1:8100/health             # 期望: {"status":"ok"}
curl -sS http://127.0.0.1:8000/health             # 期望: {"status":"ok","version":"..."}
```

详细的启动说明和环境变量配置见 [service_startup.md](./service_startup.md)。

### 3.2 运行 pytest

```bash
# 跑所有生成的测试
pytest test_workspace/tests/generated/ -v

# 只跑某个模块
pytest test_workspace/tests/generated/test_calibration_business.py -v

# 只跑某一条用例
pytest test_workspace/tests/generated/test_calibration_business.py::TestCalibrationBusiness::test_tc_cal_001 -v

# 跑所有但跳过标记为 manual 的
pytest test_workspace/tests/generated/ -v -m "not manual"
```

## 第四步：看懂测试结果 / 处理失败

### 全部通过

```
test_calibration_business.py::TestCalibrationBusiness::test_tc_cal_001 PASSED
test_calibration_business.py::TestCalibrationBusiness::test_tc_cal_002 PASSED
...
14 passed in 8.23s
```

### 失败了怎么办

失败分两类，处理方式不同：

| 失败类型 | 表现 | 怎么处理 |
|---------|------|---------|
| **用例问题** | 断言逻辑本身写错了（比如期望值算错） | 改 `cases/` 下的 Markdown → 重新 codegen |
| **fixture/codegen 问题** | 前置操作不对、请求构造有误、变量提取路径错 | 改 `fixtures/` 或 `codegen_profile` → 重新 codegen |

**判断方法**：看 pytest 的错误输出。

```
# 典型的断言失败 → 可能是用例逻辑问题
AssertionError: assert 0.62 == 0.74 ± 1.0e-04

# 典型的连接/请求失败 → 服务没启动或 fixture 配置有问题
httpx.ConnectError: [Errno 61] Connection refused
```

## 各文件的职责速查

### conftest.py — 全局 fixture

提供所有模块共用的基础 fixture：

| fixture | 作用 |
|---------|------|
| `http_base_url` | 主服务 HTTP 地址，默认 `http://localhost:8000` |
| `grpc_target` | 主服务 gRPC 地址，默认 `localhost:50051` |
| `ab_base_url` | AB 实验服务地址，默认 `http://localhost:8100` |
| `redis_url` | Redis 连接地址，默认 `redis://localhost:6379/0` |
| `redis_tracker` | 带自动清理的 Redis 客户端，测试结束自动删除写入的 key |

这些地址通过环境变量覆盖：`HTTP_BASE_URL`、`GRPC_TARGET`、`AB_SERVICE_URL`、`REDIS_URL`。

### helpers/ — 测试工具函数

| 文件 | 作用 | 关键点 |
|------|------|--------|
| `http.py` | 封装 `httpx` 的 GET/POST/PUT/DELETE | 使用 `HTTPTransport()` 绕过 macOS 系统代理 |
| `grpc_ops.py` | 封装 gRPC 推荐接口调用 | 把 dict 转成 protobuf Request，响应转回 dict |
| `redis_ops.py` | 封装 Redis 读写 | `RedisTracker` 自动追踪写入的 key，测试结束自动清理 |

### fixtures/模块.py — 模块级 fixture

每个模块一个 fixture 文件，负责该模块测试的前置操作和清理。以 calibration 为例：

- `setup_calibration(case_id)` — 每条用例调用一次，内部完成：
  1. 在临时目录创建该用例需要的校准规则文件
  2. 通过 AB 服务 API 临时覆盖实验参数，指向隔离目录
  3. 设置 AB 白名单，让测试用户命中指定策略
  4. 初始化优惠券库存
  5. 测试结束后自动恢复原始配置、清理白名单

### codegen_profile — 模块 codegen 规则

告诉 emitter 如何为该模块生成代码，包含：
- 该模块用到哪些 fixture
- 请求体的变化规则
- 断言文本 → pytest 代码的映射规则（YAML 格式）
- 已知的调试经验

## Markdown 用例格式规范

共享配置的格式是框架标准，所有项目统一使用。codegen 的 parser 依赖这些固定的 section 名来提取结构化数据。

### 共享配置 section 名（不可自定义）

| section 名 | 作用 | 必填 |
|------------|------|------|
| `## 共享配置` | 共享配置块的起始标记 | 是 |
| `**接口**` | 接口路径，如 `POST /api/v1/recommend` | 是 |
| `**基础请求体（HTTP）**` | HTTP 请求体 JSON 块 | 推荐 |
| `**基础请求体（gRPC）**` | gRPC 请求体文本块 | 按需 |
| `**标准前置**` | 前置条件列表 | 按需 |
| `**通用断言**` | 所有用例共享的断言 | 推荐 |
| `**变量定义**` | 共享变量定义 | 按需 |

### JSON 块规则

**最重要的一条规则**：`json` 代码块必须是严格合法 JSON。

```
✗ 错误 — parser 会解析失败，导致整个模块 codegen 被阻断
"external": {{external}}
"items": {{items}}

✓ 正确 — 用合法默认值，case 级差异放到 codegen_profile
"external": 0
"items": [{"item_id": "DEFAULT_001", "coupon_type": "discount", "value": 80}]
```

### 用例字段名（不可自定义）

每条用例以 `### TC-XXX-NNN：标题` 开头，包含以下字段：

| 字段名 | 作用 |
|--------|------|
| `**优先级**` | P0/P1/P2 |
| `**场景变量**` | 该用例的输入差异描述（给人读） |
| `**断言**` | 该用例的验证条件（给 emitter 读） |

### module_type 声明

codegen_profile 的 YAML 块中应声明 `module_type`，告诉 emitter 该模块的接口类型：

```yaml
module_type: standard_recommend   # 用默认 /api/v1/recommend 模板
module_type: multi_endpoint       # 必须提供 case_bodies
module_type: subprocess_capture   # 需要隔离进程 + 日志采集
module_type: isolated_service     # 需要隔离服务实例 + 配置覆盖
```

## 常见问题

### Q: codegen 报 E001 诊断并拒绝生成

Markdown 中的 `json` 代码块不是合法 JSON。最常见的原因是使用了 `{{var}}` 模板占位符：

```json
// 错误 — parser 无法解析
"external": {{external}}

// 正确 — 用合法默认值，case 级差异放到 codegen_profile 的 request_overrides
"external": 0
```

修复：打开 `cases/模块名/business.md`（或 `boundary.md`），找到报错的 JSON 块，将模板占位符替换为合法 JSON 默认值。

### Q: codegen 报 BLOCKED — 缺少请求体定义

emitter 发现 `base_request_http` 为空，且存在未被 `case_bodies` 覆盖的用例。两种修复方式：
1. 修复 Markdown 中的 JSON 块（见上一条）
2. 如果该模块不使用默认推荐接口模板，在 codegen_profile 中用 `case_bodies` 为每条用例声明完整执行体

### Q: codegen 之后 `.py` 文件里有 `# UNPARSED ASSERTION`

emitter 没有匹配到对应的断言规则。两种处理方式：
1. 手动把注释替换成 pytest 代码（临时方案）
2. 在 `codegen_profile` 中增加断言规则，然后重新 codegen（长期方案）

### Q: 新增了 Markdown 用例，codegen 后 fixture 报错

新用例的 `case_id` 需要在模块 fixture 中注册。例如 calibration 模块需要在 `fixtures/calibration.py` 的 `_CASE_CONFIGS` 字典中添加对应条目。

### Q: pytest 报 `NameError: name '_req' is not defined`

这是 codegen 防御层应该拦截的问题。如果你看到这个错误，说明 codegen 没有正确生成 `_req` helper。原因通常是 Markdown 中的 JSON 块不合法。运行 `aitest codegen <模块名>` 查看诊断输出。

### Q: pytest 报 `ModuleNotFoundError`

确认已经用 `pip install -e ".[dev,server]"` 安装了项目依赖。

### Q: 跑测试全是 500 错误

大概率是某个下游服务没启动，或者主服务被代理干扰。按 [service_startup.md](./service_startup.md) 的健康检查逐个排查。

### Q: 想只验证 codegen 有没有过时

```bash
aitest codegen --all --check
```

会对比 `generated/` 下的文件和重新生成的结果，输出 diff。
