from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Resolution(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESOLUTION_UNSPECIFIED: _ClassVar[Resolution]
    RESOLUTION_360P: _ClassVar[Resolution]
    RESOLUTION_480P: _ClassVar[Resolution]
    RESOLUTION_720P: _ClassVar[Resolution]
    RESOLUTION_1080P: _ClassVar[Resolution]
    RESOLUTION_4K: _ClassVar[Resolution]
RESOLUTION_UNSPECIFIED: Resolution
RESOLUTION_360P: Resolution
RESOLUTION_480P: Resolution
RESOLUTION_720P: Resolution
RESOLUTION_1080P: Resolution
RESOLUTION_4K: Resolution

class CameraRequest(_message.Message):
    __slots__ = ("id", "target_fps", "target_resolution", "uri")
    ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_FPS_FIELD_NUMBER: _ClassVar[int]
    TARGET_RESOLUTION_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    id: str
    target_fps: int
    target_resolution: Resolution
    uri: str
    def __init__(self, id: _Optional[str] = ..., target_fps: _Optional[int] = ..., target_resolution: _Optional[_Union[Resolution, str]] = ..., uri: _Optional[str] = ...) -> None: ...

class StreamCamerasRequest(_message.Message):
    __slots__ = ("primary", "secondaries")
    PRIMARY_FIELD_NUMBER: _ClassVar[int]
    SECONDARIES_FIELD_NUMBER: _ClassVar[int]
    primary: CameraRequest
    secondaries: _containers.RepeatedCompositeFieldContainer[CameraRequest]
    def __init__(self, primary: _Optional[_Union[CameraRequest, _Mapping]] = ..., secondaries: _Optional[_Iterable[_Union[CameraRequest, _Mapping]]] = ...) -> None: ...

class StreamCamerasResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StreamTelemetryRequest(_message.Message):
    __slots__ = ("target_fps", "uri")
    TARGET_FPS_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    target_fps: int
    uri: str
    def __init__(self, target_fps: _Optional[int] = ..., uri: _Optional[str] = ...) -> None: ...

class StreamTelemetryResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
