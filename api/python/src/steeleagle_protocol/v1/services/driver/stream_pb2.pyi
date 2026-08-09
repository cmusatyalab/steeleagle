from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as _telemetry_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetVideoStreamURLRequest(_message.Message):
    __slots__ = ("resolution",)
    class Resolution(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RESOLUTION_UNSPECIFIED: _ClassVar[GetVideoStreamURLRequest.Resolution]
        RESOLUTION_480P: _ClassVar[GetVideoStreamURLRequest.Resolution]
        RESOLUTION_720P: _ClassVar[GetVideoStreamURLRequest.Resolution]
        RESOLUTION_1080P: _ClassVar[GetVideoStreamURLRequest.Resolution]
        RESOLUTION_4K: _ClassVar[GetVideoStreamURLRequest.Resolution]
    RESOLUTION_UNSPECIFIED: GetVideoStreamURLRequest.Resolution
    RESOLUTION_480P: GetVideoStreamURLRequest.Resolution
    RESOLUTION_720P: GetVideoStreamURLRequest.Resolution
    RESOLUTION_1080P: GetVideoStreamURLRequest.Resolution
    RESOLUTION_4K: GetVideoStreamURLRequest.Resolution
    RESOLUTION_FIELD_NUMBER: _ClassVar[int]
    resolution: GetVideoStreamURLRequest.Resolution
    def __init__(self, resolution: _Optional[_Union[GetVideoStreamURLRequest.Resolution, str]] = ...) -> None: ...

class GetVideoStreamURLResponse(_message.Message):
    __slots__ = ("stream_url", "target_fps")
    STREAM_URL_FIELD_NUMBER: _ClassVar[int]
    TARGET_FPS_FIELD_NUMBER: _ClassVar[int]
    stream_url: str
    target_fps: int
    def __init__(self, stream_url: _Optional[str] = ..., target_fps: _Optional[int] = ...) -> None: ...

class StreamVideoFramesRequest(_message.Message):
    __slots__ = ("target_fps",)
    TARGET_FPS_FIELD_NUMBER: _ClassVar[int]
    target_fps: int
    def __init__(self, target_fps: _Optional[int] = ...) -> None: ...

class StreamVideoFramesResponse(_message.Message):
    __slots__ = ("frame",)
    FRAME_FIELD_NUMBER: _ClassVar[int]
    frame: _telemetry_pb2.EncodedFrame
    def __init__(self, frame: _Optional[_Union[_telemetry_pb2.EncodedFrame, _Mapping]] = ...) -> None: ...

class StreamTelemetryRequest(_message.Message):
    __slots__ = ("target_fps",)
    TARGET_FPS_FIELD_NUMBER: _ClassVar[int]
    target_fps: int
    def __init__(self, target_fps: _Optional[int] = ...) -> None: ...

class StreamTelemetryResponse(_message.Message):
    __slots__ = ("telemetry",)
    TELEMETRY_FIELD_NUMBER: _ClassVar[int]
    telemetry: _telemetry_pb2.Telemetry
    def __init__(self, telemetry: _Optional[_Union[_telemetry_pb2.Telemetry, _Mapping]] = ...) -> None: ...
