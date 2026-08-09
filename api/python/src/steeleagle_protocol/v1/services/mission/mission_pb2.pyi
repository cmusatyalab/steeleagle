from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MissionData(_message.Message):
    __slots__ = ("json", "binary", "map")
    JSON_FIELD_NUMBER: _ClassVar[int]
    BINARY_FIELD_NUMBER: _ClassVar[int]
    MAP_FIELD_NUMBER: _ClassVar[int]
    json: str
    binary: bytes
    map: bytes
    def __init__(self, json: _Optional[str] = ..., binary: _Optional[bytes] = ..., map: _Optional[bytes] = ...) -> None: ...

class UploadMissionRequest(_message.Message):
    __slots__ = ("mission",)
    MISSION_FIELD_NUMBER: _ClassVar[int]
    mission: MissionData
    def __init__(self, mission: _Optional[_Union[MissionData, _Mapping]] = ...) -> None: ...

class UploadMissionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

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
