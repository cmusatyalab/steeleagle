import httpx
import pytest
from fastapi import FastAPI
from steeleagle_protocol.v1.services.eagled import eagled_pb2

from app import daemon_backends, daemon_config, eagled_routes
from app.eagled_routes import (
    DaemonAddressBody,
    PutConfigBody,
    RestartBody,
    _discovered_daemons_from_status,
    get_config,
    get_discovered_daemons,
    get_plugins,
    get_status,
    put_config,
    reset_config,
    restart_plugins,
)

MOCK = "mock://lab-a"
SEED = daemon_backends.SEED_PATH.read_text()


def asgi_client() -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(eagled_routes.router)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def mock() -> "daemon_backends.MockDaemonBackend":
    return daemon_backends._mock_for(MOCK)


async def loaded():
    """GET /config as a plain dict, the way the frontend sees it."""
    return (await get_config(MOCK)).model_dump()


def section(name="tracker", plugin_id="tracker_engine", **plugin):
    return {
        "name": name,
        "plugin": {
            "id": plugin_id,
            "runtime": "process",
            "source": None,
            "args": {},
            "extra": {},
            **plugin,
        },
        "instance_fields": {},
    }


# --- status / plugins ------------------------------------------------------


async def test_status_reports_settings_and_hash(mock_daemons):
    result = await get_status(MOCK)

    assert result.reachable is True and result.ok is True and result.configured is True
    assert result.settings["hostname"] == "mock-eagled"
    assert result.config_hash == daemon_config.config_hash(SEED)


async def test_status_mock_disabled_is_unreachable():
    result = await get_status(MOCK)
    assert result.reachable is False and "disabled" in result.error


async def test_status_over_grpc(daemon_server_factory):
    _servicer, address = await daemon_server_factory(
        {
            "GetConfiguration": eagled_pb2.GetConfigurationResponse(
                config_toml=b'hostname = "real"\n'
            )
        }
    )

    result = await get_status(address)

    assert result.reachable is True and result.settings == {"hostname": "real"}


async def test_status_grpc_unreachable(daemon_server_factory):
    _servicer, address = await daemon_server_factory(
        {"GetConfiguration": Exception("down")}
    )

    result = await get_status(address)

    assert result.reachable is False and "down" in result.error


async def test_plugins_lists_every_configured_instance(mock_daemons):
    result = await get_plugins(MOCK)

    assert result.reachable is True and result.ok is True
    got = {(i.name, i.category) for i in result.instances}
    assert got == {
        ("harpy", "vehicle"),
        ("kestrel", "vehicle"),
        ("detector", "engine"),
        ("battery-watch", "monitor"),
        ("swarm-controller", "extra"),
        ("gcs", "extra"),
    }
    harpy = next(i for i in result.instances if i.name == "harpy")
    assert harpy.source == {
        "kind": "image",
        "url": "docker.io/cmusatyalab/parrot-anafi-driver",
        "tag": "v4.0",
    }
    assert harpy.section["instance_fields"]["args"] == {"ip": "10.202.0.1"}
    assert harpy.section["instance_fields"]["sim"]["lat"] == 40.413664
    detector = next(i for i in result.instances if i.name == "detector")
    assert detector.section["plugin"]["args"] == {"model": "yolov8n", "confidence": 0.5}


async def test_plugins_returns_odd_config_values_verbatim(mock_daemons):
    mock()._config = SEED.replace(
        'runtime = "container"\nimage', 'runtime = "podman"\nimage', 1
    )

    harpy = next(i for i in (await get_plugins(MOCK)).instances if i.name == "harpy")

    assert harpy.runtime == "podman"


@pytest.mark.parametrize("text", ["name = \n", '[vehicles]\nname = "x"\n'])
async def test_bad_daemon_config_is_ok_false_not_a_crash(mock_daemons, text):
    mock()._config = text
    async with asgi_client() as client:
        for path in ("status", "plugins", "config"):
            response = await client.get(
                f"/api/daemons/{path}", params={"address": MOCK}
            )
            assert response.status_code == 200, path
            assert response.json()["ok"] is False, path


