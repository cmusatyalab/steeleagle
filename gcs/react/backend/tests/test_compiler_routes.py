import pytest
from fastapi import HTTPException

import app.compiler_routes as compiler_routes
from app.compiler_config import load_compiler_config
from app.compiler_routes import (
    BuildRequest,
    MissionGraph,
    ParseDslRequest,
    build_route,
    compile_route,
    get_schema,
    parse_dsl_route,
    render_dsl_route,
)
from app.eaglec_client import EaglecCompileErrors, EaglecFailure
from tests.fake_eaglec import FakeEaglecClient
from tests.translate_examples import AST, GRAPH, POLY_GEOJSON, REGISTRY


@pytest.fixture
def make_state(monkeypatch, tmp_path):
    """Installs a ready compiler state around a FakeEaglecClient built from
    kwargs, and returns the client."""

    async def make(**kwargs) -> FakeEaglecClient:
        client = FakeEaglecClient(registry=REGISTRY, **kwargs)
        config = load_compiler_config(None, repo_root=tmp_path)
        state = await compiler_routes.load_state(config, client)
        monkeypatch.setattr(compiler_routes, "_state", state)
        monkeypatch.setattr(compiler_routes, "_setup_task", None)
        return client

    return make


def _graph(**overrides) -> MissionGraph:
    return MissionGraph(**{**GRAPH, **overrides})


async def test_schema_is_translated_and_lists_imports(make_state):
    await make_state()

    schema = await get_schema()

    assert schema["actions"]["Patrol"]["type"] == "actions.Patrol"
    assert schema["imports"][0]["path"].endswith("/sdk/dsl/actions")
    assert "default_role" not in schema


async def test_schema_refresh_reloads(make_state):
    client = await make_state()

    await get_schema(refresh=True)

    assert len(client.schema_calls) == 2


async def test_setup_failure_is_reported_by_ready(monkeypatch):
    async def no_go(config):
        raise RuntimeError("building eaglec needs the go toolchain on PATH")

    monkeypatch.setattr(compiler_routes, "ensure_eaglec", no_go)
    monkeypatch.setattr(compiler_routes, "_state", None)
    monkeypatch.setattr(compiler_routes, "_setup_error", None)
    monkeypatch.setattr(compiler_routes, "_setup_task", None)

    compiler_routes.start(None)
    with pytest.raises(HTTPException) as exc:
        await get_schema()

    assert exc.value.status_code == 503
    assert exc.value.detail == (
        "FSM compiler unavailable: building eaglec needs the go toolchain on PATH"
    )


async def test_compile_ok_compiles_amd64_without_geojson(make_state):
    client = await make_state()

    assert await compile_route(_graph()) == {"ok": True}

    [(ast, geojson, arch)] = client.compile_calls
    assert ast["Actions"] == AST["Actions"]
    assert ast["Mission"] == AST["Mission"]
    assert geojson is None
    assert arch == "amd64"


async def test_compile_passes_drawn_features(make_state):
    client = await make_state()

    await compile_route(_graph(geojson=POLY_GEOJSON))

    assert client.compile_calls[0][1] == POLY_GEOJSON.encode()


async def test_compile_structural_errors_skip_eaglec(make_state):
    client = await make_state()

    result = await compile_route(_graph(start_id=None))

    assert result == {
        "errors": [
            {
                "node_id": None,
                "event_id": None,
                "message": "No start state: right-click a node and set it as the start state",
            }
        ]
    }
    assert client.compile_calls == []


async def test_compile_reports_dangling_edges_and_duplicates(make_state):
    await make_state()
    graph = _graph(
        nodes=[*GRAPH["nodes"], GRAPH["nodes"][0]],
        edges=[{"source": "patrol", "event_id": "nope", "target": "ghost"}],
    )

    messages = [e["message"] for e in (await compile_route(graph))["errors"]]

    assert messages == [
        "Duplicate node instance_id: 'takeoff'",
        "Edge target 'ghost' does not refer to any node",
        "Edge event_id 'nope' does not refer to any declared event",
    ]


async def test_compile_feature_name_errors_skip_eaglec(make_state):
    client = await make_state()
    bad = POLY_GEOJSON.replace('"Poly"', '"Area B"')

    result = await compile_route(_graph(geojson=bad))

    assert result == {
        "errors": [
            {
                "node_id": None,
                "event_id": None,
                "message": "Map feature 'Area B' can only contain letters, digits and underscores",
            }
        ]
    }
    assert client.compile_calls == []


async def test_compile_errors_map_decls_to_nodes_and_events(make_state):
    await make_state(
        compile_error=EaglecCompileErrors(
            [
                {
                    "file": "",
                    "decl": "patrol",
                    "line": 0,
                    "message": "no field Altitud",
                },
                {"file": "", "decl": "low", "line": 0, "message": "bad comparator"},
                {
                    "file": "main.go",
                    "decl": "",
                    "line": 3,
                    "message": "go build failed",
                },
            ]
        )
    )

    result = await compile_route(_graph())

    assert result == {
        "errors": [
            {"node_id": "patrol", "event_id": None, "message": "no field Altitud"},
            {"node_id": None, "event_id": "low", "message": "bad comparator"},
            {"node_id": None, "event_id": None, "message": "go build failed"},
        ]
    }


