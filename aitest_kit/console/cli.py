from __future__ import annotations

import ipaddress
import secrets
import threading
import webbrowser
from importlib import resources
from pathlib import Path

import click


def console_static_dir() -> Path:
    """Return the frontend bundle installed with ``aitest-kit``."""
    return Path(resources.files("aitest_kit.console").joinpath("web"))


@click.command(name="console")
@click.option("--workspace", type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--host", envvar="AITEST_CONSOLE_HOST", default="127.0.0.1", show_default=True)
@click.option("--port", envvar="AITEST_CONSOLE_PORT", type=click.IntRange(1, 65535), required=True)
@click.option("--no-open", is_flag=True, help="Do not open the browser automatically")
def console_command(workspace: Path | None, host: str, port: int, no_open: bool) -> None:
    """Run the local AITest Console on a loopback address."""
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise click.ClickException("Console MVP only allows loopback host addresses")
    except ValueError as exc:
        raise click.ClickException("--host must be a loopback IP address") from exc

    try:
        import uvicorn
        from aitest_kit.console.app import create_app
    except ImportError as exc:
        raise click.ClickException('Console requires `pip install "aitest-kit[server]"`') from exc

    root = workspace.expanduser().resolve() if workspace is not None else None
    static_dir = console_static_dir()
    if not static_dir.is_dir() or not (static_dir / "index.html").is_file():
        raise click.ClickException(
            "Installed AITest Console frontend is missing; reinstall an official aitest-kit build"
        )
    token = secrets.token_urlsafe(32)
    app = create_app(initial_workspace=root, token=token, static_dir=static_dir)
    launch_id = secrets.token_urlsafe(8)
    # A unique document URL forces a reload when the browser reuses an existing tab.
    # Keep the sensitive session token in the fragment so it is never sent to the server.
    url = f"http://{host}:{port}/?launch={launch_id}#token={token}"
    click.echo(f"AITest Console: http://{host}:{port}/")
    if not no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    elif no_open:
        click.echo(f"Session URL: {url}")
    uvicorn.run(app, host=host, port=port, log_level="info")
