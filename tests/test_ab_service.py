from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from ab_experiment_sdk.service import create_app


def _write_experiments(path: Path) -> None:
    payload = {
        "experiments": [
            {
                "name": "exp_game",
                "strategies": [
                    {
                        "id": "game_on",
                        "hash_range": [0, 100],
                        "params": {"enable_coarse_rank": True},
                    }
                ],
            },
            {
                "name": "exp_cal",
                "strategies": [
                    {
                        "id": "cal_on",
                        "hash_range": [0, 100],
                        "params": {"enable_calibration": True},
                    }
                ],
            },
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def _load_experiments(path: Path) -> dict:
    return json.loads(path.read_text())


def _build_client(tmp_path: Path) -> tuple[TestClient, Path]:
    experiments_path = tmp_path / "experiments.json"
    _write_experiments(experiments_path)
    app = create_app(
        experiments_path=str(experiments_path),
        initial_whitelist={"u_white": {"exp_game": "game_on"}},
    )
    return TestClient(app), experiments_path


def test_health(tmp_path):
    client, _ = _build_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    client.close()


def test_evaluate_with_whitelist(tmp_path):
    client, _ = _build_client(tmp_path)
    response = client.post(
        "/api/v1/ab/evaluate",
        json={
            "user_id": "u_white",
            "request_id": "req-1",
            "experiment_names": ["exp_game"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    assert body["assignments"]["exp_game"]["strategy_id"] == "game_on"
    assert body["assignments"]["exp_game"]["hit_reason"] == "whitelist"
    client.close()


def test_experiment_list_and_get(tmp_path):
    client, _ = _build_client(tmp_path)
    response = client.get("/api/v1/ab/experiments")
    assert response.status_code == 200
    names = {exp["name"] for exp in response.json()}
    assert names == {"exp_game", "exp_cal"}

    response = client.get("/api/v1/ab/experiments/exp_game")
    assert response.status_code == 200
    assert response.json()["name"] == "exp_game"
    client.close()


def test_experiment_create_update_delete_and_persist(tmp_path):
    client, experiments_path = _build_client(tmp_path)

    create_payload = {
        "name": "exp_new",
        "strategies": [
            {
                "id": "new_on",
                "hash_range": [0, 100],
                "params": {"flag": 1},
            }
        ],
    }
    response = client.post("/api/v1/ab/experiments", json=create_payload)
    assert response.status_code == 200
    assert response.json()["name"] == "exp_new"

    persisted = _load_experiments(experiments_path)
    persisted_names = {exp["name"] for exp in persisted["experiments"]}
    assert "exp_new" in persisted_names

    update_payload = {
        "name": "exp_new",
        "strategies": [
            {
                "id": "new_off",
                "hash_range": [0, 100],
                "params": {"flag": 0},
            }
        ],
    }
    response = client.put("/api/v1/ab/experiments/exp_new", json=update_payload)
    assert response.status_code == 200
    assert response.json()["strategies"][0]["id"] == "new_off"

    response = client.delete("/api/v1/ab/experiments/exp_new")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    response = client.get("/api/v1/ab/experiments/exp_new")
    assert response.status_code == 404
    client.close()


def test_experiment_create_conflict(tmp_path):
    client, _ = _build_client(tmp_path)
    payload = {
        "name": "exp_game",
        "strategies": [{"id": "dup", "hash_range": [0, 100], "params": {}}],
    }
    response = client.post("/api/v1/ab/experiments", json=payload)
    assert response.status_code == 409
    client.close()


def test_whitelist_crud(tmp_path):
    client, _ = _build_client(tmp_path)

    response = client.get("/api/v1/ab/whitelist")
    assert response.status_code == 200
    assert "u_white" in response.json()

    response = client.put(
        "/api/v1/ab/whitelist/user_a",
        json={"strategy_map": {"exp_cal": "cal_on"}},
    )
    assert response.status_code == 200
    assert response.json() == {"exp_cal": "cal_on"}

    response = client.get("/api/v1/ab/whitelist/user_a")
    assert response.status_code == 200
    assert response.json() == {"exp_cal": "cal_on"}

    response = client.put(
        "/api/v1/ab/whitelist",
        json={"user_b": {"exp_game": "game_on"}},
    )
    assert response.status_code == 200
    assert response.json() == {"user_b": {"exp_game": "game_on"}}

    response = client.delete("/api/v1/ab/whitelist/user_b")
    assert response.status_code == 200
    assert response.json()["cleared"] is True

    response = client.get("/api/v1/ab/whitelist/user_b")
    assert response.status_code == 404

    response = client.delete("/api/v1/ab/whitelist")
    assert response.status_code == 200
    assert response.json()["cleared"] is True

    response = client.get("/api/v1/ab/whitelist")
    assert response.status_code == 200
    assert response.json() == {}
    client.close()


def test_whitelist_persisted_and_reloaded(tmp_path):
    """白名单变更持久化到文件，重启后自动加载"""
    experiments_path = tmp_path / "experiments.json"
    _write_experiments(experiments_path)
    whitelist_path = tmp_path / "whitelist.json"

    # 第一次启动，设置白名单
    app1 = create_app(
        experiments_path=str(experiments_path),
        whitelist_path=str(whitelist_path),
    )
    client1 = TestClient(app1)
    client1.put(
        "/api/v1/ab/whitelist/user_x",
        json={"strategy_map": {"exp_game": "game_on"}},
    )
    assert whitelist_path.exists(), "白名单文件应已持久化"
    persisted = json.loads(whitelist_path.read_text())
    assert persisted == {"user_x": {"exp_game": "game_on"}}
    client1.close()

    # 第二次启动（模拟重启），不传 initial_whitelist，应从文件加载
    app2 = create_app(
        experiments_path=str(experiments_path),
        whitelist_path=str(whitelist_path),
    )
    client2 = TestClient(app2)
    response = client2.get("/api/v1/ab/whitelist")
    assert response.status_code == 200
    assert response.json() == {"user_x": {"exp_game": "game_on"}}

    # 用白名单做 evaluate 验证
    response = client2.post(
        "/api/v1/ab/evaluate",
        json={"user_id": "user_x", "experiment_names": ["exp_game"]},
    )
    assert response.status_code == 200
    assert response.json()["assignments"]["exp_game"]["hit_reason"] == "whitelist"
    client2.close()


def test_service_module_can_import_without_coupon_system_dependency(tmp_path):
    src_pkg = Path(__file__).resolve().parents[1] / "ab_experiment_sdk"
    isolated_root = tmp_path / "isolated_pkg"
    isolated_pkg = isolated_root / "ab_experiment_sdk"
    isolated_pkg.mkdir(parents=True, exist_ok=True)
    for file in src_pkg.glob("*.py"):
        (isolated_pkg / file.name).write_text(file.read_text())

    run_dir = tmp_path / "run_import"
    run_dir.mkdir(parents=True, exist_ok=True)
    script = (
        "import os,sys;"
        f"os.chdir({str(run_dir)!r});"
        f"sys.path.insert(0,{str(isolated_root)!r});"
        "import ab_experiment_sdk.service as s;"
        "print('ok', s.__name__)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ok ab_experiment_sdk.service" in completed.stdout


def test_service_import_has_no_cwd_file_side_effect(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    run_dir = tmp_path / "run_side_effect"
    run_dir.mkdir(parents=True, exist_ok=True)
    script = (
        "import os,sys,pathlib;"
        f"os.chdir({str(run_dir)!r});"
        f"sys.path.insert(0,{str(repo_root)!r});"
        "import ab_experiment_sdk.service as s;"
        "p=pathlib.Path('coupon_system/config/experiments.json');"
        "print('exists', p.exists())"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "exists False" in completed.stdout
