# Auto-generated from test_workspace/suites/coupon_system/issuance_smoke/boundary.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/issuance_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
pytest_plugins = ["test_workspace.targets.coupon_system.modules.issuance.fixture"]


BASE_REQUEST = {
    "user_id": None,
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": None,
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [{"item_id": "COUPON_ISSUE_A", "coupon_type": "discount", "value": 100, "min_spend": 5000, "expire_days": 7}, {"item_id": "COUPON_ISSUE_B", "coupon_type": "fixed", "value": 80, "min_spend": 3000, "expire_days": 7}],
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestIssuanceBoundary:
    """issuance 边界测试用例"""

    # ── 一、库存边界 ──

    def test_tc_issue_011(self, setup_issuance):
        """TC-ISSUE-011：最高分券库存不足时尝试下一张券"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-011",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "最高分券库存不足时尝试下一张券",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 前置操作：HTTP 探测请求传入 A/B 且库存均为 100，读取 top_item 与 second_item
            # SETUP: 前置操作_2：重置库存为 top_item=0、second_item=100
            # SETUP: 请求覆盖：验证请求 max_claim_per_request=2、score_threshold=0.0

            harness = setup_issuance
            harness.set_stock("COUPON_ISSUE_A", 0)
            harness.set_stock("COUPON_ISSUE_B", 100)
            body = harness.request("u_issue_stock_next", "req_issue_011", items=harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B'), score_threshold=0.0, max_claim_per_request=2, policy_id="policy_fallback_001")
            resp = harness.post_recommend(body)
            assert resp['code'] == 0
            assert resp['coupon'] is not None
            assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
            assert harness.stock('COUPON_ISSUE_A') == 0
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_issue_012(self, setup_issuance):
        """TC-ISSUE-012：所有候选券库存不足时返回成功但 coupon 为空"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-012",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "所有候选券库存不足时返回成功但 coupon 为空",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：A/B 库存均为 0
            # SETUP: 请求覆盖：max_claim_per_request=2、score_threshold=0.0

            harness = setup_issuance
            harness.set_stock("COUPON_ISSUE_A", 0)
            harness.set_stock("COUPON_ISSUE_B", 0)
            body = harness.request("u_issue_all_empty", "req_issue_012", score_threshold=0.0, max_claim_per_request=2)
            resp = harness.post_recommend(body)
            assert resp['code'] == 0
            assert resp['coupon'] is None
            assert resp['code'] != 1006
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_issue_013(self, setup_issuance):
        """TC-ISSUE-013：并发请求同一库存只成功发放一次"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-013",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "并发请求同一库存只成功发放一次",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：SET coupon:stock:COUPON_ISSUE_CONCURRENT 1 EX 86400
            # SETUP: 请求覆盖：两个不同 user_id 并发请求同一券
            # SETUP: 请求覆盖_2：score_threshold=0.0

            harness = setup_issuance
            result = harness.concurrent_issue_once()
            assert all(r['code'] == 0 for r in result['responses'])
            assert result['success_count'] == 1
            assert result['empty_count'] == 1
            assert result['stock'] == 0
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、输入边界 ──

    def test_tc_issue_016(self, setup_issuance):
        """TC-ISSUE-016：expire_days 缺省时 HTTP item 默认值为 7 天"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-016",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "expire_days 缺省时 HTTP item 默认值为 7 天",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：HTTP 请求 item 省略 expire_days，其他字段完整
            # SETUP: 请求覆盖_2：成功发放

            harness = setup_issuance
            body = harness.request("u_issue_default_expire", "req_issue_016", items=[harness.issue_item('COUPON_ISSUE_A', expire_days=None)], score_threshold=0.0)
            resp = harness.post_recommend(body)
            assert resp['code'] == 0
            assert resp['coupon'] is not None
            assert resp['coupon']['expire_time'] - resp['coupon']['claim_time'] == 7 * 86400
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_issue_017(self, setup_issuance):
        """TC-ISSUE-017：max_claim_per_request 大于候选数时最多尝试全部候选"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-017",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "max_claim_per_request 大于候选数时最多尝试全部候选",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 前置操作：HTTP 探测请求传入 A/B 且库存均为 100，读取 top_item 与 second_item
            # SETUP: 前置操作_2：重置库存为 top_item=0、second_item=100
            # SETUP: 请求覆盖：验证请求 max_claim_per_request=10、score_threshold=0.0

            harness = setup_issuance
            harness.set_stock("COUPON_ISSUE_A", 0)
            harness.set_stock("COUPON_ISSUE_B", 100)
            body = harness.request("u_issue_max_gt_count", "req_issue_017", items=harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B'), score_threshold=0.0, max_claim_per_request=10, policy_id="policy_fallback_001")
            resp = harness.post_recommend(body)
            assert resp['code'] == 0
            assert resp['coupon'] is not None
            assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_issue_018(self, setup_issuance):
        """TC-ISSUE-018：gRPC 最高分券库存不足时尝试下一张券"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-018",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "gRPC 最高分券库存不足时尝试下一张券",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 前置操作：gRPC 探测请求传入 A/B 且库存均为 100，读取 top_item 与 second_item
            # SETUP: 前置操作_2：重置库存为 top_item=0、second_item=100
            # SETUP: 请求覆盖：验证请求 max_claim_per_request=2、score_threshold=0.0

            harness = setup_issuance
            harness.set_stock("COUPON_ISSUE_A", 0)
            harness.set_stock("COUPON_ISSUE_B", 100)
            body = harness.request("u_issue_grpc_stock_next", "req_issue_018", items=harness.issue_items('COUPON_ISSUE_A', 'COUPON_ISSUE_B'), score_threshold=0.0, max_claim_per_request=2, policy_id="policy_fallback_001")
            resp = harness.grpc_recommend(body)
            assert resp['code'] == 0
            assert resp['coupon'] is not None
            assert resp['coupon']['item_id'] == 'COUPON_ISSUE_B'
            assert harness.stock('COUPON_ISSUE_A') == 0
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_issue_019(self, setup_issuance):
        """TC-ISSUE-019：gRPC 所有候选券库存不足时返回成功但 coupon 为空"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-019",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "gRPC 所有候选券库存不足时返回成功但 coupon 为空",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 前置操作：gRPC 请求传入 A/B，库存均为 0
            # SETUP: 请求覆盖：max_claim_per_request=2、score_threshold=0.0

            harness = setup_issuance
            harness.set_stock("COUPON_ISSUE_A", 0)
            harness.set_stock("COUPON_ISSUE_B", 0)
            body = harness.request("u_issue_grpc_all_empty", "req_issue_019", score_threshold=0.0, max_claim_per_request=2)
            resp = harness.grpc_recommend(body)
            assert resp['code'] == 0
            assert resp['coupon'] is None
            assert resp['code'] != 1006
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_issue_020(self, setup_issuance):
        """TC-ISSUE-020：gRPC max_claim_per_request 大于候选数时不报错"""
        __tc_meta__ = {
            "tc_id": "TC-ISSUE-020",
            "module": "issuance",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md",
            "title": "gRPC max_claim_per_request 大于候选数时不报错",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 前置操作：gRPC 请求传入两张库存充足的候选券
            # SETUP: 请求覆盖：max_claim_per_request=10、score_threshold=0.0

            harness = setup_issuance
            body = harness.request("u_issue_grpc_max_gt_count", "req_issue_020", score_threshold=0.0, max_claim_per_request=10)
            resp = harness.grpc_recommend(body)
            assert resp['code'] == 0
            assert resp['coupon'] is None or resp['coupon']['item_id'] in {r['item_id'] for r in resp['results']}
        finally:
            reset_case_context(__aitest_ctx_token)


# SKIPPED: TC-ISSUE-014 — `[!可行性存疑: L1 未规定去重限制，当前实现未调用 has_claimed，需产品确认是否允许重复领取]`
# SKIPPED: TC-ISSUE-015 — `[!可行性存疑: 需要测试环境能在扣库存后注入 Redis 写失败]`

__codegen_skipped__ = [{"tc_id": "TC-ISSUE-014", "module": "issuance", "category": "boundary", "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md", "title": "同一用户重复请求同一券不会因已领取被拦截", "priority": "P2", "markers": ["`[!可行性存疑: L1 未规定去重限制，当前实现未调用 has_claimed，需产品确认是否允许重复领取]`"], "reason": "`[!可行性存疑: L1 未规定去重限制，当前实现未调用 has_claimed，需产品确认是否允许重复领取]`"}, {"tc_id": "TC-ISSUE-015", "module": "issuance", "category": "boundary", "source": "test_workspace/suites/coupon_system/issuance_smoke/boundary.md", "title": "Redis 保存发放记录失败时请求异常", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境能在扣库存后注入 Redis 写失败]`"], "reason": "`[!可行性存疑: 需要测试环境能在扣库存后注入 Redis 写失败]`"}]
