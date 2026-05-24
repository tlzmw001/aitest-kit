# Auto-generated from test_workspace/cases/calibration/boundary.md
# DO NOT EDIT — regenerate with: /test-codegen calibration
import pytest
from test_workspace.tests.helpers import http as http_helper
from test_workspace.tests.helpers import grpc_ops


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
    "items": [{"item_id": "COUPON_CAL_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(**overrides) -> dict:
    body = {**BASE_REQUEST}
    body.update(overrides)
    return body


class TestCalibrationBoundary:
    """calibration 边界测试用例"""

    # ── 一、目录与文件异常 ──

    def test_tc_cal_015(self, http_base_url, setup_calibration):
        """TC-CAL-015：校准目录不存在时降级为不校准"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-015",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "校准目录不存在时降级为不校准",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 环境覆盖：calibration_dir.linear="/tmp/not_exists_cal_linear_011"，目录不存在
        setup_calibration(case_id="TC-CAL-015")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req(**{"user_id": "u_cal_015", "reqId": "req_cal_015"}))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)

    @pytest.mark.manual
    def test_tc_cal_016(self, http_base_url, setup_calibration):
        """TC-CAL-016：校准目录为空时静默降级"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-016",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "校准目录为空时静默降级",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 前置操作：执行 mkdir -p /tmp/cal_empty_012/linear，目录存在但没有 *.json
        setup_calibration(case_id="TC-CAL-016")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req(**{"user_id": "u_cal_016", "reqId": "req_cal_016"}))
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        # MANUAL CHECK: cal == s
        # MANUAL CHECK: 无 WARNING/ERROR 日志

    @pytest.mark.manual
    def test_tc_cal_017(self, http_base_url, setup_calibration):
        """TC-CAL-017：校准文件 JSON 解析失败时降级"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-017",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "校准文件 JSON 解析失败时降级",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 前置操作：线性目录 1.json 内容为 {bad json
        setup_calibration(case_id="TC-CAL-017")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req(**{"user_id": "u_cal_017", "reqId": "req_cal_017"}))
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        # MANUAL CHECK: cal == s
        # MANUAL CHECK: 应用日志包含 校准文件读取失败

    @pytest.mark.manual
    def test_tc_cal_018(self, http_base_url, setup_calibration):
        """TC-CAL-018：校准文件不是 list 时降级"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-018",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "校准文件不是 list 时降级",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 前置操作：线性目录 1.json 内容为 {"conditions":{"device":"mobile"},"k":2,"b":0}
        setup_calibration(case_id="TC-CAL-018")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req(**{"user_id": "u_cal_018", "reqId": "req_cal_018"}))
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        # MANUAL CHECK: cal == s
        # MANUAL CHECK: 应用日志包含 校准文件格式错误

    def test_tc_cal_019(self, http_base_url, setup_calibration):
        """TC-CAL-019：calibration_dir 为空字符串时降级"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-019",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "calibration_dir 为空字符串时降级",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 环境覆盖：实验参数 {"calibration_dir":{"linear":"","piecewise":""}}
        setup_calibration(case_id="TC-CAL-019")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req(**{"user_id": "u_cal_019", "reqId": "req_cal_019"}))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)

    # ── 二、分段边界 ──

    def test_tc_cal_022(self, http_base_url, setup_calibration):
        """TC-CAL-022：分段区间配置非法时跳过该段"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-022",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "分段区间配置非法时跳过该段",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 请求覆盖：第一段 range=[0.7,0.3]，第二段 range=[0,1] k=1,b=0
        # SETUP: 请求覆盖_2：请求命中条件
        setup_calibration(case_id="TC-CAL-022")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req(**{"user_id": "u_cal_022", "reqId": "req_cal_022"}))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)

    # ── 三、条件类型转换 ──

    def test_tc_cal_023(self, http_base_url, setup_calibration):
        """TC-CAL-023：external 条件支持字符串和数字等值匹配"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-023",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "external 条件支持字符串和数字等值匹配",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 前置操作：线性规则 conditions={"external":"0"}、k=1.5,b=0
        # SETUP: 请求覆盖：请求 external=0
        setup_calibration(case_id="TC-CAL-023")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req(**{"user_id": "u_cal_023", "reqId": "req_cal_023"}))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(max(0, min(1, 1.5 * s)), abs=1e-4)

    def test_tc_cal_025(self, grpc_target, setup_calibration):
        """TC-CAL-025：gRPC 校准目录不存在时降级为不校准"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-025",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "gRPC 校准目录不存在时降级为不校准",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 环境覆盖：calibration_dir.linear="/tmp/not_exists_cal_linear_grpc_025"，目录不存在
        # SETUP: 请求覆盖：发送 gRPC 推荐请求
        setup_calibration(case_id="TC-CAL-025")

        resp = grpc_ops.recommend(grpc_target, _req(**{"user_id": "u_cal_025", "reqId": "req_cal_025"}))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert resp["code"] == 0
        assert cal == pytest.approx(s)

    @pytest.mark.manual
    def test_tc_cal_026(self, grpc_target, setup_calibration):
        """TC-CAL-026：gRPC 校准文件 JSON 解析失败时降级"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-026",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "gRPC 校准文件 JSON 解析失败时降级",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：线性目录 1.json 内容为 {bad json
        # SETUP: 请求覆盖：发送 gRPC 推荐请求
        setup_calibration(case_id="TC-CAL-026")

        resp = grpc_ops.recommend(grpc_target, _req(**{"user_id": "u_cal_026", "reqId": "req_cal_026"}))
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        # MANUAL CHECK: response.code == 0
        # MANUAL CHECK: cal == s
        # MANUAL CHECK: 应用日志包含 校准文件读取失败

    def test_tc_cal_027(self, grpc_target, setup_calibration):
        """TC-CAL-027：gRPC external 条件支持字符串和数字等值匹配"""
        __tc_meta__ = {
            "tc_id": "TC-CAL-027",
            "module": "calibration",
            "category": "boundary",
            "source": "test_workspace/cases/calibration/boundary.md",
            "title": "gRPC external 条件支持字符串和数字等值匹配",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：线性规则 conditions={"external":"0"}、k=1.5,b=0
        # SETUP: 请求覆盖：gRPC 请求 external=0
        setup_calibration(case_id="TC-CAL-027")

        resp = grpc_ops.recommend(grpc_target, _req(**{"user_id": "u_cal_027", "reqId": "req_cal_027"}))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert resp["code"] == 0
        assert cal == pytest.approx(max(0, min(1, 1.5 * s)), abs=1e-4)


# SKIPPED: TC-CAL-020 — `[!可行性存疑: 推荐接口无法稳定构造 s == 0.3，精确左边界需组件级测试或可控打分测试入口]`
# SKIPPED: TC-CAL-021 — `[!可行性存疑: 推荐接口无法稳定构造 s == 1.0，精确右边界需组件级测试或可控打分测试入口]`

__codegen_skipped__ = [{"tc_id": "TC-CAL-020", "module": "calibration", "category": "boundary", "source": "test_workspace/cases/calibration/boundary.md", "title": "分段左边界命中当前区间", "priority": "P2", "markers": ["`[!可行性存疑: 推荐接口无法稳定构造 s == 0.3，精确左边界需组件级测试或可控打分测试入口]`"], "reason": "`[!可行性存疑: 推荐接口无法稳定构造 s == 0.3，精确左边界需组件级测试或可控打分测试入口]`"}, {"tc_id": "TC-CAL-021", "module": "calibration", "category": "boundary", "source": "test_workspace/cases/calibration/boundary.md", "title": "最后一个分段右边界闭区间命中", "priority": "P2", "markers": ["`[!可行性存疑: 推荐接口无法稳定构造 s == 1.0，精确右边界需组件级测试或可控打分测试入口]`"], "reason": "`[!可行性存疑: 推荐接口无法稳定构造 s == 1.0，精确右边界需组件级测试或可控打分测试入口]`"}]
