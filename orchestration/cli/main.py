"""
cli/main.py

The SteelEagle CLI. Every command is a thin wrapper around an HTTP call
to the daemon. Start the daemon first with `steele daemon`.

"""

from typing import Annotated

import httpx
import typer
import uvicorn
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from trogon.typer import init_tui

DAEMON_URL = "http://127.0.0.1:8765"

app = typer.Typer(
    name="steele",
    help="SteelEagle Orchestrator — manage local/remote services, containers, and drivers.",
    no_args_is_help=True,
)

service_app = typer.Typer(help="Start/stop/log services", no_args_is_help=True)
app.add_typer(service_app, name="service")
driver_app = typer.Typer(
    help="Manage available drivers from Roost", no_args_is_help=True
)
app.add_typer(driver_app, name="driver")
config_app = typer.Typer(help="Inspect SteelEagle config files", no_args_is_help=True)
app.add_typer(config_app, name="config")
gcs_app = typer.Typer(help="GCS-specific commands", no_args_is_help=True)
app.add_typer(gcs_app, name="gcs")
console = Console()

init_tui(app)
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client() -> httpx.Client:
    try:
        # Test to see if the daemon is running...
        c = httpx.Client(base_url=DAEMON_URL, timeout=10)
        c.get("")
        return httpx.Client(base_url=DAEMON_URL, timeout=10)
    except Exception as exc:
        rprint(f"[red]Cannot connect to daemon at {DAEMON_URL}:[/red] {exc}")
        rprint("[yellow]Is the daemon running? Try: steele daemon[/yellow]")
        raise typer.Exit(1) from exc


def _check(resp: httpx.Response) -> dict:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        rprint(f"[red]Error {resp.status_code}:[/red] {detail}")
        raise typer.Exit(1)
    return resp.json()


def _status_color(status: str) -> str:
    colors = {
        "running": "green",
        "started": "green",
        "stopped": "yellow",
        "exited": "yellow",
        "not_found": "red",
        "not_started": "dim",
        "already_running": "cyan",
        "already_stopped": "yellow",
        "installed": "green",
        "installation_failed": "red",
        "uninstalled/outdated": "dim",
        "build_successful": "green",
        "build_failed": "red",
    }
    color = colors.get(status, "white")
    return f"[{color}]{status}[/{color}]"


# ---------------------------------------------------------------------------
# daemon — start the FastAPI server
# ---------------------------------------------------------------------------


