# Auto-generated from test_workspace/suites/coupon_system/validation_ratelimit_smoke/boundary.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/validation_ratelimit_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
from test_workspace.targets.coupon_system.fixtures.validation_ratelimit import BOUNDARY_ITEM, ERR, LIMITED
from test_workspace.targets.coupon_system.fixtures.validation_ratelimit import setup_validation_ratelimit


BASE_REQUEST = {
    "user_id": None,
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": None,
    "score_threshold": 0.0,
    "max_claim_per_request": 1,
    "context": {},
    "items": [{"item_id": "COUPON_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(**overrides) -> dict:
    body = {**BASE_REQUEST}
    body.update(overrides)
    return body


class TestValidationRatelimitBoundary:
    """validation_ratelimit 边界测试用例"""

    # ── 一、限流窗口 ──

    def test_tc_rate_006(self, setup_validation_ratelimit):
        """TC-RATE-006：HTTP 用户级限流窗口过期后恢复请求"""
        __tc_meta__ = {
            "tc_id": "TC-RATE-006",
            "module": "validation_ratelimit",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/boundary.md",
            "title": "HTTP 用户级限流窗口过期后恢复请求",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：服务配置 rate_limit.enabled=true、max_qps=100、per_user_qps=1、window_seconds=1
        # SETUP: 请求覆盖：HTTP 请求固定 user_id="u_rate_http_window"
        # SETUP: 请求覆盖_2：第 2 次请求触发限流后，轮询 EXISTS coupon:rate:user:u_rate_http_window 直到返回 0，最长等待 3 秒，再发送第 3 次请求

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-RATE-006")
        r1 = case.http("u_rate_http_window", "req-rate-006-1", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
        r2 = case.http("u_rate_http_window", "req-rate-006-2", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
        case.wait_rate_key_gone("u_rate_http_window")
        r3 = case.http("u_rate_http_window", "req-rate-006-3", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
        assert r1['code'] == 0
        assert r2 == LIMITED
        assert r3['code'] == 0

    def test_tc_rate_007(self, setup_validation_ratelimit):
        """TC-RATE-007：gRPC 用户级限流窗口过期后恢复请求"""
        __tc_meta__ = {
            "tc_id": "TC-RATE-007",
            "module": "validation_ratelimit",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/boundary.md",
            "title": "gRPC 用户级限流窗口过期后恢复请求",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 环境覆盖：服务配置 rate_limit.enabled=true、max_qps=100、per_user_qps=1、window_seconds=1
        # SETUP: 请求覆盖：gRPC 请求固定 user_id="u_rate_grpc_window"
        # SETUP: 请求覆盖_2：第 2 次请求触发限流后，轮询 EXISTS coupon:rate:user:u_rate_grpc_window 直到返回 0，最长等待 3 秒，再发送第 3 次请求

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-RATE-007")
        r1 = case.grpc("u_rate_grpc_window", "req-rate-007-1", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
        r2 = case.grpc("u_rate_grpc_window", "req-rate-007-2", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
        case.wait_rate_key_gone("u_rate_grpc_window")
        r3 = case.grpc("u_rate_grpc_window", "req-rate-007-3", item=BOUNDARY_ITEM, external=0, score_threshold=0.0, max_claim_per_request=1)
        assert r1['code'] == 0
        assert r2 == LIMITED
        assert r3['code'] == 0


# TODO: setup_validation_ratelimit fixture 需要手写实现（→ tests/fixtures/validation_ratelimit.py）
# SKIPPED: TC-RATE-008 — `[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 .env 或配置文件]`
# SKIPPED: TC-RATE-009 — `[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 .env 或配置文件]`
# SKIPPED: TC-RATE-010 — `[!可行性存疑: 黑盒接口测试无法直接固定服务进程内 time.time()，需要测试环境提供可控时钟或专项白盒验证；详见 mismatch.md]`
# SKIPPED: TC-SCHEMA-004 — `[!可行性存疑: 当前实现的 RecommendRequest.items 是裸 list，不会使用已定义的 CouponItemRequest 校验子字段；详见 mismatch.md]`

__codegen_skipped__ = [{"tc_id": "TC-RATE-008", "module": "validation_ratelimit", "category": "boundary", "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/boundary.md", "title": "HTTP 限流 Redis 不可用时返回 500", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 .env 或配置文件]`"], "reason": "`[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 .env 或配置文件]`"}, {"tc_id": "TC-RATE-009", "module": "validation_ratelimit", "category": "boundary", "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/boundary.md", "title": "gRPC 限流 Redis 不可用时返回 UNKNOWN", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 .env 或配置文件]`"], "reason": "`[!可行性存疑: 需要测试环境允许控制 Redis 可用性，且不能修改仓库内 .env 或配置文件]`"}, {"tc_id": "TC-RATE-010", "module": "validation_ratelimit", "category": "boundary", "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/boundary.md", "title": "同一时间戳的 3 次请求仍应按 3 次计数", "priority": "P2", "markers": ["`[!可行性存疑: 黑盒接口测试无法直接固定服务进程内 time.time()，需要测试环境提供可控时钟或专项白盒验证；详见 mismatch.md]`"], "reason": "`[!可行性存疑: 黑盒接口测试无法直接固定服务进程内 time.time()，需要测试环境提供可控时钟或专项白盒验证；详见 mismatch.md]`"}, {"tc_id": "TC-SCHEMA-004", "module": "validation_ratelimit", "category": "boundary", "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/boundary.md", "title": "HTTP item 缺少 value 时应被 Schema 拦截", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 当前实现的 RecommendRequest.items 是裸 list，不会使用已定义的 CouponItemRequest 校验子字段；详见 mismatch.md]`"], "reason": "`[!可行性存疑: 当前实现的 RecommendRequest.items 是裸 list，不会使用已定义的 CouponItemRequest 校验子字段；详见 mismatch.md]`"}]
