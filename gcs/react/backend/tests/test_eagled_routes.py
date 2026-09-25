import pytest
from pydantic import ValidationError
from steeleagle_protocol.v1.services.eagled import eagled_pb2

from app.eagled_routes import (
    DaemonAddressBody,
    InstallPluginBody,
    VehicleActionResult,
    VehicleNamesBody,
    VehicleStatusModel,
    _get_status,
    _vehicle_action_response,
    get_status,
    install_plugin,
    restart_daemon,
    stop_vehicles,
)
from tests.fake_eagled import FakeEagledClient, daemon_server_factory  # noqa: F401 -- fixture


async def test_get_status_shapes_response():
    status = eagled_pb2.GetStatusResponse(
        configured=True,
        os="linux",
        arch="arm64",
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
    assert result.os == "linux"
    assert result.arch == "arm64"
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


async def test_install_plugin_route_forwards_fields_and_reports_ok(
    daemon_server_factory,  # noqa: F811
):
    servicer, address = await daemon_server_factory(
        {"InstallPlugin": eagled_pb2.InstallPluginResponse(ok=True)}
    )

    result = await install_plugin(
        InstallPluginBody(
            address=address,
            name="mission-service",
            repo="https://example.com/plugins.git",
            ref="v1.2.0",
            category="mission",
        )
    )

    assert result.reachable is True
    assert result.ok is True
    assert result.error is None
    sent = servicer.received["InstallPlugin"][0]
    assert sent.name == "mission-service"
    assert sent.ref == "v1.2.0"
    assert sent.subpath == ""
    assert sent.category == eagled_pb2.PLUGIN_CATEGORY_MISSION


async def test_install_plugin_route_reports_install_failure_with_script_output(
    daemon_server_factory,  # noqa: F811
):
    output = "install.sh failed: exit status 1\nE: could not build wheel"
    _servicer, address = await daemon_server_factory(
        {"InstallPlugin": eagled_pb2.InstallPluginResponse(ok=False, error=output)}
    )

    result = await install_plugin(
        InstallPluginBody(
            address=address, name="x", repo="r", ref="main", category="extra"
        )
    )

    # A failed install is a normal answer from a reachable daemon, and the
    # script output must survive intact for the UI to show it.
    assert result.reachable is True
    assert result.ok is False
    assert result.error == output


async def test_install_plugin_route_unreachable_daemon_is_not_an_error(
    daemon_server_factory,  # noqa: F811
):
    _servicer, address = await daemon_server_factory(
        {"InstallPlugin": Exception("daemon went away")}
    )

    result = await install_plugin(
        InstallPluginBody(
            address=address, name="x", repo="r", ref="main", category="driver"
        )
    )

    assert result.reachable is False
    assert result.ok is False
    assert "daemon went away" in result.error


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "../evil"},
        {"name": "a/b"},
        {"name": ".hidden"},
        {"name": "has space"},
        {"repo": ""},
        {"ref": ""},
        {"subpath": "../escape"},
        {"subpath": "a/../../escape"},
        {"subpath": "/abs/path"},
        {"category": "bogus"},
    ],
)
def test_install_plugin_body_rejects_unsafe_or_missing_input(overrides):
    fields = {
        "address": "127.0.0.1:9090",
        "name": "ok-name_1.0",
        "repo": "https://example.com/plugins.git",
        "ref": "main",
        "subpath": "drivers/x",
        "category": "driver",
    }
    with pytest.raises(ValidationError):
        InstallPluginBody(**{**fields, **overrides})


def test_install_plugin_body_accepts_typical_input():
    body = InstallPluginBody(
        address="127.0.0.1:9090",
        name="parrot_anafi",
        repo="https://example.com/plugins.git",
        ref="0123456789abcdef",
        subpath="drivers/parrot_anafi",
        category="driver",
    )
    assert body.subpath == "drivers/parrot_anafi"
    assert (
        InstallPluginBody(
            address="a:1", name="n", repo="r", ref="main", category="extra"
        ).subpath
        == ""
    )
