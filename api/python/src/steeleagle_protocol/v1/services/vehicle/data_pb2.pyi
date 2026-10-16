import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from steeleagle_protocol.v1.messages.result import result_pb2 as _result_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as _telemetry_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StreamType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STREAM_TYPE_UNSPECIFIED: _ClassVar[StreamType]
    STREAM_TYPE_TELEMETRY: _ClassVar[StreamType]
    STREAM_TYPE_VIDEO: _ClassVar[StreamType]
    STREAM_TYPE_SENSOR: _ClassVar[StreamType]
    STREAM_TYPE_METRICS: _ClassVar[StreamType]
    STREAM_TYPE_MISSION: _ClassVar[StreamType]
STREAM_TYPE_UNSPECIFIED: StreamType
STREAM_TYPE_TELEMETRY: StreamType
STREAM_TYPE_VIDEO: StreamType
STREAM_TYPE_SENSOR: StreamType
STREAM_TYPE_METRICS: StreamType
STREAM_TYPE_MISSION: StreamType

class SetDataflowRequest(_message.Message):
    __slots__ = ("name", "toml")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TOML_FIELD_NUMBER: _ClassVar[int]
    name: str
    toml: bytes
    def __init__(self, name: _Optional[str] = ..., toml: _Optional[bytes] = ...) -> None: ...

class SetDataflowResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RevertToDefaultDataflowRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RevertToDefaultDataflowResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetResultRequest(_message.Message):
    __slots__ = ("name", "time_start", "time_end")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TIME_START_FIELD_NUMBER: _ClassVar[int]
    TIME_END_FIELD_NUMBER: _ClassVar[int]
    name: str
    time_start: _timestamp_pb2.Timestamp
    time_end: _duration_pb2.Duration
    def __init__(self, name: _Optional[str] = ..., time_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., time_end: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

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
    time_end: _duration_pb2.Duration
    def __init__(self, time_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., time_end: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class GetTelemetryResponse(_message.Message):
    __slots__ = ("telemetry",)
    TELEMETRY_FIELD_NUMBER: _ClassVar[int]
    telemetry: _telemetry_pb2.Telemetry
    def __init__(self, telemetry: _Optional[_Union[_telemetry_pb2.Telemetry, _Mapping]] = ...) -> None: ...

class StreamInfo(_message.Message):
    __slots__ = ("uri", "type", "active")
    URI_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    uri: str
    type: StreamType
    active: bool
    def __init__(self, uri: _Optional[str] = ..., type: _Optional[_Union[StreamType, str]] = ..., active: _Optional[bool] = ...) -> None: ...

class GetStreamInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetStreamInfoResponse(_message.Message):
    __slots__ = ("info",)
    INFO_FIELD_NUMBER: _ClassVar[int]
    info: _containers.RepeatedCompositeFieldContainer[StreamInfo]
    def __init__(self, info: _Optional[_Iterable[_Union[StreamInfo, _Mapping]]] = ...) -> None: ...
