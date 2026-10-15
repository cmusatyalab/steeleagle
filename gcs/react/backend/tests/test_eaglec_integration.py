"""End-to-end against the real eaglec and Go toolchain. Opt-in, since a
cold Go cache makes it take minutes:

    RUN_EAGLEC_INTEGRATION=1 uv run pytest tests/test_eaglec_integration.py -v
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from app.compiler_config import ensure_eaglec, load_compiler_config
from app.eaglec_client import EaglecClient, EaglecCompileErrors
from app.mission_binary import elf_arch
from app.mission_translate import (
    upgrade_legacy_dsl,
    TypeIndex,
    ast_to_dsl,
    ast_to_graph,
    graph_to_ast,
    prepare_geojson,
)
from tests.translate_examples import GRAPH, POLY_GEOJSON

LEGACY_DSL = Path(__file__).parent / "fixtures" / "legacy_import.dsl"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EAGLEC_INTEGRATION") != "1" or shutil.which("go") is None,
    reason="set RUN_EAGLEC_INTEGRATION=1 (and have go on PATH) to run",
)


@pytest.fixture
async def compiler():
    config = load_compiler_config(None)
    await ensure_eaglec(config)
    client = EaglecClient(config.eaglec, config.timeout_s)
    index = TypeIndex(await client.schema(config.header()))
    return config, client, index


def _normalize(value):
    """Drops empty strings, empty lists, empty dicts and nulls, which
    eaglec's parse output (it emits empty Data/Role stanzas) and
    graph_to_ast's output disagree on without meaning anything different."""
    if isinstance(value, dict):
        out = {k: _normalize(v) for k, v in value.items()}
        return {k: v for k, v in out.items() if v not in ("", [], None, {})}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


async def test_compile_both_archs(compiler):
    config, client, index = compiler
    ast = graph_to_ast(GRAPH, index, config.header())
    geojson, errors = prepare_geojson(POLY_GEOJSON)
    assert errors == []

    assert elf_arch(await client.compile(ast, geojson, "amd64")) == "amd64"
    assert elf_arch(await client.compile(ast, geojson, "arm64")) == "arm64"


async def test_rendered_dsl_parses_back_to_the_same_mission(compiler):
    config, client, index = compiler
    ast = graph_to_ast(GRAPH, index, config.header())

    parsed = await client.parse(ast_to_dsl(ast))

    assert _normalize(parsed) == _normalize(ast)
    graph = ast_to_graph(parsed, index)
    assert graph["nodes"] == GRAPH["nodes"]
    assert graph["events"] == GRAPH["events"]
    assert graph["edges"] == GRAPH["edges"]


async def test_misspelled_field_is_reported_on_its_decl(compiler):
    config, client, index = compiler
    graph = json.loads(json.dumps(GRAPH))
    graph["nodes"][2]["params"]["Altitud"] = graph["nodes"][2]["params"].pop("Altitude")
    ast = graph_to_ast(graph, index, config.header())

    with pytest.raises(EaglecCompileErrors) as exc:
        await client.compile(ast, prepare_geojson(POLY_GEOJSON)[0], "amd64")

    assert any(
        e["decl"] == "patrol" and "Altitud" in e["message"] for e in exc.value.errors
    )


async def test_wrong_geometry_feature_is_a_node_error(compiler):
    config, client, index = compiler
    collection = json.loads(POLY_GEOJSON)
    collection["features"].append(
        {
            "type": "Feature",
            "properties": {"name": "Pin"},
            "geometry": {"type": "Point", "coordinates": [-79.946, 40.413]},
        }
    )
    graph = json.loads(json.dumps(GRAPH))
    graph["nodes"][2]["params"]["Area"] = "Pin"
    ast = graph_to_ast(graph, index, config.header())

    with pytest.raises(EaglecCompileErrors) as exc:
        await client.compile(ast, prepare_geojson(json.dumps(collection))[0], "amd64")

    assert any(e["decl"] == "patrol" for e in exc.value.errors)


async def test_legacy_import_dsl_loads_onto_the_canvas(compiler):
    """A DSL file the Plan page exported before the SDK renamed Import: to
    Imports: (bare type names, bare enum values, a string Area, a Data
    decl) loads once its header is upgraded."""
    config, client, index = compiler
    dsl, warnings = upgrade_legacy_dsl(LEGACY_DSL.read_text())

    graph = ast_to_graph(await client.parse(dsl), index)

    assert warnings == ["Converted the old Import: header to Imports:"]
    assert graph["warnings"] == []
    assert [n["type_name"] for n in graph["nodes"]] == [
        "TakeOff",
        "SetGimbalPose",
        "Patrol",
        "ReturnToHome",
    ]
    gimbal, patrol = graph["nodes"][1]["params"], graph["nodes"][2]["params"]
    assert gimbal["Pose"] == {"Pitch": -45, "Roll": 0, "Yaw": 0}
    assert patrol["Area"] == "FieldB"
    assert patrol["Pattern"] == "PatrolModeSurvey"
    assert graph["edges"][-1] == {
        "source": "patrol_1",
        "event_id": "battery_below_10",
        "target": "return_to_home_1",
    }
