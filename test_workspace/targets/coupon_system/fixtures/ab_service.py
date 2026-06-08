"""AB service module fixtures."""
from __future__ import annotations

import json
import logging
import io
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import httpx
import pytest
from fastapi.testclient import TestClient

from ab_experiment_sdk import ABExperimentRequest
from ab_experiment_sdk.remote_client import RemoteABExperimentSDK
from ab_experiment_sdk.service import create_app
from aitest_kit.runtime_variables import require_env

logger = logging.getLogger(__name__)

_client = httpx.Client(transport=httpx.HTTPTransport())


def _experiment_payload(
    name: str,
    strategies: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    if strategies is None:
        strategies = [
            {"id": "s_a", "hash_range": [0, 50], "params": {"bucket": "a"}},
            {"id": "s_b", "hash_range": [50, 100], "params": {"bucket": "b"}},
        ]
    return {
        "name": name,
        "strategies": strategies,
    }


def _standard_experiments() -> dict[str, dict[str, Any]]:
    return {
        "exp_ab_basic": _experiment_payload("exp_ab_basic"),
        "exp_ab_extra": _experiment_payload(
            "exp_ab_extra",
            [{"id": "extra_on", "hash_range": [0, 100], "params": {"extra": True}}],
        ),
        "exp_game": _experiment_payload(
            "exp_game",
            [{"id": "game_on", "hash_range": [0, 100], "params": {"k": 1}}],
        ),
        "exp_cal": _experiment_payload(
            "exp_cal",
            [{"id": "cal_on", "hash_range": [0, 100], "params": {"b": 2}}],
        ),
    }


def write_experiments_file(path: Path, experiments: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"experiments": experiments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_isolated_client(
    tmp_path: Path,
    experiments: Optional[list[dict[str, Any]]] = None,
    whitelist: Optional[dict[str, dict[str, str]]] = None,
    whitelist_text: Optional[str] = None,
) -> tuple:
    experiments_path = tmp_path / "experiments.json"
    whitelist_path = tmp_path / "whitelist.json"
    if experiments is not None:
        write_experiments_file(experiments_path, experiments)
    if whitelist_text is not None:
        whitelist_path.write_text(whitelist_text, encoding="utf-8")
    app = create_app(
        experiments_path=str(experiments_path),
        whitelist_path=str(whitelist_path),
        initial_whitelist=whitelist,
    )
    return TestClient(app), experiments_path, whitelist_path


class ABServiceCase:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._experiment_snapshots: dict[str, Optional[dict[str, Any]]] = {}
        self._whitelist_snapshot: Optional[dict[str, Any]] = None

    def request(self, method: str, path: str, json_body: Optional[dict] = None) -> httpx.Response:
        return _client.request(method, f"{self.base_url}{path}", json=json_body, timeout=10.0)

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path)

    def post(self, path: str, json_body: Optional[dict] = None) -> httpx.Response:
        return self.request("POST", path, json_body)

    def put(self, path: str, json_body: Optional[dict] = None) -> httpx.Response:
        return self.request("PUT", path, json_body)

    def delete(self, path: str) -> httpx.Response:
        return self.request("DELETE", path)

    def snapshot_whitelist(self) -> None:
        if self._whitelist_snapshot is not None:
            return
        response = self.get("/api/v1/ab/whitelist")
        response.raise_for_status()
        body = response.json()
        self._whitelist_snapshot = body if isinstance(body, dict) else {}

    def snapshot_experiment(self, name: str) -> None:
        if name in self._experiment_snapshots:
            return
        response = self.get(f"/api/v1/ab/experiments/{name}")
        if response.status_code == 200:
            self._experiment_snapshots[name] = response.json()
            return
        if response.status_code == 404:
            self._experiment_snapshots[name] = None
            return
        response.raise_for_status()

    def upsert_experiment(self, payload: dict[str, Any]) -> None:
        name = payload["name"]
        self.snapshot_experiment(name)
        response = self.post("/api/v1/ab/experiments", payload)
        if response.status_code == 409:
            response = self.put(f"/api/v1/ab/experiments/{name}", payload)
        response.raise_for_status()

    def set_user_whitelist(self, user_id: str, strategy_map: dict[str, str]) -> None:
        self.snapshot_whitelist()
        response = self.put(
            f"/api/v1/ab/whitelist/{user_id}",
            {"strategy_map": strategy_map},
        )
        response.raise_for_status()

    def replace_whitelist(self, whitelist: dict[str, dict[str, str]]) -> None:
        self.snapshot_whitelist()
        response = self.put("/api/v1/ab/whitelist", whitelist)
        response.raise_for_status()

    def restore(self) -> None:
        if self._whitelist_snapshot is not None:
            response = self.put("/api/v1/ab/whitelist", self._whitelist_snapshot)
            if response.status_code >= 400:
                logger.warning("restore AB whitelist failed: %s %s", response.status_code, response.text)

        for name, payload in reversed(list(self._experiment_snapshots.items())):
            if payload is None:
                response = self.delete(f"/api/v1/ab/experiments/{name}")
                if response.status_code not in {200, 404}:
                    logger.warning("delete AB experiment failed: %s %s", name, response.text)
                continue
            response = self.put(f"/api/v1/ab/experiments/{name}", payload)
            if response.status_code == 404:
                response = self.post("/api/v1/ab/experiments", payload)
            if response.status_code >= 400:
                logger.warning("restore AB experiment failed: %s %s", name, response.text)

    def remote_sdk(self, tmp_path: Path) -> tuple:
        client, _, _ = build_isolated_client(
            tmp_path,
            experiments=list(_standard_experiments().values()),
            whitelist={"u1": {"exp_game": "game_on"}},
        )
        return RemoteABExperimentSDK(base_url="http://testserver", client=client), client

    def isolated_experiment_persists(self, tmp_path: Path) -> dict[str, Any]:
        payload = {
            "name": "exp_abs_persist",
            "strategies": [{"id": "s1", "hash_range": [0, 100], "params": {}}],
        }
        client1, _, _ = build_isolated_client(tmp_path, experiments=[])
        try:
            create_resp = client1.post("/api/v1/ab/experiments", json=payload)
        finally:
            client1.close()

        client2, _, _ = build_isolated_client(tmp_path)
        try:
            read_resp = client2.get("/api/v1/ab/experiments/exp_abs_persist")
            body = read_resp.json() if read_resp.status_code == 200 else {}
            return {
                "create_status": create_resp.status_code,
                "read_status": read_resp.status_code,
                "name": body.get("name"),
            }
        finally:
            client2.close()

    def isolated_whitelist_persists(self, tmp_path: Path) -> dict[str, Any]:
        client1, _, _ = build_isolated_client(
            tmp_path,
            experiments=[
                {"name": "exp_game", "strategies": [{"id": "game_on", "hash_range": [0, 100], "params": {}}]},
            ],
        )
        try:
            write_resp = client1.put(
                "/api/v1/ab/whitelist/u_abs_persist",
                json={"strategy_map": {"exp_game": "game_on"}},
            )
        finally:
            client1.close()

        client2, _, _ = build_isolated_client(tmp_path)
        try:
            read_resp = client2.get("/api/v1/ab/whitelist/u_abs_persist")
            body = read_resp.json() if read_resp.status_code == 200 else {}
            return {
                "write_status": write_resp.status_code,
                "read_status": read_resp.status_code,
                "body": body,
            }
        finally:
            client2.close()

    def missing_experiments_file_is_created(self, tmp_path: Path) -> dict[str, Any]:
        experiments_path = tmp_path / "new" / "experiments.json"
        client, _, _ = build_isolated_client(experiments_path.parent)
        try:
            resp = client.get("/api/v1/ab/experiments")
            return {
                "status": resp.status_code,
                "body": resp.json(),
                "exists": experiments_path.exists(),
            }
        finally:
            client.close()

    def malformed_whitelist_falls_back_empty(self, tmp_path: Path, caplog: Any) -> dict[str, Any]:
        caplog.set_level(logging.WARNING, logger="ab_experiment_sdk.service")
        client, _, _ = build_isolated_client(tmp_path, whitelist_text="{bad json")
        try:
            resp = client.get("/api/v1/ab/whitelist")
            return {
                "status": resp.status_code,
                "body": resp.json(),
                "logs": caplog.text,
            }
        finally:
            client.close()

    def bad_hash_range_still_evaluates(self, tmp_path: Path) -> dict[str, Any]:
        client, _, _ = build_isolated_client(
            tmp_path,
            experiments=[
                {"name": "exp_abs_bad_hash", "strategies": [{"id": "s_bad", "hash_range": ["bad"], "params": {}}]},
            ],
        )
        try:
            resp = client.post(
                "/api/v1/ab/evaluate",
                json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_hash"]},
            )
            body = resp.json()
            return {
                "status": resp.status_code,
                "strategy_id": body["assignments"]["exp_abs_bad_hash"]["strategy_id"],
            }
        finally:
            client.close()

    def bad_params_fall_back_empty(self, tmp_path: Path) -> dict[str, Any]:
        client, _, _ = build_isolated_client(
            tmp_path,
            experiments=[
                {"name": "exp_abs_bad_params", "strategies": [{"id": "s_bad_params", "hash_range": [0, 100], "params": "bad"}]},
            ],
        )
        try:
            resp = client.post(
                "/api/v1/ab/evaluate",
                json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_params"]},
            )
            body = resp.json()
            return {
                "status": resp.status_code,
                "params": body["assignments"]["exp_abs_bad_params"]["params"],
            }
        finally:
            client.close()

    def import_works_from_other_cwd(self, tmp_path: Path) -> dict[str, Any]:
        repo_root = _repo_root()
        src_pkg = repo_root / "ab_experiment_sdk"
        isolated_root = tmp_path / "isolated_pkg"
        isolated_pkg = isolated_root / "ab_experiment_sdk"
        isolated_pkg.mkdir(parents=True, exist_ok=True)
        for file in src_pkg.glob("*.py"):
            (isolated_pkg / file.name).write_text(file.read_text(encoding="utf-8"), encoding="utf-8")
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
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def import_has_no_default_file_side_effect(self, tmp_path: Path) -> dict[str, Any]:
        repo_root = _repo_root()
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
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def remote_sdk_evaluate_whitelist(self, tmp_path: Path) -> dict[str, Any]:
        sdk, client = self.remote_sdk(tmp_path)
        try:
            response = sdk.evaluate(
                ABExperimentRequest(user_id="u1", request_id="req_abs_035", experiment_names=["exp_game"])
            )
            assignment = response.assignments["exp_game"]
            return {
                "request_id": response.request_id,
                "strategy_id": assignment.strategy_id,
                "hit_reason": assignment.hit_reason,
            }
        finally:
            sdk.close()
            client.close()

    def remote_sdk_set_user_whitelist(self, tmp_path: Path) -> dict[str, Any]:
        sdk, client = self.remote_sdk(tmp_path)
        try:
            sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
            response = sdk.evaluate(ABExperimentRequest(user_id="u2", experiment_names=["exp_cal"]))
            assignment = response.assignments["exp_cal"]
            return {"strategy_id": assignment.strategy_id, "hit_reason": assignment.hit_reason}
        finally:
            sdk.close()
            client.close()

    def remote_sdk_clear_user_whitelist(self, tmp_path: Path) -> dict[str, Any]:
        sdk, client = self.remote_sdk(tmp_path)
        try:
            sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
            sdk.clear_whitelist("u2")
            return {"whitelist": sdk.get_whitelist()}
        finally:
            sdk.close()
            client.close()

    def remote_sdk_replace_whitelist(self, tmp_path: Path) -> dict[str, Any]:
        sdk, client = self.remote_sdk(tmp_path)
        try:
            sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
            return {"whitelist": sdk.get_whitelist()}
        finally:
            sdk.close()
            client.close()

    def remote_sdk_clear_all_whitelist(self, tmp_path: Path) -> dict[str, Any]:
        sdk, client = self.remote_sdk(tmp_path)
        try:
            sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
            sdk.clear_whitelist()
            return {"whitelist": sdk.get_whitelist()}
        finally:
            sdk.close()
            client.close()

    def remote_sdk_raises_on_http_error(self) -> dict[str, Any]:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "internal error"})

        mock_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ab.test")
        sdk = RemoteABExperimentSDK(base_url="http://ab.test", client=mock_client)
        try:
            try:
                sdk.evaluate(ABExperimentRequest(user_id="u_err"))
            except httpx.HTTPStatusError as exc:
                return {"raised": True, "status_code": exc.response.status_code}
            return {"raised": False, "status_code": None}
        finally:
            sdk.close()

    def isolated_experiment_persists_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.isolated_experiment_persists(Path(root))

    def isolated_whitelist_persists_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.isolated_whitelist_persists(Path(root))

    def missing_experiments_file_is_created_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.missing_experiments_file_is_created(Path(root))

    def malformed_whitelist_falls_back_empty_auto(self) -> dict[str, Any]:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger_obj = logging.getLogger("ab_experiment_sdk.service")
        old_level = logger_obj.level
        logger_obj.setLevel(logging.WARNING)
        logger_obj.addHandler(handler)
        try:
            with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
                client, _, _ = build_isolated_client(Path(root), whitelist_text="{bad json")
                try:
                    resp = client.get("/api/v1/ab/whitelist")
                    return {
                        "status": resp.status_code,
                        "body": resp.json(),
                        "logs": stream.getvalue(),
                    }
                finally:
                    client.close()
        finally:
            logger_obj.removeHandler(handler)
            logger_obj.setLevel(old_level)

    def bad_hash_range_still_evaluates_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.bad_hash_range_still_evaluates(Path(root))

    def bad_params_fall_back_empty_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.bad_params_fall_back_empty(Path(root))

    def import_works_from_other_cwd_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.import_works_from_other_cwd(Path(root))

    def import_has_no_default_file_side_effect_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.import_has_no_default_file_side_effect(Path(root))

    def remote_sdk_evaluate_whitelist_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.remote_sdk_evaluate_whitelist(Path(root))

    def remote_sdk_set_user_whitelist_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.remote_sdk_set_user_whitelist(Path(root))

    def remote_sdk_clear_user_whitelist_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.remote_sdk_clear_user_whitelist(Path(root))

    def remote_sdk_replace_whitelist_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.remote_sdk_replace_whitelist(Path(root))

    def remote_sdk_clear_all_whitelist_auto(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="aitest_abs_") as root:
            return self.remote_sdk_clear_all_whitelist(Path(root))


