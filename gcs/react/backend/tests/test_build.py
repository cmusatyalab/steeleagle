import app.api as api
import pytest
from app.api import (
    BuildMissionRequest,
    CompileNode,
    _build_stream_for_arch,
    build_route,
)
from fastapi import HTTPException
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
        },
    )


def _request(**overrides) -> BuildMissionRequest:
    defaults = dict(
        nodes=[
            CompileNode(
                instance_id="takeoff",
                type_name="TakeOff",
                params={"take_off_altitude": 10.0},
            )
        ],
        events=[],
        edges=[],
        start_id="takeoff",
        arch="amd64",
    )
    defaults.update(overrides)
    return BuildMissionRequest(**defaults)


def _mission() -> dslcompiler_pb2.MissionGraph:
    return dslcompiler_pb2.MissionGraph(start_id="takeoff")


async def test_build_stream_yields_only_requested_arch_bytes():
    chunks = [
        dslcompiler_pb2.BuildChunk(arch="amd64", data=b"AAAA", done=False),
        dslcompiler_pb2.BuildChunk(arch="amd64", data=b"BBBB", done=True),
        dslcompiler_pb2.BuildChunk(arch="arm64", data=b"CCCC", done=True),
    ]
    client = FakeDslCompilerClient(build_chunks=chunks)

    collected = b""
    async for piece in _build_stream_for_arch(client, _mission(), "amd64"):
        collected += piece
    assert collected == b"AAAABBBB"


async def test_build_stream_stops_after_requested_arch_done():
    chunks = [
        dslcompiler_pb2.BuildChunk(arch="amd64", data=b"AAAA", done=True),
        dslcompiler_pb2.BuildChunk(arch="arm64", data=b"CCCC", done=True),
    ]
    client = FakeDslCompilerClient(build_chunks=chunks)

    pieces = [p async for p in _build_stream_for_arch(client, _mission(), "amd64")]
    assert pieces == [b"AAAA"]


async def test_build_stream_raises_on_arch_error_before_yielding():
    chunks = [
        dslcompiler_pb2.BuildChunk(
            arch="amd64",
            errors=[dslcompiler_pb2.CompileError(message="go build failed: ...")],
        ),
    ]
    client = FakeDslCompilerClient(build_chunks=chunks)

    with pytest.raises(HTTPException) as exc_info:
        async for _ in _build_stream_for_arch(client, _mission(), "amd64"):
            pass
    assert exc_info.value.status_code == 422
    assert "go build failed" in str(exc_info.value.detail)


def test_build_mission_request_accepts_arch_field():
    req = BuildMissionRequest(
        nodes=[
            CompileNode(
                instance_id="takeoff", type_name="TakeOff", params={"altitude": 10.0}
            )
        ],
        events=[],
        edges=[],
        start_id="takeoff",
        arch="amd64",
    )
    assert req.arch == "amd64"


async def test_build_route_streams_bytes_for_requested_arch(monkeypatch):
    chunks = [
        dslcompiler_pb2.BuildChunk(arch="amd64", data=b"AAAA", done=False),
        dslcompiler_pb2.BuildChunk(arch="amd64", data=b"BBBB", done=True),
        dslcompiler_pb2.BuildChunk(arch="arm64", data=b"CCCC", done=True),
    ]
    fake = FakeDslCompilerClient(schema=_schema(), build_chunks=chunks)
    monkeypatch.setattr(api, "dslcompiler_client", fake)

    response = await build_route(_request())

    collected = b""
    async for piece in response.body_iterator:
        collected += piece if isinstance(piece, bytes) else piece.encode()
    assert collected == b"AAAABBBB"
    # The mission the fake actually received used the schema's qualified
    # type_name, not the bare name the request sent.
    assert fake.build_calls[0].nodes[0].type_name == "actions.TakeOff"


async def test_build_route_500_when_stream_never_produces_requested_arch(monkeypatch):
    chunks = [
        dslcompiler_pb2.BuildChunk(arch="arm64", data=b"CCCC", done=True),
    ]
    fake = FakeDslCompilerClient(schema=_schema(), build_chunks=chunks)
    monkeypatch.setattr(api, "dslcompiler_client", fake)

    with pytest.raises(HTTPException) as exc_info:
        await build_route(_request(arch="amd64"))
    assert exc_info.value.status_code == 500
