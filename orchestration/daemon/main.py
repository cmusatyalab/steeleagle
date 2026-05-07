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
from .docker_compose_manager import DockerComposeManager
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

CONFIGS: dict[str, Path] = {
    "gcs": Path("~/.steeleagle/gcs.toml").expanduser(),
    "backend": Path("~/.steeleagle/.env").expanduser(),
    "vehicles": Path("~/.steeleagle/vehicles.toml").expanduser(),
    "simulator": Path("~/.steeleagle/aviary.toml").expanduser(),
}

MAIN_REPO_PATH = Path("~/steeleagle").expanduser()
ROOST_REPO_PATH = Path("~/roost").expanduser()

SERVICES: dict[
    str, ProcessManager | ContainerManager | ProcessPool | DockerComposeManager
] = {
    "gcs": ProcessManager(
        name="gcs",
        command=[
            "uv",
            "run",
            "--directory",
            str(MAIN_REPO_PATH / "gcs" / "react" / "backend"),
            "main.py",
        ],
    ),
    "sim": ProcessManager(
        name="sim",
        command=[
            "uv",
            "run",
            "--directory",
            str(ROOST_REPO_PATH / "aviary" / "src" / "steeleagle_aviary"),
            "simulator.py",
        ],
    ),
    "backend": DockerComposeManager(
        name="backend",
        compose_files=[
            Path("~/steeleagle/backend/server/docker-compose.yml").expanduser()
        ],
        environment=[Path("~/steeleagle/backend/server/.env").expanduser()],
    ),
    "vehicle": ProcessPool(
        name="vehicle",
        command=[
            "uv",
            "run",
            "--directory",
            str(MAIN_REPO_PATH / "vehicle"),
            "launch.py",
        ],
    ),
}


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # check if ~/.steeleagle conf dir exists, and create it
    logger.info("Checking for .steeleagle conf dir (and optionally creating)...")
    Path("~/.steeleagle").expanduser().mkdir(exist_ok=True)
    logger.info("Waiting for API calls from CLI...")
    yield
    # Graceful shutdown: stop all services.
    logger.info("Stopping services...")
    for svc in SERVICES.values():
        logger.info(f"Stopping '{svc.name}'...")
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


def _get(
    name: str,
) -> ProcessManager | ContainerManager | ProcessPool | DockerComposeManager:
    svc = SERVICES.get(name)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"Unknown service: '{name}'")
    return svc


def _require_single(
    name: str,
) -> ProcessManager | ContainerManager | DockerComposeManager:
    svc = _get(name)
    if isinstance(svc, ProcessPool):
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' is not a ProcessManager/ContainerManager.",
        )
    return svc


def _require_pool(name: str) -> ProcessPool:
    svc = _get(name)
    if not isinstance(svc, ProcessPool):
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' is not a ProcessPool.",
        )
    return svc


async def _call(svc: ProcessManager | ContainerManager, method: str, **kwargs):
    fn = getattr(svc, method)
    if asyncio.iscoroutinefunction(fn):
        return await fn(**kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(**kwargs))


async def _log_stream(
    get_logs,  # callable() → list[str]
    subscribe,  # callable() → asyncio.Queue
    unsubscribe,  # callable(q) → None
    tail: int,
) -> AsyncIterator[str]:
    for line in get_logs(tail):
        yield f"data: {line}\n\n"
    q = subscribe()
    try:
        while True:
            try:
                line = await asyncio.wait_for(q.get(), timeout=15.0)
                yield f"data: {line}"
            except TimeoutError:
                yield ": keep-alive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        unsubscribe(q)


def _get_repo() -> git.Repo:
    roost_dir = "~/roost"
    exists = Path(roost_dir).expanduser().exists()
    if not exists:
        repo_url = "https://git.cmusatyalab.org/steeleagle/roost"
        repo = git.Repo.clone_from(repo_url, roost_dir)
    else:
        repo = git.Repo(roost_dir)
    return repo


