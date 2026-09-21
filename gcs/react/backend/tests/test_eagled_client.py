import grpc
import pytest
from steeleagle_protocol.v1.services.eagled import eagled_pb2

from app.eagled_client import EagledClient
from tests.fake_eagled import daemon_server_factory  # noqa: F401 -- used as a pytest fixture


async def test_get_status_returns_response(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.GetStatusResponse(
        configured=True,
        config=eagled_pb2.DaemonConfig(daemon_name="host-a"),
        vehicles=[
            eagled_pb2.VehicleStatus(
                name="alpha", driver="parrot_anafi", running=True, port=9091
            )
        ],
    )
    _servicer, address = await daemon_server_factory({"GetStatus": resp})

    async with EagledClient(address) as client:
        result = await client.get_status()

    assert result == resp


async def test_stop_vehicles_sends_names(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.StopVehiclesResponse(
        vehicles=[eagled_pb2.VehicleResult(name="alpha", ok=True)]
    )
    servicer, address = await daemon_server_factory({"StopVehicles": resp})

    async with EagledClient(address) as client:
        result = await client.stop_vehicles(["alpha", "bravo"])

    assert result == resp
    sent = servicer.received["StopVehicles"][0]
    assert list(sent.names) == ["alpha", "bravo"]


async def test_restart_vehicles_sends_names(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.RestartVehiclesResponse(
        vehicles=[eagled_pb2.VehicleResult(name="alpha", ok=True)]
    )
    servicer, address = await daemon_server_factory({"RestartVehicles": resp})

    async with EagledClient(address) as client:
        await client.restart_vehicles(["alpha"])

    assert list(servicer.received["RestartVehicles"][0].names) == ["alpha"]


async def test_forget_vehicles_sends_names(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.ForgetVehiclesResponse(
        vehicles=[eagled_pb2.VehicleResult(name="alpha", ok=True)]
    )
    servicer, address = await daemon_server_factory({"ForgetVehicles": resp})

    async with EagledClient(address) as client:
        await client.forget_vehicles(["alpha"])

    assert list(servicer.received["ForgetVehicles"][0].names) == ["alpha"]


async def test_get_installed_plugins(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.GetInstalledPluginsResponse(
        plugins=[
            eagled_pb2.InstalledPlugin(
                name="parrot_anafi",
                ref="v1.0.0",
                category=eagled_pb2.PLUGIN_CATEGORY_DRIVER,
            )
        ]
    )
    _servicer, address = await daemon_server_factory({"GetInstalledPlugins": resp})

    async with EagledClient(address) as client:
        result = await client.get_installed_plugins()

    assert result == resp


async def test_restart_daemon(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.RestartDaemonResponse()
    _servicer, address = await daemon_server_factory({"RestartDaemon": resp})

    async with EagledClient(address) as client:
        result = await client.restart_daemon()

    assert result == resp


async def test_reset_config(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.ResetConfigResponse()
    _servicer, address = await daemon_server_factory({"ResetConfig": resp})

    async with EagledClient(address) as client:
        result = await client.reset_config()

    assert result == resp


async def test_get_status_channel_failure_raises_aio_rpc_error(daemon_server_factory):  # noqa: F811
    _servicer, address = await daemon_server_factory(
        {"GetStatus": RuntimeError("daemon down")}
    )

    async with EagledClient(address) as client:
        with pytest.raises(grpc.aio.AioRpcError):
            await client.get_status()
