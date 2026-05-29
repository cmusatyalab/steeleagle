"""
cli/main.py

The SteelEagle CLI. Every command is a thin wrapper around a REST call
to the daemon.

"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvicorn
from daemon.systemd import (
    UnitConfig,
    current_user,
    install,
    render_unit,
    uninstall,
    unit_path,
)
from rich import box
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from trogon.typer import init_tui

_CLI_NAME = "steele"
state = {"daemon_url": "http://127.0.0.1:8765"}

app = typer.Typer(
    name=_CLI_NAME,
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
daemon_app = typer.Typer(
    name="daemon", help="Manage the daemon as a systemd service.", no_args_is_help=True
)
app.add_typer(daemon_app, name="daemon")

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
        rprint(
            f"[yellow]Is the daemon running? Start with: `{_CLI_NAME} daemon` or install as systemd service.[/yellow]"
        )
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
                if raw.startswith("data:"):
                    rprint(f"{escape(raw[5:])}")
    except KeyboardInterrupt:
        rprint("\n[dim]Stream closed.[/dim]")


def _orch_executable() -> str:
    """
    Find the installed `orch` binary.  Prefers the PATH entry so it works
    whether installed as a uv tool or via pip.
    """
    found = shutil.which(_CLI_NAME)
    if found:
        return found
    raise RuntimeError(
        f"Cannot find the `{_CLI_NAME}` executable on PATH.\n"
        "Install it first with: uv tool install -e ."
    )


@app.callback()
def main(daemon_url: str = "http://127.0.0.1:8765"):
    state["daemon_url"] = daemon_url


# ---------------------------------------------------------------------------
# daemon — start the FastAPI server, install it as a systemd service
# ---------------------------------------------------------------------------


@daemon_app.command("start")
def daemon(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8765, help="Bind port"),
    config: str = typer.Option(
        "orchestrator.yaml",
        "--config",
        "-c",
        help="Path to the YAML service config file.",
        show_default=True,
    ),
    reload: bool = typer.Option(
        False, help="Enable reload on source changes (dev mode)"
    ),
    loglevel: str = typer.Option(
        "error", help="Uvicorn log level: critical, error, warning, info, debug"
    ),
):
    """Start the orchestrator daemon (blocking)."""
    os.environ.setdefault("ORCH_CONFIG", str(Path(config)))
    rprint(f"[bold green]Starting orchestrator daemon[/bold green] on {host}:{port}")
    uvicorn.run(
        "daemon.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=loglevel,
    )


@daemon_app.command("install")
def systemd_install(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to the YAML service config (stored in the unit file).",
        ),
    ] = "orchestrator.yaml",
    service_name: str = typer.Option(
        f"{_CLI_NAME}d",
        "--name",
        "-n",
        help="Systemd unit name (without .service).",
    ),
    description: str = typer.Option(
        "SteelEagle Daemon",
        "--description",
        help="Service to manage the orchestration of SteelEagle services.",
    ),
    working_dir: Annotated[
        Path,
        typer.Option(
            None,
            "--working-dir",
            "-w",
            help="Working directory for the unit. Defaults to the current directory.",
        ),
    ]
    | None = None,
    user_service: bool = typer.Option(
        False,
        "--user",
        help=(
            "Install as a user-level service (~/.config/systemd/user/) "
            "instead of a system-level service (/etc/systemd/system/). "
            "Does not require root, but needs `loginctl enable-linger <user>` "
            "to start at boot."
        ),
    ),
    enable: bool = typer.Option(
        True, "--enable/--no-enable", help="Enable the service to start at boot."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the unit file without writing it."
    ),
):
    """
    Generate and install a systemd unit file for the orchestrator daemon.
    """

    try:
        executable = _orch_executable()
    except RuntimeError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(1) from RuntimeError

    cwd = Path(working_dir) or Path.cwd()
    abs_config = config if config.is_absolute() else (cwd / config).resolve()

    run_user, run_group = ("", "") if user_service else current_user()

    exec_start = f"{executable} daemon start --config {abs_config}"

    cfg = UnitConfig(
        service_name=service_name,
        description=description,
        exec_start=exec_start,
        working_directory=str(cwd.resolve()),
        config_path=str(abs_config),
        user_service=user_service,
        run_as_user=run_user,
        run_as_group=run_group,
    )

    if dry_run:
        rprint(
            f"[dim]# Would write to: {__import__('daemon.systemd', fromlist=['unit_path']).unit_path(service_name, user_service)}[/dim]"
        )
        rprint(render_unit(cfg))
        return

    try:
        dest = install(cfg, enable=enable)
    except PermissionError:
        rprint(
            f"[red]Permission denied writing to {__import__('daemon.systemd', fromlist=['unit_path']).unit_path(service_name, user_service)}[/red]\n"
            "[yellow]Re-run with sudo, or use --user for a user-level service.[/yellow]"
        )
        raise typer.Exit(1) from PermissionError

    rprint(f"[green]✓[/green] Unit file written to [bold]{dest}[/bold]")
    if enable:
        rprint(
            f"[green]✓[/green] Enabled: will start at {'next login' if user_service else 'boot'}"
        )
    rprint()
    rprint("Useful commands:")
    scope = "--user " if user_service else ""
    rprint(f"  [cyan]systemctl {scope}start {service_name}[/cyan]   # start now")
    rprint(f"  [cyan]systemctl {scope}stop {service_name}[/cyan]   # stop")
    rprint(f"  [cyan]systemctl {scope}status {service_name}[/cyan]   # check status")
    rprint(f"  [cyan]journalctl {scope}-u {service_name} -f[/cyan]   # follow logs")


@daemon_app.command("uninstall")
def systemd_uninstall(
    service_name: str = typer.Option(f"{_CLI_NAME}d", "--name", "-n"),
    user_service: bool = typer.Option(False, "--user"),
):
    """Stop, disable, and remove the systemd unit file."""

    dest = unit_path(service_name, user_service)
    if not dest.exists():
        rprint(f"[yellow]Unit file not found: {dest}[/yellow]")
        raise typer.Exit(1)

    confirm = typer.confirm(f"Remove {dest} and disable {service_name}?")
    if not confirm:
        raise typer.Abort()

    try:
        uninstall(service_name, user_service)
    except PermissionError:
        rprint("[red]Permission denied. Re-run with sudo.[/red]")
        raise typer.Exit(1) from PermissionError

    rprint(f"[green]✓[/green] {service_name} stopped, disabled, and removed.")


@daemon_app.command("status")
def systemd_status(
    service_name: str = typer.Option(f"{_CLI_NAME}d", "--name", "-n"),
    user_service: bool = typer.Option(False, "--user"),
):
    """Show the systemd status of the daemon service."""
    cmd = ["systemctl"]
    if user_service:
        cmd.append("--user")
    cmd += ["status", service_name]
    subprocess.run(cmd)  # let systemctl handle its own formatting


@daemon_app.command("show")
def systemd_show(
    service_name: str = typer.Option("steeld", "--name", "-n"),
    user_service: bool = typer.Option(False, "--user"),
):
    """Print the installed unit file contents."""
    dest = unit_path(service_name, user_service)
    if not dest.exists():
        rprint(f"[red]Unit file not found: {dest}[/red]")
        raise typer.Exit(1)
    rprint(dest.read_text())


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


# @app.command(
#    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
# )
def start(ctx: typer.Context, name: str = typer.Argument(..., help="Service name")):
    """Start a service."""
    with (
        console.status(f"Starting [bold]{name}[/bold]…", spinner="aesthetic"),
        _client() as c,
    ):
        params = {"q": ctx.args}
        data = _check(c.post(f"/services/{name}/start", params=params))

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

        table = Table(
            title=f"Status: {name}",
            show_header=False,
            show_lines=False,
            box=box.SIMPLE_HEAVY,
        )
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
        rprint(f"{escape(line)}")


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
def ps(
    details: Annotated[
        bool, typer.Option(help="Display detailed information about each service.")
    ] = False,
):
    """Status of every service."""
    with _client() as c:
        svc_list = _check(c.get("/services"))["services"]

        table = Table(title="Service Status", show_lines=False, box=box.SIMPLE_HEAVY)
        table.add_column("Service", style="bold cyan")
        table.add_column("Type", style="dim")
        table.add_column("Status / Instances")
        if details:
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
                    if running == len(containers):
                        color = "green"
                    elif running == 0:
                        color = "red"
                    else:
                        color = "yellow"
                    table.add_row(
                        "backend",
                        stype,
                        f"[{color}]{running}/{len(containers)} running[/{color}]",
                        extras if details else None,
                    )
                case "ProcessPool":
                    data = _check(c.get(f"/services/{name}/pool"))
                    instances = data.get("instances", [])
                    running = sum(1 for i in instances if i.get("status") == "running")
                    extras = Table(show_lines=False, box=box.SIMPLE_HEAVY)
                    extras.add_column("Instance Name", style="bold cyan")
                    extras.add_column("Status")
                    for d in instances:
                        extras.add_row(
                            f"{d['instance_id']}",
                            _status_color(d["status"]),
                        )
                    if running == len(instances):
                        color = "green"
                    elif running == 0:
                        color = "red"
                    else:
                        color = "yellow"
                    table.add_row(
                        name,
                        stype,
                        f"[{color}]{running}/{len(instances)} running[/{color}]",
                        extras if details else None,
                    )
                case _:
                    data = _check(c.get(f"/services/{name}/status"))
                    st = data.get("status", "?")
                    extras = Table(show_lines=False, box=box.SIMPLE_HEAVY)
                    extras.add_column("PID/Exit Code", style="bold cyan")
                    extras.add_column("Started At")
                    extras.add_row(
                        f"{data.get('pid', data.get('exit_code'))}",
                        data.get("started_at", None),
                    )
                    table.add_row(
                        name, stype, _status_color(st), extras if details else None
                    )

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

    table = Table(title="Config Files", show_lines=False, box=box.SIMPLE_HEAVY)
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


@gcs_app.command(
    "start", context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def gcs_start(ctx: typer.Context):
    """Start React-based GCS via FastAPI."""
    start(ctx, "gcs")


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


@sim_app.command(
    "start", context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def sim_start(ctx: typer.Context):
    """Start Aviary simulator."""
    start(ctx, "sim")


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


@vehicle_app.command(
    "start", context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def instance_start(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Vehicle name"),
):
    """Start a new vehicle in a pool. Any additional options will be passed as keyword arguments to the launch script. (e.g. --config canary.toml)"""

    params = {"label": name, "q": ctx.args} if name else {ctx.args}
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

    table = Table(title="Vehicle Instances", show_lines=False, box=box.SIMPLE_HEAVY)
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
    table = Table(
        title=f"Vehicle instance {instance_id}", show_header=False, box=box.SIMPLE_HEAVY
    )
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
    console.rule(title=f"[bold]Logs of: [cyan]vehicle.{instance_id}[/cyan][/bold]")
    for line in data.get("logs", []):
        rprint(f"{escape(line)}")


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
        rprint(f"{escape(line)}")


if __name__ == "__main__":
    app()