async def _execute_async_subprocess(command: list[str] | str, use_shell: bool = False):
    """If use_shell is True, create_subprocess_shell is used and command should be a str."""
    """If use_shell is False (the default), create_subprocess_exec is used and command should be list[str]."""
    if use_shell:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # merge stderr → stdout
        )
    else:
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
                "entrypoint": svc.entrypoint(),
            }
            for name, svc in SERVICES.items()
        ]
    }


@app.post("/services/{name}/start", summary="Start a service")
async def start_service(name: str):
    svc = _require_single(name)
    return {"service": name, **await _call(svc, "start")}


@app.post("/services/{name}/stop", summary="Stop a service")
async def stop_service(name: str):
    svc = _require_single(name)
    return {"service": name, **await _call(svc, "stop")}


@app.get("/services/{name}/status", summary="Get service status")
async def service_status(name: str):
    svc = _require_single(name)
    return {"service": name, **await _call(svc, "status")}


@app.get("/services/{name}/logs", summary="Get or stream service logs")
async def service_logs(name: str, tail: int = 100, stream: bool = False):
    svc = _require_single(name)
    if not stream:
        if isinstance(svc, ProcessManager):
            lines = svc.get_logs(tail=tail)
        else:
            loop = asyncio.get_running_loop()
            lines = await loop.run_in_executor(None, lambda: svc.get_logs(tail=tail))
        return {"service": name, "logs": lines}

    return StreamingResponse(
        _log_stream(
            get_logs=lambda t: svc.get_logs(tail=t)
            if isinstance(svc, ProcessManager)
            else svc.get_logs(tail=t),
            subscribe=svc.subscribe,
            unsubscribe=svc.unsubscribe,
            tail=tail,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# ProcessPool routes
# ---------------------------------------------------------------------------


@app.get("/services/{name}/pool")
def list_instances(name: str):
    pool = _require_pool(name)
    return {"service": name, "instances": pool.list_instances()}


@app.post("/services/{name}/pool")
async def start_instance(name: str, label: str | None = None):
    pool = _require_pool(name)
    result = await pool.start_instance(label=label)
    return {"service": name, **result}


@app.post("/services/{name}/pool/{instance_id}/stop")
async def stop_instance(name: str, instance_id: str):
    pool = _require_pool(name)
    try:
        result = await pool.stop_instance(instance_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"service": name, **result}


@app.get("/services/{name}/pool/{instance_id}/status")
def instance_status(name: str, instance_id: str):
    pool = _require_pool(name)
    try:
        return {"service": name, **pool.instance_status(instance_id)}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/services/{name}/pool/{instance_id}/logs")
async def instance_logs(
    name: str, instance_id: str, tail: int = 100, stream: bool = False
):
    pool = _require_pool(name)
    try:
        if not stream:
            return {
                "service": name,
                "instance_id": instance_id,
                "logs": pool.get_logs(instance_id, tail=tail),
            }
        return StreamingResponse(
            _log_stream(
                get_logs=lambda t: pool.get_logs(instance_id, tail=t),
                subscribe=lambda: pool.subscribe(instance_id),
                unsubscribe=lambda q: pool.unsubscribe(instance_id, q),
                tail=tail,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


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
    summary="Build the frontend React app for the GCS using npm",
)
async def gcs_build():
    path = Path(" ~/steeleagle/gcs/react/prime").expanduser()
    returncode, output = await _execute_async_subprocess(
        ["npm", "run", "build", "--prefix", path]
    )
    return {
        "status": "build_successful" if returncode == 0 else "build_failed",
        "log": output,
    }


@app.post(
    "/gcs/install",
    summary="Installs required nvm/npm tools for building React GCS",
)
async def gcs_install():
    returncode, output = await _execute_async_subprocess(
        "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash",
        use_shell=True,
    )
    return {
        "status": "installed" if returncode == 0 else "installation_failed",
        "log": output,
    }


@app.get(
    "/backend/list",
    summary="List the services in the Docker Compose YAML file.",
)
async def backend_list():
    svc = _require_single("backend")
    return {**await _call(svc, "list")}
