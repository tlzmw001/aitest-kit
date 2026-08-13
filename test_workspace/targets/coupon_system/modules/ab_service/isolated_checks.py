"""Isolated file, import, and Remote SDK checks for the AB service Harness."""
from __future__ import annotations

import io
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from ab_experiment_sdk import ABExperimentRequest
from ab_experiment_sdk.remote_client import RemoteABExperimentSDK
from test_workspace.targets.coupon_system.modules.ab_service.resources import (
    build_isolated_client,
    repository_root,
    standard_experiments,
)


class ABIsolatedChecks:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def isolated_experiment_persists(self) -> dict[str, Any]:
        root = self._root("experiment_persists")
        payload = {
            "name": "exp_abs_persist",
            "strategies": [{"id": "s1", "hash_range": [0, 100], "params": {}}],
        }
        first, _, _ = build_isolated_client(root, experiments=[])
        try:
            create_response = first.post("/api/v1/ab/experiments", json=payload)
        finally:
            first.close()
        second, _, _ = build_isolated_client(root)
        try:
            read_response = second.get("/api/v1/ab/experiments/exp_abs_persist")
            body = read_response.json() if read_response.status_code == 200 else {}
            return {
                "create_status": create_response.status_code,
                "read_status": read_response.status_code,
                "name": body.get("name"),
            }
        finally:
            second.close()

    def isolated_whitelist_persists(self) -> dict[str, Any]:
        root = self._root("whitelist_persists")
        first, _, _ = build_isolated_client(
            root,
            experiments=[{
                "name": "exp_game",
                "strategies": [{"id": "game_on", "hash_range": [0, 100], "params": {}}],
            }],
        )
        try:
            write_response = first.put(
                "/api/v1/ab/whitelist/u_abs_persist",
                json={"strategy_map": {"exp_game": "game_on"}},
            )
        finally:
            first.close()
        second, _, _ = build_isolated_client(root)
        try:
            read_response = second.get("/api/v1/ab/whitelist/u_abs_persist")
            return {
                "write_status": write_response.status_code,
                "read_status": read_response.status_code,
                "body": read_response.json() if read_response.status_code == 200 else {},
            }
        finally:
            second.close()

    def missing_experiments_file_is_created(self) -> dict[str, Any]:
        client, experiments_path, _ = build_isolated_client(
            self._root("missing_experiments") / "new"
        )
        try:
            response = client.get("/api/v1/ab/experiments")
            return {
                "status": response.status_code,
                "body": response.json(),
                "exists": experiments_path.exists(),
            }
        finally:
            client.close()

    def malformed_whitelist_falls_back_empty(self) -> dict[str, Any]:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        target_logger = logging.getLogger("ab_experiment_sdk.service")
        old_level = target_logger.level
        target_logger.setLevel(logging.WARNING)
        target_logger.addHandler(handler)
        try:
            client, _, _ = build_isolated_client(
                self._root("malformed_whitelist"),
                whitelist_text="{bad json",
            )
            try:
                response = client.get("/api/v1/ab/whitelist")
                return {
                    "status": response.status_code,
                    "body": response.json(),
                    "logs": stream.getvalue(),
                }
            finally:
                client.close()
        finally:
            target_logger.removeHandler(handler)
            target_logger.setLevel(old_level)

    def bad_hash_range_still_evaluates(self) -> dict[str, Any]:
        client, _, _ = build_isolated_client(
            self._root("bad_hash_range"),
            experiments=[{
                "name": "exp_abs_bad_hash",
                "strategies": [{"id": "s_bad", "hash_range": ["bad"], "params": {}}],
            }],
        )
        try:
            response = client.post(
                "/api/v1/ab/evaluate",
                json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_hash"]},
            )
            return {
                "status": response.status_code,
                "strategy_id": response.json()["assignments"]["exp_abs_bad_hash"]["strategy_id"],
            }
        finally:
            client.close()

    def bad_params_fall_back_empty(self) -> dict[str, Any]:
        client, _, _ = build_isolated_client(
            self._root("bad_params"),
            experiments=[{
                "name": "exp_abs_bad_params",
                "strategies": [{"id": "s_bad_params", "hash_range": [0, 100], "params": "bad"}],
            }],
        )
        try:
            response = client.post(
                "/api/v1/ab/evaluate",
                json={"user_id": "u_abs_any_0", "experiment_names": ["exp_abs_bad_params"]},
            )
            return {
                "status": response.status_code,
                "params": response.json()["assignments"]["exp_abs_bad_params"]["params"],
            }
        finally:
            client.close()

    def import_works_from_other_cwd(self) -> dict[str, Any]:
        repo_root = repository_root()
        source_package = repo_root / "ab_experiment_sdk"
        isolated_root = self._root("import_other_cwd") / "isolated_pkg"
        isolated_package = isolated_root / "ab_experiment_sdk"
        isolated_package.mkdir(parents=True, exist_ok=True)
        for source in source_package.glob("*.py"):
            (isolated_package / source.name).write_text(
                source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        run_dir = self._root("import_other_cwd") / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        script = (
            "import os,sys;"
            f"os.chdir({str(run_dir)!r});"
            f"sys.path.insert(0,{str(isolated_root)!r});"
            "import ab_experiment_sdk.service as s;"
            "print('ok', s.__name__)"
        )
        return _completed_process_result(subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        ))

    def import_has_no_default_file_side_effect(self) -> dict[str, Any]:
        repo_root = repository_root()
        run_dir = self._root("import_side_effect")
        script = (
            "import os,sys,pathlib;"
            f"os.chdir({str(run_dir)!r});"
            f"sys.path.insert(0,{str(repo_root)!r});"
            "import ab_experiment_sdk.service;"
            "p=pathlib.Path('coupon_system/config/experiments.json');"
            "print('exists', p.exists())"
        )
        return _completed_process_result(subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        ))

    def remote_sdk_evaluate_whitelist(self) -> dict[str, Any]:
        sdk, client = self._remote_sdk("sdk_evaluate")
        try:
            response = sdk.evaluate(ABExperimentRequest(
                user_id="u1", request_id="req_abs_035", experiment_names=["exp_game"]
            ))
            assignment = response.assignments["exp_game"]
            return {
                "request_id": response.request_id,
                "strategy_id": assignment.strategy_id,
                "hit_reason": assignment.hit_reason,
            }
        finally:
            sdk.close()
            client.close()

    def remote_sdk_set_user_whitelist(self) -> dict[str, Any]:
        sdk, client = self._remote_sdk("sdk_set_whitelist")
        try:
            sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
            response = sdk.evaluate(ABExperimentRequest(user_id="u2", experiment_names=["exp_cal"]))
            assignment = response.assignments["exp_cal"]
            return {"strategy_id": assignment.strategy_id, "hit_reason": assignment.hit_reason}
        finally:
            sdk.close()
            client.close()

    def remote_sdk_clear_user_whitelist(self) -> dict[str, Any]:
        sdk, client = self._remote_sdk("sdk_clear_user")
        try:
            sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
            sdk.clear_whitelist("u2")
            return {"whitelist": sdk.get_whitelist()}
        finally:
            sdk.close()
            client.close()

    def remote_sdk_replace_whitelist(self) -> dict[str, Any]:
        sdk, client = self._remote_sdk("sdk_replace_whitelist")
        try:
            sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
            return {"whitelist": sdk.get_whitelist()}
        finally:
            sdk.close()
            client.close()

    def remote_sdk_clear_all_whitelist(self) -> dict[str, Any]:
        sdk, client = self._remote_sdk("sdk_clear_all")
        try:
            sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
            sdk.clear_whitelist()
            return {"whitelist": sdk.get_whitelist()}
        finally:
            sdk.close()
            client.close()

    @staticmethod
    def remote_sdk_raises_on_http_error() -> dict[str, Any]:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "internal error"})

        mock_client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="http://ab.test",
        )
        sdk = RemoteABExperimentSDK(base_url="http://ab.test", client=mock_client)
        try:
            try:
                sdk.evaluate(ABExperimentRequest(user_id="u_err"))
            except httpx.HTTPStatusError as exc:
                return {"raised": True, "status_code": exc.response.status_code}
            return {"raised": False, "status_code": None}
        finally:
            sdk.close()

    def _remote_sdk(self, name: str) -> tuple[RemoteABExperimentSDK, Any]:
        client, _, _ = build_isolated_client(
            self._root(name),
            experiments=list(standard_experiments().values()),
            whitelist={"u1": {"exp_game": "game_on"}},
        )
        return RemoteABExperimentSDK(base_url="http://testserver", client=client), client

    def _root(self, name: str) -> Path:
        root = self.workspace / name
        root.mkdir(parents=True, exist_ok=True)
        return root


def _completed_process_result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