# --- restart / reset --------------------------------------------------------


async def test_restart_sends_one_request_for_all_instances(mock_daemons):
    body = RestartBody(
        address=MOCK,
        instances=[
            {"name": "harpy", "category": "vehicle"},
            {"name": "gcs", "category": "extra"},
        ],
    )

    result = await restart_plugins(body)

    assert result.ok is True
    assert [e for e in mock().events if e[0] == "restart"][0][1][0].name == "harpy"


async def test_restart_unknown_instance_is_ok_false(mock_daemons):
    result = await restart_plugins(
        RestartBody(address=MOCK, instances=[{"name": "ghost", "category": "vehicle"}])
    )
    assert result.reachable is True and result.ok is False and "ghost" in result.error


async def test_restart_body_validation():
    async with asgi_client() as client:
        empty = await client.post(
            "/api/daemons/plugins/restart", json={"address": MOCK, "instances": []}
        )
        bad_name = await client.post(
            "/api/daemons/plugins/restart",
            json={
                "address": MOCK,
                "instances": [{"name": "../x", "category": "vehicle"}],
            },
        )
    assert empty.status_code == 422 and bad_name.status_code == 422


async def test_reset_config_then_status_is_unconfigured(mock_daemons):
    assert (await reset_config(DaemonAddressBody(address=MOCK))).ok is True
    assert (await get_status(MOCK)).configured is False


# --- GET /config -------------------------------------------------------------


async def test_get_config_returns_raw_form_and_hash(mock_daemons):
    result = await loaded()

    assert result["ok"] is True
    assert result["raw_toml"] == SEED
    assert result["config_hash"] == daemon_config.config_hash(SEED)
    assert result["form"]["settings"]["hostname"] == "mock-eagled"
    assert [s["name"] for s in result["form"]["instances"]["vehicle"]] == [
        "harpy",
        "kestrel",
    ]
    assert result["form"]["instances"]["engine"][0]["plugin"]["args"] == {
        "model": "yolov8n",
        "confidence": 0.5,
    }


async def test_get_config_of_bad_config_still_returns_raw_for_repair(mock_daemons):
    mock()._config = "name = \n"
    result = await loaded()
    assert (
        result["ok"] is False
        and result["form"] is None
        and result["raw_toml"] == "name = \n"
    )


async def test_get_config_with_values_the_form_cannot_save_is_raw_only(mock_daemons):
    mock()._config = SEED.replace(
        'runtime = "container"\nimage', 'runtime = "podman"\nimage', 1
    )
    result = await loaded()
    assert (
        result["ok"] is False
        and result["form"] is None
        and "Raw TOML" in result["error"]
    )


# --- PUT /config -------------------------------------------------------------


async def test_put_form_merges_into_the_current_config_and_configures(mock_daemons):
    current = await loaded()
    form = current["form"]
    form["instances"]["engine"][0]["plugin"]["args"]["model"] = "yolov8s"
    form["instances"]["monitor"] = []
    form["instances"]["vehicle"].append(section("osprey", "parrot_anafi"))
    form["settings"]["gabriel_port"] = 9100

    result = await put_config(
        PutConfigBody(address=MOCK, config_hash=current["config_hash"], form=form)
    )

    assert result.ok is True
    text = await mock().get_configuration()
    assert result.config_hash == daemon_config.config_hash(text)
    assert mock().events == ["configure"]
    assert 'model = "yolov8s"' in text and "gabriel-port = 9100" in text
    assert "battery-watch" not in text and 'name = "osprey"' in text
    assert "# Seed config for mock daemons" in text  # comments survive


async def test_put_unchanged_form_sends_the_identical_text(mock_daemons):
    current = await loaded()
    await put_config(
        PutConfigBody(
            address=MOCK, config_hash=current["config_hash"], form=current["form"]
        )
    )
    assert await mock().get_configuration() == SEED


