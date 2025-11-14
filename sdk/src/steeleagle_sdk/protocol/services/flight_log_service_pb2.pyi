import common_pb2 as _common_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class LogType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DEBUG: _ClassVar[LogType]
    INFO: _ClassVar[LogType]
    PROTO: _ClassVar[LogType]
    WARNING: _ClassVar[LogType]
    ERROR: _ClassVar[LogType]
    CRITICAL: _ClassVar[LogType]
DEBUG: LogType
INFO: LogType
PROTO: LogType
WARNING: LogType
ERROR: LogType
CRITICAL: LogType

class LogRequest(_message.Message):
    __slots__ = ('request', 'topic', 'log')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    LOG_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    topic: str
    log: LogMessage

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., topic: _Optional[str]=..., log: _Optional[_Union[LogMessage, _Mapping]]=...) -> None:
        ...

class LogMessage(_message.Message):
    __slots__ = ('type', 'msg')
    TYPE_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    type: LogType
    msg: str

    def __init__(self, type: _Optional[_Union[LogType, str]]=..., msg: _Optional[str]=...) -> None:
        ...

class ReqRepProto(_message.Message):
    __slots__ = ('request', 'response', 'name', 'content')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    response: _common_pb2.Response
    name: str
    content: str

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., response: _Optional[_Union[_common_pb2.Response, _Mapping]]=..., name: _Optional[str]=..., content: _Optional[str]=...) -> None:
        ...

class LogProtoRequest(_message.Message):
    __slots__ = ('request', 'topic', 'reqrep_proto')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    REQREP_PROTO_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    topic: str
    reqrep_proto: ReqRepProto

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., topic: _Optional[str]=..., reqrep_proto: _Optional[_Union[ReqRepProto, _Mapping]]=...) -> None:
        ...