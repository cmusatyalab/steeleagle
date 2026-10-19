import pytest

from app import daemon_registry, daemon_config
from app.daemon_backend import DaemonError, DaemonUnreachable, ServiceRef, ServiceState
from app.mock_daemon import MockDaemonBackend
from app.plugin_toml import TELEMETRY_TYPE, parse_driver, parse_engine

SEED = daemon_registry.SEED_PATH.read_text()
HARPY = ServiceRef("harpy", "vehicle")


def _mock():
    return MockDaemonBackend("mock://t", SEED, configure_delay=0, follow_interval=0.01)


async def test_get_configuration_returns_the_seed():
    assert await _mock().get_configuration() == SEED


async def test_configure_replaces_the_config_whole():
    mock = _mock()
    doc = daemon_config.parse(SEED)
    form = daemon_config.to_form(doc)
    form["instances"]["vehicle"] = []
    daemon_config.apply_form(doc, form)
    text = daemon_config.dumps(doc)

    await mock.configure(text)

    assert await mock.get_configuration() == text
    assert mock.events == ["configure"]


@pytest.mark.parametrize(
    "text, match",
    [("name = \n", "invalid config"), ('[vehicles]\nname = "x"\n', "array of tables")],
)
async def test_configure_rejects_invalid_or_wrong_shape_config(text, match):
    mock = _mock()
    with pytest.raises(DaemonError, match=match):
        await mock.configure(text)
    assert await mock.get_configuration() == SEED


async def test_reset_configuration_empties_config():
    mock = _mock()
    await mock.reset_configuration()
    assert await mock.get_configuration() == ""


async def test_restart_services_checks_refs():
    mock = _mock()
    detector = ServiceRef("detector", "engine")
    await mock.restart_services([HARPY, detector])
    assert mock.events == [("restart", [HARPY, detector])]
    with pytest.raises(DaemonError, match="no engine named 'harpy'"):
        await mock.restart_services([ServiceRef("harpy", "engine")])


async def test_restart_services_refuses_what_only_configure_restarts():
    # As eagled does: commanders, simulators, databases and extras restart
    # through Configure.
    mock = _mock()
    with pytest.raises(DaemonError, match="commander gcs"):
        await mock.restart_services([HARPY, ServiceRef("gcs", "commander")])
    assert mock.events == []


async def test_corrupt_config_makes_restart_a_daemon_error():
    mock = _mock()
    mock._config = "name = \n"
    with pytest.raises(DaemonError, match="not valid TOML"):
        await mock.restart_services([HARPY])


async def test_log_sources_cover_daemon_and_instances():
    names = {s.name for s in await _mock().list_log_sources()}
    assert {
        "eagled",
        "harpy-driver",
        "harpy-mission",
        "kestrel-driver",
        "swarm-controller",
    } <= names
    assert "harpy" not in names


async def test_stream_logs_backlog_honours_tail_and_after_seq():
    mock = _mock()
    records = [r async for r in mock.stream_logs(["harpy"], 3, False, {})]
    assert [r.seq for r in records] == [3, 4, 5]
    assert all(r.source == "harpy" for r in records)

    records = [r async for r in mock.stream_logs(["harpy"], 3, False, {"harpy": 4})]
    assert [r.seq for r in records] == [5]


async def test_stream_logs_follow_keeps_producing_new_records():
    mock = _mock()
    stream = mock.stream_logs(["harpy"], 1, True, {})
    seqs = [(await stream.__anext__()).seq for _ in range(3)]
    await stream.aclose()
    assert seqs == [5, 6, 7]


async def test_open_backend_reuses_one_mock_per_address(mock_daemons):
    async with mock_daemons.open_backend("mock://lab-a") as first:
        await first.reset_configuration()
    async with mock_daemons.open_backend("mock://lab-a") as second:
        assert second is first
    async with mock_daemons.open_backend("mock://lab-b") as other:
        assert other is not first


async def test_open_backend_refuses_mocks_when_disabled():
    daemon_registry.setup(None)
    with pytest.raises(DaemonUnreachable, match="disabled"):
        async with daemon_registry.open_backend("mock://lab-a"):
            pass


RAW = "steeleagle_protocol/v1/messages/frame/RawFrame"
PLUGIN_SERVICES = {"harpy", "kestrel", "yolo", "detector", "telemetry"}


def _plugin_mock():
    return MockDaemonBackend(
        "mock://t", SEED, configure_delay=0, plugin_dir=daemon_registry.MOCK_PLUGINS_DIR
    )


async def test_get_plugin_tomls_returns_files_for_configured_services():
    tomls = await _plugin_mock().get_plugin_tomls()

    assert set(tomls) == PLUGIN_SERVICES
    assert all(isinstance(v, bytes) for v in tomls.values())


async def test_get_plugin_tomls_without_a_dir_is_empty():
    assert await _mock().get_plugin_tomls() == {}


async def test_shipped_mock_plugins_parse():
    tomls = await _plugin_mock().get_plugin_tomls()

    drivers = {n: parse_driver(tomls[n].decode()) for n in ("harpy", "kestrel")}
    engines = {
        n: parse_engine(tomls[n].decode()) for n in ("yolo", "detector", "telemetry")
    }
    assert all(d.problems == [] for d in drivers.values())
    assert all(e.problems == [] for e in engines.values())
    assert [s.name for s in drivers["harpy"].streams] == [
        "telemetry",
        "frames",
        "thermal",
        "downward",
    ]
    assert engines["telemetry"].accepts == [TELEMETRY_TYPE, RAW]


async def test_plugin_tomls_follow_config_edits():
    mock = _plugin_mock()
    doc = daemon_config.parse(SEED)
    form = daemon_config.to_form(doc)
    form["instances"]["vehicle"] = [
        s for s in form["instances"]["vehicle"] if s["name"] != "harpy"
    ]
    daemon_config.apply_form(doc, form)

    await mock.configure(daemon_config.dumps(doc))

    assert "harpy" not in await mock.get_plugin_tomls()


class Clock:
    def __init__(self, now: float = 100.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def _uptimes(states: list[ServiceState]) -> dict[str, float | None]:
    return {s.name: s.uptime_s for s in states}


async def test_list_services_reports_every_configured_service_running():
    clock = Clock()
    mock = MockDaemonBackend("mock://t", SEED, configure_delay=0, clock=clock)
    clock.now = 130.0

    states = await mock.list_services()

    assert {(s.name, s.category) for s in states} == {
        (ref.name, ref.category) for ref in mock._refs()
    }
    assert all(s.running for s in states)
    assert set(_uptimes(states).values()) == {30.0}


async def test_restart_and_configure_reset_service_uptime():
    clock = Clock()
    mock = MockDaemonBackend("mock://t", SEED, configure_delay=0, clock=clock)
    clock.now = 130.0
    await mock.restart_services([HARPY])
    clock.now = 140.0

    uptimes = _uptimes(await mock.list_services())
    assert uptimes["harpy"] == 10.0 and uptimes["kestrel"] == 40.0

    await mock.configure(SEED)
    clock.now = 145.0
    assert set(_uptimes(await mock.list_services()).values()) == {5.0}


async def test_list_services_after_reset_is_empty():
    mock = _mock()
    await mock.reset_configuration()

    assert await mock.list_services() == []
