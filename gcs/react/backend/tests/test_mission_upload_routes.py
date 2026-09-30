import io
import json

import grpc
import httpx
import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from steeleagle_protocol.v1.services.dslcompiler import dslcompiler_pb2

import app.dslcompiler_routes as dslcompiler_routes
import app.mission_upload_routes as routes
from app.mission_binary import MAX_MISSION_SIZE
from app.mission_upload_routes import (
    DeployRequest,
    deploy_events,
    deploy_route,
    upload_events,
    upload_route,
    variants_from_files,
)
from tests.elf_fixtures import EM_AARCH64, EM_X86_64, fake_elf
from tests.fake_dslcompiler import FakeDslCompilerClient

AMD = fake_elf(EM_X86_64, 200)
ARM = fake_elf(EM_AARCH64, 100)


class FakeSwarm:
    """Stands in for SwarmClient.upload_mission."""

    def __init__(self, events=None, error: grpc.aio.AioRpcError | None = None):
        self._events = events or []
        self._error = error
        self.calls: list[tuple[list[str], dict[str, bytes]]] = []

    async def upload_mission(self, vehicles, variants):
        self.calls.append((vehicles, variants))
        if self._error is not None:
            raise self._error
        for e in self._events:
            yield e


def _rpc_error(details="controller down") -> grpc.aio.AioRpcError:
    return grpc.aio.AioRpcError(
        grpc.StatusCode.UNAVAILABLE,
        grpc.aio.Metadata(),
        grpc.aio.Metadata(),
        details=details,
    )


async def _collect(gen) -> list[dict]:
    return [e async for e in gen]


async def _ndjson_lines(response) -> list[dict]:
    body = "".join([chunk async for chunk in response.body_iterator])
    assert body.endswith("\n")
    return [json.loads(line) for line in body.splitlines()]


def _result(vehicle, success=True, details=""):
    return {
        "type": "result",
        "vehicle": vehicle,
        "success": success,
        "details": details,
    }


def _asgi_client() -> httpx.AsyncClient:
    """A real ASGI-level client for routes.router, so multipart/form parsing
    goes through FastAPI's actual request handling instead of calling the
    route function directly with pre-built UploadFile objects."""
    app = FastAPI()
    app.include_router(routes.router)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


# --- variants_from_files -----------------------------------------------------


def test_variants_from_files_maps_by_elf_arch():
    assert variants_from_files([("a.bin", AMD), ("b.bin", ARM)]) == {
        "amd64": AMD,
        "arm64": ARM,
    }


def test_variants_from_files_ignores_filename():
    assert variants_from_files([("mission", ARM)]) == {"arm64": ARM}
    assert variants_from_files([("mission-amd64.txt", ARM)]) == {"arm64": ARM}


@pytest.mark.parametrize(
    "files, fragment",
    [
        ([], "at least one"),
        ([("a", AMD), ("b", ARM), ("c", AMD)], "At most two"),
        (
            [("a", AMD), ("b", fake_elf(EM_X86_64, 300))],
            "Two files were built for amd64",
        ),
        ([("notes.txt", b"hello there, not a binary")], "notes.txt: not an ELF"),
    ],
)
def test_variants_from_files_rejects(files, fragment):
    with pytest.raises(HTTPException) as exc:
        variants_from_files(files)
    assert exc.value.status_code == 400
    assert fragment in exc.value.detail


def test_max_mission_size_is_128_mib():
    assert MAX_MISSION_SIZE == 128 * 1024 * 1024


def test_variants_from_files_rejects_oversize(monkeypatch):
    # Shrink the limit rather than allocating 128 MiB in a unit test.
    monkeypatch.setattr(routes, "MAX_MISSION_SIZE", 1024 * 1024)
    big = AMD + bytes(1024 * 1024)
    with pytest.raises(HTTPException) as exc:
        variants_from_files([("huge.bin", big)])
    assert exc.value.status_code == 400
    assert "huge.bin is larger than the 1 MiB limit" in exc.value.detail


# --- upload_events / upload_route ---------------------------------------------


async def test_upload_events_relays_after_stage():
    swarm = FakeSwarm(events=[_result("drone1")])

    events = await _collect(upload_events(swarm, ["drone1"], {"amd64": AMD}))

    assert events == [{"type": "stage", "stage": "uploading"}, _result("drone1")]
    assert swarm.calls == [(["drone1"], {"amd64": AMD})]


