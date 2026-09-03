import pytest
from app.api import parse_dsl_response_to_dict
from fastapi import HTTPException
from steeleagle_protocol.v1.services.dslcompiler import dslcompiler_pb2


def test_parse_dsl_translates_nodes_events_edges():
    mission = dslcompiler_pb2.MissionGraph(
        nodes=[
            dslcompiler_pb2.Node(
                instance_id="takeoff", type_name="actions.TakeOff", params={}
            ),
            dslcompiler_pb2.Node(
                instance_id="gimbal",
                type_name="actions.SetGimbalPose",
                params={
                    "Pose": dslcompiler_pb2.FieldValue(
                        inline_value=dslcompiler_pb2.InlineCtorValue(
                            type_name="types.Pose",
                            args={
                                "Pitch": dslcompiler_pb2.FieldValue(float_value=-30.0),
                                "Yaw": dslcompiler_pb2.FieldValue(float_value=0.0),
                            },
                        )
                    ),
                    "AngleMode": dslcompiler_pb2.FieldValue(
                        ident_ref="enums.AngleModeAbsolute"
                    ),
                },
            ),
        ],
        events=[],
        edges=[
            dslcompiler_pb2.Edge(source="takeoff", event_id="done", target="gimbal")
        ],
        start_id="takeoff",
        role="explorer",
        imports=[
            dslcompiler_pb2.ImportSpec(
                alias="", path="github.com/cmusatyalab/steeleagle/sdk/enums", version=""
            )
        ],
    )
    resp = dslcompiler_pb2.ParseDslResponse(ok=True, mission=mission)

    result = parse_dsl_response_to_dict(resp)

    assert result["start_id"] == "takeoff"
    assert result["nodes"][1]["type_name"] == "SetGimbalPose"
    assert result["nodes"][1]["params"]["Pose"] == {"Pitch": -30.0, "Yaw": 0.0}
    assert result["nodes"][1]["params"]["AngleMode"] == "enums.AngleModeAbsolute"
    assert result["edges"] == [
        {"source": "takeoff", "event_id": "done", "target": "gimbal"}
    ]
    assert result["role"] == "explorer"
    assert result["imports"] == [
        {
            "alias": "",
            "path": "github.com/cmusatyalab/steeleagle/sdk/enums",
            "version": "",
        }
    ]


def test_parse_dsl_syntax_error_raises_http_exception():
    resp = dslcompiler_pb2.ParseDslResponse(
        ok=False,
        errors=[dslcompiler_pb2.CompileError(message="unexpected token at line 3")],
    )
    with pytest.raises(HTTPException) as exc_info:
        parse_dsl_response_to_dict(resp)
    assert exc_info.value.status_code == 422
    assert "unexpected token" in exc_info.value.detail
