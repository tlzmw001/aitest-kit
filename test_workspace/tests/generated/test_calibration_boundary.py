# Auto-generated from test_workspace/cases/calibration/boundary.md
# DO NOT EDIT — regenerate with: /test-codegen calibration
import pytest
from test_workspace.tests.helpers import http as http_helper


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


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestCalibrationBoundary:
    """calibration 边界测试用例"""

    # ── 一、目录与文件异常 ──

    def test_tc_cal_015(self, http_base_url, setup_calibration):
        """TC-CAL-015：校准目录不存在时降级为不校准"""
        # SETUP: 环境覆盖：calibration_dir.linear="/tmp/not_exists_cal_linear_011"，目录不存在
        setup_calibration(case_id="TC-CAL-015")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_015", "req_cal_015"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)

    @pytest.mark.manual
    def test_tc_cal_016(self, http_base_url, setup_calibration):
        """TC-CAL-016：校准目录为空时静默降级"""
        # SETUP: 前置操作：执行 mkdir -p /tmp/cal_empty_012/linear，目录存在但没有 *.json
        setup_calibration(case_id="TC-CAL-016")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_016", "req_cal_016"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)
        # MANUAL CHECK: 无 WARNING/ERROR 日志

    @pytest.mark.manual
    def test_tc_cal_017(self, http_base_url, setup_calibration):
        """TC-CAL-017：校准文件 JSON 解析失败时降级"""
        # SETUP: 前置操作：线性目录 1.json 内容为 {bad json
        setup_calibration(case_id="TC-CAL-017")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_017", "req_cal_017"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)
        # MANUAL CHECK: 应用日志包含 "校准文件读取失败"

    @pytest.mark.manual
    def test_tc_cal_018(self, http_base_url, setup_calibration):
        """TC-CAL-018：校准文件不是 list 时降级"""
        # SETUP: 前置操作：线性目录 1.json 内容为 {"conditions":{"device":"mobile"},"k":2,"b":0}
        setup_calibration(case_id="TC-CAL-018")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_018", "req_cal_018"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)
        # MANUAL CHECK: 应用日志包含 "校准文件格式错误"

    def test_tc_cal_019(self, http_base_url, setup_calibration):
        """TC-CAL-019：calibration_dir 为空字符串时降级"""
        # SETUP: 环境覆盖：实验参数 {"calibration_dir":{"linear":"","piecewise":""}}
        setup_calibration(case_id="TC-CAL-019")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_019", "req_cal_019"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)

    # ── 二、分段边界 ──

    # SKIPPED: TC-CAL-020 — [!可行性存疑: 推荐接口无法稳定构造 s == 0.3，精确左边界需组件级测试或可控打分测试入口]
    # SKIPPED: TC-CAL-021 — [!可行性存疑: 推荐接口无法稳定构造 s == 1.0，精确右边界需组件级测试或可控打分测试入口]

    def test_tc_cal_022(self, http_base_url, setup_calibration):
        """TC-CAL-022：分段区间配置非法时跳过该段"""
        # SETUP: 请求覆盖：第一段 range=[0.7,0.3]，第二段 range=[0,1] k=1,b=0
        # SETUP: 请求覆盖_2：请求命中条件
        setup_calibration(case_id="TC-CAL-022")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_022", "req_cal_022"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        # UNPARSED ASSERTION: 非法第一段不生效
        assert cal == pytest.approx(s)

    # ── 三、条件类型转换 ──

    def test_tc_cal_023(self, http_base_url, setup_calibration):
        """TC-CAL-023：external 条件支持字符串和数字等值匹配"""
        # SETUP: 前置操作：线性规则 conditions={"external":"0"}, k=1.5, b=0
        # SETUP: 请求覆盖：请求 external=0
        setup_calibration(case_id="TC-CAL-023")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_023", "req_cal_023"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(max(0, min(1, 1.5 * s)), abs=1e-4)

    def test_tc_cal_024(self, http_base_url, setup_calibration):
        """TC-CAL-024：布尔条件支持字符串和布尔等值匹配"""
        # SETUP: 前置操作：请求 item 包含 isPrior=true 但 isPrior 不在校准匹配白名单
        # SETUP: 前置操作_2：线性规则 conditions={"isPrior":"true"}, k=2, b=0
        setup_calibration(case_id="TC-CAL-024")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_024", "req_cal_024"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)
        # NOTE: 详见 mismatch.md — isPrior 不在 _MATCHABLE_FIELDS 白名单

    # ── gRPC 边界用例 ──

    def test_tc_cal_025(self, http_base_url, setup_calibration):
        """TC-CAL-025：gRPC 校准目录不存在时降级为不校准"""
        # SETUP: 协议：gRPC
        # SETUP: 环境覆盖：calibration_dir.linear="/tmp/not_exists_cal_linear_grpc_025"，目录不存在
        # TODO: gRPC call — 第一版使用 HTTP 替代验证
        setup_calibration(case_id="TC-CAL-025")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_025", "req_cal_025"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)

    @pytest.mark.manual
    def test_tc_cal_026(self, http_base_url, setup_calibration):
        """TC-CAL-026：gRPC 校准文件 JSON 解析失败时降级"""
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：线性目录 1.json 内容为 {bad json
        # TODO: gRPC call — 第一版使用 HTTP 替代验证
        setup_calibration(case_id="TC-CAL-026")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_026", "req_cal_026"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(s)
        # MANUAL CHECK: 应用日志包含 "校准文件读取失败"

    def test_tc_cal_027(self, http_base_url, setup_calibration):
        """TC-CAL-027：gRPC external 条件支持字符串和数字等值匹配"""
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：线性规则 conditions={"external":"0"}, k=1.5, b=0
        # TODO: gRPC call — 第一版使用 HTTP 替代验证
        setup_calibration(case_id="TC-CAL-027")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_cal_027", "req_cal_027"))
        assert resp["code"] == 0
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert cal == pytest.approx(max(0, min(1, 1.5 * s)), abs=1e-4)


# TODO: setup_calibration fixture 需要在 conftest.py 中手写实现
# SKIPPED: TC-CAL-020 — [!可行性存疑: 推荐接口无法稳定构造 s == 0.3]
# SKIPPED: TC-CAL-021 — [!可行性存疑: 推荐接口无法稳定构造 s == 1.0]
