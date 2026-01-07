import common_pb2 as _common_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class MissionData(_message.Message):
    __slots__ = ('content', 'map')
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    MAP_FIELD_NUMBER: _ClassVar[int]
    content: str
    map: bytes

    def __init__(self, content: _Optional[str]=..., map: _Optional[bytes]=...) -> None:
        ...

class UploadRequest(_message.Message):
    __slots__ = ('request', 'mission')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    MISSION_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    mission: MissionData

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., mission: _Optional[_Union[MissionData, _Mapping]]=...) -> None:
        ...

class StartRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class StopRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class NotifyRequest(_message.Message):
    __slots__ = ('request', 'notify_code')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    NOTIFY_CODE_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    notify_code: int

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., notify_code: _Optional[int]=...) -> None:
        ...

class ConfigureTelemetryStreamRequest(_message.Message):
    __slots__ = ('request', 'frequency')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    FREQUENCY_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    frequency: int

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., frequency: _Optional[int]=...) -> None:
        ...

class ConfigureTelemetryStreamResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...