@pytest.fixture
def setup_ab_service():
    """Prepare AB service state through its public API and restore it after each case."""
    ab_base_url = require_env("COUPON_AB_BASE_URL")
    case = ABServiceCase(ab_base_url)

    def _setup(case_id: str) -> ABServiceCase:
        standard = _standard_experiments()
        for name in _experiments_for_case(case_id):
            case.upsert_experiment(standard[name])

        if case_id == "TC-ABS-003":
            case.set_user_whitelist("u_abs_white", {"exp_ab_basic": "s_b"})
        elif case_id == "TC-ABS-013":
            case.set_user_whitelist("u_white", {"exp_game": "game_on"})
        elif case_id == "TC-ABS-016":
            case.set_user_whitelist("user_b", {"exp_game": "game_on"})
        elif case_id == "TC-ABS-017":
            case.replace_whitelist({"user_b": {"exp_game": "game_on"}})
        elif case_id == "TC-ABS-023":
            case.upsert_experiment(_experiment_payload(
                "exp_abs_overlap",
                [
                    {"id": "s_first", "hash_range": [0, 80], "params": {}},
                    {"id": "s_second", "hash_range": [50, 100], "params": {}},
                ],
            ))
        elif case_id == "TC-ABS-024":
            case.upsert_experiment(_experiment_payload("exp_abs_empty", []))
        return case

    yield _setup
    case.restore()


def _experiments_for_case(case_id: str) -> set[str]:
    mapping = {
        "TC-ABS-002": {"exp_ab_basic"},
        "TC-ABS-003": {"exp_ab_basic"},
        "TC-ABS-004": {"exp_ab_basic", "exp_ab_extra"},
        "TC-ABS-006": {"exp_ab_basic"},
        "TC-ABS-007": {"exp_game", "exp_cal"},
        "TC-ABS-008": {"exp_game"},
        "TC-ABS-013": {"exp_game"},
        "TC-ABS-035": {"exp_game", "exp_cal"},
        "TC-ABS-036": {"exp_game", "exp_cal"},
        "TC-ABS-037": {"exp_game", "exp_cal"},
        "TC-ABS-038": {"exp_game", "exp_cal"},
        "TC-ABS-039": {"exp_game", "exp_cal"},
    }
    return set(mapping.get(case_id, set()))


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("cannot locate repository root")