async def test_put_raw_toml_replaces_the_config_even_a_corrupt_one(mock_daemons):
    mock()._config = "name = \n"
    current_hash = (await loaded())["config_hash"]

    result = await put_config(
        PutConfigBody(
            address=MOCK, config_hash=current_hash, raw_toml='hostname = "fixed"\n'
        )
    )

    assert result.ok is True
    assert await mock().get_configuration() == 'hostname = "fixed"\n'


async def test_put_with_stale_hash_is_a_conflict_and_changes_nothing(mock_daemons):
    current = await loaded()
    mock()._config = SEED + "\n"

    result = await put_config(
        PutConfigBody(
            address=MOCK, config_hash=current["config_hash"], form=current["form"]
        )
    )

    assert result.conflict is True and result.ok is False
    assert mock().events == []


async def test_put_form_onto_a_corrupt_config_is_ok_false(mock_daemons):
    mock()._config = "name = \n"
    form = {"settings": {}, "instances": {}}
    result = await put_config(
        PutConfigBody(
            address=MOCK, config_hash=daemon_config.config_hash("name = \n"), form=form
        )
    )
    assert result.ok is False and "not valid TOML" in result.error


async def test_put_unreachable():
    result = await put_config(PutConfigBody(address=MOCK, config_hash="x", raw_toml=""))
    assert result.reachable is False


@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({"raw_toml": "name = \n"}, ""),
        ({"raw_toml": '[vehicles]\nname = "x"\n'}, "array of tables"),
        (
            {"form": {"instances": {"vehicle": [section("a"), section("a")]}}},
            "duplicate vehicle names",
        ),
        ({"form": {"instances": {"vehicle": [section("../x")]}}}, "pattern"),
        (
            {"form": {"instances": {"engine": [section(plugin_id="")]}}},
            "plugin ID or a source",
        ),
        (
            {"form": {"instances": {"engine": [section(args={"a": None})]}}},
            "null values",
        ),
        ({"form": {"instances": {"engine": [section(runtime="podman")]}}}, "runtime"),
        (
            {
                "form": {
                    "instances": {
                        "engine": [{**section(), "instance_fields": {"name": "x"}}]
                    }
                }
            },
            "can't set",
        ),
        (
            {"form": {"instances": {"engine": [section(extra={"url": "x"})]}}},
            "can't set",
        ),
        ({"form": {"settings": {"gabriel_port": 70000}}}, "less than or equal"),
        ({"form": {"settings": {"unknown": 1}}}, "Extra inputs"),
        ({}, "exactly one"),
        ({"form": {}, "raw_toml": ""}, "exactly one"),
    ],
)
async def test_put_request_errors_are_422(mock_daemons, payload, fragment):
    async with asgi_client() as client:
        response = await client.put(
            "/api/daemons/config", json={"address": MOCK, "config_hash": "x", **payload}
        )
    assert response.status_code == 422
    assert fragment in response.text
    assert mock().events == []


# --- convert -------------------------------------------------------------------


async def test_convert_round_trip_keeps_comments(mock_daemons):
    form = (await loaded())["form"]
    form["instances"]["engine"][0]["plugin"]["args"]["model"] = "yolov8s"
    async with asgi_client() as client:
        raw = (
            await client.post(
                "/api/daemons/config/convert",
                json={"to": "raw", "form": form, "base_toml": SEED},
            )
        ).json()["raw_toml"]
        back = (
            await client.post(
                "/api/daemons/config/convert", json={"to": "form", "raw_toml": raw}
            )
        ).json()["form"]

    assert "# Seed config for mock daemons" in raw and 'model = "yolov8s"' in raw
    assert back == form


