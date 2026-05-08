# 待测系统：智能优惠券/权益发放系统

## 架构

双协议服务（同一进程），共享 `CouponBizService` 实例：
- HTTP (FastAPI) :8000
- gRPC :50051
- 数据层：Redis :6379

## 目录结构

```
coupon_system/
├── main.py                 # 启动入口，编译proto、初始化依赖、启动双服务
├── http_app.py             # HTTP 路由 + Pydantic 模型
├── config/
│   ├── __init__.py         # 配置 dataclass 定义 + YAML 加载
│   └── settings.yaml       # 场景/券模板/限流/兜底/模型/Redis 配置
├── services/
│   ├── coupon_service.py   # 核心业务逻辑（领券pipeline、查询、批量评估）
│   ├── redis_store.py      # Redis 数据操作（库存、领取记录、画像、限流、券实例）
│   ├── model_service.py    # Mock ML 打分服务（支持故障注入）
│   └── grpc_servicer.py    # gRPC 服务实现
└── protos/
    └── coupon.proto        # gRPC 服务定义
```

## API 接口

| 接口 | HTTP | gRPC |
|------|------|------|
| 领券 | `POST /api/v1/coupon/claim` | `ClaimCoupon` |
| 查询用户券 | `GET /api/v1/coupons/{user_id}` | `QueryUserCoupons` |
| 批量评估 | `POST /api/v1/coupon/evaluate` | `BatchEvaluate` |
| 设置用户画像 | `POST /api/v1/admin/user-profile` | 无 |
| 初始化库存 | `POST /api/v1/admin/stock` | 无 |
| 查询库存 | `GET /api/v1/admin/stock/{coupon_id}` | 无 |
| 健康检查 | `GET /health` | 无 |

## 领券 Pipeline

```
参数校验 → 限流 → 场景路由 → 模板查找 → 场景匹配 → 获取用户画像 → 规则粗筛 → 模型精排 → 库存扣减 → 记录领取
```

## 错误码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1001 | 参数无效 |
| 1002 | 场景不存在 |
| 1003 | 优惠券不存在 |
| 1004 | 券不适用当前场景 |
| 1005 | 已领取过 |
| 1006 | 库存不足 |
| 1007 | 超过领取次数限制 |
| 1008 | 非新用户 |
| 1009 | 非会员 |
| 1010 | 限流 |
| 1011 | 模型拒绝 |
| 5000 | 内部错误 |

## 场景

| 场景 | 每人上限 | 要求 |
|------|---------|------|
| `new_user` | 1 | 新用户 |
| `activity` | 3 | 无 |
| `member_day` | 5 | 会员 |

## 券模板

| ID | 类型 | 面值 | 门槛 | 库存 | 场景 |
|----|------|------|------|------|------|
| `COUPON_NEW_001` | fixed | 20元 | 100元 | 10,000 | new_user |
| `COUPON_ACT_001` | discount | 8折 | 50元 | 50,000 | activity |
| `COUPON_MEM_001` | fixed | 50元 | 200元 | 5,000 | member_day |
| `COUPON_SHIP_001` | free_shipping | 0 | 0 | 100,000 | activity |

## Redis Key

| Key 模式 | 类型 | 用途 |
|----------|------|------|
| `coupon:stock:{coupon_id}` | STRING | 库存计数 |
| `coupon:user:{uid}:claimed` | SET | 已领券ID集合 |
| `coupon:user:{uid}:scene_count:{scene}` | STRING | 场景领取计数 |
| `coupon:user_profile:{uid}` | STRING(JSON) | 用户画像 |
| `coupon:instance:{uuid}` | STRING(JSON) | 券实例 |
| `coupon:user:{uid}:instances` | SET | 用户持有券实例ID |
| `coupon:rate:*` | ZSET | 滑动窗口限流 |

## 模型服务

MockModelService，进程内 mock，基础分 0.5 + 用户特征加分 + 随机噪声。支持 `set_simulate_failure()` / `set_simulate_timeout()` 故障注入。
