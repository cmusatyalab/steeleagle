import asyncio

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


async def test_list_log_sources_returns_response(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.ListLogSourcesResponse(
        sources=[
            eagled_pb2.LogSource(name="daemon", running=True, size_bytes=10),
            eagled_pb2.LogSource(name="alpha", running=False, size_bytes=5),
        ]
    )
    _servicer, address = await daemon_server_factory({"ListLogSources": resp})

    async with EagledClient(address) as client:
        result = await client.list_log_sources()

    assert result == resp


async def test_stream_logs_yields_records_and_sends_request(daemon_server_factory):  # noqa: F811
    records = [
        eagled_pb2.LogRecord(source="daemon", seq=4, text="four"),
        eagled_pb2.LogRecord(source="daemon", seq=5, text="five"),
    ]
    servicer, address = await daemon_server_factory({"StreamLogs": records})

    async with EagledClient(address) as client:
        got = [
            r
            async for r in client.stream_logs(
                ["daemon"], tail=5, follow=False, after_seq={"daemon": 3}
            )
        ]

    assert got == records
    sent = servicer.received["StreamLogs"][0]
    assert list(sent.sources) == ["daemon"]
    assert sent.tail == 5
    assert sent.follow is False
    assert dict(sent.after_seq) == {"daemon": 3}


async def test_stream_logs_sets_no_deadline(daemon_server_factory):  # noqa: F811
    servicer, address = await daemon_server_factory({"StreamLogs": []})

    async with EagledClient(address) as client:
        _ = [r async for r in client.stream_logs([], 0, False, {})]

    assert servicer.stream_time_remaining is None


async def test_stream_logs_cancels_upstream_when_generator_closed(
    daemon_server_factory,  # noqa: F811
):
    servicer, address = await daemon_server_factory(
        {"StreamLogs": [eagled_pb2.LogRecord(source="daemon", seq=1, text="x")]}
    )

    async with EagledClient(address) as client:
        gen = client.stream_logs([], 0, True, {})
        first = await gen.__anext__()
        assert first.seq == 1
        await gen.aclose()
        await asyncio.wait_for(servicer.stream_finished.wait(), timeout=2)


async def test_stream_logs_raises_when_daemon_unavailable(daemon_server_factory):  # noqa: F811
    _servicer, address = await daemon_server_factory({"StreamLogs": Exception("down")})

    async with EagledClient(address) as client:
        with pytest.raises(grpc.aio.AioRpcError) as excinfo:
            async for _ in client.stream_logs([], 0, False, {}):
                pass

    assert excinfo.value.code() == grpc.StatusCode.UNAVAILABLE
    assert "down" in (excinfo.value.details() or "")


async def test_install_plugin_sends_request_with_long_deadline(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.InstallPluginResponse(ok=True)
    servicer, address = await daemon_server_factory({"InstallPlugin": resp})

    async with EagledClient(address) as client:
        result = await client.install_plugin(
            name="parrot_anafi",
            repo="https://example.com/plugins.git",
            ref="abc123",
            subpath="drivers/parrot_anafi",
            category=eagled_pb2.PLUGIN_CATEGORY_DRIVER,
        )

    assert result == resp
    sent = servicer.received["InstallPlugin"][0]
    assert sent.name == "parrot_anafi"
    assert sent.repo == "https://example.com/plugins.git"
    assert sent.ref == "abc123"
    assert sent.subpath == "drivers/parrot_anafi"
    assert sent.category == eagled_pb2.PLUGIN_CATEGORY_DRIVER
    # eagled bounds install.sh at 5 minutes on top of the git fetch, so the
    # default 5s call timeout would abort a healthy install.
    assert servicer.time_remaining["InstallPlugin"] > 300
