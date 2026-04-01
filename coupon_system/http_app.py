"""FastAPI 应用 — 优惠券服务的 HTTP 接口"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from coupon_system.services.coupon_service import CouponBizService

app = FastAPI(
    title="智能优惠券/权益发放系统",
    description="支持场景路由、规则引擎、模型精排、兜底降级的优惠券发放服务",
    version="0.1.0",
)

# 全局 biz_service 引用，由 main.py 注入
_biz_service: CouponBizService | None = None


def set_biz_service(biz: CouponBizService) -> None:
    global _biz_service
    _biz_service = biz


def get_biz() -> CouponBizService:
    if _biz_service is None:
        raise RuntimeError("BizService not initialized")
    return _biz_service


# ========== Request/Response Models ==========

class ClaimCouponRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    coupon_id: str = Field(..., description="优惠券ID")
    scene: str = Field(..., description="场景: new_user, activity, member_day")
    extra: dict | None = Field(default=None, description="扩展字段")


class CouponInfoResponse(BaseModel):
    id: str
    coupon_id: str
    user_id: str
    status: str
    coupon_type: str
    value: int
    min_spend: int
    expire_time: int
    claim_time: int


class ClaimCouponResponse(BaseModel):
    code: int
    message: str
    coupon: CouponInfoResponse | None = None


class QueryCouponsResponse(BaseModel):
    code: int
    message: str
    coupons: list[CouponInfoResponse]
    total: int


class BatchEvaluateRequest(BaseModel):
    user_id: str
    scene: str
    candidate_coupon_ids: list[str]


class EvaluateResultItem(BaseModel):
    coupon_id: str
    score: float
    recommended: bool
    reason: str


class BatchEvaluateResponse(BaseModel):
    code: int
    message: str
    results: list[EvaluateResultItem]


class UserProfileRequest(BaseModel):
    user_id: str
    is_new_user: bool = False
    is_member: bool = False
    total_spend: int = 0
    register_days: int = 0


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
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/v1/coupon/claim", response_model=ClaimCouponResponse)
def claim_coupon(req: ClaimCouponRequest):
    """领取优惠券"""
    biz = get_biz()
    result = biz.claim_coupon(
        user_id=req.user_id,
        coupon_id=req.coupon_id,
        scene=req.scene,
        extra=req.extra,
    )
    coupon = None
    if result.get("coupon"):
        coupon = CouponInfoResponse(**result["coupon"])
    return ClaimCouponResponse(code=result["code"], message=result["message"], coupon=coupon)


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
    coupons = [CouponInfoResponse(**c) for c in result.get("coupons", [])]
    return QueryCouponsResponse(
        code=result["code"],
        message=result["message"],
        coupons=coupons,
        total=result["total"],
    )


@app.post("/api/v1/coupon/evaluate", response_model=BatchEvaluateResponse)
def batch_evaluate(req: BatchEvaluateRequest):
    """批量评估优惠券发放价值"""
    biz = get_biz()
    result = biz.batch_evaluate(
        user_id=req.user_id,
        scene=req.scene,
        candidate_coupon_ids=req.candidate_coupon_ids,
    )
    results = [EvaluateResultItem(**r) for r in result.get("results", [])]
    return BatchEvaluateResponse(
        code=result["code"],
        message=result["message"],
        results=results,
    )


# ========== 测试辅助接口（管理操作）==========

@app.post("/api/v1/admin/user-profile")
def set_user_profile(req: UserProfileRequest):
    """设置用户画像（测试辅助）"""
    biz = get_biz()
    profile = {
        "is_new_user": req.is_new_user,
        "is_member": req.is_member,
        "total_spend": req.total_spend,
        "register_days": req.register_days,
    }
    biz.redis.set_user_profile(req.user_id, profile)
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
