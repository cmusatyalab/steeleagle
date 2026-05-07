"""
cli/main.py

The SteelEagle CLI. Every command is a thin wrapper around an HTTP call
to the daemon. Start the daemon first with `steele daemon`.

"""

from typing import Annotated

import httpx
import typer
import uvicorn
from rich import box
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from trogon.typer import init_tui

state = {"daemon_url": "http://127.0.0.1:8765"}

app = typer.Typer(
    name="steele",
    help="SteelEagle Orchestrator — manage local/remote services, containers, and drivers.",
    no_args_is_help=True,
)

driver_app = typer.Typer(
    help="Manage available drivers from Roost", no_args_is_help=True
)
app.add_typer(driver_app, name="driver")

config_app = typer.Typer(help="Inspect SteelEagle config files", no_args_is_help=True)
app.add_typer(config_app, name="config")

gcs_app = typer.Typer(help="Manage Ground Control System", no_args_is_help=True)
app.add_typer(gcs_app, name="gcs")

vehicle_app = typer.Typer(
    name="vehicle", help="Manage SteelEagle vehicles.", no_args_is_help=True
)
app.add_typer(vehicle_app, name="vehicle")

backend_app = typer.Typer(
    name="backend",
    help="Manage backend containers (gabriel, cognitive engines, redis, etc).",
    no_args_is_help=True,
)
app.add_typer(backend_app, name="backend")

sim_app = typer.Typer(name="sim", help="Manage Aviary simulator.", no_args_is_help=True)
app.add_typer(sim_app, name="sim")


console = Console()

init_tui(app)
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client() -> httpx.Client:
    try:
        # Test to see if the daemon is running...
        c = httpx.Client(base_url=state["daemon_url"], timeout=10)
        c.get("/docs")
        return httpx.Client(base_url=state["daemon_url"], timeout=None)
    except Exception as exc:
        rprint(f"[red]Cannot connect to daemon at {state['daemon_url']}:[/red] {exc}")
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


def _follow_sse(url: str, params: dict, prefix: str = "") -> None:
    console.rule(
        title=f"[bold]Following logs for [cyan]{prefix}[/cyan] (Ctrl-C to stop)[/bold]"
    )
    try:
        with (
            httpx.Client(base_url=state["daemon_url"], timeout=None) as c,
            c.stream("GET", url, params=params) as resp,
        ):
            if resp.status_code >= 400:
                rprint(f"[red]Error {resp.status_code}[/red]")
                raise typer.Exit(1)
            for raw in resp.iter_lines():
                if raw.startswith("data: "):
                    rprint(f"{raw[6:]}")
    except KeyboardInterrupt:
        rprint("\n[dim]Stream closed.[/dim]")


@app.callback()
def main(daemon_url: str = "http://127.0.0.1:8765"):
    state["daemon_url"] = daemon_url


# ---------------------------------------------------------------------------
# daemon — start the FastAPI server
# ---------------------------------------------------------------------------


@app.command()
def daemon(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8765, help="Bind port"),
    reload: bool = typer.Option(
        False, help="Enable reload on source changes (dev mode)"
    ),
    loglevel: str = typer.Option(
        "error", help="Uvicorn log level: critical, error, warning, info, debug"
    ),
):
    """Start the orchestrator daemon (blocking)."""

    rprint(f"[bold green]Starting orchestrator daemon[/bold green] on {host}:{port}")
    uvicorn.run(
        "daemon.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=loglevel,
    )


# ---------------------------------------------------------------------------
# services — list all registered services
# ---------------------------------------------------------------------------


@app.command()
def services():
    """List all registered services and their types."""
    with _client() as c:
        data = _check(c.get("/services"))

    table = Table(title="Registered Services", show_lines=False, box=box.SIMPLE_HEAVY)
    table.add_column("Name", style="bold cyan")
    table.add_column("Type", style="dim")
    table.add_column("Entrypoint", style="dark_orange3")

    for svc in data["services"]:
        table.add_row(svc["name"], svc["type"], svc["entrypoint"])

    console.print(table)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


