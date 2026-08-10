from steeleagle_protocol.v1.messages.result import result_pb2 as _result_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as _telemetry_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetResultRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class GetResultResponse(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: _result_pb2.ComputeResult
    def __init__(self, result: _Optional[_Union[_result_pb2.ComputeResult, _Mapping]] = ...) -> None: ...

class GetTelemetryRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetTelemetryResponse(_message.Message):
    __slots__ = ("telemetry",)
    TELEMETRY_FIELD_NUMBER: _ClassVar[int]
    telemetry: _telemetry_pb2.Telemetry
    def __init__(self, telemetry: _Optional[_Union[_telemetry_pb2.Telemetry, _Mapping]] = ...) -> None: ...

class GetFrameRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetFrameResponse(_message.Message):
    __slots__ = ("frame",)
    FRAME_FIELD_NUMBER: _ClassVar[int]
    frame: _telemetry_pb2.EncodedFrame
    def __init__(self, frame: _Optional[_Union[_telemetry_pb2.EncodedFrame, _Mapping]] = ...) -> None: ...

class StreamVideoFramesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StreamVideoFramesResponse(_message.Message):
    __slots__ = ("frame",)
    FRAME_FIELD_NUMBER: _ClassVar[int]
    frame: _telemetry_pb2.EncodedFrame
    def __init__(self, frame: _Optional[_Union[_telemetry_pb2.EncodedFrame, _Mapping]] = ...) -> None: ...

class StreamTelemetryRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StreamTelemetryResponse(_message.Message):
    __slots__ = ("telemetry",)
    TELEMETRY_FIELD_NUMBER: _ClassVar[int]
    telemetry: _telemetry_pb2.Telemetry
    def __init__(self, telemetry: _Optional[_Union[_telemetry_pb2.Telemetry, _Mapping]] = ...) -> None: ...
