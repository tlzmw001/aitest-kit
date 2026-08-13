"""Public module Harness for AB service tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from test_workspace.targets.coupon_system.modules.ab_service.api import ABApiClient
from test_workspace.targets.coupon_system.modules.ab_service.isolated_checks import ABIsolatedChecks
from test_workspace.targets.coupon_system.modules.ab_service.resources import standard_experiments


class AbServiceHarness:
    """Expose explicit AB state preparation, public API calls, and isolated checks."""

    def __init__(self, *, api: ABApiClient, workspace: Path) -> None:
        self.api = api
        self.isolated = ABIsolatedChecks(workspace)

    def get(self, path: str) -> httpx.Response:
        return self.api.get(path)

    def post(self, path: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
        return self.api.post(path, json_body)

    def put(self, path: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
        return self.api.put(path, json_body)

    def delete(self, path: str) -> httpx.Response:
        return self.api.delete(path)

    def snapshot_whitelist(self) -> None:
        self.api.snapshot_whitelist()

    def snapshot_experiment(self, name: str) -> None:
        self.api.snapshot_experiment(name)

    def upsert_experiment(self, payload: dict[str, Any]) -> None:
        self.api.upsert_experiment(payload)

    def prepare_standard_experiments(self, names: list[str]) -> None:
        experiments = standard_experiments()
        unknown = sorted(set(names) - experiments.keys())
        if unknown:
            raise ValueError(f"unknown standard AB experiments: {', '.join(unknown)}")
        for name in names:
            self.api.upsert_experiment(experiments[name])

    def prepare_user_whitelist(self, user_id: str, strategy_map: dict[str, str]) -> None:
        self.api.set_user_whitelist(user_id, strategy_map)

    def prepare_whitelist(self, whitelist: dict[str, dict[str, str]]) -> None:
        self.api.replace_whitelist(whitelist)

    def isolated_experiment_persists(self) -> dict[str, Any]:
        return self.isolated.isolated_experiment_persists()

    def isolated_whitelist_persists(self) -> dict[str, Any]:
        return self.isolated.isolated_whitelist_persists()

    def missing_experiments_file_is_created(self) -> dict[str, Any]:
        return self.isolated.missing_experiments_file_is_created()

    def malformed_whitelist_falls_back_empty(self) -> dict[str, Any]:
        return self.isolated.malformed_whitelist_falls_back_empty()

    def bad_hash_range_still_evaluates(self) -> dict[str, Any]:
        return self.isolated.bad_hash_range_still_evaluates()

    def bad_params_fall_back_empty(self) -> dict[str, Any]:
        return self.isolated.bad_params_fall_back_empty()

    def import_works_from_other_cwd(self) -> dict[str, Any]:
        return self.isolated.import_works_from_other_cwd()

    def import_has_no_default_file_side_effect(self) -> dict[str, Any]:
        return self.isolated.import_has_no_default_file_side_effect()

    def remote_sdk_evaluate_whitelist(self) -> dict[str, Any]:
        return self.isolated.remote_sdk_evaluate_whitelist()

    def remote_sdk_set_user_whitelist(self) -> dict[str, Any]:
        return self.isolated.remote_sdk_set_user_whitelist()

    def remote_sdk_clear_user_whitelist(self) -> dict[str, Any]:
        return self.isolated.remote_sdk_clear_user_whitelist()

    def remote_sdk_replace_whitelist(self) -> dict[str, Any]:
        return self.isolated.remote_sdk_replace_whitelist()

    def remote_sdk_clear_all_whitelist(self) -> dict[str, Any]:
        return self.isolated.remote_sdk_clear_all_whitelist()

    def remote_sdk_raises_on_http_error(self) -> dict[str, Any]:
        return self.isolated.remote_sdk_raises_on_http_error()

    def close(self) -> None:
        self.api.close()
