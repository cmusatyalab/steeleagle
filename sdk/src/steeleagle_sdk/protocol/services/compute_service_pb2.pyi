from steeleagle_sdk.protocol import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DatasinkLocation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    REMOTE: _ClassVar[DatasinkLocation]
    LOCAL: _ClassVar[DatasinkLocation]

class InputSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SOURCE_UNSPECIFIED: _ClassVar[InputSource]
    DRIVER_TELEMETRY: _ClassVar[InputSource]
    MISSION_TELEMETRY: _ClassVar[InputSource]
    IMAGERY: _ClassVar[InputSource]
REMOTE: DatasinkLocation
LOCAL: DatasinkLocation
SOURCE_UNSPECIFIED: InputSource
DRIVER_TELEMETRY: InputSource
MISSION_TELEMETRY: InputSource
IMAGERY: InputSource

class DatasinkInfo(_message.Message):
    __slots__ = ("id", "location", "sources")
    ID_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    id: str
    location: DatasinkLocation
    sources: _containers.RepeatedScalarFieldContainer[InputSource]
    def __init__(self, id: _Optional[str] = ..., location: _Optional[_Union[DatasinkLocation, str]] = ..., sources: _Optional[_Iterable[_Union[InputSource, str]]] = ...) -> None: ...

class AddDatasinksRequest(_message.Message):
    __slots__ = ("request", "datasinks")
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    datasinks: _containers.RepeatedCompositeFieldContainer[DatasinkInfo]
    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]] = ..., datasinks: _Optional[_Iterable[_Union[DatasinkInfo, _Mapping]]] = ...) -> None: ...

class SetDatasinksRequest(_message.Message):
    __slots__ = ("request", "datasinks")
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    datasinks: _containers.RepeatedCompositeFieldContainer[DatasinkInfo]
    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]] = ..., datasinks: _Optional[_Iterable[_Union[DatasinkInfo, _Mapping]]] = ...) -> None: ...

class RemoveDatasinksRequest(_message.Message):
    __slots__ = ("request", "datasinks")
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    datasinks: _containers.RepeatedCompositeFieldContainer[DatasinkInfo]
    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]] = ..., datasinks: _Optional[_Iterable[_Union[DatasinkInfo, _Mapping]]] = ...) -> None: ...