async def test_upload_events_rpc_failure_is_terminal_error_line():
    events = await _collect(
        upload_events(FakeSwarm(error=_rpc_error()), ["d"], {"amd64": AMD})
    )

    assert events[-1]["type"] == "error"
    assert "UNAVAILABLE" in events[-1]["detail"]
    assert "controller down" in events[-1]["detail"]


async def test_upload_route_streams_ndjson(monkeypatch):
    swarm = FakeSwarm(events=[_result("drone1")])
    monkeypatch.setattr(routes, "_swarm_client_provider", lambda: swarm)

    response = await upload_route(
        files=[UploadFile(file=io.BytesIO(AMD), filename="mission-amd64")],
        vehicles=["drone1"],
    )

    assert response.media_type == "application/x-ndjson"
    assert await _ndjson_lines(response) == [
        {"type": "stage", "stage": "uploading"},
        _result("drone1"),
    ]


async def test_upload_route_requires_vehicles(monkeypatch):
    swarm = FakeSwarm()
    monkeypatch.setattr(routes, "_swarm_client_provider", lambda: swarm)

    with pytest.raises(HTTPException) as exc:
        await upload_route(
            files=[UploadFile(file=io.BytesIO(AMD), filename="m")], vehicles=[]
        )

    assert exc.value.status_code == 400
    assert swarm.calls == []


async def test_upload_route_rejects_too_many_files_before_reading(monkeypatch):
    swarm = FakeSwarm()
    monkeypatch.setattr(routes, "_swarm_client_provider", lambda: swarm)
    read_calls: list[str] = []

    class SpyFile:
        def __init__(self, filename, data):
            self.filename = filename
            self._data = data

        async def read(self, n=-1):
            read_calls.append(self.filename)
            return self._data

    files = [SpyFile("a", AMD), SpyFile("b", ARM), SpyFile("c", AMD)]

    with pytest.raises(HTTPException) as exc:
        await upload_route(files=files, vehicles=["drone1"])

    assert exc.value.status_code == 400
    assert "At most two" in exc.value.detail
    assert read_calls == []
    assert swarm.calls == []


async def test_upload_route_503_before_setup(monkeypatch):
    monkeypatch.setattr(routes, "_swarm_client_provider", None)

    with pytest.raises(HTTPException) as exc:
        await upload_route(
            files=[UploadFile(file=io.BytesIO(AMD), filename="m")], vehicles=["d"]
        )

    assert exc.value.status_code == 503


async def test_upload_events_non_grpc_exception_is_terminal_error_line():
    class BoomSwarm:
        async def upload_mission(self, vehicles, variants):
            yield {"type": "progress", "vehicle": "d", "sent": 0, "total": 10}
            raise RuntimeError("boom")

    events = await _collect(upload_events(BoomSwarm(), ["d"], {"amd64": AMD}))

    assert events[0] == {"type": "stage", "stage": "uploading"}
    assert events[1]["type"] == "progress"
    assert len(events) == 3
    assert events[-1]["type"] == "error"
    assert "boom" in events[-1]["detail"]


# --- ASGI-level tests (real HTTP layer) ----------------------------------------


async def test_upload_asgi_no_files_is_400():
    routes.setup(lambda: FakeSwarm())
    try:
        async with _asgi_client() as client:
            response = await client.post("/api/upload", data={"vehicles": ["drone1"]})
        assert response.status_code == 400
        assert "at least one mission binary" in response.json()["detail"]
    finally:
        routes.setup(None)


async def test_upload_asgi_streams_ndjson_with_repeated_vehicle_fields():
    swarm = FakeSwarm(events=[_result("drone1"), _result("drone2")])
    routes.setup(lambda: swarm)
    try:
        async with _asgi_client() as client:
            response = await client.post(
                "/api/upload",
                data={"vehicles": ["drone1", "drone2"]},
                files={"files": ("mission", AMD, "application/octet-stream")},
            )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        lines = [json.loads(line) for line in response.text.splitlines()]
        assert lines[0] == {"type": "stage", "stage": "uploading"}
        assert lines[1:] == [_result("drone1"), _result("drone2")]
        assert swarm.calls == [(["drone1", "drone2"], {"amd64": AMD})]
    finally:
        routes.setup(None)


# --- deploy -------------------------------------------------------------------


