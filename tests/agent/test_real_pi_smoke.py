from __future__ import annotations

import os
from pathlib import Path

import pytest

from aitest_kit.agent.client import WorkerClient, default_worker_command
from aitest_kit.agent.config import build_worker_environment, load_agent_config


@pytest.mark.skipif(
    os.environ.get("AITEST_PI_SMOKE") != "1",
    reason="set AITEST_PI_SMOKE=1 with a configured BYOK model to run the real Pi smoke test",
)
def test_real_pi_can_read_workspace_without_mutation() -> None:
    workspace = Path(os.environ.get("AITEST_PI_SMOKE_WORKSPACE", Path.cwd())).expanduser().resolve()
    config = load_agent_config(workspace)
    events = []
    with WorkerClient(
        default_worker_command(),
        env=build_worker_environment(config),
        startup_timeout=20,
        message_timeout=180,
        shutdown_timeout=10,
    ) as client:
        client.start(
            {
                "cwd": str(workspace),
                "model": {
                    "provider": config.model.provider,
                    "name": config.model.name,
                    "protocol": config.model.protocol,
                    "api_key_env": config.model.api_key_env,
                    "base_url": config.model.base_url,
                    "base_url_env": config.model.base_url_env,
                },
                "skill_paths": [],
                "permission_mode": "approval",
            }
        )
        events = client.run_prompt(
            "Read README.md and reply with only the project name. Do not modify files or run shell commands.",
            approval_handler=lambda _event: "deny",
        )

    assert any(event.type == "text_delta" for event in events)
    assert events[-1].type == "agent_finished"
