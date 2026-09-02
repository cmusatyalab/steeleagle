from app.dslcompiler_client import DslCompilerClient
from steeleagle_protocol.v1.services.dslcompiler import dslcompiler_pb2


class _FakeStub:
    """A fake at the grpc-stub level (not DslCompilerClient level) --
    exercises DslCompilerClient's own request-wrapping logic, distinct
    from FakeDslCompilerClient which fakes the client itself for route
    tests."""

    def __init__(self):
        self.get_schema_calls = 0

    async def GetSchema(self, request):
        self.get_schema_calls += 1
        return dslcompiler_pb2.GetSchemaResponse(default_role="Patrol")

    async def Validate(self, request):
        assert request.mission.start_id == "takeoff"
        return dslcompiler_pb2.ValidateResponse(ok=True)


async def test_get_schema_wraps_request_and_returns_response():
    stub = _FakeStub()
    client = DslCompilerClient(stub)
    resp = await client.get_schema()
    assert resp.default_role == "Patrol"
    assert stub.get_schema_calls == 1


async def test_validate_wraps_mission_into_request():
    stub = _FakeStub()
    client = DslCompilerClient(stub)
    mission = dslcompiler_pb2.MissionGraph(start_id="takeoff")
    resp = await client.validate(mission)
    assert resp.ok is True
