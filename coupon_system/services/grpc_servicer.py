"""gRPC Servicer — 优惠券服务的 gRPC 接口实现"""

import grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection

from coupon_system.services.coupon_service import CouponBizService

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

    def ClaimCoupon(self, request, context):
        extra = dict(request.extra) if request.extra else {}
        result = self.biz.claim_coupon(
            user_id=request.user_id,
            coupon_id=request.coupon_id,
            scene=request.scene,
            extra=extra,
        )

        coupon_info = None
        if result.get("coupon"):
            c = result["coupon"]
            coupon_info = _pb2.CouponInfo(
                id=c["id"],
                coupon_id=c["coupon_id"],
                user_id=c["user_id"],
                status=c["status"],
                coupon_type=c["coupon_type"],
                value=c["value"],
                min_spend=c["min_spend"],
                expire_time=c["expire_time"],
                claim_time=c["claim_time"],
            )

        return _pb2.ClaimCouponResponse(
            code=result["code"],
            message=result["message"],
            coupon=coupon_info,
        )

    def QueryUserCoupons(self, request, context):
        result = self.biz.query_user_coupons(
            user_id=request.user_id,
            status_filter=request.status_filter or "all",
            page=request.page or 1,
            page_size=request.page_size or 20,
        )

        coupons = []
        for c in result.get("coupons", []):
            coupons.append(_pb2.CouponInfo(
                id=c["id"],
                coupon_id=c["coupon_id"],
                user_id=c["user_id"],
                status=c["status"],
                coupon_type=c["coupon_type"],
                value=c["value"],
                min_spend=c["min_spend"],
                expire_time=c["expire_time"],
                claim_time=c["claim_time"],
            ))

        return _pb2.QueryUserCouponsResponse(
            code=result["code"],
            message=result["message"],
            coupons=coupons,
            total=result["total"],
        )

    def BatchEvaluate(self, request, context):
        result = self.biz.batch_evaluate(
            user_id=request.user_id,
            scene=request.scene,
            candidate_coupon_ids=list(request.candidate_coupon_ids),
        )

        eval_results = []
        for r in result.get("results", []):
            eval_results.append(_pb2.EvaluateResult(
                coupon_id=r["coupon_id"],
                score=r["score"],
                recommended=r["recommended"],
                reason=r["reason"],
            ))

        return _pb2.BatchEvaluateResponse(
            code=result["code"],
            message=result["message"],
            results=eval_results,
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
