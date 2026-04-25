# validation_ratelimit 规格偏差记录

> 生成方式：test-design skill
> 关联知识库：L1/validation_ratelimit
> 生成日期：2026-04-25

---

### MISMATCH-001：同一时间戳请求会绕过全局限流计数
- **关联**：L1/validation_ratelimit
- **知识库描述**：L1 规定全局限流由 `config.rate_limit.max_qps` 控制，窗口内超出阈值的请求应返回 `{"code": 1010, "message": "请求过于频繁，请稍后重试"}`。
- **实际实现**：`coupon_system/services/redis_store.py` 的 `check_rate_limit()` 使用 `pipe.zadd(key, {str(now): now})` 写入 Redis ZSET；当多个请求命中完全相同的 `time.time()` 值时，会复用同一个 member，`zcard` 统计的是唯一 member 数而不是请求次数。
- **影响**：在高并发或同时间戳场景下，真实请求数可能超过 `max_qps` 但仍被误判为未超限，导致限流精度下降，超出配额的请求继续进入后续推荐链路。
- **建议**：修代码
