# scene_routing 规格偏差记录

> 生成方式：test-design skill
> 关联知识库：L1/scene_routing
> 生成日期：2026-04-26

---

### MISMATCH-001：场景路由配置不支持运行时热更新
- **关联**：L1/scene_routing
- **知识库描述**：L1 描述场景路由通过 `(scene_name, device)` 查表得到 `scene_id`，但未说明路由表加载时机和配置变更生效方式。
- **实际实现**：`coupon_system/services/scene_router.py` 在 `SceneRouter.__init__()` 中把 `config.routes` 构建为内存 `_route_map`；后续 `route()` 只读该内存 map，不重新读取配置文件。
- **影响**：运行中修改场景配置不会影响已启动服务；若测试或运维期望热更新，会观察到配置文件与接口结果不一致。
- **建议**：补文档
