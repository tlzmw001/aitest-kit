"""Configuration transforms used by the rough-ranking Harness."""
from __future__ import annotations

import copy
from typing import Any


def patch_strategy_params(
    experiment: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    patched = copy.deepcopy(experiment)
    for strategy in patched["strategies"]:
        if strategy["id"] == "cr_v2_full":
            strategy["params"] = copy.deepcopy(params)
            break
    return patched
