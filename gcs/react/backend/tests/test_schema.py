from app.api import build_schema_response
from steeleagle_protocol.v1.services.dslcompiler import dslcompiler_pb2


def _patrol_schema() -> dslcompiler_pb2.GetSchemaResponse:
    algo_field = dslcompiler_pb2.FieldSchema(
        name="algo", type="string", required=True, description=""
    )
    alt_field = dslcompiler_pb2.FieldSchema(
        name="alt", type="number", required=True, description=""
    )
    area_field = dslcompiler_pb2.FieldSchema(
        name="area", type="string", required=True, description=""
    )
    waypoints_field = dslcompiler_pb2.FieldSchema(
        name="waypoints",
        type="object",
        required=True,
        description="",
        object_type="types.Waypoints",
        nested_fields=[area_field, alt_field, algo_field],
    )
    hover_time_field = dslcompiler_pb2.FieldSchema(
        name="hover_time", type="number", required=False, description=""
    )
    patrol = dslcompiler_pb2.TypeSchema(
        description="Patrol a set of waypoints.",
        fields=[waypoints_field, hover_time_field],
    )
    target_field = dslcompiler_pb2.FieldSchema(
        name="target", type="object", required=True, description=""
    )
    detection_found = dslcompiler_pb2.TypeSchema(
        description="Fires when an object is detected.", fields=[target_field]
    )
    return dslcompiler_pb2.GetSchemaResponse(
        actions={"actions.Patrol": patrol},
        events={"events.DetectionFound": detection_found},
        default_role="Patrol",
        imports=[
            dslcompiler_pb2.ImportSpec(
                path="github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
            )
        ],
    )


def test_schema_has_actions_and_events():
    schema = build_schema_response(_patrol_schema())
    assert "actions" in schema
    assert "events" in schema
    assert len(schema["actions"]) > 0
    assert len(schema["events"]) > 0


def test_schema_action_keyed_by_bare_name():
    schema = build_schema_response(_patrol_schema())
    assert "Patrol" in schema["actions"]
    assert "actions.Patrol" not in schema["actions"]
    patrol = schema["actions"]["Patrol"]
    assert patrol["description"] == "Patrol a set of waypoints."
    field_names = [f["name"] for f in patrol["fields"]]
    assert "hover_time" in field_names
    assert "waypoints" in field_names


def test_schema_field_has_required_keys():
    schema = build_schema_response(_patrol_schema())
    for type_name, entry in schema["actions"].items():
        for field in entry["fields"]:
            assert "name" in field, f"{type_name} field missing 'name'"
            assert "type" in field, f"{type_name}.{field.get('name')} missing 'type'"
            assert "required" in field, (
                f"{type_name}.{field.get('name')} missing 'required'"
            )


def test_schema_waypoints_field_has_bare_object_type():
    schema = build_schema_response(_patrol_schema())
    patrol_fields = {f["name"]: f for f in schema["actions"]["Patrol"]["fields"]}
    assert patrol_fields["waypoints"]["type"] == "object"
    assert patrol_fields["waypoints"].get("object_type") == "Waypoints"


def test_schema_event_detectionfound_keyed_by_bare_name():
    schema = build_schema_response(_patrol_schema())
    assert "DetectionFound" in schema["events"]
    df = schema["events"]["DetectionFound"]
    field_names = [f["name"] for f in df["fields"]]
    assert "target" in field_names


def test_schema_waypoints_field_has_nested_fields():
    schema = build_schema_response(_patrol_schema())
    patrol_fields = {f["name"]: f for f in schema["actions"]["Patrol"]["fields"]}
    waypoints = patrol_fields["waypoints"]
    assert "nested_fields" in waypoints
    nested_names = [nf["name"] for nf in waypoints["nested_fields"]]
    assert "area" in nested_names
    assert "alt" in nested_names
    assert "algo" in nested_names


def test_schema_non_object_field_has_no_nested_fields():
    schema = build_schema_response(_patrol_schema())
    patrol_fields = {f["name"]: f for f in schema["actions"]["Patrol"]["fields"]}
    hover_time = patrol_fields.get("hover_time")
    assert hover_time is not None
    assert "nested_fields" not in hover_time


def test_schema_includes_imports_and_default_role():
    schema = build_schema_response(_patrol_schema())
    assert schema["default_role"] == "Patrol"
    assert schema["imports"] == [
        {
            "alias": "",
            "path": "github.com/cmusatyalab/steeleagle/sdk/dsl/actions",
            "version": "",
        }
    ]


def test_schema_empty_registry_raises():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        build_schema_response(dslcompiler_pb2.GetSchemaResponse())
