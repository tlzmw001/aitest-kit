# Auto-generated from test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md
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
    "items": [{"item_id": "COUPON_VAL_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(**overrides) -> dict:
    body = {**BASE_REQUEST}
    body.update(overrides)
    return body


class TestValidationRatelimitBusiness:
    """validation_ratelimit 业务测试用例"""

    # ── 一、业务层参数校验 ──

    def test_tc_val_001(self, setup_validation_ratelimit):
        """TC-VAL-001：user_id 为空时返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-001",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "user_id 为空时返回参数错误",
            "priority": "P0 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id=""、reqId="req-val-001"、external=0、score_threshold=0.5、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-001")
        resp = case.http("", "req-val-001", external=0, score_threshold=0.5, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_002(self, setup_validation_ratelimit):
        """TC-VAL-002：scene_name 为空时返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-002",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "scene_name 为空时返回参数错误",
            "priority": "P0 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id="u_val_scene_empty"、scene_name=""、reqId="req-val-002"、external=0、score_threshold=0.5、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-002")
        resp = case.http("u_val_scene_empty", "req-val-002", scene_name="", external=0, score_threshold=0.5, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_003(self, setup_validation_ratelimit):
        """TC-VAL-003：device 为空时返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-003",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "device 为空时返回参数错误",
            "priority": "P0 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id="u_val_device_empty"、device=""、reqId="req-val-003"、external=0、score_threshold=0.5、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-003")
        resp = case.http("u_val_device_empty", "req-val-003", device="", external=0, score_threshold=0.5, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_004(self, setup_validation_ratelimit):
        """TC-VAL-004：items 为空列表时返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-004",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "items 为空列表时返回参数错误",
            "priority": "P0 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id="u_val_items_empty"、items=[]、reqId="req-val-004"、external=0、score_threshold=0.5、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-004")
        resp = case.http("u_val_items_empty", "req-val-004", items=[], external=0, score_threshold=0.5, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_005(self, setup_validation_ratelimit):
        """TC-VAL-005：缺少业务必填控制字段时返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-005",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "缺少业务必填控制字段时返回参数错误",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：通过 gRPC 请求或业务层调用省略 external、score_threshold、max_claim_per_request 中任一字段，其他字段合法

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-005")
        resp = case.grpc_missing("u_val_grpc_missing_control", "req-val-005", "external")
        assert resp == ERR

    def test_tc_val_006(self, setup_validation_ratelimit):
        """TC-VAL-006：HTTP 拒绝 external 非法值"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-006",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 拒绝 external 非法值",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id="u_val_http_external_2"、reqId="req-val-006"、external=2、score_threshold=0.5、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-006")
        resp = case.http("u_val_http_external_2", "req-val-006", external=2, score_threshold=0.5, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_007(self, setup_validation_ratelimit):
        """TC-VAL-007：gRPC 拒绝 external 非法值"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-007",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 拒绝 external 非法值",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求使用 user_id="u_val_grpc_external_2"、req_id="req-val-007"、external=2、score_threshold=0.5、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-007")
        resp = case.grpc("u_val_grpc_external_2", "req-val-007", external=2, score_threshold=0.5, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_008(self, setup_validation_ratelimit):
        """TC-VAL-008：HTTP 拒绝 score_threshold 小于 0"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-008",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 拒绝 score_threshold 小于 0",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id="u_val_http_threshold_low"、reqId="req-val-008"、external=0、score_threshold=-0.01、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-008")
        resp = case.http("u_val_http_threshold_low", "req-val-008", external=0, score_threshold=-0.01, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_009(self, setup_validation_ratelimit):
        """TC-VAL-009：gRPC 拒绝 score_threshold 大于 1"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-009",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 拒绝 score_threshold 大于 1",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求使用 user_id="u_val_grpc_threshold_high"、req_id="req-val-009"、external=0、score_threshold=1.01、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-009")
        resp = case.grpc("u_val_grpc_threshold_high", "req-val-009", external=0, score_threshold=1.01, max_claim_per_request=1)
        assert resp == ERR

    def test_tc_val_010(self, setup_validation_ratelimit):
        """TC-VAL-010：HTTP 拒绝 max_claim_per_request 小于 1"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-010",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 拒绝 max_claim_per_request 小于 1",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id="u_val_http_max_claim_0"、reqId="req-val-010"、external=0、score_threshold=0.5、max_claim_per_request=0

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-010")
        resp = case.http("u_val_http_max_claim_0", "req-val-010", external=0, score_threshold=0.5, max_claim_per_request=0)
        assert resp == ERR

    def test_tc_val_011(self, setup_validation_ratelimit):
        """TC-VAL-011：gRPC 拒绝 max_claim_per_request 小于 1"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-011",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 拒绝 max_claim_per_request 小于 1",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求使用 user_id="u_val_grpc_max_claim_0"、req_id="req-val-011"、external=0、score_threshold=0.5、max_claim_per_request=0

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-011")
        resp = case.grpc("u_val_grpc_max_claim_0", "req-val-011", external=0, score_threshold=0.5, max_claim_per_request=0)
        assert resp == ERR

    # ── 二、请求标识 ──

    @pytest.mark.manual
    def test_tc_val_012(self, setup_validation_ratelimit):
        """TC-VAL-012：HTTP reqId 为空时自动生成请求标识"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-012",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP reqId 为空时自动生成请求标识",
            "priority": "P1",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用 user_id="u_reqid_http_auto"、reqId=""、external=0、score_threshold=0.0、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-012")
        resp = case.http("u_reqid_http_auto", "", external=0, score_threshold=0.0, max_claim_per_request=1)
        assert resp['code'] == 0
        # MANUAL CHECK: 应用日志存在 recommend request:，其中 reqId= 的值匹配 UUID 正则

    @pytest.mark.manual
    def test_tc_val_013(self, setup_validation_ratelimit):
        """TC-VAL-013：gRPC req_id 为空时自动生成请求标识"""
        __tc_meta__ = {
            "tc_id": "TC-VAL-013",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC req_id 为空时自动生成请求标识",
            "priority": "P1",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求使用 user_id="u_reqid_grpc_auto"、req_id=""、external=0、score_threshold=0.0、max_claim_per_request=1

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-VAL-013")
        resp = case.grpc("u_reqid_grpc_auto", "", external=0, score_threshold=0.0, max_claim_per_request=1)
        assert resp['code'] == 0
        # MANUAL CHECK: 应用日志存在 recommend request:，其中 reqId= 的值匹配 UUID 正则

    # ── 三、HTTP Schema 校验 ──

    def test_tc_schema_001(self, setup_validation_ratelimit):
        """TC-SCHEMA-001：HTTP 请求缺少 external 字段返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-SCHEMA-001",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 请求缺少 external 字段返回 422",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用完整基础请求体，但删除 external 字段

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-SCHEMA-001")
        body = case.body("u_schema_external_missing", "req-schema-001", external=0, score_threshold=0.5, max_claim_per_request=1)
        body.pop("external")
        resp = case.http_response(body)
        assert resp.status_code == 422
        locs = [item["loc"] for item in resp.json()["detail"]]
        assert ["body", "external"] in locs

    def test_tc_schema_002(self, setup_validation_ratelimit):
        """TC-SCHEMA-002：HTTP 请求缺少 score_threshold 字段返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-SCHEMA-002",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 请求缺少 score_threshold 字段返回 422",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用完整基础请求体，但删除 score_threshold 字段

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-SCHEMA-002")
        body = case.body("u_schema_threshold_missing", "req-schema-002", external=0, score_threshold=0.5, max_claim_per_request=1)
        body.pop("score_threshold")
        resp = case.http_response(body)
        assert resp.status_code == 422
        locs = [item["loc"] for item in resp.json()["detail"]]
        assert ["body", "score_threshold"] in locs

    def test_tc_schema_003(self, setup_validation_ratelimit):
        """TC-SCHEMA-003：HTTP 请求缺少 max_claim_per_request 字段返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-SCHEMA-003",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 请求缺少 max_claim_per_request 字段返回 422",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求使用完整基础请求体，但删除 max_claim_per_request 字段

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-SCHEMA-003")
        body = case.body("u_schema_max_claim_missing", "req-schema-003", external=0, score_threshold=0.5, max_claim_per_request=1)
        body.pop("max_claim_per_request")
        resp = case.http_response(body)
        assert resp.status_code == 422
        locs = [item["loc"] for item in resp.json()["detail"]]
        assert ["body", "max_claim_per_request"] in locs

    # ── 四、gRPC 协议字段校验 ──

    def test_tc_grpc_001(self, setup_validation_ratelimit):
        """TC-GRPC-001：gRPC 请求缺少 external 字段返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-GRPC-001",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 请求缺少 external 字段返回参数错误",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 请求设置 score_threshold=0.5、max_claim_per_request=1，不设置 optional external

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-GRPC-001")
        resp = case.grpc_missing("u_grpc_external_missing", "req-grpc-001", "external")
        assert resp == ERR

    def test_tc_grpc_002(self, setup_validation_ratelimit):
        """TC-GRPC-002：gRPC 请求缺少 score_threshold 字段返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-GRPC-002",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 请求缺少 score_threshold 字段返回参数错误",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 请求设置 external=0、max_claim_per_request=1，不设置 optional score_threshold

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-GRPC-002")
        resp = case.grpc_missing("u_grpc_threshold_missing", "req-grpc-002", "score_threshold")
        assert resp == ERR

    def test_tc_grpc_003(self, setup_validation_ratelimit):
        """TC-GRPC-003：gRPC 请求缺少 max_claim_per_request 字段返回参数错误"""
        __tc_meta__ = {
            "tc_id": "TC-GRPC-003",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 请求缺少 max_claim_per_request 字段返回参数错误",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 请求设置 external=0、score_threshold=0.5，不设置 optional max_claim_per_request

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-GRPC-003")
        resp = case.grpc_missing("u_grpc_max_claim_missing", "req-grpc-003", "max_claim_per_request")
        assert resp == ERR

    def test_tc_grpc_004(self, setup_validation_ratelimit):
        """TC-GRPC-004：gRPC 请求包含所有必填字段可通过校验"""
        __tc_meta__ = {
            "tc_id": "TC-GRPC-004",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 请求包含所有必填字段可通过校验",
            "priority": "P0",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 请求完整设置 external=0、score_threshold=0.5、max_claim_per_request=1，其他字段使用基础请求体合法值

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-GRPC-004")
        resp = case.grpc("u_grpc_valid", "req-grpc-004", external=0, score_threshold=0.5, max_claim_per_request=1)
        assert resp['code'] == 0

    # ── 五、限流 ──

    def test_tc_rate_001(self, setup_validation_ratelimit):
        """TC-RATE-001：用户级限流达到上限时拒绝同用户第 3 个请求"""
        __tc_meta__ = {
            "tc_id": "TC-RATE-001",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "用户级限流达到上限时拒绝同用户第 3 个请求",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：服务配置 rate_limit.enabled=true、max_qps=100、per_user_qps=2、window_seconds=1
        # SETUP: 请求覆盖：1 秒窗口内连续发送 3 个 HTTP 请求，均使用 user_id="u_rate_old_user"，reqId 分别为 req-rate-001-1、req-rate-001-2、req-rate-001-3

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-RATE-001")
        r1 = case.http("u_rate_old_user", "req-rate-001-1", external=0, score_threshold=0.0, max_claim_per_request=1)
        r2 = case.http("u_rate_old_user", "req-rate-001-2", external=0, score_threshold=0.0, max_claim_per_request=1)
        r3 = case.http("u_rate_old_user", "req-rate-001-3", external=0, score_threshold=0.0, max_claim_per_request=1)
        assert r1['code'] == 0
        assert r2['code'] == 0
        assert r3 == LIMITED

    def test_tc_rate_002(self, setup_validation_ratelimit):
        """TC-RATE-002：HTTP 全局限流达到上限时拒绝第 3 个请求"""
        __tc_meta__ = {
            "tc_id": "TC-RATE-002",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 全局限流达到上限时拒绝第 3 个请求",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：服务配置 rate_limit.enabled=true、max_qps=2、per_user_qps=10、window_seconds=1
        # SETUP: 请求覆盖：1 秒窗口内连续发送 3 个 HTTP 请求，user_id 依次为 u_rate_http_global_1、u_rate_http_global_2、u_rate_http_global_3，其余字段使用基础请求体合法值

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-RATE-002")
        r1 = case.http("u_rate_http_global_1", "req-rate-002-1", external=0, score_threshold=0.0, max_claim_per_request=1)
        r2 = case.http("u_rate_http_global_2", "req-rate-002-2", external=0, score_threshold=0.0, max_claim_per_request=1)
        r3 = case.http("u_rate_http_global_3", "req-rate-002-3", external=0, score_threshold=0.0, max_claim_per_request=1)
        assert r1['code'] == 0
        assert r2['code'] == 0
        assert r3 == LIMITED

    def test_tc_rate_003(self, setup_validation_ratelimit):
        """TC-RATE-003：gRPC 全局限流达到上限时拒绝第 3 个请求"""
        __tc_meta__ = {
            "tc_id": "TC-RATE-003",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 全局限流达到上限时拒绝第 3 个请求",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 环境覆盖：服务配置 rate_limit.enabled=true、max_qps=2、per_user_qps=10、window_seconds=1
        # SETUP: 请求覆盖：1 秒窗口内连续发送 3 个 gRPC 请求，user_id 依次为 u_rate_grpc_global_1、u_rate_grpc_global_2、u_rate_grpc_global_3，其余字段使用基础请求体合法值

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-RATE-003")
        r1 = case.grpc("u_rate_grpc_global_1", "req-rate-003-1", external=0, score_threshold=0.0, max_claim_per_request=1)
        r2 = case.grpc("u_rate_grpc_global_2", "req-rate-003-2", external=0, score_threshold=0.0, max_claim_per_request=1)
        r3 = case.grpc("u_rate_grpc_global_3", "req-rate-003-3", external=0, score_threshold=0.0, max_claim_per_request=1)
        assert r1['code'] == 0
        assert r2['code'] == 0
        assert r3 == LIMITED

    def test_tc_rate_004(self, setup_validation_ratelimit):
        """TC-RATE-004：HTTP 用户级限流达到上限时拒绝同用户第 2 个请求"""
        __tc_meta__ = {
            "tc_id": "TC-RATE-004",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "HTTP 用户级限流达到上限时拒绝同用户第 2 个请求",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：服务配置 rate_limit.enabled=true、max_qps=100、per_user_qps=1、window_seconds=1
        # SETUP: 请求覆盖：1 秒窗口内发送 2 个 HTTP 请求，均使用 user_id="u_rate_http_user"，reqId 分别为 req-rate-004-1、req-rate-004-2

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-RATE-004")
        r1 = case.http("u_rate_http_user", "req-rate-004-1", external=0, score_threshold=0.0, max_claim_per_request=1)
        r2 = case.http("u_rate_http_user", "req-rate-004-2", external=0, score_threshold=0.0, max_claim_per_request=1)
        assert r1['code'] == 0
        assert r2 == LIMITED

    def test_tc_rate_005(self, setup_validation_ratelimit):
        """TC-RATE-005：gRPC 用户级限流达到上限时拒绝同用户第 2 个请求"""
        __tc_meta__ = {
            "tc_id": "TC-RATE-005",
            "module": "validation_ratelimit",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/validation_ratelimit_smoke/business.md",
            "title": "gRPC 用户级限流达到上限时拒绝同用户第 2 个请求",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 环境覆盖：服务配置 rate_limit.enabled=true、max_qps=100、per_user_qps=1、window_seconds=1
        # SETUP: 请求覆盖：1 秒窗口内发送 2 个 gRPC 请求，均使用 user_id="u_rate_grpc_user"，req_id 分别为 req-rate-005-1、req-rate-005-2

        client_factory = setup_validation_ratelimit
        case = client_factory(case_id="TC-RATE-005")
        r1 = case.grpc("u_rate_grpc_user", "req-rate-005-1", external=0, score_threshold=0.0, max_claim_per_request=1)
        r2 = case.grpc("u_rate_grpc_user", "req-rate-005-2", external=0, score_threshold=0.0, max_claim_per_request=1)
        assert r1['code'] == 0
        assert r2 == LIMITED


# TODO: setup_validation_ratelimit fixture 需要手写实现（→ tests/fixtures/validation_ratelimit.py）

__codegen_skipped__ = []
