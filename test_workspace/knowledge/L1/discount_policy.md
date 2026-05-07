# discount_policy

discount_system 的折扣策略模块根据购买请求评估折扣资格，返回确定性折扣决策，并支持按 `request_id` 查询或删除成功评估后的决策记录。

## 接口

- HTTP 端点：`GET /health`
- HTTP 端点：`POST /api/v1/discount/policy`
- HTTP 端点：`GET /api/v1/discount/decisions/{request_id}`
- HTTP 端点：`DELETE /api/v1/discount/decisions/{request_id}`
- 请求/响应完整字段定义：[docs/discount_system/public_api_doc.md](../../../docs/discount_system/public_api_doc.md)

## 输入

- `POST /api/v1/discount/policy` 请求体必填字段：
  - `user_id: string`
  - `user_level: string`，允许值：`normal`、`vip`、`black`
  - `item_id: string`
  - `item_price: number`，必须 `>= 0`
  - `scene: string`，允许值：`checkout`、`campaign`、`fallback`
  - `stock: integer`，必须 `>= 0`
  - `request_id: string`
- 查询和删除接口从路径参数读取 `request_id`。

## 输出

- 健康检查成功返回 `{"status": "ok"}`。
- 策略评估成功返回 `code`、`eligible`、`discount_rate`、`reason_code`、`request_id`。
- 查询已存在决策返回 `found=true`、`request_id` 和嵌套 `decision`。
- 查询不存在决策返回 HTTP `404`，响应体包含 `found=false`、`request_id`、`error="DECISION_NOT_FOUND"`。
- 删除决策返回 `deleted` 和 `request_id`；不存在时仍成功且 `deleted=false`。
- 校验错误使用 HTTP 框架标准校验错误格式，[?行为未定义: 具体状态码和 body 字段未固定]。

## 业务规则

1. 规则按优先级执行，多个条件同时命中时高优先级胜出。
2. `user_level=black` 命中 Blocked user：`eligible=false`、`discount_rate=1.0`、`reason_code=USER_BLOCKED`。
3. `stock=0` 命中 Empty stock：`eligible=false`、`discount_rate=1.0`、`reason_code=STOCK_EMPTY`。
4. `scene=campaign` 且 `stock>0` 命中 Campaign：`eligible=true`、`discount_rate=0.8`、`reason_code=CAMPAIGN`。
5. `user_level=vip` 且 `scene=checkout` 且 `stock>0` 命中 VIP checkout：`eligible=true`、`discount_rate=0.9`、`reason_code=VIP_CHECKOUT`。
6. 未命中更高优先级规则时命中 Default：`eligible=true`、`discount_rate=1.0`、`reason_code=DEFAULT`。
7. 成功策略评估结果可通过 `request_id` 查询。
8. 校验失败不会创建决策记录。

## 错误场景

- [设计行为] 查询不存在的 `request_id` → HTTP `404`，`error="DECISION_NOT_FOUND"`。
- [设计行为] 删除不存在的 `request_id` → 成功响应，`deleted=false`。
- [设计行为] `item_price < 0`、`stock < 0`、枚举值非法或缺少必填字段 → HTTP 框架标准校验错误。
- [?行为未定义: 空字符串 user_id/item_id/request_id 是否允许未说明]。
- [?行为未定义: 重复 request_id 是否覆盖已有决策未说明]。

## 可观测状态

- 可观测：HTTP 状态码、响应体字段、按 `request_id` 查询到的决策记录、删除后的查询结果。
- 可观测：成功评估决策存储在本地运行时内存，可通过查询接口观察。
- 盲区：文档未定义日志、指标、存储内部结构。
- 盲区：运行时内存重启后记录可能消失，文档未定义持久化恢复行为。

## 已有测试覆盖

- 已覆盖：业务优先级、五条折扣规则、决策查询、决策删除、查询/删除不存在记录、公开字段校验边界。
- 未覆盖：重复 `request_id` 行为、空字符串字段行为、服务重启后的记录消失行为、校验错误 body 精确字段。

## 关联 L2

- [discount_system_initial_public_api](../L2/discount_system_initial_public_api.md) — discount_system 首次按公开 API 文档接入测试飞轮。