async def test_compile_eaglec_failure_is_500(make_state):
    await make_state(
        compile_error=EaglecFailure("eaglec dsl exited with status 2", "usage: ...")
    )

    with pytest.raises(HTTPException) as exc:
        await compile_route(_graph())

    assert exc.value.status_code == 500
    assert "status 2" in exc.value.detail and "usage: ..." in exc.value.detail


async def test_render_dsl(make_state):
    await make_state()

    dsl = (await render_dsl_route(_graph()))["dsl"]

    assert (
        "    actions.Patrol patrol(Area=params.Polygon_Poly, Altitude=15.0, Pattern=actions.PatrolModeSurvey)\n"
        in dsl
    )
    assert "    Start takeoff\n" in dsl
    assert "Role" not in dsl


async def test_render_dsl_without_start(make_state):
    await make_state()

    dsl = (await render_dsl_route(_graph(start_id=None)))["dsl"]

    assert "Mission:" not in dsl


async def test_parse_dsl_returns_graph_and_warns_about_extra_imports(make_state):
    ast = {
        **AST,
        "Imports": {
            "Imports": [*AST["Imports"]["Imports"], {"Path": "example.com/x/actions"}]
        },
    }
    client = await make_state(parse_result=ast)

    result = await parse_dsl_route(ParseDslRequest(dsl="Actions:\n"))

    assert client.parse_calls == ["Actions:\n"]
    assert result["nodes"] == GRAPH["nodes"]
    assert result["start_id"] == "takeoff"
    assert result["warnings"] == [
        "Imports not in the GCS configuration are ignored when compiling: example.com/x/actions"
    ]


async def test_parse_dsl_upgrades_the_legacy_import_header(make_state):
    client = await make_state(parse_result=AST)

    result = await parse_dsl_route(ParseDslRequest(dsl='Import:\n    "x"\nActions:\n'))

    assert client.parse_calls == ['Imports:\n    "x"\nActions:\n']
    assert result["warnings"][0] == "Converted the old Import: header to Imports:"


async def test_parse_dsl_syntax_error_is_422(make_state):
    await make_state(
        parse_error=EaglecCompileErrors(
            [
                {
                    "file": "mission.dsl",
                    "decl": "",
                    "line": 0,
                    "message": "mission.dsl:2:5: unexpected token",
                }
            ]
        )
    )

    with pytest.raises(HTTPException) as exc:
        await parse_dsl_route(ParseDslRequest(dsl="Actions:\n  x"))

    assert exc.value.status_code == 422
    assert exc.value.detail == "mission.dsl:2:5: unexpected token"


async def test_build_returns_the_binary(make_state):
    client = await make_state(binaries={"arm64": b"\x7fELF-arm"})

    response = await build_route(BuildRequest(**GRAPH, arch="arm64"))

    assert response.body == b"\x7fELF-arm"
    assert response.media_type == "application/octet-stream"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="mission-arm64"'
    )
    assert [arch for _, _, arch in client.compile_calls] == ["arm64"]


async def test_build_compile_errors_are_422(make_state):
    await make_state(
        compile_error=EaglecCompileErrors(
            [{"file": "", "decl": "patrol", "line": 0, "message": "bad area"}]
        )
    )

    with pytest.raises(HTTPException) as exc:
        await build_route(BuildRequest(**GRAPH, arch="amd64"))

    assert exc.value.status_code == 422
    assert exc.value.detail == "Build failed for amd64: bad area"


async def test_compile_rejects_non_identifier_node_names(make_state):
    client = await make_state()
    nodes = [{**GRAPH["nodes"][0], "instance_id": "land here"}, *GRAPH["nodes"][1:]]

    result = await compile_route(_graph(nodes=nodes))

    assert {
        "node_id": "land here",
        "event_id": None,
        "message": "Node name 'land here' can only contain letters, digits and underscores, and can't start with a digit",
    } in result["errors"]
    assert client.compile_calls == []


async def test_compile_rejects_non_identifier_event_names(make_state):
    client = await make_state()
    events = [{**GRAPH["events"][0], "instance_id": "1st-event"}, *GRAPH["events"][1:]]

    result = await compile_route(_graph(events=events))

    assert {
        "node_id": None,
        "event_id": "1st-event",
        "message": "Event name '1st-event' can only contain letters, digits and underscores, and can't start with a digit",
    } in result["errors"]
    assert client.compile_calls == []


async def test_compile_rejects_the_reserved_event_name_done(make_state):
    client = await make_state()
    events = [{**GRAPH["events"][0], "instance_id": "done"}, *GRAPH["events"][1:]]

    result = await compile_route(_graph(events=events))

    assert {
        "node_id": None,
        "event_id": "done",
        "message": "Event name 'done' is reserved for the action-finished transition",
    } in result["errors"]
    assert client.compile_calls == []


async def test_duplicate_and_dangling_event_errors_carry_event_id(make_state):
    await make_state()
    graph = _graph(
        events=[*GRAPH["events"], GRAPH["events"][0]],
        edges=[{"source": "patrol", "event_id": "nope", "target": "takeoff"}],
    )

    errors = (await compile_route(graph))["errors"]

    by_message = {e["message"]: e for e in errors}
    dup = by_message[
        f"Duplicate event instance_id: '{GRAPH['events'][0]['instance_id']}'"
    ]
    assert (
        dup["node_id"] is None and dup["event_id"] == GRAPH["events"][0]["instance_id"]
    )
    dangling = by_message["Edge event_id 'nope' does not refer to any declared event"]
    assert dangling["node_id"] is None and dangling["event_id"] == "nope"
