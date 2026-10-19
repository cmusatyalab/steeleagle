import grpc
import pytest
from steeleagle_protocol.v1.services.daemon import daemon_pb2

from google.protobuf.duration_pb2 import Duration

from app.daemon_backend import (
    DaemonError,
    DaemonUnreachable,
    NotSupported,
    ServiceRef,
    ServiceState,
)
from app.grpc_daemon_backend import GrpcDaemonBackend


async def test_get_configuration_decodes_the_toml_bytes(daemon_server_factory):
    _servicer, address = await daemon_server_factory(
        {
            "GetConfiguration": daemon_pb2.GetConfigurationResponse(
                config_toml='hostname = "é"\n'.encode()
            )
        }
    )

    async with GrpcDaemonBackend(address) as backend:
        assert await backend.get_configuration() == 'hostname = "é"\n'


async def test_get_configuration_that_is_not_utf8_is_a_daemon_error(
    daemon_server_factory,
):
    _servicer, address = await daemon_server_factory(
        {"GetConfiguration": daemon_pb2.GetConfigurationResponse(config_toml=b"\xff")}
    )

    async with GrpcDaemonBackend(address) as backend:
        with pytest.raises(DaemonError, match="UTF-8"):
            await backend.get_configuration()


async def test_configure_reset_and_restart_send_requests(daemon_server_factory):
    servicer, address = await daemon_server_factory(
        {
            "Configure": daemon_pb2.ConfigureResponse(),
            "ResetConfiguration": daemon_pb2.ResetConfigurationResponse(),
            "RestartServices": daemon_pb2.RestartServicesResponse(),
        }
    )

    async with GrpcDaemonBackend(address) as backend:
        await backend.configure('hostname = "x"\n')
        await backend.reset_configuration()
        await backend.restart_services(
            [ServiceRef("harpy", "vehicle"), ServiceRef("detector", "engine")]
        )

    assert servicer.received["Configure"][0].config_toml == 'hostname = "x"\n'
    assert servicer.time_remaining["Configure"] > 500
    assert len(servicer.received["ResetConfiguration"]) == 1
    restarted = [
        (s.name, s.category) for s in servicer.received["RestartServices"][0].services
    ]
    assert restarted == [
        ("harpy", daemon_pb2.SERVICE_CATEGORY_VEHICLE),
        ("detector", daemon_pb2.SERVICE_CATEGORY_ENGINE),
    ]
    assert servicer.time_remaining["RestartServices"] > 30


@pytest.mark.parametrize(
    ("outcome", "error", "match"),
    [
        (Exception("daemon down"), DaemonUnreachable, "daemon down"),
        ((grpc.StatusCode.UNIMPLEMENTED, "nope"), NotSupported, "GetConfiguration"),
        (
            (grpc.StatusCode.FAILED_PRECONDITION, "busy installing"),
            DaemonError,
            "busy installing",
        ),
    ],
)
async def test_grpc_status_codes_map_to_backend_failures(
    daemon_server_factory,
    outcome,
    error,
    match,
):
    _servicer, address = await daemon_server_factory({"GetConfiguration": outcome})

    async with GrpcDaemonBackend(address) as backend:
        with pytest.raises(error, match=match):
            await backend.get_configuration()


async def test_connection_refused_is_unreachable():
    async with GrpcDaemonBackend("127.0.0.1:1", timeout=2.0) as backend:
        with pytest.raises(DaemonUnreachable):
            await backend.get_configuration()


async def test_logs_are_not_supported_without_a_call():
    async with GrpcDaemonBackend("127.0.0.1:1") as backend:
        with pytest.raises(NotSupported, match="ListLogSources"):
            await backend.list_log_sources()
        with pytest.raises(NotSupported, match="StreamLogs"):
            [r async for r in backend.stream_logs([], 5, False, {})]


async def test_get_plugin_tomls_returns_the_map(daemon_server_factory):
    _servicer, address = await daemon_server_factory(
        {
            "GetConfiguration": daemon_pb2.GetConfigurationResponse(
                config_toml=b"",
                plugin_tomls={"harpy": b"[driver]\n", "bad": b"\xff"},
            )
        }
    )

    async with GrpcDaemonBackend(address) as backend:
        assert await backend.get_plugin_tomls() == {
            "harpy": b"[driver]\n",
            "bad": b"\xff",
        }


async def test_list_services_maps_category_run_state_and_uptime(
    daemon_server_factory,
):
    _servicer, address = await daemon_server_factory(
        {
            "ListServices": daemon_pb2.ListServicesResponse(
                services=[
                    daemon_pb2.ActiveService(
                        name="harpy",
                        category=daemon_pb2.SERVICE_CATEGORY_VEHICLE,
                        running=True,
                        uptime=Duration(seconds=90, nanos=500_000_000),
                    ),
                    daemon_pb2.ActiveService(
                        name="detector",
                        category=daemon_pb2.SERVICE_CATEGORY_ENGINE,
                        running=False,
                    ),
                    daemon_pb2.ActiveService(
                        name="gcs",
                        category=daemon_pb2.SERVICE_CATEGORY_COMMANDER,
                        running=True,
                    ),
                    daemon_pb2.ActiveService(
                        name="db",
                        category=daemon_pb2.SERVICE_CATEGORY_DATABASE,
                        running=True,
                    ),
                    # A category this GCS doesn't know is left out.
                    daemon_pb2.ActiveService(name="odd", running=True),
                ]
            )
        }
    )

    async with GrpcDaemonBackend(address) as backend:
        assert await backend.list_services() == [
            ServiceState("harpy", "vehicle", running=True, uptime_s=90.5),
            ServiceState("detector", "engine", running=False, uptime_s=None),
            ServiceState("gcs", "commander", running=True, uptime_s=None),
            ServiceState("db", "database", running=True, uptime_s=None),
        ]