# @service_app.command()
def start(name: str = typer.Argument(..., help="Service name")):
    """Start a service."""
    with (
        console.status(f"Starting [bold]{name}[/bold]…", spinner="aesthetic"),
        _client() as c,
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


# @service_app.command()
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


# @service_app.command()
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


# @service_app.command()
def logs(
    name: str = typer.Argument(..., help="Service name"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    stream: bool = typer.Option(False, "--stream", "-f", help="Follow live output"),
):
    """Logs for a single-instance service."""
    if stream:
        _follow_sse(
            f"/services/{name}/logs", {"stream": True, "tail": tail}, prefix=name
        )
        return
    with _client() as c:
        data = _check(c.get(f"/services/{name}/logs", params={"tail": tail}))
    for line in data.get("logs", []):
        rprint(f"{line}")


# ---------------------------------------------------------------------------
# restart  (convenience: stop then start)
# ---------------------------------------------------------------------------


# @service_app.command()
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
    """Status of every service."""
    with _client() as c:
        svc_list = _check(c.get("/services"))["services"]

        table = Table(title="Service Status", show_lines=False, box=box.SIMPLE_HEAVY)
        table.add_column("Service", style="bold cyan")
        table.add_column("Type", style="dim")
        table.add_column("Status / Instances")
        table.add_column("Details", style="dim", justify="center")

        for svc in svc_list:
            name, stype = svc["name"], svc["type"]
            match stype:
                case "DockerComposeManager":
                    data = _check(c.get(f"/services/{name}/status"))
                    containers = data.get("containers", [])
                    running = sum(1 for c in containers if c.get("status") == "running")
                    extras = Table(show_lines=False, box=box.SIMPLE_HEAVY)
                    extras.add_column("Name", style="bold cyan")
                    extras.add_column("Image", style="dim")
                    extras.add_column("Status")
                    extras.add_column("Short Id", style="dim")
                    for container in containers:
                        extras.add_row(
                            f"{container['name']}",
                            container["image"],
                            _status_color(container["status"]),
                            container["id"],
                        )
                    table.add_row(
                        "backend", stype, f"{running}/{len(containers)} running", extras
                    )
                case "ProcessPool":
                    data = _check(c.get(f"/services/{name}/pool"))
                    instances = data.get("instances", [])
                    running = sum(1 for i in instances if i.get("status") == "running")
                    extras = Table(show_lines=False, box=box.SIMPLE_HEAVY)
                    extras.add_column("Instance Name", style="bold cyan")
                    extras.add_column("Status")
                    rprint(instances)
                    for d in instances:
                        extras.add_row(
                            f"{d['instance_id']}",
                            _status_color(d["status"]),
                        )
                    table.add_row(
                        name, stype, f"{running}/{len(instances)} running", extras
                    )
                case _:
                    data = _check(c.get(f"/services/{name}/status"))
                    st = data.get("status", "?")
                    extras = " ".join(
                        f"{k}: {v}"
                        for k, v in data.items()
                        if k not in {"service", "status"}
                    )
                    table.add_row(name, stype, _status_color(st), extras)

    console.print(table)


# ---------------------------------------------------------------------------
# drivers — list all roost drivers
# ---------------------------------------------------------------------------


@driver_app.command("list")
def drivers():
    """List all roost drivers."""
    with _client() as c:
        data = _check(c.get("/drivers"))

    table = Table(title="Roost Drivers", show_lines=False, box=box.SIMPLE_HEAVY)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description", style="dark_orange3")
    table.add_column("Installation Status", style="dim")

    for d in data["drivers"]:
        table.add_row(d["name"], d["desc"], _status_color(d["status"]))

    console.print(table)


# ---------------------------------------------------------------------------
# install — install a driver from roost
# ---------------------------------------------------------------------------


@driver_app.command("install")
def driver_install(name: str = typer.Argument(..., help="Driver name")):
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
# Config related commands
# ---------------------------------------------------------------------------


@config_app.command("list")
def list_configs():
    """List all config files."""
    with _client() as c:
        data = _check(c.get("/configs"))

    table = Table(title="Config Files", show_lines=False)
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


# ---------------------------------------------------------------------------
# GCS commands
# ---------------------------------------------------------------------------
@gcs_app.command()
def build():
    """Build the frontend React app for the GCS with npm."""
    with console.status("Building GCS React app…", spinner="aesthetic"), _client() as c:
        data = _check(c.post("/gcs/build"))

    console.rule(title="[bold]Log output for npm run build command[/bold]")
    rprint(f"{data.get('log', 'No log data')}")
    rprint(
        f"[bold]npm run build[/bold] → {_status_color(data.get('status', 'unknown'))}"
    )
    if data.get("status", "unknown") == "build_successful":
        rprint(
            "[bold][yellow]:warning: Restart the GCS for these changes to take effect! :warning:[/yellow][/bold]"
        )


@gcs_app.command("install")
def gcs_install():
    """Installs nvm/npm and then calls build if successfully installed."""
    with (
        console.status("Installing prerequisites…", spinner="aesthetic"),
        _client() as c,
    ):
        data = _check(c.post("/gcs/install"))

    console.rule(title="[bold]Log output from installing prerequisites[/bold]")
    rprint(f"{data.get('log', 'No log data')}")
    rprint(
        f"[bold]nvm/npm installation[/bold] → {_status_color(data.get('status', 'unknown'))}"
    )
    if data.get("status", "unknown") == "installed":
        build()


@gcs_app.command("start")
def gcs_start():
    """Start React-based GCS via FastAPI."""
    start("gcs")


@gcs_app.command("stop")
def gcs_stop():
    """Start GCS process."""
    stop("gcs")


@gcs_app.command("restart")
def gcs_restart():
    """Restart GCS."""
    restart("gcs")


@gcs_app.command("status")
def gcs_status():
    """Retrieve status of GCS process."""
    status("gcs")


@gcs_app.command("logs")
def gcs_logs(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    stream: bool = typer.Option(False, "--stream", "-f", help="Follow live output"),
):
    """Retrieve logs for the GCS."""
    logs("gcs", tail, stream)


# ---------------------------------------------------------------------------
# Simulator commands
# ---------------------------------------------------------------------------


@sim_app.command("start")
def sim_start():
    """Start Aviary simulator."""
    start("sim")


@sim_app.command("stop")
def sim_stop():
    """Stop Aviary simulator."""
    stop("sim")


@sim_app.command("restart")
def sim_restart():
    """Restart Aviary."""
    restart("sim")


@sim_app.command("status")
def sim_status():
    """Retrieve status of Aviary process."""
    status("sim")


@sim_app.command("logs")
def sim_logs(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    stream: bool = typer.Option(False, "--stream", "-f", help="Follow live output"),
):
    """Retrieve logs for Aviary."""
    logs("sim", tail, stream)


# ---------------------------------------------------------------------------
# Pool / instance sub-commands
# ---------------------------------------------------------------------------


@vehicle_app.command("start")
def instance_start(
    name: str | None = typer.Option(None, "--name", "-n", help="Optional vehicle name"),
):
    """Start a new vehicle in a pool."""
    params = {"label": name} if name else {}
    with (
        console.status(
            "Starting instance of [bold]vehicle[/bold]…", spinner="aesthetic"
        ),
        _client() as c,
    ):
        data = _check(c.post("/services/vehicle/pool", params=params))
    iid = data.get("instance_id", "?")
    rprint(
        f"[bold]{name}[/bold] instance [cyan]{iid}[/cyan] → {_status_color(data.get('status', '?'))}"
    )


@vehicle_app.command("stop")
def instance_stop(
    instance_id: str = typer.Argument(..., help="Instance ID"),
):
    """Stop a specific vehicle instance."""
    with (
        console.status(
            f"Stopping vehicle instance [cyan]{instance_id}[/cyan]…",
            spinner="aesthetic",
        ),
        _client() as c,
    ):
        data = _check(c.post(f"/services/vehicle/pool/{instance_id}/stop"))
    rprint(
        f"Vehicle instance [cyan]{instance_id}[/cyan] → {_status_color(data.get('status', '?'))}"
    )


@vehicle_app.command("list")
def instance_list():
    """List all instances in the vehicle pool."""
    with _client() as c:
        data = _check(c.get("/services/vehicle/pool"))

    table = Table(title="Vehicle Instances", show_lines=False)
    table.add_column("ID", style="bold cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for inst in data.get("instances", []):
        iid = inst.get("instance_id", "?")
        st = inst.get("status", "?")
        extras = " ".join(
            f"{k}: {v}" for k, v in inst.items() if k not in {"instance_id", "status"}
        )
        table.add_row(iid, _status_color(st), extras)

    console.print(table)


@vehicle_app.command("status")
def instance_status(
    instance_id: str = typer.Argument(..., help="Instance ID"),
):
    """Status of a specific vehicle instance."""
    with _client() as c:
        data = _check(c.get(f"/services/vehicle/pool/{instance_id}/status"))
    table = Table(title=f"Vehicle instance {instance_id}", show_header=False)
    table.add_column("Key", style="dim")
    table.add_column("Value")
    for k, v in data.items():
        if k in {"service"}:
            continue
        table.add_row(k, _status_color(str(v)) if k == "status" else str(v))
    console.print(table)


@vehicle_app.command("logs")
def instance_logs(
    instance_id: str = typer.Argument(..., help="Instance ID"),
    tail: int = typer.Option(50, "--tail", "-n"),
    stream: bool = typer.Option(False, "--stream", "-f"),
):
    """Logs for a specific vehicle instance."""
    if stream:
        _follow_sse(
            f"/services/vehicle/pool/{instance_id}/logs",
            {"stream": True, "tail": tail},
            prefix=f"vehicle.{instance_id}",
        )
        return
    with _client() as c:
        data = _check(
            c.get(f"/services/vehicle/pool/{instance_id}/logs", params={"tail": tail})
        )
    for line in data.get("logs", []):
        rprint(f"[dim]vehicle.{instance_id}[/dim] {line}")


# ---------------------------------------------------------------------------
# Backend - docker compose commands
# ---------------------------------------------------------------------------


@backend_app.command("start")
def backend_start():
    """Start the backend containers using docker compose."""
    with (
        console.status("Starting backend containers…", spinner="aesthetic"),
        _client() as c,
    ):
        data = _check(c.post("/services/backend/start"))

    rprint(f"[bold]Backend[/bold]  → {_status_color(data.get('status', '?'))}")
    containers = data.get("containers", False)

    if containers:
        running = sum(1 for c in containers if c.get("status") == "running")
        rprint(f"[bold red]{running}/{len(containers)} backend containers running")


@backend_app.command("stop")
def backend_stop():
    """Stop all backend containers."""
    with (
        console.status("Stopping backend containers…", spinner="aesthetic"),
        _client() as c,
    ):
        data = _check(c.post("/services/backend/stop"))
    rprint(f"Backend Containers → {_status_color(data.get('status', '?'))}")
    containers = data.get("containers", False)

    if containers:
        running = sum(1 for c in containers if c.get("status") == "running")
        rprint(f"[bold red]{running}/{len(containers)} backend containers running")


@backend_app.command("list")
def backend_list():
    """List services in the backend docker-compose.yml file."""
    with _client() as c:
        data = _check(c.get("/backend/list"))

    table = Table(title="Backend Containers", show_lines=False, box=box.SIMPLE_HEAVY)
    table.add_column("Name", style="bold cyan")
    table.add_column("Image/Dockerfile", style="dim")
    table.add_column("Ports", style="dark_orange3")
    for _s, props in data["services"].items():
        name = props.get("container_name", "?")
        image = props.get("image", None)
        if image is None:
            build = props.get("build")
            image = (
                f"[magenta]{build.get('context')}/{build.get('dockerfile')}[/magenta]"
            )
        ports = props.get("ports", None)
        mappings = ""
        if ports is not None:
            for p in ports:
                mappings += (
                    f"{p['target']} :right_arrow: {p['published']} {p['protocol']}, "
                )
        table.add_row(name, image, mappings)

    console.print(table)


@backend_app.command("status")
def backend_status(
    name: Annotated[str, typer.Argument(..., help="Container name")] = None,
):
    """Status of backend containers."""
    with _client() as c:
        data = _check(c.get("/services/backend/status"))
    containers = data.get("containers", [])
    running = sum(1 for c in containers if c.get("status") == "running")
    extras = Table(show_lines=False, box=box.SIMPLE_HEAVY)
    extras.add_column("Name", style="bold cyan")
    extras.add_column("Image", style="dim")
    extras.add_column("Status")
    extras.add_column("Short Id", style="dim")
    for c in containers:
        extras.add_row(f"{c['name']}", c["image"], _status_color(c["status"]), c["id"])
    console.print(extras)
    console.rule(f"[bold red]{running}/{len(containers)} backend containers running")


@backend_app.command("logs")
def compose_logs(
    name: Annotated[str, typer.Argument(..., help="Container name")] = None,
    tail: int = typer.Option(50, "--tail", "-n"),
    stream: bool = typer.Option(False, "--stream", "-f"),
):
    """Logs for a specific container instance."""
    if stream:
        _follow_sse(
            "/services/backend/logs",
            {"stream": True, "tail": tail},
        )
        return
    with _client() as c:
        data = _check(c.get("/services/backend/logs", params={"tail": tail}))
    for line in data.get("logs", []):
        rprint(f"{line}")


if __name__ == "__main__":
    app()
