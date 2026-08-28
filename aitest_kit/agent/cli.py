"""CLI commands for the local Pi Agent Runtime."""
from __future__ import annotations

from pathlib import Path

import click

from aitest_kit.agent.client import AgentWorkerError, WorkerClient, default_worker_command
from aitest_kit.agent.config import AgentConfigError, build_worker_environment, load_agent_config
from aitest_kit.agent.doctor import format_doctor_checks, run_agent_doctor


@click.group(name="agent")
def agent_command() -> None:
    """Run and diagnose the local Pi Agent Runtime."""


@agent_command.command(name="doctor")
@click.option("--workspace", type=click.Path(file_okay=False, path_type=Path), default=Path.cwd)
def agent_doctor_command(workspace: Path) -> None:
    """Check Node, locked dependencies, BYOK references, and Worker handshake."""
    checks = run_agent_doctor(workspace)
    click.echo("AITest Agent Doctor")
    click.echo(f"Workspace: {workspace.expanduser().resolve()}")
    click.echo(format_doctor_checks(checks))
    if any(not check.ok for check in checks):
        raise click.exceptions.Exit(1)


@agent_command.command(name="run")
@click.option("--workspace", type=click.Path(file_okay=False, path_type=Path), default=Path.cwd)
@click.option("--mode", "permission_mode", type=click.Choice(["approval", "full_trust"]), default="approval")
@click.option("--skill-path", "skill_paths", multiple=True, type=click.Path(exists=True, path_type=Path))
@click.option("--prompt", "prompt_text", required=True, help="Prompt sent to the local Pi session")
def agent_run_command(
    workspace: Path,
    permission_mode: str,
    skill_paths: tuple[Path, ...],
    prompt_text: str,
) -> None:
    """Run one local Pi Agent request with CLI permission approval."""
    root = workspace.expanduser().resolve()
    if permission_mode == "full_trust":
        click.confirm(
            f"完全信任 {root}？工具将继承当前本机用户权限，文件内容可能进入模型上下文。",
            abort=True,
        )
    try:
        config = load_agent_config(root)
        with WorkerClient(default_worker_command(), env=build_worker_environment(config)) as client:
            client.start(
                {
                    "cwd": str(root),
                    "model": {
                        "provider": config.model.provider,
                        "name": config.model.name,
                        "protocol": config.model.protocol,
                        "api_key_env": config.model.api_key_env,
                        "base_url": config.model.base_url,
                        "base_url_env": config.model.base_url_env,
                    },
                    "skill_paths": [str(path.expanduser().resolve()) for path in skill_paths],
                    "permission_mode": permission_mode,
                }
            )
            try:
                client.run_prompt(
                    prompt_text,
                    on_event=_render_event,
                    approval_handler=_request_cli_approval,
                )
            except KeyboardInterrupt:
                client.abort()
                raise click.Abort() from None
    except (AgentConfigError, AgentWorkerError) as exc:
        raise click.ClickException(str(exc)) from exc


def _request_cli_approval(event) -> str:
    payload = event.payload
    click.echo("")
    click.echo("Permission requested")
    for label, key in (
        ("Tool", "tool_name"),
        ("Cwd", "cwd"),
        ("Target", "target"),
        ("Command", "command"),
        ("Summary", "summary"),
    ):
        if payload.get(key):
            click.echo(f"{label}: {payload[key]}")
    choice = click.prompt(
        "Decision",
        type=click.Choice(["allow_once", "allow_session", "deny"]),
        default="deny",
    )
    return str(choice)


def _render_event(event) -> None:
    if event.type == "text_delta":
        click.echo(str(event.payload.get("delta", "")), nl=False)
    elif event.type in {"tool_call_requested", "tool_call_finished", "permission_resolved"}:
        click.echo(f"\n[{event.type}] {event.payload}")
    elif event.type == "agent_finished":
        click.echo("")
