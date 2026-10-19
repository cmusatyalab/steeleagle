from steeleagle_protocol.v1.services.daemon import daemon_pb2

from app import daemon_registry
from app.flow_routes import get_catalog
from app.plugin_toml import TELEMETRY_TYPE

MOCK = "mock://lab-a"
SEED = daemon_registry.SEED_PATH.read_text()
RAW = "steeleagle_protocol/v1/messages/frame/RawFrame"
DETECTION = "steeleagle_protocol/v1/messages/result/DetectionResult"
GENERIC = "steeleagle_protocol/v1/messages/result/GenericResult"


def by_name(items):
    return {item.name: item for item in items}


def mock():
    return daemon_registry._mock_for(MOCK)


def without_plugin_files(monkeypatch, *names, replace=None):
    """Makes the mock serve its plugin files minus `names`, with `replace`
    ({name: bytes}) swapped in."""
    real = mock().get_plugin_tomls

    async def patched():
        tomls = {k: v for k, v in (await real()).items() if k not in names}
        return {**tomls, **(replace or {})}

    monkeypatch.setattr(mock(), "get_plugin_tomls", patched)


async def test_catalog_vehicles_come_from_plugin_files(mock_daemons):
    result = await get_catalog(MOCK)

    assert result.reachable is True and result.ok is True and result.error is None
    vehicles = by_name(result.vehicles)
    assert set(vehicles) == {"harpy", "kestrel"}
    harpy = vehicles["harpy"]
    assert (harpy.typed, harpy.problem) == (True, None)
    streams = by_name(harpy.streams)
    assert [s.name for s in harpy.streams] == [
        "telemetry",
        "frames",
        "thermal",
        "downward",
    ]
    frames = streams["frames"]
    assert (frames.kind, frames.type, frames.primary, frames.hres) == (
        "camera",
        RAW,
        True,
        1080,
    )
    assert frames.description == "Main RGB camera on gimbal"
    telemetry = streams["telemetry"]
    assert (telemetry.kind, telemetry.type, telemetry.primary, telemetry.hres) == (
        "telemetry",
        TELEMETRY_TYPE,
        False,
        None,
    )
    assert telemetry.description is None


async def test_catalog_engines_come_from_plugin_files(mock_daemons):
    engines = by_name((await get_catalog(MOCK)).engines)

    assert set(engines) == {"detector", "yolo", "telemetry"}
    yolo = engines["yolo"]
    assert (yolo.category, yolo.accepts, yolo.typed, yolo.problem) == (
        "detection",
        [RAW],
        True,
        None,
    )
    assert [e.model_dump() for e in yolo.events] == [
        {"label": "result", "type": DETECTION},
        {"label": "dropped", "type": GENERIC},
    ]
    assert engines["telemetry"].accepts == [TELEMETRY_TYPE, RAW]


async def test_catalog_leaves_out_monitors_commanders_and_extras(mock_daemons):
    result = await get_catalog(MOCK)
    names = {i.name for i in result.vehicles} | {i.name for i in result.engines}
    assert not names & {"battery-watch", "gcs", "swarm-controller"}


async def test_service_without_plugin_file_falls_back(mock_daemons, monkeypatch):
    without_plugin_files(monkeypatch, "kestrel", "detector")

    result = await get_catalog(MOCK)

    kestrel = by_name(result.vehicles)["kestrel"]
    assert (kestrel.typed, kestrel.problem) == (False, "no plugin file")
    assert [(s.name, s.type) for s in kestrel.streams] == [
        ("telemetry", TELEMETRY_TYPE)
    ]
    detector = by_name(result.engines)["detector"]
    assert (detector.typed, detector.problem, detector.accepts) == (
        False,
        "no plugin file",
        ["*"],
    )
    assert [e.model_dump() for e in detector.events] == [
        {"label": "result", "type": None}
    ]


async def test_unparseable_plugin_file_is_that_services_problem(
    mock_daemons, monkeypatch
):
    without_plugin_files(monkeypatch, replace={"yolo": b"[engine\n"})

    engines = by_name((await get_catalog(MOCK)).engines)

    assert engines["yolo"].typed is False and "TOML" in engines["yolo"].problem
    assert engines["detector"].typed is True


async def test_dropped_entries_are_reported_but_stay_typed(mock_daemons, monkeypatch):
    without_plugin_files(
        monkeypatch,
        replace={
            "harpy": b'[driver]\n[[driver.cameras]]\nname = "rgb"\n'
            + f'[[driver.cameras]]\nname = "ir"\ntype = "{RAW}"\n'.encode()
        },
    )

    harpy = by_name((await get_catalog(MOCK)).vehicles)["harpy"]

    assert harpy.typed is True and '"rgb"' in harpy.problem
    assert [s.name for s in harpy.streams] == ["telemetry", "ir"]


async def test_catalog_reflects_config_edits(mock_daemons):
    mock()._config = (
        SEED
        + '\n[[engines]]\nname = "tracker"\n[engines.plugin]\nid = "t"\n'
        + '\n[[vehicles]]\nname = "osprey"\n[vehicles.plugin]\nid = "o"\n'
    )

    result = await get_catalog(MOCK)

    tracker = by_name(result.engines)["tracker"]
    assert (tracker.accepts, tracker.typed, tracker.problem) == (
        ["*"],
        False,
        "no plugin file",
    )
    osprey = by_name(result.vehicles)["osprey"]
    assert osprey.typed is False
    assert [s.name for s in osprey.streams] == ["telemetry"]


async def test_catalog_of_an_unconfigured_daemon_is_empty(mock_daemons):
    mock()._config = ""

    result = await get_catalog(MOCK)

    assert result.reachable is True and result.vehicles == [] and result.engines == []


async def test_catalog_with_mocks_disabled_is_unreachable():
    result = await get_catalog(MOCK)
    assert result.reachable is False and result.ok is False
    assert "disabled" in result.error


async def test_catalog_over_grpc_reads_plugin_tomls(daemon_server_factory):
    harpy = (daemon_registry.MOCK_PLUGINS_DIR / "harpy.plugin.toml").read_bytes()
    _servicer, address = await daemon_server_factory(
        {
            "GetConfiguration": daemon_pb2.GetConfigurationResponse(
                config_toml=(
                    b'[[vehicles]]\nname = "harpy"\n[vehicles.plugin]\nid = "p"\n'
                    b'[[engines]]\nname = "yolo"\n[engines.plugin]\nid = "y"\n'
                ),
                plugin_tomls={"harpy": harpy, "yolo": b"\xff"},
            )
        }
    )

    result = await get_catalog(address)

    assert result.reachable is True and result.ok is True
    [vehicle] = result.vehicles
    assert vehicle.typed is True
    assert [s.name for s in vehicle.streams][:2] == ["telemetry", "frames"]
    [engine] = result.engines
    assert (engine.typed, engine.problem, engine.accepts) == (
        False,
        "plugin TOML is not UTF-8",
        ["*"],
    )


async def test_wrongly_shaped_plugin_file_degrades_only_that_service(
    mock_daemons, monkeypatch
):
    without_plugin_files(
        monkeypatch,
        replace={
            "yolo": b'[engine]\ninput = "x"\n',
            "harpy": b'[driver]\ncameras = "x"\n',
        },
    )

    result = await get_catalog(MOCK)

    assert result.ok is True
    engines, vehicles = by_name(result.engines), by_name(result.vehicles)
    assert engines["yolo"].typed is False and "input" in engines["yolo"].problem
    assert engines["detector"].typed is True
    assert vehicles["harpy"].typed is False and "cameras" in vehicles["harpy"].problem
    assert vehicles["kestrel"].typed is True
