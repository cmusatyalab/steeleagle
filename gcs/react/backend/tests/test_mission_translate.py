import json

import pytest

from app.mission_translate import (
    TypeIndex,
    ast_to_dsl,
    ast_to_graph,
    bare,
    graph_to_ast,
    prepare_geojson,
    qualifier,
    upgrade_legacy_dsl,
    registry_to_schema,
)
from tests.translate_examples import AST, DSL, GRAPH, HEADER, INDEX, POLY_GEOJSON


def _field(schema_entry: dict, name: str) -> dict:
    return next(f for f in schema_entry["fields"] if f["name"] == name)


def test_bare_and_qualifier():
    assert bare("actions.Patrol") == "Patrol"
    assert bare("params.Polygon_Area_1") == "Polygon_Area_1"
    assert bare("Patrol") == "Patrol"
    assert qualifier("enums.AltitudeMode") == "enums"
    assert qualifier("Patrol") == ""


def test_kinds():
    assert INDEX.kind("params.Polygon") == "feature"
    assert INDEX.kind("enums.AltitudeMode") == "enum"
    assert INDEX.kind("actions.PatrolMode") == "enum"
    assert INDEX.kind("datatypes.Pose") == "object"
    assert INDEX.kind("[]float32") == "array"
    assert INDEX.kind("float32") == "number"
    assert INDEX.kind("uint32") == "integer"
    assert INDEX.kind("bool") == "boolean"
    assert INDEX.kind("string") == "string"
    assert INDEX.kind("chan int") == "unknown"


def test_keys_and_field_types():
    assert INDEX.key("actions", "actions.Patrol") == "Patrol"
    assert INDEX.qualify("actions", "Patrol") == "actions.Patrol"
    assert INDEX.qualify("events", "Battery") == "events.Battery"
    assert INDEX.key("actions", "nope.Nope") is None
    assert INDEX.field_type("actions.Patrol", "Area") == "params.Polygon"
    assert INDEX.field_type("datatypes.Pose", "Pitch") == "float32"
    assert INDEX.field_type("actions.Patrol", "Nope") is None


def test_patrol_schema():
    schema = registry_to_schema(INDEX)
    patrol = schema["actions"]["Patrol"]

    assert patrol["type"] == "actions.Patrol"
    assert patrol["description"].startswith("Patrol orders the vehicle")
    names = [f["name"] for f in patrol["fields"]]
    assert names[:2] == ["Area", "Altitude"]  # required fields first
    assert _field(patrol, "Area") == {
        "name": "Area",
        "go_type": "params.Polygon",
        "type": "string",
        "required": True,
        "description": "polygon to patrol around",
        "map_feature": True,
        "feature_type": "Polygon",
    }
    assert _field(patrol, "Altitude")["type"] == "number"
    assert _field(patrol, "Altitude")["required"] is True
    assert _field(patrol, "SurveySpacing")["default"] == 10.0
    assert _field(patrol, "SurveySpacing")["required"] is False
    assert _field(patrol, "Pattern")["enum_type"] == "PatrolMode"
    assert _field(patrol, "AltitudeMode")["enum_type"] == "AltitudeMode"
    assert "default" not in _field(patrol, "SurveyHeading")


def test_datatype_fields_become_nested_objects():
    gimbal = registry_to_schema(INDEX)["actions"]["SetGimbalPose"]
    pose = _field(gimbal, "Pose")

    assert pose["type"] == "object"
    assert pose["object_type"] == "Pose"
    assert [(f["name"], f["type"], f["required"]) for f in pose["nested_fields"]] == [
        ("Pitch", "number", True),
        ("Roll", "number", True),
        ("Yaw", "number", True),
    ]


def test_integer_defaults_are_ints():
    battery = registry_to_schema(INDEX)["events"]["Battery"]

    assert _field(battery, "Threshold")["type"] == "integer"
    assert _field(battery, "Threshold")["default"] == 20
    assert _field(battery, "Comparator")["enum_type"] == "Comparator"


def test_enums_exclude_map_features():
    enums = registry_to_schema(INDEX)["enums"]

    assert enums["PatrolMode"]["values"] == ["PatrolModeCorridor", "PatrolModeSurvey"]
    assert enums["Comparator"]["values"] == ["GreaterOrEqual", "LessOrEqual"]
    assert enums["PatrolMode"]["type"] == "actions.PatrolMode"
    for feature in ("Polygon", "Point", "LineString", "MultiLineString"):
        assert feature not in enums


