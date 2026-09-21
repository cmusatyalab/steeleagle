"""FastAPI routes proxying the subset of eagled's DaemonService that
needs no new input UI -- see
docs/superpowers/specs/2026-09-18-orchestration-eagled-wiring-design.md.
Configure and InstallPlugin are deliberately not here (need a TOML
config editor / plugin repo+ref form that doesn't exist yet), and there
is no logs RPC on DaemonService at all to wire up.

Every route always returns HTTP 200; `reachable` on the response is how
the frontend tells an unreachable daemon (expected, ordinary state for
this UI) from a real error, rather than the route raising
HTTPException."""

import grpc
from fastapi import APIRouter
from pydantic import BaseModel
from steeleagle_protocol.v1.services.eagled import eagled_pb2

from app.eagled_client import EagledClient

router = APIRouter(prefix="/api/daemons", tags=["daemons"])


class VehicleStatusModel(BaseModel):
    name: str
    driver: str
    running: bool
    port: int
    config_stale: bool


class DaemonConfigModel(BaseModel):
    daemon_name: str
    swarm_controller_address: str
    tailscale_hostname: str
    plugin_dir: str
    port_base: int
    vpn: bool
    vehicle_vpn: bool
    tailscale_authkey_env: str
    gabriel_server_endpoint: str


class DaemonStatusResponse(BaseModel):
    reachable: bool
    configured: bool | None = None
    config: DaemonConfigModel | None = None
    vehicles: list[VehicleStatusModel] = []
    error: str | None = None


class VehicleActionResult(BaseModel):
    name: str
    ok: bool
    error: str
    reconfigured: bool
    restart_required: bool


class VehicleActionResponse(BaseModel):
    reachable: bool
    results: list[VehicleActionResult] = []
    error: str | None = None


class InstalledPluginModel(BaseModel):
    name: str
    ref: str
    category: str


class PluginsResponse(BaseModel):
    reachable: bool
    plugins: list[InstalledPluginModel] = []
    error: str | None = None


class SimpleActionResponse(BaseModel):
    reachable: bool
    error: str | None = None


class VehicleNamesBody(BaseModel):
    address: str
    names: list[str]


class DaemonAddressBody(BaseModel):
    address: str


def _category_name(category: int) -> str:
    """PLUGIN_CATEGORY_DRIVER -> "DRIVER". Falls back to a raw numeric
    label rather than raising if a daemon reports a category value this
    proto doesn't know about (e.g. a newer proto with more categories)
    -- this route must never 500 on daemon-supplied data."""
    try:
        return eagled_pb2.PluginCategory.Name(category).removeprefix("PLUGIN_CATEGORY_")
    except ValueError:
        return f"UNKNOWN_{category}"


def _daemon_config_model(config: eagled_pb2.DaemonConfig) -> DaemonConfigModel:
    return DaemonConfigModel(
        daemon_name=config.daemon_name,
        swarm_controller_address=config.swarm_controller_address,
        tailscale_hostname=config.tailscale_hostname,
        plugin_dir=config.plugin_dir,
        port_base=config.port_base,
        vpn=config.vpn,
        vehicle_vpn=config.vehicle_vpn,
        tailscale_authkey_env=config.tailscale_authkey_env,
        gabriel_server_endpoint=config.gabriel_server_endpoint,
    )


async def _get_status(client: EagledClient) -> DaemonStatusResponse:
    resp = await client.get_status()
    return DaemonStatusResponse(
        reachable=True,
        configured=resp.configured,
        config=_daemon_config_model(resp.config),
        vehicles=[
            VehicleStatusModel(
                name=v.name,
                driver=v.driver,
                running=v.running,
                port=v.port,
                config_stale=v.config_stale,
            )
            for v in resp.vehicles
        ],
    )


@router.get("/status")
async def get_status(address: str) -> DaemonStatusResponse:
    try:
        async with EagledClient(address) as client:
            return await _get_status(client)
    except grpc.aio.AioRpcError as e:
        return DaemonStatusResponse(reachable=False, error=e.details() or e.code().name)


def _vehicle_action_response(resp) -> VehicleActionResponse:
    return VehicleActionResponse(
        reachable=True,
        results=[
            VehicleActionResult(
                name=r.name,
                ok=r.ok,
                error=r.error,
                reconfigured=r.reconfigured,
                restart_required=r.restart_required,
            )
            for r in resp.vehicles
        ],
    )


@router.post("/stop-vehicles")
async def stop_vehicles(body: VehicleNamesBody) -> VehicleActionResponse:
    try:
        async with EagledClient(body.address) as client:
            resp = await client.stop_vehicles(body.names)
            return _vehicle_action_response(resp)
    except grpc.aio.AioRpcError as e:
        return VehicleActionResponse(
            reachable=False, error=e.details() or e.code().name
        )


@router.post("/restart-vehicles")
async def restart_vehicles(body: VehicleNamesBody) -> VehicleActionResponse:
    try:
        async with EagledClient(body.address) as client:
            resp = await client.restart_vehicles(body.names)
            return _vehicle_action_response(resp)
    except grpc.aio.AioRpcError as e:
        return VehicleActionResponse(
            reachable=False, error=e.details() or e.code().name
        )


@router.post("/forget-vehicles")
async def forget_vehicles(body: VehicleNamesBody) -> VehicleActionResponse:
    try:
        async with EagledClient(body.address) as client:
            resp = await client.forget_vehicles(body.names)
            return _vehicle_action_response(resp)
    except grpc.aio.AioRpcError as e:
        return VehicleActionResponse(
            reachable=False, error=e.details() or e.code().name
        )


@router.get("/plugins")
async def get_installed_plugins(address: str) -> PluginsResponse:
    try:
        async with EagledClient(address) as client:
            resp = await client.get_installed_plugins()
            return PluginsResponse(
                reachable=True,
                plugins=[
                    InstalledPluginModel(
                        name=p.name, ref=p.ref, category=_category_name(p.category)
                    )
                    for p in resp.plugins
                ],
            )
    except grpc.aio.AioRpcError as e:
        return PluginsResponse(reachable=False, error=e.details() or e.code().name)


@router.post("/restart-daemon")
async def restart_daemon(body: DaemonAddressBody) -> SimpleActionResponse:
    try:
        async with EagledClient(body.address) as client:
            await client.restart_daemon()
            return SimpleActionResponse(reachable=True)
    except grpc.aio.AioRpcError as e:
        return SimpleActionResponse(reachable=False, error=e.details() or e.code().name)


@router.post("/reset-config")
async def reset_config(body: DaemonAddressBody) -> SimpleActionResponse:
    try:
        async with EagledClient(body.address) as client:
            await client.reset_config()
            return SimpleActionResponse(reachable=True)
    except grpc.aio.AioRpcError as e:
        return SimpleActionResponse(reachable=False, error=e.details() or e.code().name)
