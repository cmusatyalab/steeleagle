import common_pb2 as _common_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class CompileMissionRequest(_message.Message):
    __slots__ = ('dsl_content',)
    DSL_CONTENT_FIELD_NUMBER: _ClassVar[int]
    dsl_content: str

    def __init__(self, dsl_content: _Optional[str]=...) -> None:
        ...

class CompileMissionResponse(_message.Message):
    __slots__ = ('compiled_dsl_content', 'response')
    COMPILED_DSL_CONTENT_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    compiled_dsl_content: str
    response: _common_pb2.Response

    def __init__(self, compiled_dsl_content: _Optional[str]=..., response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class CommandRequest(_message.Message):
    __slots__ = ('sequence_number', 'request', 'method_name', 'identity', 'vehicle_id')
    SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    METHOD_NAME_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_FIELD_NUMBER: _ClassVar[int]
    VEHICLE_ID_FIELD_NUMBER: _ClassVar[int]
    sequence_number: int
    request: _any_pb2.Any
    method_name: str
    identity: str
    vehicle_id: str

    def __init__(self, sequence_number: _Optional[int]=..., request: _Optional[_Union[_any_pb2.Any, _Mapping]]=..., method_name: _Optional[str]=..., identity: _Optional[str]=..., vehicle_id: _Optional[str]=...) -> None:
        ...

class CommandResponse(_message.Message):
    __slots__ = ('sequence_number', 'response')
    SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    sequence_number: int
    response: _common_pb2.Response

    def __init__(self, sequence_number: _Optional[int]=..., response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...