def test_actions_without_opt_fields():
    land = registry_to_schema(INDEX)["actions"]["Land"]

    assert land["fields"] == []


def test_colliding_bare_names_fall_back_to_qualified_keys():
    registry = {
        "actions": {
            "a.Patrol": {"type": "a.Patrol", "fields": []},
            "b.Patrol": {"type": "b.Patrol", "fields": []},
            "a.Land": {"type": "a.Land", "fields": []},
        },
        "events": {},
        "datatypes": {},
        "enums": {},
    }
    index = TypeIndex(registry)

    assert sorted(registry_to_schema(index)["actions"]) == [
        "Land",
        "a.Patrol",
        "b.Patrol",
    ]
    assert index.qualify("actions", "a.Patrol") == "a.Patrol"
    assert index.qualify("actions", "Patrol") is None


@pytest.mark.parametrize("value", ["abc", ""])
def test_unparseable_defaults_are_kept_as_strings(value):
    registry = {
        "actions": {
            "a.X": {
                "type": "a.X",
                "fields": [],
                "optFields": [{"name": "N", "type": "float32", "value": value}],
            }
        },
    }
    fields = registry_to_schema(TypeIndex(registry))["actions"]["X"]["fields"]

    assert fields[0].get("default") == (value or None)


def test_graph_to_ast_full_mission():
    assert graph_to_ast(GRAPH, INDEX, HEADER) == AST


def test_graph_to_ast_has_no_role():
    assert "Role" not in graph_to_ast(GRAPH, INDEX, HEADER)


def test_graph_to_ast_skips_unset_params():
    graph = {
        **GRAPH,
        "nodes": [
            {
                "instance_id": "patrol",
                "type_name": "Patrol",
                "params": {"Area": None, "Altitude": "", "Speed": 3},
            }
        ],
        "edges": [],
        "start_id": "patrol",
    }

    [decl] = graph_to_ast(graph, INDEX, HEADER)["Actions"]["Decls"]

    assert decl["Attrs"] == [{"Key": "Speed", "Value": {"Float": 3.0}}]


def test_graph_to_ast_skips_unset_nested_fields():
    graph = {
        **GRAPH,
        "nodes": [
            {
                "instance_id": "gimbal",
                "type_name": "SetGimbalPose",
                "params": {"Pose": {"Pitch": -10, "Roll": None, "Yaw": ""}},
            }
        ],
        "edges": [],
    }

    [decl] = graph_to_ast(graph, INDEX, HEADER)["Actions"]["Decls"]

    assert decl["Attrs"][0]["Value"]["Inline"]["Args"] == [
        {"Key": "Pitch", "Value": {"Float": -10.0}}
    ]


def test_graph_to_ast_passes_unknown_types_through():
    graph = {
        **GRAPH,
        "nodes": [
            {"instance_id": "x", "type_name": "Dance", "params": {"Style": "salsa"}}
        ],
        "edges": [],
    }

    [decl] = graph_to_ast(graph, INDEX, HEADER)["Actions"]["Decls"]

    assert decl == {
        "Type": "Dance",
        "Name": "x",
        "Attrs": [{"Key": "Style", "Value": {"String": "salsa"}}],
    }


def test_graph_to_ast_without_start_has_no_mission():
    assert "Mission" not in graph_to_ast({**GRAPH, "start_id": None}, INDEX, HEADER)


def test_number_kinds():
    def attrs(type_name, params, section="nodes"):
        graph = {"nodes": [], "events": [], "edges": [], "start_id": None}
        graph[section] = [
            {"instance_id": "x", "type_name": type_name, "params": params}
        ]
        stanza = "Actions" if section == "nodes" else "Events"
        return graph_to_ast(graph, INDEX, HEADER)[stanza]["Decls"][0]["Attrs"]

    # a whole number in a float field is still a float literal
    assert attrs("Patrol", {"Altitude": 15}) == [
        {"Key": "Altitude", "Value": {"Float": 15.0}}
    ]
    # a whole float in an integer field is an int literal
    assert attrs("Battery", {"Threshold": 15.0}, "events") == [
        {"Key": "Threshold", "Value": {"Int": 15}}
    ]
    # a fractional number in an integer field reaches the compiler as-is
    assert attrs("Battery", {"Threshold": 15.5}, "events") == [
        {"Key": "Threshold", "Value": {"Float": 15.5}}
    ]
    # booleans are idents
    assert attrs("Dance", {"Loud": True}) == [
        {"Key": "Loud", "Value": {"Ident": "true"}}
    ]


