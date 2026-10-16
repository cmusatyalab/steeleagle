import pytest

from app import daemon_registry, daemon_config
from app.daemon_backend import DaemonError, DaemonUnreachable, ServiceRef
from app.mock_daemon import MockDaemonBackend

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
    await mock.restart_services([HARPY, ServiceRef("gcs", "extra")])
    assert mock.events == [("restart", [HARPY, ServiceRef("gcs", "extra")])]
    with pytest.raises(DaemonError, match="no engine named 'harpy'"):
        await mock.restart_services([ServiceRef("harpy", "engine")])


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
