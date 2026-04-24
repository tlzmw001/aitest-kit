# 场景路由 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/scene_routing
> 生成日期：2026-04-25

---

## 一、兜底分数三级 Fallback

### TC-ROUTE-007：Redis 场景级兜底分存在时优先使用
- **关联**：L1/scene_routing
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  - Redis 设置场景级兜底分：`SET coupon:fallback:score:3001 0.8`
  - Redis 设置全局兜底分：`SET coupon:fallback:score:default 0.6`
  - 配置默认兜底分为 0.5
  - 初始化库存，候选券至少 1 个
- **输入**：
  ```json
  {
    "user_id": "u_fb_001",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "policy_id": "policy_fallback_001",
    "max_claim_per_request": 1,
    "score_threshold": 0.0,
    "external": 0
  }
  ```
- **测试步骤**：
  1. 通过 Redis CLI 执行 `SET coupon:fallback:score:3001 0.8` 和 `SET coupon:fallback:score:default 0.6`
  2. POST /api/recommend，body 为上述 JSON
  3. 断言 response.body 中 calibrated_score 或 score 值
- **预期结果**：兜底分使用场景级 Redis 值 0.8，而非全局 0.6 或配置默认 0.5

### TC-ROUTE-008：Redis 场景级不存在时回退到全局兜底分
- **关联**：L1/scene_routing
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  - Redis 中不存在 `coupon:fallback:score:3001`
  - Redis 设置全局兜底分：`SET coupon:fallback:score:default 0.6`
  - 配置默认兜底分为 0.5
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_fb_002",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "policy_id": "policy_fallback_001",
    "max_claim_per_request": 1,
    "score_threshold": 0.0,
    "external": 0
  }
  ```
- **测试步骤**：
  1. 通过 Redis CLI 执行 `DEL coupon:fallback:score:3001`
  2. 通过 Redis CLI 执行 `SET coupon:fallback:score:default 0.6`
  3. POST /api/recommend，body 为上述 JSON
  4. 断言 response.body 中兜底分值
- **预期结果**：兜底分使用全局 Redis 值 0.6，而非配置默认 0.5

### TC-ROUTE-009：Redis 场景级和全局都不存在时使用配置默认值
- **关联**：L1/scene_routing
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  - Redis 中不存在 `coupon:fallback:score:3001` 和 `coupon:fallback:score:default`
  - 配置默认兜底分为 0.5
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_fb_003",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "policy_id": "policy_fallback_001",
    "max_claim_per_request": 1,
    "score_threshold": 0.0,
    "external": 0
  }
  ```
- **测试步骤**：
  1. 通过 Redis CLI 执行 `DEL coupon:fallback:score:3001` 和 `DEL coupon:fallback:score:default`
  2. POST /api/recommend，body 为上述 JSON
  3. 断言 response.body 中兜底分值
- **预期结果**：兜底分使用配置默认值 0.5

---

## 二、路由异常场景

### TC-ROUTE-010：兜底分 Redis 读取异常时的行为
- **关联**：L1/scene_routing
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  - Redis 服务不可用（停止 Redis 或 mock 连接超时）
  - 配置默认兜底分为 0.5
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_fb_004",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "policy_id": "policy_fallback_001",
    "max_claim_per_request": 1,
    "score_threshold": 0.0,
    "external": 0
  }
  ```
- **测试步骤**：
  1. 停止 Redis 服务（或 mock Redis 连接超时）
  2. POST /api/recommend，body 为上述 JSON
  3. 检查 response status_code 和 body
- **预期结果**：请求失败，返回 500（`_resolve_fallback_score` 调用 `redis.get_fallback_score` 无 try/except，ConnectionError 上抛）。注：来自第二轮代码确认，见 MISMATCH-001

### TC-ROUTE-011：路由表中无任何场景映射时走兜底
- **关联**：L1/scene_routing
- **优先级**：P1
- **类型**：异常
- **前置条件**：
  - 场景路由表配置为空：修改 `coupon_system/config/scenes.json`，将 `routes` 设为 `[]`，重启服务
  - `config.fallback_scene_id` 配置为 3001
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_route_001",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "max_claim_per_request": 1,
    "score_threshold": 0.5,
    "external": 0
  }
  ```
- **测试步骤**：
  1. 备份 `coupon_system/config/scenes.json`，将 routes 改为 `[]`，重启服务
  2. POST /api/recommend，body 为上述 JSON
  3. 断言 response.body.scene_id 和 experiment_info
- **预期结果**：scene_id=3001（fallback_scene_id），experiment_info={}（跳过实验评估）

---

## 三、场景与路由隔离

### TC-ROUTE-012：external=1 时场景路由正常计算不受影响
- **关联**：L1/scene_routing, L2/0402
- **优先级**：P1
- **类型**：业务
- **前置条件**：
  - 路由表中 game/mobile → scene_id=1001
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_ext_001",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "max_claim_per_request": 1,
    "score_threshold": 0.5,
    "external": 1
  }
  ```
- **测试步骤**：
  1. POST /api/recommend，body 为上述 JSON（external=1）
  2. 断言 response.body.scene_id
- **预期结果**：scene_id=1001，与 external=0 时相同，场景路由不受 external 字段影响

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/scene_routing | 三级兜底分读取顺序（Redis 场景级→全局→配置）、兜底分 Redis 读取异常时行为、路由表为空时行为 | 场景配置热更新（代码不支持，见 MISMATCH-003） |
| L2/0402 | 兜底分 Redis 优先读取的三级验证 | （无新增未覆盖） |
