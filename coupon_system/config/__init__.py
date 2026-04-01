"""配置加载模块"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SceneConfig:
    name: str
    allowed_coupon_types: list[str]
    max_claim_per_user: int
    require_new_user: bool = False
    require_member: bool = False


@dataclass
class CouponTemplate:
    name: str
    type: str
    value: int
    min_spend: int
    total_stock: int
    expire_days: int
    scenes: list[str]


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
    on_model_timeout: FallbackAction = field(default_factory=FallbackAction)
    on_model_unavailable: FallbackAction = field(default_factory=FallbackAction)


@dataclass
class ModelServiceConfig:
    host: str = "localhost"
    port: int = 50052
    timeout: float = 2.0
    enabled: bool = True


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/0"
    key_prefix: str = "coupon:"
    stock_ttl: int = 86400
    user_claim_ttl: int = 604800


@dataclass
class AppConfig:
    scenes: dict[str, SceneConfig] = field(default_factory=dict)
    coupon_templates: dict[str, CouponTemplate] = field(default_factory=dict)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    model_service: ModelServiceConfig = field(default_factory=ModelServiceConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)


def load_config(config_path: str | None = None) -> AppConfig:
    """加载配置文件"""
    if config_path is None:
        config_path = os.environ.get(
            "COUPON_CONFIG_PATH",
            str(Path(__file__).parent / "settings.yaml"),
        )

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    scenes = {}
    for key, val in raw.get("scenes", {}).items():
        scenes[key] = SceneConfig(**val)

    templates = {}
    for key, val in raw.get("coupon_templates", {}).items():
        templates[key] = CouponTemplate(**val)

    rl_raw = raw.get("rate_limit", {})
    rate_limit = RateLimitConfig(**rl_raw)

    fb_raw = raw.get("fallback", {})
    fallback = FallbackConfig(
        enabled=fb_raw.get("enabled", True),
        on_model_timeout=FallbackAction(**fb_raw.get("on_model_timeout", {})),
        on_model_unavailable=FallbackAction(**fb_raw.get("on_model_unavailable", {})),
    )

    model_raw = raw.get("model_service", {})
    model_service = ModelServiceConfig(**model_raw)

    redis_raw = raw.get("redis", {})
    redis_config = RedisConfig(**redis_raw)

    return AppConfig(
        scenes=scenes,
        coupon_templates=templates,
        rate_limit=rate_limit,
        fallback=fallback,
        model_service=model_service,
        redis=redis_config,
    )
