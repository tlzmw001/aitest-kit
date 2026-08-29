# AITest Local Console Agent Connection Spec

状态：已实现、已验证并已提交（commit `8026c24`）
依赖：`test_workspace/plans/pi_agent_runtime_integration_spec.md`
范围：本地 Console 的模型连接配置、真实连接测试和 Pi 协议映射

## 1. 问题与目标

Phase 1 已经能够通过 `provider`、模型名、API Key 环境变量和可选 Base URL 启动 Pi Worker，但 `provider` 是 Pi 的内部适配器标识，不是用户购买 API 的服务商名称。要求用户判断 `openai`、`openai-codex` 或自定义 Provider 会把协议实现细节泄漏到产品界面。

本阶段建立最小、真实的连接配置闭环：

```text
用户填写连接名称、接口类型、Base URL、API Key、模型名
  -> Console 后端校验输入
  -> Pi Worker 使用候选协议发起最小真实请求
  -> 返回检测协议、内部适配器、模型响应和耗时
  -> 用户保存非敏感配置
```

用户不需要查询 Pi Provider，也不需要知道网关背后的上游供应商。

## 2. 锁定范围

### 2.1 本阶段实现

- Console 设置入口增加“模型连接”专用页面。
- 支持 `auto`、OpenAI Responses、OpenAI Chat Completions 和 Anthropic Messages 四个公开接口类型。
- Base URL、模型名和连接名称使用普通表单字段。
- API Key 使用密码输入，不回显，不进入浏览器 localStorage/sessionStorage。
- “测试连接”必须经过真实 Pi Worker 请求，不使用静态成功响应或只做 YAML 校验。
- `auto` 由后端选择有限候选协议；只有明确的端点/协议不兼容错误才继续候选，鉴权、额度、超时和服务错误直接返回。
- 保存非敏感连接配置，内部生成 Pi Provider 映射。
- API Key 只保存在当前 Console Python 进程内存；Console 重启后显示“需要重新输入”。
- Workspace 切换时清除当前会话 API Key，避免跨 workspace 复用。

### 2.2 本阶段不实现

- 不实现 Agent 对话页、会话恢复、权限卡片和工具时间线。
- 不实现 macOS Keychain、Windows Credential Manager 或 Linux Secret Service。
- 不把 API Key 写入 `aitest.yaml`、`.env`、前端存储、日志、异常或 API 响应。
- 不修改用户 shell profile，不自动 export 环境变量。
- 不实现任意自定义 headers、Azure deployment、mTLS 或网关专有签名。
- 不把“自动检测”描述成对所有 OpenAI 兼容服务的保证。

## 3. 用户概念与内部映射

公开协议值固定为：

```text
auto
openai_responses
openai_chat_completions
anthropic_messages
```

内部映射：

| 公开协议 | Pi Provider | Pi API |
|---|---|---|
| `openai_responses` | `openai` | `openai-responses` |
| `openai_chat_completions` | `aitest-openai-chat` | `openai-completions` |
| `anthropic_messages` | `anthropic` | `anthropic-messages` |

`auto` 不直接进入 Worker。后端按模型名选择候选顺序：

- `claude*`：Anthropic Messages，再 OpenAI Chat Completions。
- 其他模型：OpenAI Responses，再 OpenAI Chat Completions。

首个成功协议成为测试结果的 `detected_protocol`。自动检测不得在 `401/403/429`、超时或 `5xx` 后继续尝试，防止把凭证、额度或服务故障误报为协议问题。

## 4. 配置与凭证边界

Workspace 的非敏感配置形态：

```yaml
agent:
  runtime: pi
  connection_name: 黑羽 Code
  model:
    protocol: openai_responses
    provider: openai
    name: gpt-5.5
    api_key_env: HEIYU_API_KEY
    base_url: https://www.heiyucode.com
    base_url_env: null
```

规则：

- `provider` 由系统从协议生成，前端普通表单不允许编辑。
- `base_url` 允许保存非敏感 URL；`base_url_env` 继续兼容 CLI 和已有配置。
- Console API 不解析或回传 `base_url_env` 的值，避免恶意 workspace 借该字段读取任意环境变量；CLI 在传给 Worker 前验证其值为安全 HTTP(S) URL。
- `api_key_env` 保留 CLI/BYOK 边界；Console 会话 Key 优先于该环境变量，但只存在内存。
- 保存 YAML 时只替换顶层 `agent` block，必须保留其他配置文本和顺序。
- 写入使用同目录临时文件和原子替换，不产生半写文件。
- GET 和 PUT 响应只返回 `has_api_key`、`credential_source` 等状态，不返回 Key。

## 5. Console API

### 5.1 `GET /api/agent/connection`

返回：

```json
{
  "connection_name": "黑羽 Code",
  "protocol": "openai_responses",
  "base_url": "https://www.heiyucode.com",
  "model": "gpt-5.5",
  "api_key_env": "HEIYU_API_KEY",
  "has_api_key": false,
  "credential_source": "missing"
}
```

`credential_source` 只允许 `session | environment | missing`。

### 5.2 `POST /api/agent/connection/test`

请求包含当前表单字段和可选 API Key。API Key 只在该请求和测试 Worker 生命周期内存在，不写入配置。成功返回：

```json
{
  "status": "connected",
  "detected_protocol": "openai_responses",
  "internal_provider": "openai",
  "model": "gpt-5.5",
  "response_text": "OK",
  "latency_ms": 6200
}
```

如果请求没有 Key，后端可以使用当前 workspace 的会话 Key或 `api_key_env` 指向的环境变量。全部缺失时返回稳定错误 `AGENT_API_KEY_REQUIRED`。

### 5.3 `PUT /api/agent/connection`

