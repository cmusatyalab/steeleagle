import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from steeleagle_protocol.v1.messages.result import result_pb2 as _result_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as _telemetry_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SetDataflowRequest(_message.Message):
    __slots__ = ("toml",)
    TOML_FIELD_NUMBER: _ClassVar[int]
    toml: bytes
    def __init__(self, toml: _Optional[bytes] = ...) -> None: ...

class SetDataflowResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetFlowRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetFlowResponse(_message.Message):
    __slots__ = ("toml",)
    TOML_FIELD_NUMBER: _ClassVar[int]
    toml: bytes
    def __init__(self, toml: _Optional[bytes] = ...) -> None: ...

class GetResultRequest(_message.Message):
    __slots__ = ("engine", "time_start", "time_end")
    ENGINE_FIELD_NUMBER: _ClassVar[int]
    TIME_START_FIELD_NUMBER: _ClassVar[int]
    TIME_END_FIELD_NUMBER: _ClassVar[int]
    engine: str
    time_start: _timestamp_pb2.Timestamp
    time_end: _timestamp_pb2.Timestamp
    def __init__(self, engine: _Optional[str] = ..., time_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., time_end: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetResultResponse(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: _containers.RepeatedCompositeFieldContainer[_result_pb2.ComputeResult]
    def __init__(self, result: _Optional[_Iterable[_Union[_result_pb2.ComputeResult, _Mapping]]] = ...) -> None: ...

class GetTelemetryRequest(_message.Message):
    __slots__ = ("time_start", "time_end")
    TIME_START_FIELD_NUMBER: _ClassVar[int]
    TIME_END_FIELD_NUMBER: _ClassVar[int]
    time_start: _timestamp_pb2.Timestamp
    time_end: _timestamp_pb2.Timestamp
    def __init__(self, time_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., time_end: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetTelemetryResponse(_message.Message):
    __slots__ = ("telemetry",)
    TELEMETRY_FIELD_NUMBER: _ClassVar[int]
    telemetry: _containers.RepeatedCompositeFieldContainer[_telemetry_pb2.Telemetry]
    def __init__(self, telemetry: _Optional[_Iterable[_Union[_telemetry_pb2.Telemetry, _Mapping]]] = ...) -> None: ...
