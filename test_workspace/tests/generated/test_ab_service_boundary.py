# Auto-generated from test_workspace/cases/ab_service/boundary.md
# DO NOT EDIT — regenerate with: /test-codegen ab_service
import pytest
from test_workspace.tests.helpers import http as http_helper
import httpx
import logging
import subprocess
import sys
from pathlib import Path
from ab_experiment_sdk import ABExperimentRequest
from ab_experiment_sdk.remote_client import RemoteABExperimentSDK
from test_workspace.tests.fixtures.ab_service import build_isolated_client, write_experiments_file


class TestAbServiceBoundary:
    """ab_service 边界测试用例"""

    # ── 一、分流边界 ──

    def test_tc_abs_023(self, setup_ab_service):
        """TC-ABS-023：hash_range 重叠时命中第一个匹配策略"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-023",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "hash_range 重叠时命中第一个匹配策略",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 请求覆盖：实验 exp_abs_overlap 策略顺序为 s_first [0,80)、s_second [50,100)
        # SETUP: 前置操作：选择 hash=60 的 user_id

        ab = setup_ab_service(case_id="TC-ABS-023")
        resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_overlap_243", "request_id": "req_abs_023", "experiment_names": ["exp_abs_overlap"]})
        assert resp.status_code == 200
        assert resp.json()["assignments"]["exp_abs_overlap"]["strategy_id"] == "s_first"

    def test_tc_abs_024(self, setup_ab_service):
        """TC-ABS-024：空策略实验评估后不返回 assignment"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-024",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "空策略实验评估后不返回 assignment",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 前置操作：创建实验 exp_abs_empty，strategies=[]
        # SETUP: 接口调用：evaluate 指定该实验

        ab = setup_ab_service(case_id="TC-ABS-024")
        resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_024", "experiment_names": ["exp_abs_empty"]})
        assert resp.status_code == 200
        assert resp.json()["assignments"] == {}

    def test_tc_abs_025(self, setup_ab_service):
        """TC-ABS-025：evaluate 指定不存在实验名时静默跳过"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-025",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "evaluate 指定不存在实验名时静默跳过",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 接口调用：evaluate experiment_names=["not_exists_exp"]

        ab = setup_ab_service(case_id="TC-ABS-025")
        resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_025", "experiment_names": ["not_exists_exp"]})
        assert resp.status_code == 200
        assert resp.json()["assignments"] == {}

    # ── 二、文件容错 ──

    def test_tc_abs_026(self, tmp_path):
        """TC-ABS-026：实验配置文件不存在时自动创建空配置"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-026",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "实验配置文件不存在时自动创建空配置",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 环境覆盖：使用不存在的 AB_SERVICE_EXPERIMENTS_PATH=/tmp/aitest_ab_service_boundary/new/experiments.json 启动服务

        experiments_path = tmp_path / "new" / "experiments.json"
        client, _, _ = build_isolated_client(experiments_path.parent)
        resp = client.get("/api/v1/ab/experiments")
        assert resp.status_code == 200
        assert resp.json() == []
        assert experiments_path.exists()
        client.close()

    @pytest.mark.manual
    def test_tc_abs_027(self, tmp_path, caplog):
        """TC-ABS-027：白名单文件损坏时忽略并以空白名单启动"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-027",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "白名单文件损坏时忽略并以空白名单启动",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 环境覆盖：白名单文件内容为 {bad json，启动服务

        caplog.set_level(logging.WARNING, logger="ab_experiment_sdk.service")
        client, _, _ = build_isolated_client(tmp_path, whitelist_text="{bad json")
        resp = client.get("/api/v1/ab/whitelist")
        assert resp.status_code == 200
        assert resp.json() == {}
        assert "白名单文件读取失败" in caplog.text
        client.close()

    def test_tc_abs_028(self, tmp_path):
        """TC-ABS-028：实验策略 hash_range 格式异常时回退到 [0,100]"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-028",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "实验策略 hash_range 格式异常时回退到 [0,100]",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 请求覆盖：实验配置文件中策略 s_bad 的 hash_range=["bad"]

        client, _, _ = build_isolated_client(tmp_path, experiments=[
            {"name": "exp_abs_bad_hash", "strategies": [{"id": "s_bad", "hash_range": ["bad"], "params": {}}]},
        ])
        resp = client.post("/api/v1/ab/evaluate", json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_hash"]})
        assert resp.status_code == 200
        assert resp.json()["assignments"]["exp_abs_bad_hash"]["strategy_id"] == "s_bad"
        client.close()

    def test_tc_abs_029(self, tmp_path):
        """TC-ABS-029：实验策略 params 非 dict 时回退为空 dict"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-029",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "实验策略 params 非 dict 时回退为空 dict",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 请求覆盖：实验配置文件中策略 s_bad_params 的 params="bad"

        client, _, _ = build_isolated_client(tmp_path, experiments=[
            {"name": "exp_abs_bad_params", "strategies": [{"id": "s_bad_params", "hash_range": [0, 100], "params": "bad"}]},
        ])
        resp = client.post("/api/v1/ab/evaluate", json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_params"]})
        assert resp.status_code == 200
        assert resp.json()["assignments"]["exp_abs_bad_params"]["params"] == {}
        client.close()

    # ── 三、Schema 校验 ──

    def test_tc_abs_030(self, setup_ab_service):
        """TC-ABS-030：evaluate 缺少 user_id 返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-030",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "evaluate 缺少 user_id 返回 422",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 接口调用：POST /api/v1/ab/evaluate body 缺少 user_id

        ab = setup_ab_service(case_id="TC-ABS-030")
        resp = ab.post("/api/v1/ab/evaluate", {"request_id": "req_abs_030", "experiment_names": ["exp_ab_basic"]})
        assert resp.status_code == 422
        assert ["body", "user_id"] in [item["loc"] for item in resp.json()["detail"]]

    def test_tc_abs_031(self, setup_ab_service):
        """TC-ABS-031：创建实验 strategies 类型错误返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-031",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "创建实验 strategies 类型错误返回 422",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 接口调用：POST /api/v1/ab/experiments body {"name":"exp_abs_bad_schema","strategies":"bad"}

        ab = setup_ab_service(case_id="TC-ABS-031")
        resp = ab.post("/api/v1/ab/experiments", {"name": "exp_abs_bad_schema", "strategies": "bad"})
        assert resp.status_code == 422

    def test_tc_abs_032(self, setup_ab_service):
        """TC-ABS-032：单用户白名单 strategy_map 类型错误返回 422"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-032",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "单用户白名单 strategy_map 类型错误返回 422",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 接口调用：PUT /api/v1/ab/whitelist/u_abs_bad_schema body {"strategy_map":"bad"}

        ab = setup_ab_service(case_id="TC-ABS-032")
        resp = ab.put("/api/v1/ab/whitelist/u_abs_bad_schema", {"strategy_map": "bad"})
        assert resp.status_code == 422

    # ── 四、服务隔离与远程 SDK ──

    def test_tc_abs_033(self, tmp_path):
        """TC-ABS-033：service 模块可独立导入"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-033",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "service 模块可独立导入",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 请求覆盖：在仅包含 ab_experiment_sdk 包的隔离 Python 进程中执行 import ab_experiment_sdk.service

        repo_root = Path(__file__).resolve().parents[3]
        src_pkg = repo_root / "ab_experiment_sdk"
        isolated_root = tmp_path / "isolated_pkg"
        isolated_pkg = isolated_root / "ab_experiment_sdk"
        isolated_pkg.mkdir(parents=True, exist_ok=True)
        for file in src_pkg.glob("*.py"):
            (isolated_pkg / file.name).write_text(file.read_text(), encoding="utf-8")
        run_dir = tmp_path / "run_import"
        run_dir.mkdir(parents=True, exist_ok=True)
        script = (
            "import os,sys;"
            f"os.chdir({str(run_dir)!r});"
            f"sys.path.insert(0,{str(isolated_root)!r});"
            "import ab_experiment_sdk.service as s;"
            "print('ok', s.__name__)"
        )
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert "ok ab_experiment_sdk.service" in completed.stdout

    def test_tc_abs_034(self, tmp_path):
        """TC-ABS-034：service 导入不在当前目录产生副作用文件"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-034",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "service 导入不在当前目录产生副作用文件",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 前置操作：在临时目录中执行 import ab_experiment_sdk.service，随后检查当前工作目录

        repo_root = Path(__file__).resolve().parents[3]
        run_dir = tmp_path / "run_side_effect"
        run_dir.mkdir(parents=True, exist_ok=True)
        script = (
            "import os,sys,pathlib;"
            f"os.chdir({str(run_dir)!r});"
            f"sys.path.insert(0,{str(repo_root)!r});"
            "import ab_experiment_sdk.service;"
            "p=pathlib.Path('coupon_system/config/experiments.json');"
            "print('exists', p.exists())"
        )
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert "exists False" in completed.stdout

    def test_tc_abs_035(self, setup_ab_service, tmp_path):
        """TC-ABS-035：Remote SDK evaluate 端到端调用"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-035",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "Remote SDK evaluate 端到端调用",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 前置操作：AB 服务启动，白名单 u1 -> {"exp_game":"game_on"}
        # SETUP: 请求覆盖：调用 RemoteABExperimentSDK.evaluate(user_id="u1", experiment_names=["exp_game"])

        ab = setup_ab_service(case_id="TC-ABS-035")
        sdk, client = ab.remote_sdk(tmp_path)
        response = sdk.evaluate(ABExperimentRequest(user_id="u1", request_id="req_abs_035", experiment_names=["exp_game"]))
        assert response.request_id == "req_abs_035"
        assert response.assignments["exp_game"].strategy_id == "game_on"
        assert response.assignments["exp_game"].hit_reason == "whitelist"
        sdk.close()
        client.close()

    def test_tc_abs_036(self, setup_ab_service, tmp_path):
        """TC-ABS-036：Remote SDK 设置单用户白名单并验证 evaluate"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-036",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "Remote SDK 设置单用户白名单并验证 evaluate",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 接口调用：调用 sdk.set_user_whitelist("u2", {"exp_cal":"cal_on"})，随后 evaluate user_id="u2"、experiment_names=["exp_cal"]

        ab = setup_ab_service(case_id="TC-ABS-036")
        sdk, client = ab.remote_sdk(tmp_path)
        sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
        response = sdk.evaluate(ABExperimentRequest(user_id="u2", experiment_names=["exp_cal"]))
        assert response.assignments["exp_cal"].strategy_id == "cal_on"
        assert response.assignments["exp_cal"].hit_reason == "whitelist"
        sdk.close()
        client.close()

    def test_tc_abs_037(self, setup_ab_service, tmp_path):
        """TC-ABS-037：Remote SDK 清除单用户白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-037",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "Remote SDK 清除单用户白名单",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 前置操作：u2 白名单已存在
        # SETUP: 请求覆盖：调用 sdk.clear_whitelist("u2")

        ab = setup_ab_service(case_id="TC-ABS-037")
        sdk, client = ab.remote_sdk(tmp_path)
        sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
        sdk.clear_whitelist("u2")
        assert "u2" not in sdk.get_whitelist()
        sdk.close()
        client.close()

    def test_tc_abs_038(self, setup_ab_service, tmp_path):
        """TC-ABS-038：Remote SDK 批量覆盖白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-038",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "Remote SDK 批量覆盖白名单",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 前置操作：已有白名单数据
        # SETUP: 请求覆盖：调用 sdk.set_whitelist({"u3":{"exp_game":"game_on"}})

        ab = setup_ab_service(case_id="TC-ABS-038")
        sdk, client = ab.remote_sdk(tmp_path)
        sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
        assert sdk.get_whitelist() == {"u3": {"exp_game": "game_on"}}
        sdk.close()
        client.close()

    def test_tc_abs_039(self, setup_ab_service, tmp_path):
        """TC-ABS-039：Remote SDK 清空全部白名单"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-039",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "Remote SDK 清空全部白名单",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 前置操作：已有白名单数据
        # SETUP: 请求覆盖：调用 sdk.clear_whitelist()

        ab = setup_ab_service(case_id="TC-ABS-039")
        sdk, client = ab.remote_sdk(tmp_path)
        sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
        sdk.clear_whitelist()
        assert sdk.get_whitelist() == {}
        sdk.close()
        client.close()

    def test_tc_abs_040(self, setup_ab_service):
        """TC-ABS-040：Remote SDK 遇到服务端 500 时抛出 HTTPStatusError"""
        __tc_meta__ = {
            "tc_id": "TC-ABS-040",
            "module": "ab_service",
            "category": "boundary",
            "source": "test_workspace/cases/ab_service/boundary.md",
            "title": "Remote SDK 遇到服务端 500 时抛出 HTTPStatusError",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：mock AB 服务端对 /api/v1/ab/evaluate 固定返回 HTTP 500
        # SETUP: 请求覆盖_2：调用 sdk.evaluate(user_id="u_err")

        def handler(request):
            return httpx.Response(500, json={"detail": "internal error"})

        mock_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ab.test")
        sdk = RemoteABExperimentSDK(base_url="http://ab.test", client=mock_client)
        with pytest.raises(httpx.HTTPStatusError):
            sdk.evaluate(ABExperimentRequest(user_id="u_err"))
        sdk.close()



__codegen_skipped__ = []
