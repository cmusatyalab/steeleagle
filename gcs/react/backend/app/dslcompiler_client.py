from collections.abc import AsyncIterator

from steeleagle_protocol.v1.services.dslcompiler import (
    dslcompiler_pb2,
    dslcompiler_pb2_grpc,
)


class DslCompilerClient:
    """Thin wrapper over DslCompilerServiceStub: one typed method per RPC,
    mirroring swarm_client.SwarmClient's pattern for the swarm service."""

    def __init__(self, stub: dslcompiler_pb2_grpc.DslCompilerServiceStub) -> None:
        self._stub = stub

    async def get_schema(self) -> dslcompiler_pb2.GetSchemaResponse:
        return await self._stub.GetSchema(dslcompiler_pb2.GetSchemaRequest())

    async def validate(
        self, mission: dslcompiler_pb2.MissionGraph
    ) -> dslcompiler_pb2.ValidateResponse:
        return await self._stub.Validate(
            dslcompiler_pb2.ValidateRequest(mission=mission)
        )

    async def parse_dsl(self, dsl: str) -> dslcompiler_pb2.ParseDslResponse:
        return await self._stub.ParseDsl(dslcompiler_pb2.ParseDslRequest(dsl=dsl))

    def build(
        self, mission: dslcompiler_pb2.MissionGraph
    ) -> AsyncIterator[dslcompiler_pb2.BuildChunk]:
        """Returns an async iterator of BuildChunk immediately (no await
        here) -- matches grpc.aio's unary_stream call semantics, same as
        swarm_client's _collect_stream(self._stub.SwarmStartMission(...))
        pattern."""
        return self._stub.Build(dslcompiler_pb2.BuildRequest(mission=mission))