@app.command()
def daemon(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8765, help="Bind port"),
    reload: bool = typer.Option(False, help="Enable hot-reload (dev mode)"),
):
    DAEMON_URL = f"{host}:{port}"
    """Start the orchestrator daemon (blocking)."""

    rprint(f"[bold green]Starting orchestrator daemon[/bold green] on {host}:{port}")
    uvicorn.run(
        "daemon.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


# ---------------------------------------------------------------------------
# services — list all registered services
# ---------------------------------------------------------------------------


@app.command()
def services():
    """List all registered services and their types."""
    with _client() as c:
        data = _check(c.get("/services"))

    table = Table(title="Registered Services", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Type", style="dim")
    table.add_column("Command/Image", style="dark_orange3")

    for svc in data["services"]:
        table.add_row(
            svc["name"],
            svc["type"],
            " ".join(svc["command_or_image"])
            if svc["type"] == "ProcessManager"
            else svc["command_or_image"],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


@service_app.command()
def start(name: str = typer.Argument(..., help="Service name")):
    """Start a service."""
    with (
        console.status(f"Starting [bold]{name}[/bold]…", spinner="aesthetic"),
        _client as c,
    ):
        data = _check(c.post(f"/services/{name}/start"))

    status = data.get("status", "unknown")
    rprint(f"[bold]{name}[/bold] → {_status_color(status)}", end="")

    extras = {k: v for k, v in data.items() if k not in {"service", "status"}}
    if extras:
        detail = "  " + "  ".join(f"{k}={v}" for k, v in extras.items())
        rprint(detail, end="")
    rprint()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


@service_app.command()
def stop(name: str = typer.Argument(..., help="Service name")):
    """Stop a service."""
    with (
        console.status(f"Stopping [bold]{name}[/bold]…", spinner="aesthetic"),
        _client() as c,
    ):
        data = _check(c.post(f"/services/{name}/stop"))

    status = data.get("status", "unknown")
    rprint(f"[bold]{name}[/bold] → {_status_color(status)}")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@service_app.command()
def status(
    name: Annotated[str, typer.Argument(..., help="Service name")] = None,
):
    """Show detailed status for a service."""

    def show_status(name):
        with _client() as c:
            data = _check(c.get(f"/services/{name}/status"))

        table = Table(title=f"Status: {name}", show_header=False, show_lines=False)
        table.add_column("Key", style="dim")
        table.add_column("Value")

        for key, val in data.items():
            if key == "service":
                continue
            display = _status_color(str(val)) if key == "status" else str(val)
            table.add_row(key, display)

        console.print(table)

    if name:
        show_status(name)
    else:
        with _client() as c:
            data = _check(c.get("/services"))
        for svc in data["services"]:
            show_status(svc["name"])


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------


@service_app.command()
def logs(
    name: str = typer.Argument(..., help="Service name"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    stream: bool = typer.Option(False, "--stream", "-f", help="Follow live output"),
):
    """
    Print recent logs for a service.
    Use --stream / -f to follow live output (Ctrl-C to stop).
    """
    if not stream:
        with _client() as c:
            data = _check(c.get(f"/services/{name}/logs", params={"tail": tail}))
        for line in data.get("logs", []):
            rprint(f"{line}")
        return

    # ---- Live SSE stream ----
    console.rule(
        title=f"[bold]Following logs for [cyan]{name}[/cyan] (Ctrl-C to stop)[/bold]"
    )
    try:
        with (
            httpx.Client(base_url=DAEMON_URL, timeout=None) as c,
            c.stream(
                "GET",
                f"/services/{name}/logs",
                params={"stream": True, "tail": tail},
            ) as resp,
        ):
            if resp.status_code >= 400:
                rprint(f"[red]Error {resp.status_code}[/red]")
                raise typer.Exit(1)
            for raw in resp.iter_lines():
                if raw.startswith("data: "):
                    rprint(f"{raw[6:]}")
                # skip ": keep-alive" and blank lines
    except KeyboardInterrupt:
        rprint("\n[dim]Stream closed.[/dim]")


# ---------------------------------------------------------------------------
# restart  (convenience: stop then start)
# ---------------------------------------------------------------------------


@service_app.command()
def restart(name: str = typer.Argument(..., help="Service name")):
    """Stop then start a service."""
    with (
        console.status(f"Restarting [bold]{name}[/bold]…", spinner="aesthetic"),
        _client() as c,
    ):
        _check(c.post(f"/services/{name}/stop"))
        data = _check(c.post(f"/services/{name}/start"))

    rprint(f"[bold]{name}[/bold] → {_status_color(data.get('status', 'unknown'))}")


# ---------------------------------------------------------------------------
# ps  — status of all services at once
# ---------------------------------------------------------------------------


@app.command()
def ps():
    """Show the status of every registered service (like docker ps)."""
    with _client() as c:
        svc_list = _check(c.get("/services"))["services"]
        statuses = [_check(c.get(f"/services/{s['name']}/status")) for s in svc_list]

    table = Table(title="Service Status", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for data in statuses:
        name = data.pop("service")
        status_val = data.pop("status", "unknown")
        details = "  ".join(f"{k}={v}" for k, v in data.items())
        table.add_row(name, _status_color(status_val), details)

    console.print(table)


# ---------------------------------------------------------------------------
# drivers — list all roost drivers
# ---------------------------------------------------------------------------


@app.command()
def drivers():
    """List all roost drivers."""
    with _client() as c:
        data = _check(c.get("/drivers"))

    table = Table(title="Roost Drivers", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description", style="dark_orange3")
    table.add_column("Installation Status", style="dim")

    for d in data["drivers"]:
        table.add_row(d["name"], d["desc"], _status_color(d["status"]))

    console.print(table)


# ---------------------------------------------------------------------------
# install — install a driver from roost
# ---------------------------------------------------------------------------


@driver_app.command()
def install(name: str = typer.Argument(..., help="Driver name")):
    """Install a driver from roost repository."""
    with (
        console.status(f"Installing [bold]{name}[/bold]…", spinner="aesthetic"),
        _client() as c,
    ):
        data = _check(c.post(f"/drivers/{name}/install"))

    rprint(f"[bold]{name}[/bold] → {_status_color(data.get('result', 'unknown'))}")
    console.rule(
        title=f"[bold]Installation output for driver [cyan]{name}[/cyan][/bold]"
    )
    rprint(f"{data.get('log', 'No log data')}")


# ---------------------------------------------------------------------------
# configs — list all SteelEagle config files
# ---------------------------------------------------------------------------


@app.command()
def configs():
    """List all config files."""
    with _client() as c:
        data = _check(c.get("/configs"))

    table = Table(title="Config Files", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Path", style="dim")

    for c in data["configs"]:
        table.add_row(
            c["name"],
            c["path"],
        )

    console.print(table)


@config_app.command()
def inspect(name: str = typer.Argument(..., help="Config name")):
    """Print the contents of a config file."""
    with _client() as c:
        data = _check(c.post(f"/configs/{name}/inspect"))
    console.rule(title=f"[bold]Contents of: [cyan]{name}[/cyan][/bold]")
    rprint(data)


@gcs_app.command()
def build():
    """Build the frontend React app for the GCS with npm."""
    with console.status("Building GCS React app…", spinner="aesthetic"), _client() as c:
        data = _check(c.post("/gcs/build"))

    rprint(
        f"[bold]npm run build[/bold] → {_status_color(data.get('status', 'unknown'))}"
    )
    rprint(
        ":warning: [bold][yellow]Restart the GCS for these changes to take effect![/yellow][/bold]"
    )
    console.rule(title="[bold]Log output for npm run build command[/bold]")
    rprint(f"{data.get('log', 'No log data')}")


if __name__ == "__main__":
    app()
