from app.api import build_schema_response


def test_schema_has_actions_and_events():
    schema = build_schema_response()
    assert "actions" in schema
    assert "events" in schema
    assert len(schema["actions"]) > 0
    assert len(schema["events"]) > 0


def test_schema_action_has_fields():
    schema = build_schema_response()
    # Patrol is always registered
    assert "Patrol" in schema["actions"]
    patrol = schema["actions"]["Patrol"]
    assert "description" in patrol
    assert "fields" in patrol
    field_names = [f["name"] for f in patrol["fields"]]
    assert "hover_time" in field_names
    assert "waypoints" in field_names


def test_schema_field_has_required_keys():
    schema = build_schema_response()
    for type_name, entry in schema["actions"].items():
        for field in entry["fields"]:
            assert "name" in field, f"{type_name} field missing 'name'"
            assert "type" in field, f"{type_name}.{field.get('name')} missing 'type'"
            assert "required" in field, (
                f"{type_name}.{field.get('name')} missing 'required'"
            )


def test_schema_waypoints_field_has_object_type():
    schema = build_schema_response()
    patrol_fields = {f["name"]: f for f in schema["actions"]["Patrol"]["fields"]}
    assert patrol_fields["waypoints"]["type"] == "object"
    assert patrol_fields["waypoints"].get("object_type") == "Waypoints"


def test_schema_event_detectionfound():
    schema = build_schema_response()
    assert "DetectionFound" in schema["events"]
    df = schema["events"]["DetectionFound"]
    assert "fields" in df
    field_names = [f["name"] for f in df["fields"]]
    assert "target" in field_names
