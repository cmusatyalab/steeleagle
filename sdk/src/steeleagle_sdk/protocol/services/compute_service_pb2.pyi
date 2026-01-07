import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class DatasinkLocation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    REMOTE: _ClassVar[DatasinkLocation]
    LOCAL: _ClassVar[DatasinkLocation]
REMOTE: DatasinkLocation
LOCAL: DatasinkLocation

class DatasinkInfo(_message.Message):
    __slots__ = ('id', 'location')
    ID_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    id: str
    location: DatasinkLocation

    def __init__(self, id: _Optional[str]=..., location: _Optional[_Union[DatasinkLocation, str]]=...) -> None:
        ...

class AddDatasinksRequest(_message.Message):
    __slots__ = ('request', 'datasinks')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    datasinks: _containers.RepeatedCompositeFieldContainer[DatasinkInfo]

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., datasinks: _Optional[_Iterable[_Union[DatasinkInfo, _Mapping]]]=...) -> None:
        ...

class SetDatasinksRequest(_message.Message):
    __slots__ = ('request', 'datasinks')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    datasinks: _containers.RepeatedCompositeFieldContainer[DatasinkInfo]

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., datasinks: _Optional[_Iterable[_Union[DatasinkInfo, _Mapping]]]=...) -> None:
        ...

class RemoveDatasinksRequest(_message.Message):
    __slots__ = ('request', 'datasinks')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    datasinks: _containers.RepeatedCompositeFieldContainer[DatasinkInfo]

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., datasinks: _Optional[_Iterable[_Union[DatasinkInfo, _Mapping]]]=...) -> None:
        ...