def test_qualified_enum_values_are_kept():
    graph = {
        **GRAPH,
        "nodes": [
            {
                "instance_id": "p",
                "type_name": "Patrol",
                "params": {"Pattern": "actions.PatrolModeCorridor"},
            }
        ],
        "edges": [],
    }

    [decl] = graph_to_ast(graph, INDEX, HEADER)["Actions"]["Decls"]

    assert decl["Attrs"] == [
        {"Key": "Pattern", "Value": {"Ident": "actions.PatrolModeCorridor"}}
    ]


def test_arrays_become_array_values():
    registry = {
        "actions": {
            "a.Fly": {
                "type": "a.Fly",
                "fields": [{"name": "Speeds", "type": "[]float32"}],
            }
        }
    }
    index = TypeIndex(registry)
    graph = {
        "nodes": [
            {"instance_id": "f", "type_name": "Fly", "params": {"Speeds": [1, 2.5]}}
        ],
        "events": [],
        "edges": [],
        "start_id": None,
    }

    [decl] = graph_to_ast(graph, index, HEADER)["Actions"]["Decls"]

    assert decl["Attrs"] == [
        {
            "Key": "Speeds",
            "Value": {"Array": {"Elems": [{"Float": 1.0}, {"Float": 2.5}]}},
        }
    ]


def test_object_for_a_non_object_field_is_rejected():
    graph = {
        **GRAPH,
        "nodes": [
            {
                "instance_id": "p",
                "type_name": "Patrol",
                "params": {"Altitude": {"x": 1}},
            }
        ],
        "edges": [],
    }

    with pytest.raises(ValueError, match="float32"):
        graph_to_ast(graph, INDEX, HEADER)


def test_prepare_geojson_passes_valid_features_through():
    assert prepare_geojson(POLY_GEOJSON) == (POLY_GEOJSON.encode(), [])


@pytest.mark.parametrize(
    "text",
    ["", "   ", json.dumps({"type": "FeatureCollection", "features": []})],
)
def test_prepare_geojson_without_features_is_none(text):
    assert prepare_geojson(text) == (None, [])


def _fc(*features):
    return json.dumps({"type": "FeatureCollection", "features": list(features)})


def _feature(name, geometry="Polygon"):
    props = {} if name is None else {"name": name}
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": geometry, "coordinates": []},
    }


@pytest.mark.parametrize(
    "features, message",
    [
        (
            [_feature("Area B")],
            "Map feature 'Area B' can only contain letters, digits and underscores",
        ),
        (
            [_feature("north-field")],
            "Map feature 'north-field' can only contain letters, digits and underscores",
        ),
        ([_feature(None)], "Map feature 1 has no name"),
        ([_feature("")], "Map feature 1 has no name"),
        (
            [_feature("A"), _feature("A", "Point")],
            "Map feature name 'A' is used more than once",
        ),
        (
            [_feature("C", "GeometryCollection")],
            "Map feature 'C' is a GeometryCollection, but only Point, LineString, MultiLineString and Polygon features are supported",
        ),
    ],
)
def test_prepare_geojson_reports_features_eaglec_rejects(features, message):
    _, errors = prepare_geojson(_fc(*features))

    assert errors == [message]


def test_prepare_geojson_accepts_leading_digits():
    assert prepare_geojson(_fc(_feature("1st")))[1] == []


def test_prepare_geojson_reports_invalid_json():
    _, errors = prepare_geojson("{not json")

    assert len(errors) == 1 and errors[0].startswith(
        "Map features are not valid GeoJSON"
    )


