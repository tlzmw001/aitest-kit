# Auto-generated from test_workspace/suites/coupon_system/ab_service_smoke/business.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/ab_service_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
from test_workspace.targets.coupon_system.fixtures.ab_service import setup_ab_service


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


class TestAbServiceBusiness:
    """ab_service 业务测试用例"""

    # ── 一、健康检查与评估 ──

    def test_tc_abs_001(self, setup_ab_service):
        """TC-ABS-001：健康检查返回 ok"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-001",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "健康检查返回 ok",
            "priority": "P0",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：GET /health

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-001")
            resp = ab.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {'status': 'ok'}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_002(self, setup_ab_service):
        """TC-ABS-002：hash 分流命中半开区间策略"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-002",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "hash 分流命中半开区间策略",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：POST /api/v1/ab/evaluate，user_id 选择 md5(user_id)%100 落入 s_a 的 [0,50)，experiment_names=["exp_ab_basic"]

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-002")
            resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_002", "context": {}, "experiment_names": ["exp_ab_basic"]})
            assert resp.status_code == 200
            assign = resp.json()['assignments']
            assert assign['exp_ab_basic']['strategy_id'] == 's_a'
            assert assign['exp_ab_basic']['hit_reason'] == 'hash'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_003(self, setup_ab_service):
        """TC-ABS-003：白名单优先于 hash 分流"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-003",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "白名单优先于 hash 分流",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：先 PUT /api/v1/ab/whitelist/u_abs_white，body {"strategy_map":{"exp_ab_basic":"s_b"}}
            # SETUP: 接口调用：再 evaluate user_id="u_abs_white"、experiment_names=["exp_ab_basic"]

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-003")
            resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_white", "request_id": "req_abs_003", "context": {}, "experiment_names": ["exp_ab_basic"]})
            assert resp.status_code == 200
            assign = resp.json()['assignments']
            assert assign['exp_ab_basic']['strategy_id'] == 's_b'
            assert assign['exp_ab_basic']['hit_reason'] == 'whitelist'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_004(self, setup_ab_service):
        """TC-ABS-004：experiment_names 为 null 时评估全部实验"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-004",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "experiment_names 为 null 时评估全部实验",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：evaluate 请求 experiment_names=null
            # SETUP: 请求覆盖：服务中至少存在 exp_ab_basic 和 exp_ab_extra

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-004")
            resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_004", "context": {}, "experiment_names": None})
            assert resp.status_code == 200
            assign = resp.json()['assignments']
            assert {'exp_ab_basic', 'exp_ab_extra'} <= set(assign.keys())
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_005(self, setup_ab_service):
        """TC-ABS-005：experiment_names 为空数组时返回空 assignments"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-005",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "experiment_names 为空数组时返回空 assignments",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：evaluate 请求 experiment_names=[]

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-005")
            resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_005", "context": {}, "experiment_names": []})
            assert resp.status_code == 200
            assert resp.json()['assignments'] == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_006(self, setup_ab_service):
        """TC-ABS-006：experiment_names 指定实验时只评估该实验"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-006",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "experiment_names 指定实验时只评估该实验",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：evaluate 请求 experiment_names=["exp_ab_basic"]

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-006")
            resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_006", "context": {}, "experiment_names": ["exp_ab_basic"]})
            assert resp.status_code == 200
            assert set(resp.json()['assignments'].keys()) <= {'exp_ab_basic'}
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、实验管理 ──

    def test_tc_abs_007(self, setup_ab_service):
        """TC-ABS-007：列出所有实验"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-007",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "列出所有实验",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：服务已初始化 exp_game 和 exp_cal 两个实验
            # SETUP: 接口调用：调用 GET /api/v1/ab/experiments

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-007")
            resp = ab.get("/api/v1/ab/experiments")
            assert resp.status_code == 200
            assert {'exp_game', 'exp_cal'} <= {item['name'] for item in resp.json()}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_008(self, setup_ab_service):
        """TC-ABS-008：获取单个实验详情"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-008",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "获取单个实验详情",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：exp_game 已存在
            # SETUP: 接口调用：调用 GET /api/v1/ab/experiments/exp_game

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-008")
            resp = ab.get("/api/v1/ab/experiments/exp_game")
            assert resp.status_code == 200
            assert resp.json()['name'] == 'exp_game'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_009(self, setup_ab_service):
        """TC-ABS-009：创建实验并可查询"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-009",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "创建实验并可查询",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：POST /api/v1/ab/experiments，body 为 {"name":"exp_abs_create","strategies":[{"id":"s1","hash_range":[0,100],"params":{"k":"v"}}]}

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-009")
            payload = {'name': 'exp_abs_create', 'strategies': [{'id': 's1', 'hash_range': [0, 100], 'params': {'k': 'v'}}]}
            ab.snapshot_experiment("exp_abs_create")
            resp = ab.post("/api/v1/ab/experiments", payload)
            assert resp.status_code == 200
            assert resp.json()['name'] == 'exp_abs_create'
            resp = ab.get("/api/v1/ab/experiments/exp_abs_create")
            assert resp.status_code == 200
            assert resp.json()['name'] == 'exp_abs_create'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_010(self, setup_ab_service):
        """TC-ABS-010：更新实验整体替换策略列表"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-010",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "更新实验整体替换策略列表",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：已有 exp_abs_update，执行 PUT /api/v1/ab/experiments/exp_abs_update，body 中策略只保留 s_new

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-010")
            ab.upsert_experiment({"name": "exp_abs_update", "strategies": [{"id": "s_old", "hash_range": [0, 100], "params": {}}]})
            payload = {'name': 'exp_abs_update', 'strategies': [{'id': 's_new', 'hash_range': [0, 100], 'params': {}}]}
            resp = ab.put("/api/v1/ab/experiments/exp_abs_update", payload)
            assert resp.status_code == 200
            resp = ab.get("/api/v1/ab/experiments/exp_abs_update")
            assert [item['id'] for item in resp.json()['strategies']] == ['s_new']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_011(self, setup_ab_service):
        """TC-ABS-011：删除实验后查询返回 404"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-011",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "删除实验后查询返回 404",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：创建 exp_abs_delete 后执行 DELETE /api/v1/ab/experiments/exp_abs_delete，再 GET 同名实验

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-011")
            ab.upsert_experiment({"name": "exp_abs_delete", "strategies": [{"id": "s1", "hash_range": [0, 100], "params": {}}]})
            resp = ab.delete("/api/v1/ab/experiments/exp_abs_delete")
            assert resp.status_code == 200
            assert resp.json() == {'deleted': True}
            resp = ab.get("/api/v1/ab/experiments/exp_abs_delete")
            assert resp.status_code == 404
            assert resp.json()['detail'] == 'experiment not found'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_012(self, setup_ab_service):
        """TC-ABS-012：实验增删改持久化到文件并重启恢复"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-012",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "实验增删改持久化到文件并重启恢复",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 环境覆盖：使用独立 AB_SERVICE_EXPERIMENTS_PATH 创建 exp_abs_persist，重启 AB 服务

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-012")
            result = ab.isolated_experiment_persists_auto()
            assert result['create_status'] == 200
            assert result['read_status'] == 200
            assert result['name'] == 'exp_abs_persist'
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 三、白名单管理 ──

    def test_tc_abs_013(self, setup_ab_service):
        """TC-ABS-013：查询全部白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-013",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "查询全部白名单",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：服务已有白名单 u_white -> {"exp_game":"game_on"}
            # SETUP: 接口调用：调用 GET /api/v1/ab/whitelist

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-013")
            resp = ab.get("/api/v1/ab/whitelist")
            assert resp.status_code == 200
            assert 'u_white' in resp.json()
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_014(self, setup_ab_service):
        """TC-ABS-014：单用户白名单设置和查询"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-014",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "单用户白名单设置和查询",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：PUT /api/v1/ab/whitelist/u_abs_user，body {"strategy_map":{"exp_ab_basic":"s_a"}}
            # SETUP: 请求覆盖：随后 GET /api/v1/ab/whitelist/u_abs_user

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-014")
            ab.snapshot_whitelist()
            resp = ab.put("/api/v1/ab/whitelist/u_abs_user", {"strategy_map": {"exp_ab_basic": "s_a"}})
            assert resp.status_code == 200
            resp = ab.get("/api/v1/ab/whitelist/u_abs_user")
            assert resp.status_code == 200
            assert resp.json() == {'exp_ab_basic': 's_a'}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_015(self, setup_ab_service):
        """TC-ABS-015：全量白名单替换和查看"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-015",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "全量白名单替换和查看",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：PUT /api/v1/ab/whitelist，body {"u_abs_1":{"exp_ab_basic":"s_a"},"u_abs_2":{"exp_ab_basic":"s_b"}}

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-015")
            ab.snapshot_whitelist()
            resp = ab.put("/api/v1/ab/whitelist", {"u_abs_1": {"exp_ab_basic": "s_a"}, "u_abs_2": {"exp_ab_basic": "s_b"}})
            assert resp.status_code == 200
            resp = ab.get("/api/v1/ab/whitelist")
            assert resp.status_code == 200
            assert resp.json() == {'u_abs_1': {'exp_ab_basic': 's_a'}, 'u_abs_2': {'exp_ab_basic': 's_b'}}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_016(self, setup_ab_service):
        """TC-ABS-016：删除单用户白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-016",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "删除单用户白名单",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：user_b 白名单已存在
            # SETUP: 接口调用：调用 DELETE /api/v1/ab/whitelist/user_b，随后查询该用户白名单

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-016")
            resp = ab.delete("/api/v1/ab/whitelist/user_b")
            assert resp.status_code == 200
            assert resp.json() == {'cleared': True}
            resp = ab.get("/api/v1/ab/whitelist/user_b")
            assert resp.status_code == 404
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_017(self, setup_ab_service):
        """TC-ABS-017：清空全部白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-017",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "清空全部白名单",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：先设置全量白名单，再 DELETE /api/v1/ab/whitelist

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-017")
            resp = ab.delete("/api/v1/ab/whitelist")
            assert resp.status_code == 200
            assert resp.json() == {'cleared': True}
            resp = ab.get("/api/v1/ab/whitelist")
            assert resp.status_code == 200
            assert resp.json() == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_018(self, setup_ab_service):
        """TC-ABS-018：白名单持久化并重启恢复"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-018",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "白名单持久化并重启恢复",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：设置 u_abs_persist 白名单后重启 AB 服务

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-018")
            result = ab.isolated_whitelist_persists_auto()
            assert result['write_status'] == 200
            assert result['read_status'] == 200
            assert result['body'] == {'exp_game': 'game_on'}
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 四、错误场景 ──

    def test_tc_abs_019(self, setup_ab_service):
        """TC-ABS-019：创建重名实验返回 409"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-019",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "创建重名实验返回 409",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：连续两次 POST /api/v1/ab/experiments 创建 exp_abs_dup

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-019")
            payload = {'name': 'exp_abs_dup', 'strategies': [{'id': 's1', 'hash_range': [0, 100], 'params': {}}]}
            ab.snapshot_experiment("exp_abs_dup")
            first = ab.post("/api/v1/ab/experiments", payload)
            assert first.status_code == 200
            second = ab.post("/api/v1/ab/experiments", payload)
            assert second.status_code == 409
            assert second.json()['detail'] == 'experiment already exists: exp_abs_dup'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_020(self, setup_ab_service):
        """TC-ABS-020：更新实验路径名与 body 名不一致返回 400"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-020",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "更新实验路径名与 body 名不一致返回 400",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：PUT /api/v1/ab/experiments/exp_abs_path，body {"name":"exp_abs_body","strategies":[]}

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-020")
            resp = ab.put("/api/v1/ab/experiments/exp_abs_path", {"name": "exp_abs_body", "strategies": []})
            assert resp.status_code == 400
            assert resp.json()['detail'] == 'path name and payload name mismatch'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_021(self, setup_ab_service):
        """TC-ABS-021：查询不存在用户白名单返回 404"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-021",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "查询不存在用户白名单返回 404",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：GET /api/v1/ab/whitelist/u_abs_not_exists

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-021")
            resp = ab.get("/api/v1/ab/whitelist/u_abs_not_exists")
            assert resp.status_code == 404
            assert resp.json()['detail'] == 'user whitelist not found'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_abs_022(self, setup_ab_service):
        """TC-ABS-022：删除不存在用户白名单静默成功"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-022",
            "module": "ab_service",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/ab_service_smoke/business.md",
            "title": "删除不存在用户白名单静默成功",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：DELETE /api/v1/ab/whitelist/u_abs_not_exists

            ab = setup_ab_service
            ab = setup_ab_service(case_id="TC-ABS-022")
            resp = ab.delete("/api/v1/ab/whitelist/u_abs_not_exists")
            assert resp.status_code == 200
            assert resp.json() == {'cleared': True}
        finally:
            reset_case_context(__aitest_ctx_token)


# TODO: setup_ab_service fixture 需要手写实现（→ tests/fixtures/ab_service.py）

__codegen_skipped__ = []
