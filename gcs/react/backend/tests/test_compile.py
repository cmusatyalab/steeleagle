from app.api import (
    CompileEdge,
    CompileEvent,
    CompileNode,
    CompileRequest,
    compile_mission,
)


def _minimal_request():
    return CompileRequest(
        nodes=[
            CompileNode(
                instance_id="take_off",
                type_name="TakeOff",
                params={"take_off_altitude": 10.0},
            )
        ],
        events=[],
        edges=[],
        start_id="take_off",
    )


def test_compile_minimal_mission():
    result = compile_mission(_minimal_request())
    assert "mission" in result
    mission = result["mission"]
    assert mission["start_action_id"] == "take_off"
    assert "take_off" in mission["actions"]
    assert mission["actions"]["take_off"]["type_name"] == "TakeOff"


def test_compile_transitions():
    req = CompileRequest(
        nodes=[
            CompileNode(
                instance_id="take_off",
                type_name="TakeOff",
                params={"take_off_altitude": 10.0},
            ),
            CompileNode(
                instance_id="patrol",
                type_name="Patrol",
                params={"waypoints": {"area": "AreaB", "alt": 15.0, "algo": "edge"}},
            ),
        ],
        events=[],
        edges=[
            CompileEdge(source="take_off", event_id="done", target="patrol"),
            CompileEdge(source="patrol", event_id="done", target="patrol"),  # self-loop
        ],
        start_id="take_off",
    )
    result = compile_mission(req)
    assert result["mission"]["transitions"]["take_off"]["done"] == "patrol"
    assert result["mission"]["transitions"]["patrol"]["done"] == "patrol"


def test_compile_with_events():
    req = CompileRequest(
        nodes=[
            CompileNode(
                instance_id="patrol",
                type_name="Patrol",
                params={"waypoints": {"area": "AreaB", "alt": 15.0, "algo": "edge"}},
            ),
            CompileNode(
                instance_id="track",
                type_name="Track",
                params={"target": {"class_name": "person", "score": 60.0}},
            ),
        ],
        events=[
            CompileEvent(
                instance_id="person_seen",
                type_name="DetectionFound",
                params={"target": {"class_name": "person", "score": 60.0}},
            ),
        ],
        edges=[
            CompileEdge(source="patrol", event_id="person_seen", target="track"),
        ],
        start_id="patrol",
    )
    result = compile_mission(req)
    assert "person_seen" in result["mission"]["events"]
    assert result["mission"]["transitions"]["patrol"]["person_seen"] == "track"


def test_compile_unknown_type_name_returns_error():
    req = CompileRequest(
        nodes=[CompileNode(instance_id="foo", type_name="DoesNotExist", params={})],
        events=[],
        edges=[],
        start_id="foo",
    )
    result = compile_mission(req)
    assert "errors" in result
    assert any("DoesNotExist" in e["message"] for e in result["errors"])


def test_compile_invalid_params_returns_error():
    req = CompileRequest(
        nodes=[
            CompileNode(
                instance_id="take_off",
                type_name="TakeOff",
                params={"take_off_altitude": "not_a_number"},
            )
        ],
        events=[],
        edges=[],
        start_id="take_off",
    )
    result = compile_mission(req)
    assert "errors" in result
