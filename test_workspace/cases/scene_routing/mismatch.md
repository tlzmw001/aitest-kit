# 场景路由 Mismatch 记录

> 生成方式：test-design skill（第二轮，规格与实现对比）
> 关联知识库：L1/scene_routing
> 生成日期：2026-04-25

---

### MISMATCH-001：Redis 异常时兜底分读取无降级保护
- **关联**：L1/scene_routing
- **知识库描述**：兜底分数获取顺序为 Redis 场景级 → Redis 全局 → 配置默认值（三级 fallback）
- **实际实现**：`CouponService._resolve_fallback_score`（coupon_service.py:478）调用 `self.redis.get_fallback_score()`，`RedisStore.get_fallback_score`（redis_store.py:145）直接调用 `self.client.get()`，均无 try/except。Redis 连接异常时 `redis.ConnectionError` 直接上抛，请求返回 500
- **影响**：Redis 故障时，本应走配置默认值兜底的请求会直接失败，影响可用性
- **建议**：修代码 — 在 `_resolve_fallback_score` 或 `get_fallback_score` 中捕获 Redis 异常，降级到配置默认值

### MISMATCH-002：Redis 场景级兜底分解析失败时不会回退到全局默认
- **关联**：L1/scene_routing
- **知识库描述**：三级 fallback：Redis 场景级 → Redis 全局 → 配置默认值
- **实际实现**：`get_fallback_score`（redis_store.py:154-157）场景级值存在但 float() 解析失败时，直接 `return None`，不会继续读全局默认 key。调用方拿到 None 后回退到配置默认值，跳过了全局默认这一级
- **影响**：场景级 Redis 值被写入非数字内容时，全局默认值被跳过，直接降级到配置值。三级 fallback 实际只有两级
- **建议**：待产品确认 — 是否需要在场景级解析失败时继续尝试全局默认

### MISMATCH-003：场景配置不支持热更新
- **关联**：L1/scene_routing
- **知识库描述**：知识库"未覆盖"列表中提到"场景配置热更新"
- **实际实现**：`SceneRouter.__init__`（scene_router.py:26-29）在初始化时一次性构建 `_route_map`，无 reload 机制。修改 scenes.json 后必须重启服务才能生效
- **影响**：运行时修改路由配置不会生效，需要重启服务
- **建议**：补文档 — 在 L1/scene_routing 中明确标注"路由表在服务启动时加载，运行时不可变"
