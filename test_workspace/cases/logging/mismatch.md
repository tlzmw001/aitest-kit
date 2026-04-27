# logging 规格偏差记录

> 生成方式：test-design skill
> 关联知识库：L1/logging
> 生成日期：2026-04-26

---

### MISMATCH-001：默认启动未显式配置业务 logger，INFO 日志可能不可见
- **关联**：L1/logging
- **知识库描述**：L1 规定每次请求打印 INFO 日志，包含 reqId、user_id、item ID、route、scene_id。
- **实际实现**：`coupon_system/services/coupon_service.py` 使用模块 logger 调用 `logger.info()`；`coupon_system/main.py` 只给 uvicorn 设置 `log_level="info"`，没有显式配置 root logger 或业务 logger handler。Python 默认 lastResort handler 只处理 WARNING 及以上，业务 INFO 日志在默认进程中可能不可见。
- **影响**：功能代码已调用日志，但生产/本地默认启动方式下可能无法观测到请求级 INFO 日志，日志模块的可观测性目标落空。
- **建议**：修代码

### MISMATCH-002：空 items 日志路径无法通过黑盒接口覆盖
- **关联**：L1/logging
- **知识库描述**：L1 要求日志包含 item 的 ID。
- **实际实现**：日志代码会对 `items` 生成 `item_ids=",".join(...)`，但推荐接口在进入日志前会拦截 `items=[]` 并返回 `code=1001`。
- **影响**：通过 HTTP/gRPC 黑盒接口只能验证非空 item 列表的日志；空列表日志字段行为需要组件级专项测试。
- **建议**：补文档
