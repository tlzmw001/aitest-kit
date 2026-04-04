"""gRPC Servicer — 优惠券策略服务的 gRPC 接口实现"""

import logging

import grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection

from coupon_system.services.coupon_service import CouponBizService

logger = logging.getLogger(__name__)

# 延迟导入编译后的 proto 模块
_pb2 = None
_pb2_grpc = None


def _lazy_import():
    global _pb2, _pb2_grpc
    if _pb2 is None:
        from coupon_system.protos import coupon_pb2, coupon_pb2_grpc
        _pb2 = coupon_pb2
        _pb2_grpc = coupon_pb2_grpc


class CouponGrpcServicer:
    """gRPC 服务实现"""

    def __init__(self, biz_service: CouponBizService):
        _lazy_import()
        self.biz = biz_service

    def Recommend(self, request, context):
        """推荐 + 发放"""
        items = []
        for item in request.items:
            items.append({
                "item_id": item.item_id,
                "coupon_type": item.coupon_type,
                "value": item.value,
                "min_spend": item.min_spend,
                "expire_days": item.expire_days,
                "isPrior": item.is_prior,
            })

        result = self.biz.recommend_and_claim(
            user_id=request.user_id,
            scene_name=request.scene_name,
            device=request.device,
            policy_id=request.policy_id,
            external=request.external if request.HasField("external") else None,
            req_id=request.req_id,
            score_threshold=request.score_threshold if request.HasField("score_threshold") else None,
            max_claim_per_request=(
                request.max_claim_per_request
                if request.HasField("max_claim_per_request")
                else None
            ),
            context=dict(request.context),
            items=items,
        )

        # 构建 results
        scored_items = []
        for r in result.get("results", []):
            scored_items.append(_pb2.ScoredItem(
                item_id=r["item_id"],
                score=r["score"],
                calibrated_score=r["calibrated_score"],
                recommended=r["recommended"],
            ))

        # 构建 coupon
        coupon = None
        if result.get("coupon"):
            c = result["coupon"]
            coupon = _pb2.ClaimedCoupon(
                instance_id=c["instance_id"],
                item_id=c["item_id"],
                user_id=c["user_id"],
                status=c["status"],
                coupon_type=c["coupon_type"],
                value=c["value"],
                min_spend=c["min_spend"],
                expire_time=c["expire_time"],
                claim_time=c["claim_time"],
            )

        return _pb2.RecommendResponse(
            code=result["code"],
            message=result["message"],
            scene_id=result.get("scene_id", 0),
            experiment_info=result.get("experiment_info", {}),
            results=scored_items,
            coupon=coupon,
        )

    def QueryUserCoupons(self, request, context):
        """查询用户优惠券列表"""
        result = self.biz.query_user_coupons(
            user_id=request.user_id,
            status_filter=request.status_filter or "all",
            page=request.page or 1,
            page_size=request.page_size or 20,
        )

        coupons = []
        for c in result.get("coupons", []):
            coupons.append(_pb2.ClaimedCoupon(
                instance_id=c.get("instance_id", c.get("id", "")),
                item_id=c.get("item_id", c.get("coupon_id", "")),
                user_id=c.get("user_id", ""),
                status=c.get("status", ""),
                coupon_type=c.get("coupon_type", ""),
                value=c.get("value", 0),
                min_spend=c.get("min_spend", 0),
                expire_time=c.get("expire_time", 0),
                claim_time=c.get("claim_time", 0),
            ))

        return _pb2.QueryUserCouponsResponse(
            code=result["code"],
            message=result["message"],
            coupons=coupons,
            total=result["total"],
        )


def create_grpc_server(biz_service: CouponBizService, port: int = 50051) -> grpc.Server:
    """创建并配置 gRPC server（含 reflection）"""
    _lazy_import()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = CouponGrpcServicer(biz_service)
    _pb2_grpc.add_CouponServiceServicer_to_server(servicer, server)

    # 开启 Server Reflection
    service_names = (
        _pb2.DESCRIPTOR.services_by_name["CouponService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    return server