@pytest.mark.parametrize(
    "body",
    [
        {"to": "form", "raw_toml": "a = \n"},
        {"to": "form", "raw_toml": '[vehicles]\nname = "x"\n'},
        {
            "to": "form",
            "raw_toml": SEED.replace('runtime = "process"', 'runtime = "podman"', 1),
        },
        {"to": "raw", "form": {}, "base_toml": "a = \n"},
        {"to": "raw"},
        {"to": "form"},
    ],
)
async def test_convert_errors_are_422(body):
    async with asgi_client() as client:
        response = await client.post("/api/daemons/config/convert", json=body)
    assert response.status_code == 422


async def test_convert_parse_error_carries_its_position():
    async with asgi_client() as client:
        response = await client.post(
            "/api/daemons/config/convert",
            json={"to": "form", "raw_toml": "a = 1\nb = \n"},
        )
    assert response.json()["detail"]["line"] == 2


# --- discovery ---------------------------------------------------------------


async def test_discovered_includes_mock_daemons_when_enabled(mock_daemons, monkeypatch):
    async def no_tailscale():
        return None

    monkeypatch.setattr(eagled_routes, "_run_tailscale_status", no_tailscale)

    result = await get_discovered_daemons()

    assert [(d.address, d.online) for d in result.daemons] == [
        ("mock://lab-a", True),
        ("mock://lab-b", True),
    ]


# A trimmed real `tailscale status --json` shape (field names/nesting as
# observed on a live tailnet): only Peer entries carrying
# tag:steeleagle-daemon should surface as discovered daemons.
FAKE_TAILSCALE_STATUS = {
    "Peer": {
        "nodekey:aaa": {
            "HostName": "heisenberg-eagled",
            "DNSName": "heisenberg-eagled.tailnet-1234.ts.net.",
            "Tags": ["tag:steeleagle-daemon"],
            "Online": True,
        },
        "nodekey:bbb": {
            "HostName": "fermi-eagled",
            "DNSName": "fermi-eagled.tailnet-1234.ts.net.",
            "Tags": ["tag:steeleagle-daemon"],
            "Online": False,
        },
        "nodekey:ccc": {
            "HostName": "cloudlet033",
            "DNSName": "cloudlet033.tailnet-1234.ts.net.",
            "Tags": ["tag:steeleagle-backend"],
            "Online": True,
        },
        "nodekey:ddd": {
            "HostName": "untagged-laptop",
            "DNSName": "untagged-laptop.tailnet-1234.ts.net.",
            "Tags": None,
            "Online": True,
        },
    }
}


def test_discovered_daemons_from_status_filters_by_tag_and_sorts():
    daemons = _discovered_daemons_from_status(FAKE_TAILSCALE_STATUS)

    assert [d.name for d in daemons] == ["fermi-eagled", "heisenberg-eagled"]
    assert daemons[0].address == "fermi-eagled.tailnet-1234.ts.net:9090"
    assert daemons[0].online is False
    assert daemons[1].address == "heisenberg-eagled.tailnet-1234.ts.net:9090"
    assert daemons[1].online is True


def test_discovered_daemons_from_status_skips_peer_with_no_dns_name():
    status = {
        "Peer": {
            "nodekey:eee": {
                "HostName": "no-dns",
                "DNSName": "",
                "Tags": ["tag:steeleagle-daemon"],
                "Online": True,
            }
        }
    }

    assert _discovered_daemons_from_status(status) == []


async def test_discovered_daemons_route_returns_tagged_peers(monkeypatch):
    async def fake_run_tailscale_status():
        return FAKE_TAILSCALE_STATUS

    monkeypatch.setattr(
        eagled_routes, "_run_tailscale_status", fake_run_tailscale_status
    )

    result = await get_discovered_daemons()

    assert [d.name for d in result.daemons] == ["fermi-eagled", "heisenberg-eagled"]


async def test_discovered_daemons_route_empty_when_tailscale_unavailable(
    monkeypatch,
):
    async def fake_run_tailscale_status():
        return None

    monkeypatch.setattr(
        eagled_routes, "_run_tailscale_status", fake_run_tailscale_status
    )

    result = await get_discovered_daemons()

    assert result.daemons == []
