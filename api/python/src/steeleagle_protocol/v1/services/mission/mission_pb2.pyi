from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MissionHeader(_message.Message):
    __slots__ = ("arch", "size", "sha256")
    ARCH_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    arch: str
    size: int
    sha256: bytes
    def __init__(self, arch: _Optional[str] = ..., size: _Optional[int] = ..., sha256: _Optional[bytes] = ...) -> None: ...

class UploadMissionRequest(_message.Message):
    __slots__ = ("header", "chunk")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    header: MissionHeader
    chunk: bytes
    def __init__(self, header: _Optional[_Union[MissionHeader, _Mapping]] = ..., chunk: _Optional[bytes] = ...) -> None: ...

class UploadMissionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMissionInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMissionInfoResponse(_message.Message):
    __slots__ = ("arch",)
    ARCH_FIELD_NUMBER: _ClassVar[int]
    arch: str
    def __init__(self, arch: _Optional[str] = ...) -> None: ...

class StartMissionRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StartMissionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StopMissionRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StopMissionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
