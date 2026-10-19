import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UploadMissionRequest(_message.Message):
    __slots__ = ("name", "chunk", "number", "total")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    name: str
    chunk: bytes
    number: int
    total: int
    def __init__(self, name: _Optional[str] = ..., chunk: _Optional[bytes] = ..., number: _Optional[int] = ..., total: _Optional[int] = ...) -> None: ...

class UploadMissionResponse(_message.Message):
    __slots__ = ("received",)
    RECEIVED_FIELD_NUMBER: _ClassVar[int]
    received: int
    def __init__(self, received: _Optional[int] = ...) -> None: ...

class LoadMissionRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class LoadMissionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MissionInfo(_message.Message):
    __slots__ = ("name", "hash", "creation_time")
    NAME_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    CREATION_TIME_FIELD_NUMBER: _ClassVar[int]
    name: str
    hash: str
    creation_time: _timestamp_pb2.Timestamp
    def __init__(self, name: _Optional[str] = ..., hash: _Optional[str] = ..., creation_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetMissionsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMissionsResponse(_message.Message):
    __slots__ = ("active_mission", "missions")
    ACTIVE_MISSION_FIELD_NUMBER: _ClassVar[int]
    MISSIONS_FIELD_NUMBER: _ClassVar[int]
    active_mission: MissionInfo
    missions: _containers.RepeatedCompositeFieldContainer[MissionInfo]
    def __init__(self, active_mission: _Optional[_Union[MissionInfo, _Mapping]] = ..., missions: _Optional[_Iterable[_Union[MissionInfo, _Mapping]]] = ...) -> None: ...
