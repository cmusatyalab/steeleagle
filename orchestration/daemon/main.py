"""
daemon/main.py

The orchestrator daemon. Exposes a local HTTP API over localhost that the
CLI (and optionally a web UI) uses to manage services.

Start with:
    uv run uvicorn daemon.main:app --port 8765 --host 127.0.0.1

Or via the CLI:
    uv run steele daemon
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import git
import toml
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from rich.logging import RichHandler

from .container_manager import ContainerManager
from .process_manager import ProcessManager
from .process_pool import ProcessPool

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("rich")

# ---------------------------------------------------------------------------
# Service registry
#
# Add / remove entries here to manage more services. Both manager types
# expose: start(), stop(), status(), get_logs(tail), subscribe(), unsubscribe()
# ---------------------------------------------------------------------------

GCS_EXECUTABLE = (
    Path("/home/teiszler/steeleagle") / "gcs" / "react" / "backend" / "main.py"
)

CONFIGS: dict[str, Path] = {
    "gcs": Path("~/.steeleagle/gcs.toml").expanduser(),
    "backend": Path("~/.steeleagle/.env").expanduser(),
    "vehicles": Path("~/.steeleagle/vehicles.toml").expanduser(),
    "simulator": Path("~/.steeleagle/aviary.toml").expanduser(),
}

SERVICES: dict[str, ProcessManager | ContainerManager | ProcessPool] = {
    "gcs": ProcessManager(
        name="gcs",
        command=[
            "uv",
            "run",
            "--directory",
            "/home/teiszler/steeleagle/gcs/react/backend",
            "main.py",
        ],
        # command="[sys.executable, str(GCS_EXECUTABLE)]",
    ),
    "redis": ContainerManager(
        name="redis",
        image="redis:7-alpine",
        ports={"6379/tcp": 6379},
    ),
    "gabriel-server": ContainerManager(
        name="gabriel-server",
        image="cmusatyalab/gabriel-server:latest",
        environment={"POSTGRES_PASSWORD": "secret"},
        ports={"9099/tcp": 9099, "5000/tcp": 5000},
    ),
}


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Graceful shutdown: stop all process-based services.
    for svc in SERVICES.values():
        if isinstance(svc, ProcessManager):
            await svc.stop()
        elif isinstance(svc, ProcessPool):
            await svc.stop_all()


app = FastAPI(
    title="SteelEagle Orchestrator Daemon",
    description="Manages local uv processes and Docker containers for SteelEagle.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(name: str) -> ProcessManager | ContainerManager:
    svc = SERVICES.get(name)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"Unknown service: '{name}'")
    return svc


def _require_single(name: str) -> ProcessManager | ContainerManager:
    svc = _get(name)
    if isinstance(svc, ProcessPool):
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' is a pool — use /services/{name}/instances/... routes.",
        )
    return svc


def _require_pool(name: str) -> ProcessPool:
    svc = _get(name)
    if not isinstance(svc, ProcessPool):
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' is not a pool — use /services/{name}/start.",
        )
    return svc


async def _call(svc: ProcessManager | ContainerManager, method: str, **kwargs):
    """Calls start()/stop() handling the fact that ProcessManager is async."""
    fn = getattr(svc, method)
    if asyncio.iscoroutinefunction(fn):
        return await fn(**kwargs)
    # ContainerManager methods are synchronous — run in thread pool so we
    # don't block the event loop during Docker API calls.
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(**kwargs))


def _get_repo() -> git.Repo:
    local_dir = "~/roost"
    exists = Path(local_dir).expanduser().exists()
    if not exists:
        repo_url = "https://git.cmusatyalab.org/steeleagle/roost"
        repo = git.Repo.clone_from(repo_url, local_dir)
    else:
        repo = git.Repo(local_dir)
    return repo


async def _execute_async_subprocess(command: list[str]):
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,  # merge stderr → stdout
    )
    output, _ = await proc.communicate()
    return proc.returncode, output


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/services", summary="List all registered services")
def list_services():
    return {
        "services": [
            {
                "name": name,
                "type": type(svc).__name__,
                "command_or_image": svc.command
                if type(svc) is ProcessManager
                else svc.image,
            }
            for name, svc in SERVICES.items()
        ]
    }


@app.post("/services/{name}/start", summary="Start a service")
async def start_service(name: str):
    svc = _get(name)
    result = await _call(svc, "start")
    return {"service": name, **result}


@app.post("/services/{name}/stop", summary="Stop a service")
async def stop_service(name: str):
    svc = _get(name)
    result = await _call(svc, "stop")
    return {"service": name, **result}


@app.get("/services/{name}/status", summary="Get service status")
async def service_status(name: str):
    svc = _get(name)
    result = await _call(svc, "status")
    return {"service": name, **result}


@app.get("/services/{name}/logs", summary="Get or stream service logs")
async def service_logs(name: str, tail: int = 100, stream: bool = False):
    """
    Without `?stream=true` returns the last `tail` lines as JSON.
    With `?stream=true` opens a Server-Sent Events stream that pushes new
    lines in real time until the client disconnects.
    """
    svc = _get(name)

    if not stream:
        # Snapshot — works the same for both manager types.
        if isinstance(svc, ProcessManager):
            lines = svc.get_logs(tail=tail)
        else:
            loop = asyncio.get_running_loop()
            lines = await loop.run_in_executor(None, lambda: svc.get_logs(tail=tail))
        return {"service": name, "logs": lines}

    # ---- SSE streaming ----
    async def event_stream() -> AsyncIterator[str]:
        # First, replay the existing buffer so the client isn't starting blind.
        if isinstance(svc, ProcessManager):
            initial = svc.get_logs(tail=tail)
        else:
            loop = asyncio.get_running_loop()
            initial = await loop.run_in_executor(None, lambda: svc.get_logs(tail=tail))

        for line in initial:
            yield f"data: {line}\n\n"

        # Then subscribe for live lines.
        q = svc.subscribe()
        try:
            while True:
                try:
                    line = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {line}\n\n"
                except TimeoutError:
                    # Send a keep-alive comment so the connection stays open.
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            svc.unsubscribe(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/drivers", summary="List all available drivers")
async def list_drivers():
    repo = _get_repo()
    tree = repo.head.commit.tree
    drivers = []
    for entry in tree["drivers"]:
        if entry.type == "tree":
            with open(entry["pyproject.toml"].abspath) as file:
                cfg = toml.load(file)
                desc = cfg["project"]["description"]
                returncode, output = await _execute_async_subprocess(
                    ["uv", "sync", "--directory", entry.abspath, "--check"]
                )
                drivers.append(
                    {
                        "name": entry.name,
                        "desc": desc,
                        "status": "installed"
                        if returncode == 0
                        else "uninstalled/outdated",
                    }
                )
    return {"drivers": drivers}


@app.post("/drivers/{name}/install", summary="Install a driver from roost")
async def install_driver(name: str):
    repo = _get_repo()
    tree = repo.head.commit.tree
    try:
        target = tree["drivers"] / name
        if target.type != "tree":
            raise HTTPException(status_code=404, detail=f"Unknown driver: '{name}'")
    except KeyError as k:
        raise HTTPException(status_code=404, detail=f"Unknown driver: '{name}'") from k
    dir = tree["drivers"][name].abspath
    returncode, output = await _execute_async_subprocess(
        ["uv", "sync", "--directory", dir]
    )
    return {
        "driver": name,
        "result": "installed" if returncode == 0 else "installation_failed",
        "log": output,
    }


@app.get("/configs", summary="List all configuration files")
def list_configs():
    return {
        "configs": [
            {
                "name": name,
                "path": path,
            }
            for name, path in CONFIGS.items()
        ]
    }


@app.post("/configs/{name}/inspect", summary="Show a config file")
def inspect_config(name: str):
    conf = CONFIGS.get(name)
    if conf is None:
        raise HTTPException(status_code=404, detail=f"Unknown config: '{name}'")
    cfg = None
    try:
        with open(conf) as file:
            cfg = toml.load(file)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"FileNotFoundError: '{conf}'"
        ) from e
    return cfg


@app.post(
    "/gcs/build",
    summary="Build the frontend React app for the GCS (if necessary, installs nvm/npm tools)",
)
async def gcs_build():
    path = Path("~/.steeleagle/gcs/react/install.sh").expanduser()
    returncode, output = await _execute_async_subprocess(["sh", "-x", path])
    return {
        "status": "installed" if returncode == 0 else "installation_failed",
        "log": output,
    }