@pytest.mark.parametrize(
    "text, errors",
    [
        (
            '{"type": "FeatureCollection", "features": {"a": 1}}',
            ["Map features are not valid GeoJSON: features must be a list"],
        ),
        (
            '{"type": "FeatureCollection", "features": "abc"}',
            ["Map features are not valid GeoJSON: features must be a list"],
        ),
        (
            '{"type": "FeatureCollection", "features": [null]}',
            ["Map feature 1 is not a valid GeoJSON feature"],
        ),
        (
            '{"type": "FeatureCollection", "features": [5]}',
            ["Map feature 1 is not a valid GeoJSON feature"],
        ),
        (
            '{"type": "FeatureCollection", "features": ["x"]}',
            ["Map feature 1 is not a valid GeoJSON feature"],
        ),
        (
            '{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": "x", "geometry": {"type": "Polygon"}}]}',
            ["Map feature 1 has no name"],
        ),
        (
            '{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": ["a"], "geometry": {"type": "Polygon"}}]}',
            ["Map feature 1 has no name"],
        ),
        (
            '{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "A"}, "geometry": "x"}]}',
            [
                "Map feature 'A' is a None, but only Point, LineString, MultiLineString and Polygon features are supported"
            ],
        ),
        (
            '{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "A"}, "geometry": 5}]}',
            [
                "Map feature 'A' is a None, but only Point, LineString, MultiLineString and Polygon features are supported"
            ],
        ),
    ],
)
def test_prepare_geojson_reports_malformed_shapes_without_raising(text, errors):
    _, got = prepare_geojson(text)

    assert got == errors


def test_prepare_geojson_null_features_is_none():
    assert prepare_geojson('{"type": "FeatureCollection", "features": null}') == (
        None,
        [],
    )


def test_ast_to_graph_inverts_graph_to_ast():
    graph = ast_to_graph(graph_to_ast(GRAPH, INDEX, HEADER), INDEX)

    for key in ("nodes", "events", "edges", "start_id"):
        assert graph[key] == GRAPH[key], key
    assert graph["warnings"] == []
    assert graph["imports"][0] == {
        "path": HEADER["Imports"]["Imports"][0]["Path"],
        "alias": "",
    }
    assert graph["modules"] == [
        {
            "path": HEADER["Modules"]["Modules"][0]["Path"],
            "version": "",
            "override": "/repo/sdk",
        }
    ]


def test_ast_to_graph_accepts_integral_floats_from_eaglec():
    # Go marshals Float 15.0 as 15
    ast = {
        "Actions": {
            "Decls": [
                {
                    "Type": "actions.Patrol",
                    "Name": "p",
                    "Attrs": [{"Key": "Altitude", "Value": {"Float": 15}}],
                }
            ]
        },
    }

    [node] = ast_to_graph(ast, INDEX)["nodes"]

    assert node["params"] == {"Altitude": 15.0}
    assert isinstance(node["params"]["Altitude"], float)


def test_ast_to_graph_inlines_data_and_warns():
    ast = {
        **HEADER,
        "Role": {"Name": "Patroller"},
        "Data": {
            "Decls": [
                {
                    "Type": "datatypes.Pose",
                    "Name": "down",
                    "Attrs": [
                        {"Key": "Pitch", "Value": {"Float": -90}},
                        {"Key": "Roll", "Value": {"Float": 0}},
                        {"Key": "Yaw", "Value": {"Float": 0}},
                    ],
                },
                {"Type": "datatypes.Pose", "Name": "spare"},
            ]
        },
        "Actions": {
            "Decls": [
                {
                    "Type": "actions.SetGimbalPose",
                    "Name": "gimbal",
                    "Attrs": [{"Key": "Pose", "Value": {"Ident": "down"}}],
                },
                {
                    "Type": "custom.Dance",
                    "Name": "dance",
                    "Attrs": [{"Key": "Loud", "Value": {"Ident": "true"}}],
                },
                {"Type": "Land", "Name": "land"},
            ]
        },
        "Mission": {
            "Start": "gimbal",
            "Blocks": [
                {"Action": "gimbal", "Rules": [{"Event": "done", "Next": "dance"}]}
            ],
        },
    }

    graph = ast_to_graph(ast, INDEX)

    assert graph["nodes"] == [
        {
            "instance_id": "gimbal",
            "type_name": "SetGimbalPose",
            "params": {"Pose": {"Pitch": -90.0, "Roll": 0.0, "Yaw": 0.0}},
        },
        {"instance_id": "dance", "type_name": "Dance", "params": {"Loud": True}},
        {"instance_id": "land", "type_name": "Land", "params": {}},
    ]
    assert graph["events"] == []
    assert graph["edges"] == [
        {"source": "gimbal", "event_id": "done", "target": "dance"}
    ]
    assert graph["start_id"] == "gimbal"
    assert graph["warnings"] == [
        "custom.Dance is not a known action type",
        "Role Patroller is ignored: the GCS compiles missions without a role",
        "Data spare is not used by any action or event and was dropped",
    ]


