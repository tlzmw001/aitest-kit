"""Models owned by AB experiment SDK package."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExperimentStrategy:
    id: str
    hash_range: list = field(default_factory=lambda: [0, 100])
    params: dict = field(default_factory=dict)


@dataclass
class Experiment:
    name: str
    strategies: list = field(default_factory=list)


@dataclass
class ExperimentConfig:
    experiments: list = field(default_factory=list)
