# 待测系统：智能优惠券推荐策略系统 v2
## API 接口

### 主服务

| 接口 | HTTP | gRPC | 说明 |
|------|------|------|------|
| 推荐+发放 | `POST /api/v1/recommend` | `Recommend` | 新主链路 |
| 查询用户券 | `GET /api/v1/coupons/{user_id}` | `QueryUserCoupons` | 保留 |
| 设置用户特征 | `POST /api/v1/admin/user-features` | 无 | 改名 |
| 初始化库存 | `POST /api/v1/admin/stock` | 无 | 保留 |
| 查询库存 | `GET /api/v1/admin/stock/{coupon_id}` | 无 | 保留 |
| 健康检查 | `GET /health` | 无 | 保留 |

**删除接口**：`POST /api/v1/coupon/claim`、`POST /api/v1/coupon/evaluate`

### 打分服务

| 接口 | gRPC | 说明 |
|------|------|------|
| 打分 | `Score` | 接收用户/item特征，返回分数列表 |

## 推荐+发放 Pipeline

```
请求进入 → 参数校验 → 限流 → AB实验分流 → 场景路由
  ↓
粗排(实验控制) → 特征抽取 → 打分服务(gRPC) → 校准(实验控制)
  ↓
发放最优券 → 返回结果
```

### 详细流程

1. **参数校验**：user_id、scene_name、device、items 必填
2. **限流**：全局 1000 QPS + 单用户 10 QPS
3. **AB实验分流**：hash(user_id) % 100 → 命中策略
4. **场景路由**：
   - policy_id 在 fallback 列表 → 返回兜底分数 0.5
   - (scene_name, device) → scene_id 查表
5. **粗排**（实验控制）：
   - 实验开启 → 按规则截断候选券（top_value/top_min_spend/random）
   - 实验关闭 → 跳过
6. **特征抽取**：
   - 用户特征：从 Redis 读取 7 个特征字段
   - Item 特征：从 TSV 文件读取（启动时加载到内存）
7. **打分服务**：gRPC 调用独立打分服务
8. **校准**（实验控制）：
   - 实验开启 → 按场景系数校准 `y = k*x + b`
   - 实验关闭 → 跳过
9. **发放**：
   - 选择最高分 item
   - 分数 >= 阈值(0.5) → 扣库存 + 记录领取
   - 分数 < 阈值 → 不发放
10. **返回**：scene_id、实验信息、所有 item 打分结果、发放的券