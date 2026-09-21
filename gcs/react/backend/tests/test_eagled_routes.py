from steeleagle_protocol.v1.services.eagled import eagled_pb2

from app.eagled_routes import (
    DaemonAddressBody,
    VehicleActionResult,
    VehicleNamesBody,
    VehicleStatusModel,
    _get_status,
    _vehicle_action_response,
    get_status,
    restart_daemon,
    stop_vehicles,
)
from tests.fake_eagled import FakeEagledClient, daemon_server_factory  # noqa: F401 -- fixture


async def test_get_status_shapes_response():
    status = eagled_pb2.GetStatusResponse(
        configured=True,
        config=eagled_pb2.DaemonConfig(
            daemon_name="host-a", swarm_controller_address="sc:1234"
        ),
        vehicles=[
            eagled_pb2.VehicleStatus(
                name="alpha", driver="parrot_anafi", running=True, port=9091
            )
        ],
    )
    client = FakeEagledClient(status=status)

    result = await _get_status(client)

    assert result.reachable is True
    assert result.configured is True
    assert result.config.daemon_name == "host-a"
    assert result.config.swarm_controller_address == "sc:1234"
    assert result.vehicles == [
        VehicleStatusModel(
            name="alpha",
            driver="parrot_anafi",
            running=True,
            port=9091,
            config_stale=False,
        )
    ]


async def test_stop_vehicles_shapes_results_and_sends_names():
    resp = eagled_pb2.StopVehiclesResponse(
        vehicles=[eagled_pb2.VehicleResult(name="alpha", ok=True)]
    )
    client = FakeEagledClient(stop_vehicles=resp)

    result = _vehicle_action_response(await client.stop_vehicles(["alpha"]))

    assert result.reachable is True
    assert result.results == [
        VehicleActionResult(
            name="alpha", ok=True, error="", reconfigured=False, restart_required=False
        )
    ]
    assert client.stop_vehicles_calls == [["alpha"]]


async def test_get_status_route_reports_unreachable(daemon_server_factory):  # noqa: F811
    _servicer, address = await daemon_server_factory(
        {"GetStatus": RuntimeError("daemon down")}
    )

    result = await get_status(address=address)

    assert result.reachable is False
    assert result.error is not None


async def test_restart_daemon_route_reports_unreachable(daemon_server_factory):  # noqa: F811
    _servicer, address = await daemon_server_factory(
        {"RestartDaemon": RuntimeError("daemon down")}
    )

    result = await restart_daemon(DaemonAddressBody(address=address))

    assert result.reachable is False


async def test_stop_vehicles_route_success(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.StopVehiclesResponse(
        vehicles=[eagled_pb2.VehicleResult(name="alpha", ok=True)]
    )
    servicer, address = await daemon_server_factory({"StopVehicles": resp})

    result = await stop_vehicles(VehicleNamesBody(address=address, names=["alpha"]))

    assert result.reachable is True
    assert result.results[0].name == "alpha"
    assert list(servicer.received["StopVehicles"][0].names) == ["alpha"]
