# ab_service 模块 codegen profile

## fixture 依赖

| fixture | 来源 | 用途 |
|---------|------|------|
| `setup_ab_service` | `fixtures/ab_service.py` | 通过 AB 服务公开 HTTP API 预置实验、白名单，并在 teardown 恢复原状态 |
| `tmp_path` | pytest | 构造独立 experiments/whitelist 文件，验证持久化、文件容错和 Remote SDK |
| `caplog` | pytest | 验证白名单文件损坏时的日志 |

## 请求模板

`ab_service` 不是推荐主服务模块，不能使用默认 `/api/v1/recommend` 模板。该模块通过 `case_bodies`
为每条用例显式声明请求入口和断言：

- 运行中 AB 服务 API：使用 `setup_ab_service(...).get/post/put/delete(...)`，返回 `httpx.Response`，不自动 `raise_for_status`
- 文件启动/重启类：使用 fixture 中的 `build_isolated_client(...)` 构造独立 `TestClient`
- Remote SDK 类：通过 `RemoteABExperimentSDK` 搭配隔离 `TestClient` 或 `httpx.MockTransport`

## emitter 规则

```yaml
extra_imports:
  - import httpx
  - import logging
  - import subprocess
  - import sys
  - from pathlib import Path
  - from ab_experiment_sdk import ABExperimentRequest
  - from ab_experiment_sdk.remote_client import RemoteABExperimentSDK
  - from test_workspace.tests.fixtures.ab_service import build_isolated_client, write_experiments_file

case_fixtures:
  TC-ABS-012: [tmp_path]
  TC-ABS-018: [tmp_path]
  TC-ABS-026: [tmp_path]
  TC-ABS-027: [tmp_path, caplog]
  TC-ABS-028: [tmp_path]
  TC-ABS-029: [tmp_path]
  TC-ABS-033: [tmp_path]
  TC-ABS-034: [tmp_path]
  TC-ABS-035: [setup_ab_service, tmp_path]
  TC-ABS-036: [setup_ab_service, tmp_path]
  TC-ABS-037: [setup_ab_service, tmp_path]
  TC-ABS-038: [setup_ab_service, tmp_path]
  TC-ABS-039: [setup_ab_service, tmp_path]

case_bodies:
  TC-ABS-001: |
    ab = setup_ab_service(case_id="TC-ABS-001")
    resp = ab.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

  TC-ABS-002: |
    ab = setup_ab_service(case_id="TC-ABS-002")
    resp = ab.post("/api/v1/ab/evaluate", {
        "user_id": "u_abs_hash_0",
        "request_id": "req_abs_002",
        "context": {},
        "experiment_names": ["exp_ab_basic"],
    })
    assert resp.status_code == 200
    assign = resp.json()["assignments"]
    assert assign["exp_ab_basic"]["strategy_id"] == "s_a"
    assert assign["exp_ab_basic"]["hit_reason"] == "hash"

  TC-ABS-003: |
    ab = setup_ab_service(case_id="TC-ABS-003")
    resp = ab.post("/api/v1/ab/evaluate", {
        "user_id": "u_abs_white",
        "request_id": "req_abs_003",
        "context": {},
        "experiment_names": ["exp_ab_basic"],
    })
    assert resp.status_code == 200
    assign = resp.json()["assignments"]
    assert assign["exp_ab_basic"]["strategy_id"] == "s_b"
    assert assign["exp_ab_basic"]["hit_reason"] == "whitelist"

  TC-ABS-004: |
    ab = setup_ab_service(case_id="TC-ABS-004")
    resp = ab.post("/api/v1/ab/evaluate", {
        "user_id": "u_abs_hash_0",
        "request_id": "req_abs_004",
        "context": {},
        "experiment_names": None,
    })
    assert resp.status_code == 200
    assign = resp.json()["assignments"]
    assert {"exp_ab_basic", "exp_ab_extra"} <= set(assign.keys())

  TC-ABS-005: |
    ab = setup_ab_service(case_id="TC-ABS-005")
    resp = ab.post("/api/v1/ab/evaluate", {
        "user_id": "u_abs_hash_0",
        "request_id": "req_abs_005",
        "context": {},
        "experiment_names": [],
    })
    assert resp.status_code == 200
    assert resp.json()["assignments"] == {}

  TC-ABS-006: |
    ab = setup_ab_service(case_id="TC-ABS-006")
    resp = ab.post("/api/v1/ab/evaluate", {
        "user_id": "u_abs_hash_0",
        "request_id": "req_abs_006",
        "context": {},
        "experiment_names": ["exp_ab_basic"],
    })
    assert resp.status_code == 200
    assert set(resp.json()["assignments"].keys()) <= {"exp_ab_basic"}

  TC-ABS-007: |
    ab = setup_ab_service(case_id="TC-ABS-007")
    resp = ab.get("/api/v1/ab/experiments")
    assert resp.status_code == 200
    assert {"exp_game", "exp_cal"} <= {item["name"] for item in resp.json()}

  TC-ABS-008: |
    ab = setup_ab_service(case_id="TC-ABS-008")
    resp = ab.get("/api/v1/ab/experiments/exp_game")
    assert resp.status_code == 200
    assert resp.json()["name"] == "exp_game"

  TC-ABS-009: |
    ab = setup_ab_service(case_id="TC-ABS-009")
    payload = {"name": "exp_abs_create", "strategies": [{"id": "s1", "hash_range": [0, 100], "params": {"k": "v"}}]}
    ab.snapshot_experiment("exp_abs_create")
    resp = ab.post("/api/v1/ab/experiments", payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "exp_abs_create"
    resp = ab.get("/api/v1/ab/experiments/exp_abs_create")
    assert resp.status_code == 200
    assert resp.json()["name"] == "exp_abs_create"

  TC-ABS-010: |
    ab = setup_ab_service(case_id="TC-ABS-010")
    ab.upsert_experiment({"name": "exp_abs_update", "strategies": [{"id": "s_old", "hash_range": [0, 100], "params": {}}]})
    payload = {"name": "exp_abs_update", "strategies": [{"id": "s_new", "hash_range": [0, 100], "params": {}}]}
    resp = ab.put("/api/v1/ab/experiments/exp_abs_update", payload)
    assert resp.status_code == 200
    resp = ab.get("/api/v1/ab/experiments/exp_abs_update")
    assert [item["id"] for item in resp.json()["strategies"]] == ["s_new"]

  TC-ABS-011: |
    ab = setup_ab_service(case_id="TC-ABS-011")
    ab.upsert_experiment({"name": "exp_abs_delete", "strategies": [{"id": "s1", "hash_range": [0, 100], "params": {}}]})
    resp = ab.delete("/api/v1/ab/experiments/exp_abs_delete")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}
    resp = ab.get("/api/v1/ab/experiments/exp_abs_delete")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "experiment not found"

  TC-ABS-012: |
    client1, _, _ = build_isolated_client(tmp_path, experiments=[])
    payload = {"name": "exp_abs_persist", "strategies": [{"id": "s1", "hash_range": [0, 100], "params": {}}]}
    resp = client1.post("/api/v1/ab/experiments", json=payload)
    assert resp.status_code == 200
    client1.close()
    client2, _, _ = build_isolated_client(tmp_path)
    resp = client2.get("/api/v1/ab/experiments/exp_abs_persist")
    assert resp.status_code == 200
    assert resp.json()["name"] == "exp_abs_persist"
    client2.close()

  TC-ABS-013: |
    ab = setup_ab_service(case_id="TC-ABS-013")
    resp = ab.get("/api/v1/ab/whitelist")
    assert resp.status_code == 200
    assert "u_white" in resp.json()

  TC-ABS-014: |
    ab = setup_ab_service(case_id="TC-ABS-014")
    ab.snapshot_whitelist()
    resp = ab.put("/api/v1/ab/whitelist/u_abs_user", {"strategy_map": {"exp_ab_basic": "s_a"}})
    assert resp.status_code == 200
    resp = ab.get("/api/v1/ab/whitelist/u_abs_user")
    assert resp.status_code == 200
    assert resp.json() == {"exp_ab_basic": "s_a"}

  TC-ABS-015: |
    ab = setup_ab_service(case_id="TC-ABS-015")
    ab.snapshot_whitelist()
    resp = ab.put("/api/v1/ab/whitelist", {"u_abs_1": {"exp_ab_basic": "s_a"}, "u_abs_2": {"exp_ab_basic": "s_b"}})
    assert resp.status_code == 200
    resp = ab.get("/api/v1/ab/whitelist")
    assert resp.status_code == 200
    assert resp.json() == {"u_abs_1": {"exp_ab_basic": "s_a"}, "u_abs_2": {"exp_ab_basic": "s_b"}}

  TC-ABS-016: |
    ab = setup_ab_service(case_id="TC-ABS-016")
    resp = ab.delete("/api/v1/ab/whitelist/user_b")
    assert resp.status_code == 200
    assert resp.json() == {"cleared": True}
    resp = ab.get("/api/v1/ab/whitelist/user_b")
    assert resp.status_code == 404

  TC-ABS-017: |
    ab = setup_ab_service(case_id="TC-ABS-017")
    resp = ab.delete("/api/v1/ab/whitelist")
    assert resp.status_code == 200
    assert resp.json() == {"cleared": True}
    resp = ab.get("/api/v1/ab/whitelist")
    assert resp.status_code == 200
    assert resp.json() == {}

  TC-ABS-018: |
    client1, _, _ = build_isolated_client(tmp_path, experiments=[
        {"name": "exp_game", "strategies": [{"id": "game_on", "hash_range": [0, 100], "params": {}}]},
    ])
    resp = client1.put("/api/v1/ab/whitelist/u_abs_persist", json={"strategy_map": {"exp_game": "game_on"}})
    assert resp.status_code == 200
    client1.close()
    client2, _, _ = build_isolated_client(tmp_path)
    resp = client2.get("/api/v1/ab/whitelist/u_abs_persist")
    assert resp.status_code == 200
    assert resp.json() == {"exp_game": "game_on"}
    client2.close()

  TC-ABS-019: |
    ab = setup_ab_service(case_id="TC-ABS-019")
    payload = {"name": "exp_abs_dup", "strategies": [{"id": "s1", "hash_range": [0, 100], "params": {}}]}
    ab.snapshot_experiment("exp_abs_dup")
    first = ab.post("/api/v1/ab/experiments", payload)
    assert first.status_code == 200
    second = ab.post("/api/v1/ab/experiments", payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "experiment already exists: exp_abs_dup"

  TC-ABS-020: |
    ab = setup_ab_service(case_id="TC-ABS-020")
    resp = ab.put("/api/v1/ab/experiments/exp_abs_path", {"name": "exp_abs_body", "strategies": []})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "path name and payload name mismatch"

  TC-ABS-021: |
    ab = setup_ab_service(case_id="TC-ABS-021")
    resp = ab.get("/api/v1/ab/whitelist/u_abs_not_exists")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "user whitelist not found"

  TC-ABS-022: |
    ab = setup_ab_service(case_id="TC-ABS-022")
    resp = ab.delete("/api/v1/ab/whitelist/u_abs_not_exists")
    assert resp.status_code == 200
    assert resp.json() == {"cleared": True}

  TC-ABS-023: |
    ab = setup_ab_service(case_id="TC-ABS-023")
    resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_overlap_243", "request_id": "req_abs_023", "experiment_names": ["exp_abs_overlap"]})
    assert resp.status_code == 200
    assert resp.json()["assignments"]["exp_abs_overlap"]["strategy_id"] == "s_first"

  TC-ABS-024: |
    ab = setup_ab_service(case_id="TC-ABS-024")
    resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_024", "experiment_names": ["exp_abs_empty"]})
    assert resp.status_code == 200
    assert resp.json()["assignments"] == {}

  TC-ABS-025: |
    ab = setup_ab_service(case_id="TC-ABS-025")
    resp = ab.post("/api/v1/ab/evaluate", {"user_id": "u_abs_hash_0", "request_id": "req_abs_025", "experiment_names": ["not_exists_exp"]})
    assert resp.status_code == 200
    assert resp.json()["assignments"] == {}

  TC-ABS-026: |
    experiments_path = tmp_path / "new" / "experiments.json"
    client, _, _ = build_isolated_client(experiments_path.parent)
    resp = client.get("/api/v1/ab/experiments")
    assert resp.status_code == 200
    assert resp.json() == []
    assert experiments_path.exists()
    client.close()

  TC-ABS-027: |
    caplog.set_level(logging.WARNING, logger="ab_experiment_sdk.service")
    client, _, _ = build_isolated_client(tmp_path, whitelist_text="{bad json")
    resp = client.get("/api/v1/ab/whitelist")
    assert resp.status_code == 200
    assert resp.json() == {}
    assert "白名单文件读取失败" in caplog.text
    client.close()

  TC-ABS-028: |
    client, _, _ = build_isolated_client(tmp_path, experiments=[
        {"name": "exp_abs_bad_hash", "strategies": [{"id": "s_bad", "hash_range": ["bad"], "params": {}}]},
    ])
    resp = client.post("/api/v1/ab/evaluate", json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_hash"]})
    assert resp.status_code == 200
    assert resp.json()["assignments"]["exp_abs_bad_hash"]["strategy_id"] == "s_bad"
    client.close()

  TC-ABS-029: |
    client, _, _ = build_isolated_client(tmp_path, experiments=[
        {"name": "exp_abs_bad_params", "strategies": [{"id": "s_bad_params", "hash_range": [0, 100], "params": "bad"}]},
    ])
    resp = client.post("/api/v1/ab/evaluate", json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_params"]})
    assert resp.status_code == 200
    assert resp.json()["assignments"]["exp_abs_bad_params"]["params"] == {}
    client.close()

  TC-ABS-030: |
    ab = setup_ab_service(case_id="TC-ABS-030")
    resp = ab.post("/api/v1/ab/evaluate", {"request_id": "req_abs_030", "experiment_names": ["exp_ab_basic"]})
    assert resp.status_code == 422
    assert ["body", "user_id"] in [item["loc"] for item in resp.json()["detail"]]

  TC-ABS-031: |
    ab = setup_ab_service(case_id="TC-ABS-031")
    resp = ab.post("/api/v1/ab/experiments", {"name": "exp_abs_bad_schema", "strategies": "bad"})
    assert resp.status_code == 422

  TC-ABS-032: |
    ab = setup_ab_service(case_id="TC-ABS-032")
    resp = ab.put("/api/v1/ab/whitelist/u_abs_bad_schema", {"strategy_map": "bad"})
    assert resp.status_code == 422

  TC-ABS-033: |
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

  TC-ABS-034: |
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

  TC-ABS-035: |
    ab = setup_ab_service(case_id="TC-ABS-035")
    sdk, client = ab.remote_sdk(tmp_path)
    response = sdk.evaluate(ABExperimentRequest(user_id="u1", request_id="req_abs_035", experiment_names=["exp_game"]))
    assert response.request_id == "req_abs_035"
    assert response.assignments["exp_game"].strategy_id == "game_on"
    assert response.assignments["exp_game"].hit_reason == "whitelist"
    sdk.close()
    client.close()

  TC-ABS-036: |
    ab = setup_ab_service(case_id="TC-ABS-036")
    sdk, client = ab.remote_sdk(tmp_path)
    sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
    response = sdk.evaluate(ABExperimentRequest(user_id="u2", experiment_names=["exp_cal"]))
    assert response.assignments["exp_cal"].strategy_id == "cal_on"
    assert response.assignments["exp_cal"].hit_reason == "whitelist"
    sdk.close()
    client.close()

  TC-ABS-037: |
    ab = setup_ab_service(case_id="TC-ABS-037")
    sdk, client = ab.remote_sdk(tmp_path)
    sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
    sdk.clear_whitelist("u2")
    assert "u2" not in sdk.get_whitelist()
    sdk.close()
    client.close()

  TC-ABS-038: |
    ab = setup_ab_service(case_id="TC-ABS-038")
    sdk, client = ab.remote_sdk(tmp_path)
    sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
    assert sdk.get_whitelist() == {"u3": {"exp_game": "game_on"}}
    sdk.close()
    client.close()

  TC-ABS-039: |
    ab = setup_ab_service(case_id="TC-ABS-039")
    sdk, client = ab.remote_sdk(tmp_path)
    sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
    sdk.clear_whitelist()
    assert sdk.get_whitelist() == {}
    sdk.close()
    client.close()

  TC-ABS-040: |
    def handler(request):
        return httpx.Response(500, json={"detail": "internal error"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ab.test")
    sdk = RemoteABExperimentSDK(base_url="http://ab.test", client=mock_client)
    with pytest.raises(httpx.HTTPStatusError):
        sdk.evaluate(ABExperimentRequest(user_id="u_err"))
    sdk.close()
```
