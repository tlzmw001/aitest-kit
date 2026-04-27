# validation_ratelimit 规格偏差记录

> 生成方式：test-design skill
> 关联知识库：L1/validation_ratelimit
> 生成日期：2026-04-26

---

### MISMATCH-001：同一时间戳请求会绕过全局限流计数
- **关联**：L1/validation_ratelimit
- **知识库描述**：L1 规定全局限流由 `config.rate_limit.max_qps` 控制，窗口内超出阈值的请求应返回 `{"code": 1010, "message": "请求过于频繁，请稍后重试"}`。
- **实际实现**：`coupon_system/services/redis_store.py` 的 `check_rate_limit()` 使用 `pipe.zadd(key, {str(now): now})` 写入 Redis ZSET；当多个请求命中完全相同的 `time.time()` 值时，会复用同一个 member，`zcard` 统计唯一 member 数而不是请求次数。
- **影响**：高并发或可重复时间戳场景下，真实请求数可能超过 `max_qps` 但仍被误判为未超限，导致限流精度下降，超出配额的请求继续进入推荐链路。
- **建议**：修代码

### MISMATCH-002：HTTP items 子字段没有使用 CouponItemRequest 校验
- **关联**：L1/validation_ratelimit
- **知识库描述**：L1 的接口契约指向 `http_app.py CouponItemRequest/RecommendRequest`，其中 `CouponItemRequest.value`、`item_id`、`coupon_type` 均为 `Field(...)` 必填字段；TEST_SPEC 陷阱-002 也要求所有包含 items 的 HTTP/gRPC 用例必须包含 `CouponItemRequest` 全部必填字段。
- **实际实现**：`coupon_system/http_app.py` 中 `RecommendRequest.items` 定义为裸 `list = Field(...)`，未声明为 `list[CouponItemRequest]`；FastAPI/Pydantic 只校验 `items` 是列表，不校验每个 item 的 `value`、`item_id`、`coupon_type` 等子字段。
- **影响**：HTTP 请求中 item 子结构缺字段时不会在 Schema 层返回 422，缺失字段可能继续进入业务链路，并在发券结果中使用默认值或在后续阶段触发非预期错误。
- **建议**：修代码
