# Auto-generated from test_workspace/suites/coupon_system/calibration_smoke/business.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/calibration_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
pytest_plugins = ["test_workspace.targets.coupon_system.modules.calibration.fixture"]


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
    "items": [{"item_id": "COUPON_CAL_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestCalibrationBusiness:
    """calibration 业务测试用例"""

    # ── 一、旧用例迁移 ──

    def test_tc_cal_001(self, setup_calibration):
        """TC-CAL-001：线性校准按 kx+b 计算并 clamp"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-001",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "线性校准按 kx+b 计算并 clamp",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性校准文件规则 conditions={"device":"mobile"}、k=1.2、b=0.1

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-001", linear_files={1: [{"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.1}]})
            assert resp["code"] == 0
            assert harness.matches_linear(resp, k=1.2, b=0.1)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_002(self, setup_calibration):
        """TC-CAL-002：分段和线性串联校准"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-002",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "分段和线性串联校准",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：分段文件配置 [0,0.3)->k=0.5,b=0.1、[0.3,0.7)->k=1.0,b=0.0、[0.7,1.0]->k=1.5,b=-0.2
            # SETUP: 前置操作_2：线性规则 k=1.2,b=0.05

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-002", piecewise_files={1: [{"conditions": {"device": "mobile"}, "segments": [{"range": [0.0, 0.3], "k": 0.5, "b": 0.1}, {"range": [0.3, 0.7], "k": 1.0, "b": 0.0}, {"range": [0.7, 1.0], "k": 1.5, "b": -0.2}]}]}, linear_files={1: [{"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.05}]})
            assert resp["code"] == 0
            assert harness.matches_piecewise_then_linear(resp, linear_k=1.2, linear_b=0.05)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_003(self, setup_calibration):
        """TC-CAL-003：加载目录中序号最大的校准文件"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-003",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "加载目录中序号最大的校准文件",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性目录同时存在 1.json 规则 k=0.8,b=0 和 3.json 规则 k=1.3,b=0，二者均匹配

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-003", linear_files={1: [{"conditions": {"device": "mobile"}, "k": 0.8, "b": 0.0}], 3: [{"conditions": {"device": "mobile"}, "k": 1.3, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_linear(resp, k=1.3, b=0.0)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_004(self, setup_calibration):
        """TC-CAL-004：无效 condition 字段不匹配"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-004",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "无效 condition 字段不匹配",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性规则 conditions={"unknown":"x"}、k=2.0,b=0.0

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-004", linear_files={1: [{"conditions": {"unknown": "x"}, "k": 2.0, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_unchanged(resp)
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、实验控制 ──

    def test_tc_cal_005(self, setup_calibration):
        """TC-CAL-005：HTTP 实验关闭时跳过校准"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-005",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "HTTP 实验关闭时跳过校准",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 环境覆盖：校准实验参数 {"enable_calibration":false,"calibration_dir":{"linear":"/tmp/cal_linear_001"}}，线性文件存在且匹配 device=mobile

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-005", enable_calibration=False, linear_files={1: [{"conditions": {"device": "mobile"}, "k": 2.0, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_unchanged(resp)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_006(self, setup_calibration):
        """TC-CAL-006：gRPC 根据 scene_id 选择 game 校准实验"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-006",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "gRPC 根据 scene_id 选择 game 校准实验",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：scene_id=1001 的 calibration_exp_game 启用，线性规则 k=1.5,b=0.1,conditions={"device":"mobile"}
            # SETUP: 请求覆盖：ad 校准实验配置不同参数

            harness = setup_calibration
            resp = harness.run_grpc_calibration(resource_key="TC-CAL-006", linear_files={1: [{"conditions": {"device": "mobile"}, "k": 1.5, "b": 0.1}]})
            assert resp["code"] == 0
            assert harness.matches_linear(resp, k=1.5, b=0.1)
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 三、条件匹配 ──

    def test_tc_cal_007(self, setup_calibration):
        """TC-CAL-007：多条件匹配时靠上的规则优先"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-007",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "多条件匹配时靠上的规则优先",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性文件两条规则都匹配：第 1 条 k=1.2,b=0.0，第 2 条 k=2.0,b=0.0

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-007", linear_files={1: [{"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.0}, {"conditions": {"device": "mobile"}, "k": 2.0, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_linear(resp, k=1.2, b=0.0)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_008(self, setup_calibration):
        """TC-CAL-008：条件字段缺失时规则不匹配"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-008",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "条件字段缺失时规则不匹配",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性规则 conditions={"gender":"male"}
            # SETUP: 前置操作_2：Redis 不设置用户 gender 特征

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-008", linear_files={1: [{"conditions": {"gender": "male"}, "k": 2.0, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_unchanged(resp)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_009(self, setup_calibration):
        """TC-CAL-009：条件字段不在白名单时规则不匹配"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-009",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "条件字段不在白名单时规则不匹配",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性规则 conditions={"unknown_field":"x"}，k=2.0,b=0.0

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-009", linear_files={1: [{"conditions": {"unknown_field": "x"}, "k": 2.0, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_unchanged(resp)
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 四、校准计算 ──

    def test_tc_cal_010(self, setup_calibration):
        """TC-CAL-010：仅命中线性校准"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-010",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "仅命中线性校准",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：只配置线性目录
            # SETUP: 前置操作_2：规则 conditions={"device":"mobile"}、k=1.5、b=0.0

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-010", linear_files={1: [{"conditions": {"device": "mobile"}, "k": 1.5, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_linear(resp, k=1.5, b=0.0)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_011(self, setup_calibration):
        """TC-CAL-011：仅命中分段函数校准"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-011",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "仅命中分段函数校准",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：只配置分段目录
            # SETUP: 前置操作_2：分段 [0,0.3)->k=0.5,b=0.1、[0.3,0.7)->k=1.0,b=0.0、[0.7,1.0]->k=1.5,b=-0.2，条件 device=mobile

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-011", piecewise_files={1: [{"conditions": {"device": "mobile"}, "segments": [{"range": [0.0, 0.3], "k": 0.5, "b": 0.1}, {"range": [0.3, 0.7], "k": 1.0, "b": 0.0}, {"range": [0.7, 1.0], "k": 1.5, "b": -0.2}]}]})
            assert resp["code"] == 0
            assert harness.matches_piecewise(resp)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_012(self, setup_calibration):
        """TC-CAL-012：线性和分段都命中时先分段后线性"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-012",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "线性和分段都命中时先分段后线性",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：分段同 TC-CAL-011
            # SETUP: 前置操作_2：线性规则 k=1.2,b=0.05
            # SETUP: 请求覆盖：二者都匹配 device=mobile

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-012", piecewise_files={1: [{"conditions": {"device": "mobile"}, "segments": [{"range": [0.0, 0.3], "k": 0.5, "b": 0.1}, {"range": [0.3, 0.7], "k": 1.0, "b": 0.0}, {"range": [0.7, 1.0], "k": 1.5, "b": -0.2}]}]}, linear_files={1: [{"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.05}]})
            assert resp["code"] == 0
            assert harness.matches_piecewise_then_linear(resp, linear_k=1.2, linear_b=0.05)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_013(self, setup_calibration):
        """TC-CAL-013：两类规则都不匹配时不校准"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-013",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "两类规则都不匹配时不校准",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性和分段规则条件均为 device=ios，请求为 mobile

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-013", piecewise_files={1: [{"conditions": {"device": "ios"}, "segments": [{"range": [0.0, 0.3], "k": 0.5, "b": 0.1}, {"range": [0.3, 0.7], "k": 1.0, "b": 0.0}, {"range": [0.7, 1.0], "k": 1.5, "b": -0.2}]}]}, linear_files={1: [{"conditions": {"device": "ios"}, "k": 1.2, "b": 0.05}]})
            assert resp["code"] == 0
            assert harness.matches_unchanged(resp)
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_cal_014(self, setup_calibration):
        """TC-CAL-014：目录中选取序号最大的版本文件"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-014",
            "module": "calibration",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/calibration_smoke/business.md",
            "title": "目录中选取序号最大的版本文件",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：线性目录包含 1.json 规则 k=1.1,b=0 和 3.json 规则 k=1.8,b=0，均匹配 device=mobile

            harness = setup_calibration
            resp = harness.run_http_calibration(resource_key="TC-CAL-014", linear_files={1: [{"conditions": {"device": "mobile"}, "k": 1.1, "b": 0.0}], 3: [{"conditions": {"device": "mobile"}, "k": 1.8, "b": 0.0}]})
            assert resp["code"] == 0
            assert harness.matches_linear(resp, k=1.8, b=0.0)
        finally:
            reset_case_context(__aitest_ctx_token)



__codegen_skipped__ = []
