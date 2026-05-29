"""gRPC client helpers for integration tests."""
from __future__ import annotations

import grpc
from google.protobuf.json_format import MessageToDict

from coupon_system.protos import coupon_pb2, coupon_pb2_grpc


def _dict_to_request(body: dict) -> coupon_pb2.RecommendRequest:
    fields = dict(body)

    if "reqId" in fields:
        fields["req_id"] = fields.pop("reqId")

    items_raw = fields.pop("items", [])
    items = [coupon_pb2.CouponItem(**it) for it in items_raw]

    context = fields.pop("context", {})

    none_keys = [k for k, v in fields.items() if v is None]
    for k in none_keys:
        del fields[k]

    return coupon_pb2.RecommendRequest(**fields, items=items, context=context)


def recommend(target: str, body: dict, timeout: float = 10.0) -> dict:
    channel = grpc.insecure_channel(target)
    try:
        stub = coupon_pb2_grpc.CouponServiceStub(channel)
        req = _dict_to_request(body)
        resp = stub.Recommend(req, timeout=timeout)
        d = MessageToDict(
            resp,
            preserving_proto_field_name=True,
            always_print_fields_with_no_presence=True,
        )
        if "coupon" not in d:
            d["coupon"] = None
        return d
    finally:
        channel.close()


def query_user_coupons(
    target: str,
    user_id: str,
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    timeout: float = 10.0,
) -> dict:
    channel = grpc.insecure_channel(target)
    try:
        stub = coupon_pb2_grpc.CouponServiceStub(channel)
        req = coupon_pb2.QueryUserCouponsRequest(
            user_id=user_id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        resp = stub.QueryUserCoupons(req, timeout=timeout)
        d = MessageToDict(
            resp,
            preserving_proto_field_name=True,
            always_print_fields_with_no_presence=True,
        )
        d.setdefault("coupons", [])
        return d
    finally:
        channel.close()
