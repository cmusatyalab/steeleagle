"""
daemon/config.py

Pydantic schema for orchestrator.yaml.
Loader that turns the validated config into a service registry.

Supported service types and their YAML keys:

  process:
    managed: bool               # required (determines whether or not the daemon should manage this)
    command: list[str]          # required

  pool:
    managed: bool               # required (determines whether or not the daemon should manage this)
    command: list[str]          # required

  container:
    managed: bool               # required (determines whether or not the daemon should manage this)
    image:   str                # required
    ports:   dict[str, int]     # optional  e.g. {"6379/tcp": 6379}
    environment: dict[str, str] # optional
    volumes: dict[str, str]     # optional  e.g. {"./data": "/data"}

  compose:
    managed: bool               # required (determines whether or not the daemon should manage this)
    compose_files: list[str]    # required
    environment: list[str]      # optional
"""

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field

from .container_manager import ContainerManager
from .docker_compose_manager import DockerComposeManager
from .process_manager import ProcessManager
from .process_pool import ProcessPool


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class ServiceConfig(BaseModel):
    managed: bool


class ProcessServiceConfig(ServiceConfig):
    type: Literal["process"]
    command: list[str]


class PoolServiceConfig(ServiceConfig):
    type: Literal["pool"]
    command: list[str]


class ContainerServiceConfig(ServiceConfig):
    type: Literal["container"]
    image: str
    ports: dict[str, int] = {}
    environment: dict[str, str] = {}
    volumes: dict[str, str] = {}


class DockerComposeServiceConfig(ServiceConfig):
    type: Literal["compose"]
    compose_files: list[str]
    environment: list[str] = []


# Discriminated union — Pydantic routes on the "type" field automatically.
AnyServiceConfig = Annotated[
    ProcessServiceConfig
    | PoolServiceConfig
    | ContainerServiceConfig
    | DockerComposeServiceConfig,
    Field(discriminator="type"),
]


class OrchestratorConfig(BaseModel):
    roost: str = "~/roost"
    steeleagle: str = "~/steeleagle"
    services: dict[str, AnyServiceConfig] = {}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

ServiceRegistry = dict[
    str, ProcessManager | ProcessPool | ContainerManager | DockerComposeManager
]


def load_config(path: Path) -> OrchestratorConfig:
    """Parse and validate the YAML config file"""
    if not path.exists():
        raise FileNotFoundError
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}

    # Validate the configuration
    return OrchestratorConfig.model_validate(raw)


def build_registry(config: OrchestratorConfig) -> ServiceRegistry:
    """Instantiate manager objects from a validated config."""
    registry: ServiceRegistry = {}

    for name, svc in config.services.items():
        if svc.managed:
            if isinstance(svc, ProcessServiceConfig):
                registry[name] = ProcessManager(
                    name=name, command=[str(Path(f).expanduser()) for f in svc.command]
                )

            elif isinstance(svc, PoolServiceConfig):
                registry[name] = ProcessPool(
                    name=name, command=[str(Path(f).expanduser()) for f in svc.command]
                )

            elif isinstance(svc, DockerComposeServiceConfig):
                registry[name] = DockerComposeManager(
                    name=name,
                    compose_files=[Path(f).expanduser() for f in svc.compose_files],
                    environment=[Path(f).expanduser() for f in svc.environment],
                )

            elif isinstance(svc, ContainerServiceConfig):
                # docker-py's containers.run() accepts volumes as
                # {host_path: {"bind": container_path, "mode": "rw"}}
                volume_binds = {
                    host: {"bind": container, "mode": "rw"}
                    for host, container in svc.volumes.items()
                }
                registry[name] = ContainerManager(
                    name=name,
                    image=svc.image,
                    ports=svc.ports or None,
                    environment=svc.environment or None,
                    volumes=volume_binds or None,
                )

    return registry


def load_services(path: Path) -> ServiceRegistry:
    config = load_config(path)
    return build_registry(config)


def get_roost_repo(path: Path) -> Path:
    config = load_config(path)
    return Path(config.roost)


def get_steeleagle_dir(path: Path) -> Path:
    config = load_config(path)
    return Path(config.steeleagle)
