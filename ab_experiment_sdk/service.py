"""AB 实验服务：评估 + 实验管理 + 白名单管理。"""
from __future__ import annotations

import json
import logging
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ab_experiment_sdk.client import (
    ABExperimentAssignment,
    ABExperimentRequest,
    ABExperimentResponse,
    ConfigBasedABExperimentSDK,
)
from ab_experiment_sdk.models import Experiment, ExperimentConfig, ExperimentStrategy


class EvaluateRequest(BaseModel):
    user_id: str
    request_id: str = ""
    context: dict = Field(default_factory=dict)
    experiment_names: Optional[list[str]] = None


class StrategyModel(BaseModel):
    id: str
    hash_range: list[int] = Field(default_factory=lambda: [0, 100])
    params: dict = Field(default_factory=dict)


class ExperimentModel(BaseModel):
    name: str
    strategies: list[StrategyModel] = Field(default_factory=list)


class AssignmentModel(BaseModel):
    experiment_name: str
    strategy_id: str
    params: dict = Field(default_factory=dict)
    hit_reason: str = "hash"


class EvaluateResponse(BaseModel):
    request_id: str
    user_id: str
    assignments: dict[str, AssignmentModel] = Field(default_factory=dict)
    trace_id: str = ""


class UserWhitelistBody(BaseModel):
    strategy_map: dict[str, str] = Field(default_factory=dict)


