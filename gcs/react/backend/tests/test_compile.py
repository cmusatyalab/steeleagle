from app.api import (
    CompileEdge,
    CompileEvent,
    CompileNode,
    CompileRequest,
    compile_mission,
)
from steeleagle_protocol.v1.services.dslcompiler import dslcompiler_pb2
from tests.fake_dslcompiler import FakeDslCompilerClient


def _schema() -> dslcompiler_pb2.GetSchemaResponse:
    return dslcompiler_pb2.GetSchemaResponse(
        actions={
            "actions.TakeOff": dslcompiler_pb2.TypeSchema(
                fields=[
                    dslcompiler_pb2.FieldSchema(
                        name="take_off_altitude", type="number", required=True
                    )
                ]
            ),
            "actions.Patrol": dslcompiler_pb2.TypeSchema(
                fields=[
                    dslcompiler_pb2.FieldSchema(
                        name="waypoints",
                        type="object",
                        required=True,
                        object_type="types.Waypoints",
                        nested_fields=[
                            dslcompiler_pb2.FieldSchema(name="area", type="string"),
                            dslcompiler_pb2.FieldSchema(name="alt", type="number"),
                            dslcompiler_pb2.FieldSchema(name="algo", type="string"),
                        ],
                    )
                ]
            ),
            "actions.Track": dslcompiler_pb2.TypeSchema(
                fields=[
                    dslcompiler_pb2.FieldSchema(
                        name="target",
                        type="object",
                        required=True,
                        object_type="types.Detection",
                        nested_fields=[
                            dslcompiler_pb2.FieldSchema(
                                name="class_name", type="string"
                            ),
                            dslcompiler_pb2.FieldSchema(name="score", type="number"),
                        ],
                    )
                ]
            ),
        },
        events={
            "events.DetectionFound": dslcompiler_pb2.TypeSchema(
                fields=[
                    dslcompiler_pb2.FieldSchema(
                        name="target",
                        type="object",
                        object_type="types.Detection",
                        nested_fields=[
                            dslcompiler_pb2.FieldSchema(
                                name="class_name", type="string"
                            ),
                            dslcompiler_pb2.FieldSchema(name="score", type="number"),
                        ],
                    )
                ]
            )
        },
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


def _ok_client() -> FakeDslCompilerClient:
    return FakeDslCompilerClient(
        validate_response=dslcompiler_pb2.ValidateResponse(ok=True)
    )


async def test_compile_minimal_mission():
    result = await compile_mission(_minimal_request(), _ok_client(), _schema())
    assert "mission" in result
    mission = result["mission"]
    assert mission["start_action_id"] == "take_off"
    assert "take_off" in mission["actions"]
    assert mission["actions"]["take_off"]["type_name"] == "TakeOff"


async def test_compile_sends_qualified_type_name_and_typed_params():
    client = _ok_client()
    await compile_mission(_minimal_request(), client, _schema())
    assert len(client.validate_calls) == 1
    sent = client.validate_calls[0]
    assert sent.nodes[0].type_name == "actions.TakeOff"
    assert sent.nodes[0].params["take_off_altitude"].float_value == 10.0


async def test_compile_nested_object_param_becomes_inline_value():
    req = CompileRequest(
        nodes=[
            CompileNode(
                instance_id="patrol",
                type_name="Patrol",
                params={"waypoints": {"area": "AreaB", "alt": 15.0, "algo": "edge"}},
            )
        ],
        events=[],
        edges=[],
        start_id="patrol",
    )
    client = _ok_client()
    await compile_mission(req, client, _schema())
    sent_params = client.validate_calls[0].nodes[0].params
    waypoints = sent_params["waypoints"]
    assert waypoints.WhichOneof("value") == "inline_value"
    assert waypoints.inline_value.type_name == "types.Waypoints"
    assert waypoints.inline_value.args["area"].string_value == "AreaB"
    assert waypoints.inline_value.args["alt"].float_value == 15.0


async def test_compile_transitions():
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
            CompileEdge(source="patrol", event_id="done", target="patrol"),
        ],
        start_id="take_off",
    )
    result = await compile_mission(req, _ok_client(), _schema())
    assert result["mission"]["transitions"]["take_off"]["done"] == "patrol"
    assert result["mission"]["transitions"]["patrol"]["done"] == "patrol"


async def test_compile_with_events():
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
    result = await compile_mission(req, _ok_client(), _schema())
    assert "person_seen" in result["mission"]["events"]
    assert result["mission"]["transitions"]["patrol"]["person_seen"] == "track"


async def test_compile_unknown_type_name_reports_go_error():
    client = FakeDslCompilerClient(
        validate_response=dslcompiler_pb2.ValidateResponse(
            ok=False,
            errors=[
                dslcompiler_pb2.CompileError(
                    node_id="foo", message='unknown action type "DoesNotExist"'
                )
            ],
        )
    )
    req = CompileRequest(
        nodes=[CompileNode(instance_id="foo", type_name="DoesNotExist", params={})],
        events=[],
        edges=[],
        start_id="foo",
    )
    result = await compile_mission(req, client, _schema())
    assert "errors" in result
    assert any("DoesNotExist" in e["message"] for e in result["errors"])


async def test_compile_invalid_start_id_returns_error():
    req = CompileRequest(
        nodes=[
            CompileNode(
                instance_id="take_off",
                type_name="TakeOff",
                params={"take_off_altitude": 10.0},
            )
        ],
        events=[],
        edges=[],
        start_id="nonexistent",
    )
    result = await compile_mission(req, _ok_client(), _schema())
    assert "errors" in result
    assert any("nonexistent" in e["message"] for e in result["errors"])


async def test_compile_dangling_edge_returns_error():
    req = CompileRequest(
        nodes=[
            CompileNode(
                instance_id="patrol",
                type_name="Patrol",
                params={"waypoints": {"area": "AreaB", "alt": 15.0, "algo": "edge"}},
            )
        ],
        events=[],
        edges=[
            CompileEdge(source="patrol", event_id="done", target="ghost_target"),
        ],
        start_id="patrol",
    )
    result = await compile_mission(req, _ok_client(), _schema())
    assert "errors" in result
    assert any("ghost_target" in e["message"] for e in result["errors"])


async def test_compile_duplicate_instance_id_returns_error():
    req = CompileRequest(
        nodes=[
            CompileNode(
                instance_id="patrol",
                type_name="Patrol",
                params={"waypoints": {"area": "AreaB", "alt": 15.0, "algo": "edge"}},
            ),
            CompileNode(
                instance_id="patrol",
                type_name="TakeOff",
                params={"take_off_altitude": 10.0},
            ),
        ],
        events=[],
        edges=[],
        start_id="patrol",
    )
    result = await compile_mission(req, _ok_client(), _schema())
    assert "errors" in result
    assert any("patrol" in e["message"] for e in result["errors"])
    # Duplicate-id is caught locally, before ever calling Validate.
    assert len(_ok_client().validate_calls) == 0
