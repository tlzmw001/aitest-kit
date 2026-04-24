# 场景路由 边界测试用例

> 生成方式：test-design skill（第二轮，读代码补充）
> 关联知识库：L1/scene_routing
> 生成日期：2026-04-25

---

## 一、兜底分 Redis 边界

### TC-ROUTE-013：Redis 兜底分值为非数字字符串时降级到下一级
- **关联**：L1/scene_routing
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  - Redis 设置场景级兜底分为非数字：`SET coupon:fallback:score:3001 "abc"`
  - Redis 设置全局兜底分：`SET coupon:fallback:score:default 0.6`
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_edge_001",
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
  1. 通过 Redis CLI 执行 `SET coupon:fallback:score:3001 "abc"`
  2. 通过 Redis CLI 执行 `SET coupon:fallback:score:default 0.6`
  3. POST /api/recommend，body 为上述 JSON
  4. 断言 response.body 中兜底分值
- **预期结果**：场景级值解析失败（ValueError），`get_fallback_score` 返回 None，不会继续读全局默认，直接回退到配置默认值 0.5（代码逻辑：场景级解析失败后 return None，不走全局分支）

### TC-ROUTE-014：Redis 连接异常时请求失败（无降级保护）
- **关联**：L1/scene_routing
- **优先级**：P1
- **类型**：边界
- **前置条件**：
  - Redis 服务不可用（停止 Redis 进程）
  - 初始化库存（在 Redis 停止前完成）
- **输入**：
  ```json
  {
    "user_id": "u_edge_002",
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
  1. 停止 Redis 服务
  2. POST /api/recommend，body 为上述 JSON
  3. 检查 response status_code
- **预期结果**：请求失败，返回 500 或 redis.ConnectionError 上抛（`_resolve_fallback_score` 和 `RedisStore.get_fallback_score` 均无 try/except）

---

## 二、路由匹配边界

### TC-ROUTE-015：policy_id 为空字符串时不触发兜底
- **关联**：L1/scene_routing
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  - 路由表中 game/mobile → scene_id=1001
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_edge_003",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "policy_id": "",
    "max_claim_per_request": 1,
    "score_threshold": 0.5,
    "external": 0
  }
  ```
- **测试步骤**：
  1. POST /api/recommend，body 为上述 JSON（policy_id 为空字符串）
  2. 断言 response.body.scene_id
- **预期结果**：不触发兜底（代码 `if policy_id and ...` 中空字符串为 falsy），正常路由到 scene_id=1001

### TC-ROUTE-016：policy_id 不在 fallback 列表中时正常路由
- **关联**：L1/scene_routing
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  - fallback_policy_ids=["policy_fallback_001", "policy_fallback_002"]
  - 路由表中 game/mobile → scene_id=1001
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_edge_004",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "policy_id": "policy_normal_999",
    "max_claim_per_request": 1,
    "score_threshold": 0.5,
    "external": 0
  }
  ```
- **测试步骤**：
  1. POST /api/recommend，body 为上述 JSON（policy_id 存在但不在 fallback 列表中）
  2. 断言 response.body.scene_id
- **预期结果**：不触发兜底，正常路由到 scene_id=1001

### TC-ROUTE-017：scene_name 大小写敏感——大写不匹配
- **关联**：L1/scene_routing
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  - 路由表中 game/mobile → scene_id=1001（小写）
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_edge_005",
    "scene_name": "Game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "max_claim_per_request": 1,
    "score_threshold": 0.5,
    "external": 0
  }
  ```
- **测试步骤**：
  1. POST /api/recommend，body 为上述 JSON（scene_name 首字母大写）
  2. 断言 response.body.scene_id
- **预期结果**：路由不匹配（dict key 精确匹配，大小写敏感），走兜底 scene_id=3001

---

## 三、配置边界

### TC-ROUTE-018：路由表配置为空列表时所有请求走兜底
- **关联**：L1/scene_routing
- **优先级**：P2
- **类型**：边界
- **前置条件**：
  - 修改 `coupon_system/config/scenes.json`，将 routes 设为空列表 `[]`
  - 重启服务
  - 初始化库存
- **输入**：
  ```json
  {
    "user_id": "u_edge_006",
    "scene_name": "game",
    "device": "mobile",
    "items": [{"item_id": "coupon_001", "coupon_type": "discount"}],
    "max_claim_per_request": 1,
    "score_threshold": 0.5,
    "external": 0
  }
  ```
- **测试步骤**：
  1. 备份 scenes.json，将 routes 改为 `[]`
  2. 重启服务
  3. POST /api/recommend，body 为上述 JSON
  4. 断言 response.body.scene_id 和 experiment_info
  5. 恢复 scenes.json 原始内容
- **预期结果**：scene_id=3001（fallback），experiment_info={}（跳过实验）

---

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/scene_routing | Redis 兜底分非数字降级、Redis 连接异常行为、policy_id 空字符串边界、大小写敏感、路由表空配置 | （无新增未覆盖） |
