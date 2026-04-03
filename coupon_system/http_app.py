"""FastAPI 应用 — 优惠券策略服务的 HTTP 接口"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from coupon_system.services.coupon_service import CouponBizService

app = FastAPI(
    title="优惠券策略系统",
    description="AB实验 → 场景路由 → 粗排 → 特征抽取 → 打分 → 校准 → 发放",
    version="0.2.0",
)

# 全局 biz_service 引用，由 main.py 注入
_biz_service: Optional[CouponBizService] = None


def set_biz_service(biz: CouponBizService) -> None:
    global _biz_service
    _biz_service = biz


def get_biz() -> CouponBizService:
    if _biz_service is None:
        raise RuntimeError("BizService not initialized")
    return _biz_service


# ========== Request/Response Models ==========

class CouponItemRequest(BaseModel):
    item_id: str = Field(..., description="优惠券物料ID")
    coupon_type: str = Field(..., description="类型: discount, fixed, free_shipping")
    value: int = Field(..., description="面值（分）")
    min_spend: int = Field(0, description="门槛（分）")
    expire_days: int = Field(7, description="过期天数")


class RecommendRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    scene_name: str = Field(..., description="场景名: game, ad")
    device: str = Field(..., description="设备: mobile, pc, pad")
    policy_id: str = Field("", description="策略ID，命中兜底则跳过打分")
    external: int = Field(..., description="打分路由（必传），0=内部服务，1=外部服务")
    reqId: str = Field("", description="业务请求标识，用于排查")
    score_threshold: float = Field(..., description="分数阈值（必传）")
    max_claim_per_request: int = Field(..., description="本次请求最大发券数量（必传）")
    context: dict = Field(default_factory=dict, description="上下文特征")
    items: list = Field(..., description="候选优惠券物料")


class ScoredItemResponse(BaseModel):
    item_id: str
    score: float
    calibrated_score: float
    recommended: bool


class ClaimedCouponResponse(BaseModel):
    instance_id: str
    item_id: str
    user_id: str
    status: str
    coupon_type: str
    value: int
    min_spend: int
    expire_time: int
    claim_time: int


class RecommendResponse(BaseModel):
    code: int
    message: str
    scene_id: int
    experiment_info: dict
    results: list
    coupon: Optional[ClaimedCouponResponse] = None


class QueryCouponsResponse(BaseModel):
    code: int
    message: str
    coupons: list
    total: int


class UserFeatureRequest(BaseModel):
    user_id: str
    features: dict = Field(..., description="用户特征 {feature_name: value}")


class StockInitRequest(BaseModel):
    coupon_id: str
    stock: int
    ttl: int = 86400


class HealthResponse(BaseModel):
    status: str
    version: str


# ========== API Endpoints ==========

@app.get("/health", response_model=HealthResponse)
def health_check():
    """健康检查"""
    return {"status": "ok", "version": "0.2.0"}


@app.post("/api/v1/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    """推荐 + 发放"""
    biz = get_biz()
    items = [item.dict() if hasattr(item, "dict") else dict(item) for item in req.items]
    result = biz.recommend_and_claim(
        user_id=req.user_id,
        scene_name=req.scene_name,
        device=req.device,
        policy_id=req.policy_id,
        external=req.external,
        req_id=req.reqId,
        score_threshold=req.score_threshold,
        max_claim_per_request=req.max_claim_per_request,
        context=req.context,
        items=items,
    )

    coupon = None
    if result.get("coupon"):
        coupon = ClaimedCouponResponse(**result["coupon"])

    return RecommendResponse(
        code=result["code"],
        message=result["message"],
        scene_id=result.get("scene_id", 0),
        experiment_info=result.get("experiment_info", {}),
        results=result.get("results", []),
        coupon=coupon,
    )


@app.get("/api/v1/coupons/{user_id}", response_model=QueryCouponsResponse)
def query_user_coupons(
    user_id: str,
    status: str = "all",
    page: int = 1,
    page_size: int = 20,
):
    """查询用户优惠券列表"""
    biz = get_biz()
    result = biz.query_user_coupons(
        user_id=user_id,
        status_filter=status,
        page=page,
        page_size=page_size,
    )
    return QueryCouponsResponse(
        code=result["code"],
        message=result["message"],
        coupons=result.get("coupons", []),
        total=result["total"],
    )


# ========== 管理接口 ==========

@app.post("/api/v1/admin/user-features")
def set_user_features(req: UserFeatureRequest):
    """设置用户特征（测试辅助）"""
    biz = get_biz()
    biz.redis.set_user_features(req.user_id, req.features)
    return {"code": 0, "message": "success"}


@app.post("/api/v1/admin/stock")
def init_stock(req: StockInitRequest):
    """初始化库存（测试辅助）"""
    biz = get_biz()
    biz.redis.init_stock(req.coupon_id, req.stock, req.ttl)
    return {"code": 0, "message": "success", "stock": req.stock}


@app.get("/api/v1/admin/stock/{coupon_id}")
def get_stock(coupon_id: str):
    """查询库存（测试辅助）"""
    biz = get_biz()
    stock = biz.redis.get_stock(coupon_id)
    return {"code": 0, "stock": stock}