def test_ast_to_graph_without_mission():
    graph = ast_to_graph({}, INDEX)

    assert graph == {
        "nodes": [],
        "events": [],
        "edges": [],
        "start_id": None,
        "modules": [],
        "imports": [],
        "warnings": [],
    }


def test_ast_to_dsl_full_mission():
    assert ast_to_dsl(AST) == DSL


def test_ast_to_dsl_renders_every_value_form():
    ast = {
        "Role": {"Name": "Patroller"},
        "Modules": {"Modules": [{"Path": "example.com/m", "Version": "v1.2.3"}]},
        "Imports": {"Imports": [{"Path": "example.com/m/dt", "Alias": "dt"}]},
        "Data": {
            "Decls": [
                {
                    "Type": "dt.Pose",
                    "Name": "down",
                    "Attrs": [{"Key": "Pitch", "Value": {"Float": -90}}],
                }
            ]
        },
        "Actions": {
            "Decls": [
                {
                    "Type": "x.Y",
                    "Name": "y",
                    "Attrs": [
                        {
                            "Key": "A",
                            "Value": {
                                "Array": {
                                    "Elems": [
                                        {"Int": 1},
                                        {"Float": 2.5},
                                        {"String": "x"},
                                    ]
                                }
                            },
                        },
                        {"Key": "S", "Value": {"String": 'say "hi"'}},
                        {"Key": "B", "Value": {"Ident": "true"}},
                        {"Key": "P", "Value": {"Ident": "down"}},
                    ],
                }
            ]
        },
    }

    assert ast_to_dsl(ast) == (
        "Role Patroller:\n\n"
        "Modules:\n"
        '    "example.com/m" v1.2.3\n\n'
        "Imports:\n"
        '    dt "example.com/m/dt"\n\n'
        "Data:\n"
        "    dt.Pose down(Pitch=-90.0)\n\n"
        "Actions:\n"
        '    x.Y y(A=[1, 2.5, "x"], S=\'say "hi"\', B=true, P=down)\n'
    )


def test_render_floats_never_use_exponents():
    def render(f):
        ast = {
            "Actions": {
                "Decls": [
                    {
                        "Type": "a.B",
                        "Name": "b",
                        "Attrs": [{"Key": "F", "Value": {"Float": f}}],
                    }
                ]
            }
        }
        return ast_to_dsl(ast).splitlines()[1].strip()

    assert render(0.00001) == "a.B b(F=0.00001)"
    assert render(1e20) == "a.B b(F=100000000000000000000.0)"
    assert render(-3) == "a.B b(F=-3.0)"
    assert render(2.5) == "a.B b(F=2.5)"


def test_ast_to_dsl_rejects_unrenderable_values():
    def ast(value):
        return {
            "Actions": {
                "Decls": [
                    {
                        "Type": "a.B",
                        "Name": "b",
                        "Attrs": [{"Key": "V", "Value": value}],
                    }
                ]
            }
        }

    with pytest.raises(ValueError, match="quote"):
        ast_to_dsl(ast({"String": """both ' and " """}))
    with pytest.raises(ValueError, match="finite"):
        ast_to_dsl(ast({"Float": float("nan")}))


LEGACY_WARNING = "Converted the old Import: header to Imports:"


def test_upgrade_legacy_dsl_renames_the_import_header():
    dsl = 'Import:\n    "example.com/x"\nActions:\n    a.B b()\n'

    assert upgrade_legacy_dsl(dsl) == (
        'Imports:\n    "example.com/x"\nActions:\n    a.B b()\n',
        [LEGACY_WARNING],
    )


@pytest.mark.parametrize(
    "header, upgraded",
    [
        ("  Import:", "  Imports:"),
        ("Import :", "Imports :"),
        ("Import:\r", "Imports:\r"),
    ],
)
def test_upgrade_legacy_dsl_tolerates_whitespace(header, upgraded):
    dsl, warnings = upgrade_legacy_dsl(f"Role X:\n{header}\n")

    assert dsl == f"Role X:\n{upgraded}\n"
    assert warnings == [LEGACY_WARNING]


@pytest.mark.parametrize(
    "dsl",
    [
        'Imports:\n    "example.com/x"\n',
        "# Import: is the old spelling\nActions:\n",
        "Actions:\n    a.Import Import()\n",
        "",
    ],
)
def test_upgrade_legacy_dsl_leaves_current_dsl_alone(dsl):
    assert upgrade_legacy_dsl(dsl) == (dsl, [])
