"""A fake DslCompilerClient double for testing api.py's handlers as pure
functions, without a live dslcompiler gRPC server -- see the design
doc's Testing section and this plan's Global Constraints."""

from collections.abc import AsyncIterator

from steeleagle_protocol.v1.services.dslcompiler import dslcompiler_pb2


class FakeDslCompilerClient:
    """Construct with canned return values for whichever methods a test
    exercises; calling a method with no canned value raises AssertionError
    so an unexpected call fails loudly instead of returning None."""

    def __init__(
        self,
        schema: dslcompiler_pb2.GetSchemaResponse | None = None,
        validate_response: dslcompiler_pb2.ValidateResponse | None = None,
        parse_dsl_response: dslcompiler_pb2.ParseDslResponse | None = None,
        build_chunks: list[dslcompiler_pb2.BuildChunk] | None = None,
    ) -> None:
        self._schema = schema
        self._validate_response = validate_response
        self._parse_dsl_response = parse_dsl_response
        self._build_chunks = build_chunks
        self.validate_calls: list[dslcompiler_pb2.MissionGraph] = []
        self.build_calls: list[dslcompiler_pb2.MissionGraph] = []

    async def get_schema(self) -> dslcompiler_pb2.GetSchemaResponse:
        assert self._schema is not None, "FakeDslCompilerClient: no schema configured"
        return self._schema

    async def validate(
        self, mission: dslcompiler_pb2.MissionGraph
    ) -> dslcompiler_pb2.ValidateResponse:
        assert self._validate_response is not None, (
            "FakeDslCompilerClient: no validate_response configured"
        )
        self.validate_calls.append(mission)
        return self._validate_response

    async def parse_dsl(self, dsl: str) -> dslcompiler_pb2.ParseDslResponse:
        assert self._parse_dsl_response is not None, (
            "FakeDslCompilerClient: no parse_dsl_response configured"
        )
        return self._parse_dsl_response

    async def build(
        self, mission: dslcompiler_pb2.MissionGraph
    ) -> AsyncIterator[dslcompiler_pb2.BuildChunk]:
        assert self._build_chunks is not None, (
            "FakeDslCompilerClient: no build_chunks configured"
        )
        self.build_calls.append(mission)
        for chunk in self._build_chunks:
            yield chunk