def _chunks_ok():
    return [
        dslcompiler_pb2.BuildChunk(arch="amd64", data=AMD[:100]),
        dslcompiler_pb2.BuildChunk(arch="arm64", data=ARM, done=True),
        dslcompiler_pb2.BuildChunk(arch="amd64", data=AMD[100:], done=True),
    ]


async def test_deploy_events_builds_then_uploads_all_archs():
    dsl = FakeDslCompilerClient(build_chunks=_chunks_ok())
    swarm = FakeSwarm(events=[_result("drone1")])
    mission = dslcompiler_pb2.MissionGraph(start_id="takeoff")

    events = await _collect(deploy_events(dsl, swarm, mission, b'{"x":1}', ["drone1"]))

    assert events == [
        {"type": "stage", "stage": "building"},
        {"type": "stage", "stage": "uploading"},
        _result("drone1"),
    ]
    assert swarm.calls == [(["drone1"], {"amd64": AMD, "arm64": ARM})]
    assert dsl.build_geojson_calls == [b'{"x":1}']


async def test_deploy_events_build_error_stops_before_upload():
    dsl = FakeDslCompilerClient(
        build_chunks=[
            dslcompiler_pb2.BuildChunk(arch="amd64", data=AMD, done=True),
            dslcompiler_pb2.BuildChunk(
                arch="arm64",
                errors=[
                    dslcompiler_pb2.CompileError(node_id="patrol", message="bad area")
                ],
            ),
        ]
    )
    swarm = FakeSwarm()

    events = await _collect(
        deploy_events(dsl, swarm, dslcompiler_pb2.MissionGraph(), b"", ["drone1"])
    )

    assert events[0] == {"type": "stage", "stage": "building"}
    assert events[-1]["type"] == "error"
    assert "arm64" in events[-1]["detail"] and "bad area" in events[-1]["detail"]
    assert events[-1]["errors"] == [
        {"node_id": "patrol", "event_id": None, "message": "bad area"}
    ]
    assert len(events) == 2
    assert swarm.calls == []


async def test_deploy_events_non_grpc_build_exception_is_terminal_error_line():
    class BoomDsl:
        async def build(self, mission, geojson=b""):
            yield dslcompiler_pb2.BuildChunk(arch="amd64", data=AMD[:10])
            raise RuntimeError("boom")

    events = await _collect(
        deploy_events(
            BoomDsl(), FakeSwarm(), dslcompiler_pb2.MissionGraph(), b"", ["d"]
        )
    )

    assert events[0] == {"type": "stage", "stage": "building"}
    assert events[-1]["type"] == "error"
    assert "boom" in events[-1]["detail"]
    assert len(events) == 2


async def test_deploy_events_empty_build_is_error():
    events = await _collect(
        deploy_events(
            FakeDslCompilerClient(build_chunks=[]),
            FakeSwarm(),
            dslcompiler_pb2.MissionGraph(),
            b"",
            ["d"],
        )
    )

    assert events[-1] == {"type": "error", "detail": "Build produced no binaries"}


async def test_deploy_route_streams_ndjson(monkeypatch):
    schema = dslcompiler_pb2.GetSchemaResponse(
        actions={"actions.TakeOff": dslcompiler_pb2.TypeSchema()}
    )
    dsl = FakeDslCompilerClient(schema=schema, build_chunks=_chunks_ok())
    swarm = FakeSwarm(events=[_result("drone1")])
    monkeypatch.setattr(dslcompiler_routes, "_client", dsl)
    monkeypatch.setattr(routes, "_swarm_client_provider", lambda: swarm)

    response = await deploy_route(
        DeployRequest(
            nodes=[{"instance_id": "takeoff", "type_name": "TakeOff", "params": {}}],
            events=[],
            edges=[],
            start_id="takeoff",
            vehicles=["drone1"],
        )
    )

    lines = await _ndjson_lines(response)
    assert lines[0] == {"type": "stage", "stage": "building"}
    assert lines[-1] == _result("drone1")
    assert dsl.build_calls[0].nodes[0].type_name == "actions.TakeOff"


async def test_deploy_route_requires_vehicles(monkeypatch):
    monkeypatch.setattr(routes, "_swarm_client_provider", lambda: FakeSwarm())

    with pytest.raises(HTTPException) as exc:
        await deploy_route(
            DeployRequest(nodes=[], events=[], edges=[], start_id="x", vehicles=[])
        )

    assert exc.value.status_code == 400
