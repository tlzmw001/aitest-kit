# Auto-generated from test_workspace/suites/coupon_system/ab_service_smoke/boundary.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/ab_service_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
pytest_plugins = ["test_workspace.targets.coupon_system.modules.ab_service.fixture"]


BASE_REQUEST = {
    "user_id": None,
    "request_id": "req_abs_default",
    "context": {},
    "experiment_names": None,
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestAbServiceBoundary:
    """ab_service 边界测试用例"""

    # ── 一、分流边界 ──

    def test_tc_abs_023(self, setup_ab_service):
        """TC-ABS-023：hash_range 重叠时命中第一个匹配策略"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-023",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "hash_range 重叠时命中第一个匹配策略",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：实验 exp_abs_overlap 策略顺序为 s_first [0,80)、s_second [50,100)
            # SETUP: 前置操作：选择 hash=60 的 user_id

            harness = setup_ab_service
            harness.upsert_experiment({"name": "exp_abs_overlap", "strategies": [{"id": "s_first", "hash_range": [0, 80], "params": {}}, {"id": "s_second", "hash_range": [50, 100], "params": {}}]})
            resp = harness.post("/api/v1/ab/evaluate", {"user_id": "u_abs_overlap_243", "request_id": "req_abs_023", "experiment_names": ["exp_abs_overlap"]})
            assert resp.status_code == 200
            assert resp.json()['assignments']['exp_abs_overlap']['strategy_id'] == 's_first'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_024(self, setup_ab_service):
        """TC-ABS-024：空策略实验评估后不返回 assignment"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-024",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "空策略实验评估后不返回 assignment",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：创建实验 exp_abs_empty，strategies=[]
            # SETUP: 接口调用：evaluate 指定该实验

            harness = setup_ab_service
            harness.upsert_experiment({"name": "exp_abs_empty", "strategies": []})
            resp = harness.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_024", "experiment_names": ["exp_abs_empty"]})
            assert resp.status_code == 200
            assert resp.json()['assignments'] == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_025(self, setup_ab_service):
        """TC-ABS-025：evaluate 指定不存在实验名时静默跳过"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-025",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "evaluate 指定不存在实验名时静默跳过",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：evaluate experiment_names=["not_exists_exp"]

            harness = setup_ab_service
            resp = harness.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_025", "experiment_names": ["not_exists_exp"]})
            assert resp.status_code == 200
            assert resp.json()['assignments'] == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、文件容错 ──

    def test_tc_abs_026(self, setup_ab_service):
        """TC-ABS-026：实验配置文件不存在时自动创建空配置"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-026",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "实验配置文件不存在时自动创建空配置",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 环境覆盖：使用不存在的 AB_SERVICE_EXPERIMENTS_PATH=/tmp/aitest_ab_service_boundary/new/experiments.json 启动服务

            harness = setup_ab_service
            result = harness.missing_experiments_file_is_created()
            assert result['status'] == 200
            assert result['body'] == []
            assert result['exists']
        finally:
            reset_case_context(__aitest_ctx_token)

    @pytest.mark.manual
    def test_tc_abs_027(self, setup_ab_service):
        """TC-ABS-027：白名单文件损坏时忽略并以空白名单启动"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-027",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "白名单文件损坏时忽略并以空白名单启动",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 环境覆盖：白名单文件内容为 {bad json，启动服务

            harness = setup_ab_service
            result = harness.malformed_whitelist_falls_back_empty()
            assert result['status'] == 200
            assert result['body'] == {}
            assert '白名单文件读取失败' in result['logs']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_028(self, setup_ab_service):
        """TC-ABS-028：实验策略 hash_range 格式异常时回退到 [0,100]"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-028",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "实验策略 hash_range 格式异常时回退到 [0,100]",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：实验配置文件中策略 s_bad 的 hash_range=["bad"]

            harness = setup_ab_service
            result = harness.bad_hash_range_still_evaluates()
            assert result['status'] == 200
            assert result['strategy_id'] == 's_bad'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_029(self, setup_ab_service):
        """TC-ABS-029：实验策略 params 非 dict 时回退为空 dict"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-029",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "实验策略 params 非 dict 时回退为空 dict",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：实验配置文件中策略 s_bad_params 的 params="bad"

            harness = setup_ab_service
            result = harness.bad_params_fall_back_empty()
            assert result['status'] == 200
            assert result['params'] == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 三、Schema 校验 ──

    def test_tc_abs_030(self, setup_ab_service):
        """TC-ABS-030：evaluate 缺少 user_id 返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-030",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "evaluate 缺少 user_id 返回 422",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：POST /api/v1/ab/evaluate body 缺少 user_id

            harness = setup_ab_service
            resp = harness.post("/api/v1/ab/evaluate", {"request_id": "req_abs_030", "experiment_names": ["exp_ab_basic"]})
            assert resp.status_code == 422
            assert ['body', 'user_id'] in [item['loc'] for item in resp.json()['detail']]
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_031(self, setup_ab_service):
        """TC-ABS-031：创建实验 strategies 类型错误返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-031",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "创建实验 strategies 类型错误返回 422",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：POST /api/v1/ab/experiments body {"name":"exp_abs_bad_schema","strategies":"bad"}

            harness = setup_ab_service
            resp = harness.post("/api/v1/ab/experiments", {"name": "exp_abs_bad_schema", "strategies": "bad"})
            assert resp.status_code == 422
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_032(self, setup_ab_service):
        """TC-ABS-032：单用户白名单 strategy_map 类型错误返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-032",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "单用户白名单 strategy_map 类型错误返回 422",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：PUT /api/v1/ab/whitelist/u_abs_bad_schema body {"strategy_map":"bad"}

            harness = setup_ab_service
            resp = harness.put("/api/v1/ab/whitelist/u_abs_bad_schema", {"strategy_map": "bad"})
            assert resp.status_code == 422
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 四、服务隔离与远程 SDK ──

    def test_tc_abs_033(self, setup_ab_service):
        """TC-ABS-033：service 模块可独立导入"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-033",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "service 模块可独立导入",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：在仅包含 ab_experiment_sdk 包的隔离 Python 进程中执行 import ab_experiment_sdk.service

            harness = setup_ab_service
            result = harness.import_works_from_other_cwd()
            assert result['returncode'] == 0, result['stderr']
            assert 'ok ab_experiment_sdk.service' in result['stdout']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_034(self, setup_ab_service):
        """TC-ABS-034：service 导入不在当前目录产生副作用文件"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-034",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "service 导入不在当前目录产生副作用文件",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：在临时目录中执行 import ab_experiment_sdk.service，随后检查当前工作目录

            harness = setup_ab_service
            result = harness.import_has_no_default_file_side_effect()
            assert result['returncode'] == 0, result['stderr']
            assert 'exists False' in result['stdout']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_035(self, setup_ab_service):
        """TC-ABS-035：Remote SDK evaluate 端到端调用"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-035",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "Remote SDK evaluate 端到端调用",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：AB 服务启动，白名单 u1 -> {"exp_game":"game_on"}
            # SETUP: 请求覆盖：调用 RemoteABExperimentSDK.evaluate(user_id="u1", experiment_names=["exp_game"])

            harness = setup_ab_service
            harness.prepare_standard_experiments(names=["exp_game", "exp_cal"])
            result = harness.remote_sdk_evaluate_whitelist()
            assert result['request_id'] == 'req_abs_035'
            assert result['strategy_id'] == 'game_on'
            assert result['hit_reason'] == 'whitelist'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_036(self, setup_ab_service):
        """TC-ABS-036：Remote SDK 设置单用户白名单并验证 evaluate"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-036",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "Remote SDK 设置单用户白名单并验证 evaluate",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：调用 sdk.set_user_whitelist("u2", {"exp_cal":"cal_on"})，随后 evaluate user_id="u2"、experiment_names=["exp_cal"]

            harness = setup_ab_service
            harness.prepare_standard_experiments(names=["exp_game", "exp_cal"])
            result = harness.remote_sdk_set_user_whitelist()
            assert result['strategy_id'] == 'cal_on'
            assert result['hit_reason'] == 'whitelist'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_037(self, setup_ab_service):
        """TC-ABS-037：Remote SDK 清除单用户白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-037",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "Remote SDK 清除单用户白名单",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：u2 白名单已存在
            # SETUP: 请求覆盖：调用 sdk.clear_whitelist("u2")

            harness = setup_ab_service
            harness.prepare_standard_experiments(names=["exp_game", "exp_cal"])
            result = harness.remote_sdk_clear_user_whitelist()
            assert 'u2' not in result['whitelist']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_038(self, setup_ab_service):
        """TC-ABS-038：Remote SDK 批量覆盖白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-038",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "Remote SDK 批量覆盖白名单",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：已有白名单数据
            # SETUP: 请求覆盖：调用 sdk.set_whitelist({"u3":{"exp_game":"game_on"}})

            harness = setup_ab_service
            harness.prepare_standard_experiments(names=["exp_game", "exp_cal"])
            result = harness.remote_sdk_replace_whitelist()
            assert result['whitelist'] == {'u3': {'exp_game': 'game_on'}}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_039(self, setup_ab_service):
        """TC-ABS-039：Remote SDK 清空全部白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-039",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "Remote SDK 清空全部白名单",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：已有白名单数据
            # SETUP: 请求覆盖：调用 sdk.clear_whitelist()

            harness = setup_ab_service
            harness.prepare_standard_experiments(names=["exp_game", "exp_cal"])
            result = harness.remote_sdk_clear_all_whitelist()
            assert result['whitelist'] == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_040(self, setup_ab_service):
        """TC-ABS-040：Remote SDK 遇到服务端 500 时抛出 HTTPStatusError"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-040",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/boundary.md",
            "title": "Remote SDK 遇到服务端 500 时抛出 HTTPStatusError",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：mock AB 服务端对 /api/v1/ab/evaluate 固定返回 HTTP 500
            # SETUP: 请求覆盖_2：调用 sdk.evaluate(user_id="u_err")

            harness = setup_ab_service
            result = harness.remote_sdk_raises_on_http_error()
            assert result['raised'] is True
            assert result['status_code'] == 500
        finally:
            reset_case_context(__aitest_ctx_token)



__codegen_skipped__ = []
