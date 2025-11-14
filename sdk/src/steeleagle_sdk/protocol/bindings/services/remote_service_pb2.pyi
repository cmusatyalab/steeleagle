from google.protobuf import any_pb2 as _any_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class CommandRequest(_message.Message):
    __slots__ = ('sequence_number', 'request', 'method_name', 'identity', 'vehicle_ids')
    SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    METHOD_NAME_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_FIELD_NUMBER: _ClassVar[int]
    VEHICLE_IDS_FIELD_NUMBER: _ClassVar[int]
    sequence_number: int
    request: _any_pb2.Any
    method_name: str
    identity: str
    vehicle_ids: _containers.RepeatedScalarFieldContainer[str]

    def __init__(self, sequence_number: _Optional[int]=..., request: _Optional[_Union[_any_pb2.Any, _Mapping]]=..., method_name: _Optional[str]=..., identity: _Optional[str]=..., vehicle_ids: _Optional[_Iterable[str]]=...) -> None:
        ...

class CommandResponse(_message.Message):
    __slots__ = ('sequence_number', 'response', 'identity')
    SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_FIELD_NUMBER: _ClassVar[int]
    sequence_number: int
    response: _any_pb2.Any
    identity: str

    def __init__(self, sequence_number: _Optional[int]=..., response: _Optional[_Union[_any_pb2.Any, _Mapping]]=..., identity: _Optional[str]=...) -> None:
        ...

class CompileRequest(_message.Message):
    __slots__ = ('dsl', 'vehicle_ids')
    DSL_FIELD_NUMBER: _ClassVar[int]
    VEHICLE_IDS_FIELD_NUMBER: _ClassVar[int]
    dsl: str
    vehicle_ids: _containers.RepeatedScalarFieldContainer[str]

    def __init__(self, dsl: _Optional[str]=..., vehicle_ids: _Optional[_Iterable[str]]=...) -> None:
        ...

class CompileResponse(_message.Message):
    __slots__ = ('success', 'compiled', 'response_string')
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    COMPILED_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_STRING_FIELD_NUMBER: _ClassVar[int]
    success: bool
    compiled: bytes
    response_string: str

    def __init__(self, success: bool=..., compiled: _Optional[bytes]=..., response_string: _Optional[str]=...) -> None:
        ...