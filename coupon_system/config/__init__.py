"""配置加载模块 — YAML 主配置 + JSON 场景/实验/校准配置"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from ab_experiment_sdk import Experiment, ExperimentConfig, ExperimentStrategy


# ========== 主配置 dataclass ==========

@dataclass
class RateLimitConfig:
    enabled: bool = True
    max_qps: int = 1000
    per_user_qps: int = 10
    window_seconds: int = 1


@dataclass
class FallbackAction:
    action: str = "allow"
    default_score: float = 0.5


@dataclass
class FallbackConfig:
    enabled: bool = True
    on_scoring_timeout: FallbackAction = field(default_factory=FallbackAction)
    on_scoring_unavailable: FallbackAction = field(default_factory=FallbackAction)


@dataclass
class ScoringServiceConfig:
    host: str = "localhost"
    port: int = 50052
    timeout: float = 2.0
    enabled: bool = True


@dataclass
class ExternalScoringServiceConfig:
    host: str = "localhost"
    port: int = 50053
    timeout: float = 2.0
    enabled: bool = True
    path: str = "/score"
    user_id_salt: str = "coupon_external_uid_salt"


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/0"
    key_prefix: str = "coupon:"
    stock_ttl: int = 86400
    user_claim_ttl: int = 604800


@dataclass
class AppConfig:
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    scoring_service: ScoringServiceConfig = field(default_factory=ScoringServiceConfig)
    external_scoring_service: ExternalScoringServiceConfig = field(default_factory=ExternalScoringServiceConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    user_feature_keys: list = field(default_factory=list)
    item_feature_file: str = "data/item_features.tsv"


# ========== 场景路由配置 ==========

@dataclass
class SceneRoute:
    scene_name: str
    device: str
    scene_id: int
    description: str = ""


@dataclass
class SceneRoutingConfig:
    routes: list = field(default_factory=list)
    fallback_policy_ids: list = field(default_factory=list)
    fallback_scene_id: int = 3001
    fallback_score: float = 0.5


@dataclass
class SceneExperimentMappingConfig:
    scene_experiments: dict = field(default_factory=dict)
    default_experiments: list = field(default_factory=list)


# ========== 校准配置 ==========

@dataclass
class CalibrationCoefficients:
    k: float = 1.0
    b: float = 0.0


# ========== 加载函数 ==========

def _resolve_config_dir() -> Path:
    return Path(__file__).parent


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """加载主配置文件（YAML）"""
    if config_path is None:
        config_path = os.environ.get(
            "COUPON_CONFIG_PATH",
            str(_resolve_config_dir() / "settings.yaml"),
        )

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    rl_raw = raw.get("rate_limit", {})
    rate_limit = RateLimitConfig(**rl_raw)

    fb_raw = raw.get("fallback", {})
    fallback = FallbackConfig(
        enabled=fb_raw.get("enabled", True),
        on_scoring_timeout=FallbackAction(**fb_raw.get("on_scoring_timeout", {})),
        on_scoring_unavailable=FallbackAction(**fb_raw.get("on_scoring_unavailable", {})),
    )

    scoring_raw = raw.get("scoring_service", {})
    scoring_service = ScoringServiceConfig(**scoring_raw)

    external_scoring_raw = raw.get("external_scoring_service", {})
    external_scoring_service = ExternalScoringServiceConfig(**external_scoring_raw)

    redis_raw = raw.get("redis", {})
    redis_config = RedisConfig(**redis_raw)

    user_feature_keys = raw.get("user_feature_keys", [])
    item_feature_file = raw.get("item_feature_file", "data/item_features.tsv")

    return AppConfig(
        rate_limit=rate_limit,
        fallback=fallback,
        scoring_service=scoring_service,
        external_scoring_service=external_scoring_service,
        redis=redis_config,
        user_feature_keys=user_feature_keys,
        item_feature_file=item_feature_file,
    )


def load_scene_routing_config(config_path: Optional[str] = None) -> SceneRoutingConfig:
    """加载场景路由配置（JSON）"""
    if config_path is None:
        config_path = str(_resolve_config_dir() / "scenes.json")

    with open(config_path) as f:
        raw = json.load(f)

    routes = [SceneRoute(**r) for r in raw.get("routes", [])]
    return SceneRoutingConfig(
        routes=routes,
        fallback_policy_ids=raw.get("fallback_policy_ids", []),
        fallback_scene_id=raw.get("fallback_scene_id", 3001),
        fallback_score=raw.get("fallback_score", 0.5),
    )


def load_experiment_config(config_path: Optional[str] = None) -> ExperimentConfig:
    """加载 AB 实验配置（JSON）"""
    if config_path is None:
        config_path = str(_resolve_config_dir() / "experiments.json")

    with open(config_path) as f:
        raw = json.load(f)

    experiments = []
    for exp_raw in raw.get("experiments", []):
        strategies = [ExperimentStrategy(**s) for s in exp_raw.get("strategies", [])]
        experiments.append(Experiment(name=exp_raw["name"], strategies=strategies))

    return ExperimentConfig(experiments=experiments)


def load_scene_experiment_mapping_config(
    config_path: Optional[str] = None,
) -> SceneExperimentMappingConfig:
    """加载场景ID与实验名映射配置（JSON）"""
    if config_path is None:
        config_path = str(_resolve_config_dir() / "scene_experiments.json")

    with open(config_path) as f:
        raw = json.load(f)

    scene_raw = raw.get("scene_experiments", {})
    normalized_scene_experiments = {}
    if isinstance(scene_raw, dict):
        for scene_id_raw, experiment_names_raw in scene_raw.items():
            try:
                scene_id = int(scene_id_raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(experiment_names_raw, list):
                continue
            normalized_scene_experiments[scene_id] = [
                name for name in experiment_names_raw if isinstance(name, str)
            ]

    default_experiments_raw = raw.get("default_experiments", [])
    default_experiments = []
    if isinstance(default_experiments_raw, list):
        default_experiments = [
            name for name in default_experiments_raw if isinstance(name, str)
        ]

    return SceneExperimentMappingConfig(
        scene_experiments=normalized_scene_experiments,
        default_experiments=default_experiments,
    )


def load_calibration_config(config_path: Optional[str] = None) -> dict:
    """加载校准系数（JSON）→ dict[str, CalibrationCoefficients]"""
    if config_path is None:
        config_path = str(_resolve_config_dir() / "calibration.json")

    with open(config_path) as f:
        raw = json.load(f)

    result = {}
    for key, val in raw.items():
        result[key] = CalibrationCoefficients(k=val["k"], b=val["b"])
    return result
