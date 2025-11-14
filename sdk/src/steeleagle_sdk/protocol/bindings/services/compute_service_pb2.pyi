import common_pb2 as _common_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class GetAvailableDatasinksRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class Datasink(_message.Message):
    __slots__ = ('name', 'topic', 'model', 'active', 'uptime')
    NAME_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    name: str
    topic: str
    model: str
    active: bool
    uptime: _duration_pb2.Duration

    def __init__(self, name: _Optional[str]=..., topic: _Optional[str]=..., model: _Optional[str]=..., active: bool=..., uptime: _Optional[_Union[_duration_pb2.Duration, _Mapping]]=...) -> None:
        ...

class GetAvailableDatasinksResponse(_message.Message):
    __slots__ = ('response', 'datasinks')
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response
    datasinks: _containers.RepeatedCompositeFieldContainer[Datasink]

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=..., datasinks: _Optional[_Iterable[_Union[Datasink, _Mapping]]]=...) -> None:
        ...

class ConfigureDatasinksRequest(_message.Message):
    __slots__ = ('request', 'name', 'activate')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ACTIVATE_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    name: _containers.RepeatedScalarFieldContainer[str]
    activate: _containers.RepeatedScalarFieldContainer[bool]

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., name: _Optional[_Iterable[str]]=..., activate: _Optional[_Iterable[bool]]=...) -> None:
        ...

class ConfigureDatasinksResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...