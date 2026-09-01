#!/usr/bin/env python3
"""Build the wheel-packaged Pi Worker runtime seed from its canonical source."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aitest_kit.agent.seed import build_runtime_seed  # noqa: E402


def main() -> None:
    manifest = build_runtime_seed(
        ROOT / "agent_runtime" / "pi_worker",
        ROOT / "aitest_kit" / "agent" / "runtime_seed" / "pi_worker",
    )
    print(f"Built Pi Worker runtime seed {str(manifest['bundle_hash'])[:12]}")


if __name__ == "__main__":
    main()