class _ABServiceState:
    def __init__(self, experiments_path: str, whitelist_path: Optional[str] = None, whitelist: Optional[dict] = None):
        self._lock = threading.RLock()
        self._experiments_path = Path(experiments_path)
        self._whitelist_path = Path(whitelist_path) if whitelist_path else self._experiments_path.parent / "whitelist.json"
        self._config = self._load_or_init_config(self._experiments_path)
        # 优先使用显式传入的白名单，否则从文件加载
        initial_whitelist = whitelist if whitelist is not None else self._load_whitelist_file()
        self._sdk = ConfigBasedABExperimentSDK(
            config=self._config,
            whitelist=initial_whitelist,
        )

    def evaluate(self, request: EvaluateRequest) -> ABExperimentResponse:
        with self._lock:
            return self._sdk.evaluate(ABExperimentRequest(
                user_id=request.user_id,
                request_id=request.request_id,
                context=dict(request.context),
                experiment_names=request.experiment_names,
            ))

    def list_experiments(self) -> list[ExperimentModel]:
        with self._lock:
            return [
                self._to_experiment_model(exp)
                for exp in self._config.experiments
            ]

    def get_experiment(self, name: str) -> ExperimentModel:
        with self._lock:
            exp = self._find_experiment(name)
            if exp is None:
                raise KeyError(name)
            return self._to_experiment_model(exp)

    def create_experiment(self, payload: ExperimentModel) -> ExperimentModel:
        with self._lock:
            if self._find_experiment(payload.name) is not None:
                raise ValueError(f"experiment already exists: {payload.name}")

            self._config.experiments.append(self._to_experiment(payload))
            self._reload_sdk_and_persist()
            return payload

    def update_experiment(self, name: str, payload: ExperimentModel) -> ExperimentModel:
        with self._lock:
            if payload.name != name:
                raise ValueError("path name and payload name mismatch")

            for idx, exp in enumerate(self._config.experiments):
                if exp.name != name:
                    continue
                self._config.experiments[idx] = self._to_experiment(payload)
                self._reload_sdk_and_persist()
                return payload

            raise KeyError(name)

    def delete_experiment(self, name: str) -> None:
        with self._lock:
            for idx, exp in enumerate(self._config.experiments):
                if exp.name != name:
                    continue
                del self._config.experiments[idx]
                self._reload_sdk_and_persist()
                return
            raise KeyError(name)

    def get_whitelist(self) -> dict:
        with self._lock:
            return deepcopy(self._sdk.get_whitelist())

    def replace_whitelist(self, whitelist: dict) -> dict:
        with self._lock:
            self._sdk.set_whitelist(whitelist)
            self._persist_whitelist()
            return deepcopy(self._sdk.get_whitelist())

    def get_user_whitelist(self, user_id: str) -> dict:
        with self._lock:
            whitelist = self._sdk.get_whitelist()
            if user_id not in whitelist:
                raise KeyError(user_id)
            return dict(whitelist[user_id])

    def set_user_whitelist(self, user_id: str, strategy_map: dict) -> dict:
        with self._lock:
            self._sdk.set_user_whitelist(user_id, strategy_map)
            self._persist_whitelist()
            whitelist = self._sdk.get_whitelist()
            if user_id not in whitelist:
                return {}
            return dict(whitelist[user_id])

    def clear_whitelist(self, user_id: Optional[str] = None) -> None:
        with self._lock:
            self._sdk.clear_whitelist(user_id)
            self._persist_whitelist()

    def _find_experiment(self, name: str) -> Optional[Experiment]:
        for exp in self._config.experiments:
            if exp.name == name:
                return exp
        return None

    def _reload_sdk_and_persist(self) -> None:
        whitelist = deepcopy(self._sdk.get_whitelist())
        self._sdk = ConfigBasedABExperimentSDK(self._config, whitelist=whitelist)
        self._persist_config()

    def _persist_config(self) -> None:
        self._experiments_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "experiments": [
                {
                    "name": exp.name,
                    "strategies": [
                        {
                            "id": strategy.id,
                            "hash_range": list(strategy.hash_range),
                            "params": dict(strategy.params),
                        }
                        for strategy in exp.strategies
                    ],
                }
                for exp in self._config.experiments
            ]
        }
        with open(self._experiments_path, "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _persist_whitelist(self) -> None:
        self._whitelist_path.parent.mkdir(parents=True, exist_ok=True)
        whitelist = self._sdk.get_whitelist()
        with open(self._whitelist_path, "w") as f:
            json.dump(whitelist, f, ensure_ascii=False, indent=2)

    def _load_whitelist_file(self) -> dict:
        if not self._whitelist_path.exists():
            return {}
        try:
            with open(self._whitelist_path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            logging.getLogger(__name__).warning("白名单文件读取失败，忽略: %s", self._whitelist_path)
            return {}
        return data if isinstance(data, dict) else {}

    def _load_or_init_config(self, path: Path) -> ExperimentConfig:
        if path.exists():
            return _load_experiment_config(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"experiments": []}, f, ensure_ascii=False, indent=2)
        return ExperimentConfig(experiments=[])

    def _to_experiment(self, payload: ExperimentModel) -> Experiment:
        strategies = [
            ExperimentStrategy(
                id=strategy.id,
                hash_range=list(strategy.hash_range),
                params=dict(strategy.params),
            )
            for strategy in payload.strategies
        ]
        return Experiment(name=payload.name, strategies=strategies)

    def _to_experiment_model(self, exp: Experiment) -> ExperimentModel:
        return ExperimentModel(
            name=exp.name,
            strategies=[
                StrategyModel(
                    id=s.id,
                    hash_range=list(s.hash_range),
                    params=dict(s.params),
                )
                for s in exp.strategies
            ],
        )



def _load_experiment_config(path: Path) -> ExperimentConfig:
    with open(path) as f:
        raw = json.load(f)

    experiments = []
    for exp_raw in raw.get("experiments", []):
        if not isinstance(exp_raw, dict):
            continue
        name = exp_raw.get("name")
        if not isinstance(name, str):
            continue
        strategies_raw = exp_raw.get("strategies", [])
        strategies = []
        if isinstance(strategies_raw, list):
            for s in strategies_raw:
                if not isinstance(s, dict):
                    continue
                strategy_id = s.get("id")
                if not isinstance(strategy_id, str):
                    continue
                hash_range = s.get("hash_range", [0, 100])
                if (
                    not isinstance(hash_range, list)
                    or len(hash_range) != 2
                    or not all(isinstance(x, int) for x in hash_range)
                ):
                    hash_range = [0, 100]
                params = s.get("params", {})
                if not isinstance(params, dict):
                    params = {}
                strategies.append(ExperimentStrategy(
                    id=strategy_id,
                    hash_range=list(hash_range),
                    params=dict(params),
                ))
        experiments.append(Experiment(name=name, strategies=strategies))

    return ExperimentConfig(experiments=experiments)


def _default_data_dir() -> Path:
    """AB 服务数据目录：ab_experiment_sdk/data/"""
    return Path(__file__).resolve().parent / "data"


def _default_experiments_path() -> Path:
    return _default_data_dir() / "experiments.json"


def _resolve_experiments_path(config_path: Optional[str]) -> str:
    source = config_path or os.environ.get("AB_SERVICE_EXPERIMENTS_PATH", "").strip()
    if source:
        return str(Path(source).expanduser().resolve())
    return str(_default_experiments_path().resolve())


def _to_evaluate_response(response: ABExperimentResponse) -> EvaluateResponse:
    assignments = {}
    for name, assignment in response.assignments.items():
        if not isinstance(assignment, ABExperimentAssignment):
            continue
        assignments[name] = AssignmentModel(
            experiment_name=assignment.experiment_name,
            strategy_id=assignment.strategy_id,
            params=dict(assignment.params),
            hit_reason=assignment.hit_reason,
        )
    return EvaluateResponse(
        request_id=response.request_id,
        user_id=response.user_id,
        assignments=assignments,
        trace_id=response.trace_id,
    )


def create_app(
    experiments_path: Optional[str] = None,
    whitelist_path: Optional[str] = None,
    initial_whitelist: Optional[dict] = None,
    initialize_state: bool = False,
) -> FastAPI:
    app = FastAPI(title="AB Experiment Service", version="1.0.0")
    app.state._ab_state_lock = threading.RLock()
    app.state._ab_state = None
    app.state._ab_state_args = {
        "experiments_path": _resolve_experiments_path(experiments_path),
        "whitelist_path": whitelist_path,
        "whitelist": initial_whitelist,
    }

    def _get_state() -> _ABServiceState:
        state = app.state._ab_state
        if state is not None:
            return state
        with app.state._ab_state_lock:
            state = app.state._ab_state
            if state is None:
                args = app.state._ab_state_args
                state = _ABServiceState(
                    experiments_path=args["experiments_path"],
                    whitelist_path=args["whitelist_path"],
                    whitelist=args["whitelist"],
                )
                app.state._ab_state = state
        return state

    if initialize_state:
        _get_state()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/v1/ab/evaluate", response_model=EvaluateResponse)
    def evaluate(request: EvaluateRequest):
        response = _get_state().evaluate(request)
        return _to_evaluate_response(response)

    @app.get("/api/v1/ab/experiments", response_model=list[ExperimentModel])
    def list_experiments():
        return _get_state().list_experiments()

    @app.get("/api/v1/ab/experiments/{name}", response_model=ExperimentModel)
    def get_experiment(name: str):
        try:
            return _get_state().get_experiment(name)
        except KeyError:
            raise HTTPException(status_code=404, detail="experiment not found")

    @app.post("/api/v1/ab/experiments", response_model=ExperimentModel)
    def create_experiment(payload: ExperimentModel):
        try:
            return _get_state().create_experiment(payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.put("/api/v1/ab/experiments/{name}", response_model=ExperimentModel)
    def update_experiment(name: str, payload: ExperimentModel):
        try:
            return _get_state().update_experiment(name, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="experiment not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/v1/ab/experiments/{name}")
    def delete_experiment(name: str):
        try:
            _get_state().delete_experiment(name)
        except KeyError:
            raise HTTPException(status_code=404, detail="experiment not found")
        return {"deleted": True}

    @app.get("/api/v1/ab/whitelist")
    def get_whitelist():
        return _get_state().get_whitelist()

    @app.put("/api/v1/ab/whitelist")
    def put_whitelist(whitelist: dict):
        return _get_state().replace_whitelist(whitelist)

    @app.delete("/api/v1/ab/whitelist")
    def clear_whitelist():
        _get_state().clear_whitelist()
        return {"cleared": True}

    @app.get("/api/v1/ab/whitelist/{user_id}")
    def get_user_whitelist(user_id: str):
        try:
            return _get_state().get_user_whitelist(user_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="user whitelist not found")

    @app.put("/api/v1/ab/whitelist/{user_id}")
    def put_user_whitelist(user_id: str, payload: UserWhitelistBody):
        return _get_state().set_user_whitelist(user_id, payload.strategy_map)

    @app.delete("/api/v1/ab/whitelist/{user_id}")
    def delete_user_whitelist(user_id: str):
        _get_state().clear_whitelist(user_id)
        return {"cleared": True}

    return app


app = create_app(initialize_state=False)


def main():
    host = os.environ.get("AB_SERVICE_HOST", "0.0.0.0")
    port = int(os.environ.get("AB_SERVICE_PORT", "8100"))
    uvicorn.run("ab_experiment_sdk.service:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