保存非敏感配置；请求中的可选 API Key进入当前 Console 进程的 workspace-scoped 内存槽。响应不得返回 Key。

## 6. 安全要求

- 三个端点继续使用本地 Console session token。
- 响应统一 `Cache-Control: no-store`。
- API Key字段最大长度 4096，Base URL 和模型名使用有界长度。
- Base URL 只允许绝对 `http` 或 `https` URL，不允许用户名、密码、fragment 或其他 scheme。
- 前端密码输入使用 `autocomplete="off"`、`spellcheck="false"`，组件状态在页面卸载时清空。
- WorkerClient 使用显式 env mapping；Key 不进入命令参数和 JSONL initialize payload。
- 后端错误经过现有 redaction，并使用实际 Key做精确值替换。
- 测试连接初始化时显式传入 `tools: []`，不注册任何工具；prompt 同时明确禁止工具，任何意外权限请求统一 deny。
- API、测试和前端不得断言或快照真实 Key。

## 7. Pi Worker 适配

`initialize.model` 增加可选 `protocol`。旧调用缺省时保持现有 Provider 行为，兼容 Phase 1 CLI。

OpenAI Chat Completions 使用动态 Provider：

- Provider id 固定为 `aitest-openai-chat`。
- 从 Pi 内置同名 OpenAI 模型复制展示名、成本、上下文窗口、最大输出和输入能力。
- API 改为 `openai-completions`，使用用户 Base URL 和 runtime API Key。
- 找不到同名内置模型时返回稳定的 unknown model 错误，不伪造模型能力。

Responses 和 Anthropic Messages 继续复用 Pi 内置 Provider，只覆盖 Base URL。

## 8. 前端交互

路由固定为：

```text
/settings/agent
```

设置抽屉中的“模型连接”进入该页面。页面结构：

1. 标题和一句边界说明。
2. 左侧或上方连接表单。
3. 右侧或下方连接状态与最近一次真实测试结果。
4. 高级详情折叠展示检测协议和内部 Provider，不把 Provider作为输入项。

按钮：

- `测试连接`：不保存，使用当前表单发起真实测试。
- `保存连接`：保存非敏感配置，并在本地 Console 会话内保留本次 Key。

保存后 Key 输入立即清空，状态显示“当前会话已提供”。测试成功和保存成功必须分别表达，不能用一个成功状态混淆。

## 9. 视觉方向

- 沿用现有冷石墨深色外壳和信号橙，不新增渐变、玻璃效果或通用卡片网格。
- 连接表单是主工作面，状态面板通过背景层级而不是厚边框建立深度。
- 半径只使用现有 `--r1`、`--r2`、`--r3` 和 pill。
- 输入、按钮和选择器交互区域不小于 40px。
- 测试中状态原位切换；只动画 icon 的 opacity/scale，并尊重 `prefers-reduced-motion`。
- 900px 以下改为单列，375px 不出现横向滚动。

## 10. 影响文件

预计新增或修改：

- `docs/specs/local_console_agent_connection_spec.md`
- `aitest_kit/agent/config.py`
- `aitest_kit/console/agent_connections.py`
- `aitest_kit/console/app.py`
- `agent_runtime/pi_worker/src/session.ts`
- 对应 Python 与 Node 测试
- `console_web/src/types.ts`
- `console_web/src/api/client.ts`
- `console_web/src/router.ts`
- `console_web/src/components/AppShell.vue`
- `console_web/src/views/AgentConnectionView.vue`
- `console_web/src/styles/agent-connection.css`
- 对应 Vitest 和 Playwright 测试
- `aitest_kit/console/web/` 构建产物

## 11. 测试门禁

至少覆盖：

1. Config loader 兼容旧配置，并解析新的 protocol/base_url。
2. Chat Completions Provider 使用动态 provider，旧 initialize payload保持兼容。
3. API Key 不出现在配置、GET/PUT/test 响应和错误中。
4. 无 Key、非法 URL、未知协议和模型错误有稳定错误码。
5. 自动检测只在协议不兼容错误后 fallback。
6. 保存只替换 agent block，其他 YAML 文本保持不变。
7. Workspace 切换清除会话 Key。
8. 设置入口可到达连接页，表单不展示 Provider 输入。
9. 测试连接显示真实响应、协议和耗时；失败显示后端错误。
10. 保存后清空 Key 输入，并显示会话凭证状态。

验证命令：

```bash
python3 -m pytest tests/agent tests/console -q
cd agent_runtime/pi_worker && npm test && npm run check
cd ../../console_web && npm test && npm run build && npm run test:e2e
cd .. && git diff --check
```

## 12. 完成条件

- 用户无需查询或填写 Pi Provider。
- 三种公开协议都有真实 Worker 接线，`auto` 有保守 fallback。
- 真实 API Key 不落盘、不回显、不进入浏览器存储。
- 非敏感配置可从 UI 保存并在刷新后读取。
- Console 重启或 workspace 切换后如实提示重新输入 Key。
- Python、Node、Vue、构建和浏览器验证通过。

## 13. 实现验证记录

验证日期：2026-08-28

- `python3 -m pytest tests -q`：336 passed，1 skipped。
- `python3 -m pytest tests/agent tests/console -q`：89 passed，1 skipped。
- Pi Worker：14 tests passed，Node check passed。
- Vue：20 test files、75 tests passed，生产构建成功。
- Playwright：8 tests passed。
- 两个 npm workspace 的 audit 均为 0 vulnerabilities。
- 真实链路 `Console API -> Pi Worker -> openai_responses -> gpt-5.5` 成功，模型返回 `OK`，耗时 4152 ms。
- 375px 视口下连接页为单列、全部交互控件高度 40px、无横向溢出。
