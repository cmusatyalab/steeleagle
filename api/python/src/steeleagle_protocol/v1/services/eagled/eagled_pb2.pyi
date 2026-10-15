import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ServiceCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SERVICE_CATEGORY_UNSPECIFIED: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_VEHICLE: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_ENGINE: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_MONITOR: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_EXTRA: _ClassVar[ServiceCategory]
SERVICE_CATEGORY_UNSPECIFIED: ServiceCategory
SERVICE_CATEGORY_VEHICLE: ServiceCategory
SERVICE_CATEGORY_ENGINE: ServiceCategory
SERVICE_CATEGORY_MONITOR: ServiceCategory
SERVICE_CATEGORY_EXTRA: ServiceCategory

class ConfigureRequest(_message.Message):
    __slots__ = ("config_toml",)
    CONFIG_TOML_FIELD_NUMBER: _ClassVar[int]
    config_toml: str
    def __init__(self, config_toml: _Optional[str] = ...) -> None: ...

class ConfigureResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ServiceRequest(_message.Message):
    __slots__ = ("short_name", "url", "category")
    SHORT_NAME_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    short_name: str
    url: str
    category: ServiceCategory
    def __init__(self, short_name: _Optional[str] = ..., url: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ...) -> None: ...

class StartServicesRequest(_message.Message):
    __slots__ = ("services",)
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[ServiceRequest]
    def __init__(self, services: _Optional[_Iterable[_Union[ServiceRequest, _Mapping]]] = ...) -> None: ...

class StartServicesResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StopServicesRequest(_message.Message):
    __slots__ = ("services",)
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[ServiceRequest]
    def __init__(self, services: _Optional[_Iterable[_Union[ServiceRequest, _Mapping]]] = ...) -> None: ...

class StopServicesResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AvailableService(_message.Message):
    __slots__ = ("short_name", "url", "tag", "category", "running", "uptime")
    SHORT_NAME_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    short_name: str
    url: str
    tag: str
    category: ServiceCategory
    running: bool
    uptime: _duration_pb2.Duration
    def __init__(self, short_name: _Optional[str] = ..., url: _Optional[str] = ..., tag: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ..., running: _Optional[bool] = ..., uptime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class ListServicesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListServicesResponse(_message.Message):
    __slots__ = ("services",)
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[AvailableService]
    def __init__(self, services: _Optional[_Iterable[_Union[AvailableService, _Mapping]]] = ...) -> None: ...

class InstallPluginRequest(_message.Message):
    __slots__ = ("url", "tag", "category")
    URL_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    url: str
    tag: str
    category: ServiceCategory
    def __init__(self, url: _Optional[str] = ..., tag: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ...) -> None: ...

class InstallPluginResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RemovePluginRequest(_message.Message):
    __slots__ = ("short_name", "url", "category")
    SHORT_NAME_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    short_name: str
    url: str
    category: ServiceCategory
    def __init__(self, short_name: _Optional[str] = ..., url: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ...) -> None: ...

class RemovePluginResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ResetConfigurationRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ResetConfigurationResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StreamLogsRequest(_message.Message):
    __slots__ = ("sources", "tail", "follow", "after_seq")
    class AfterSeqEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    TAIL_FIELD_NUMBER: _ClassVar[int]
    FOLLOW_FIELD_NUMBER: _ClassVar[int]
    AFTER_SEQ_FIELD_NUMBER: _ClassVar[int]
    sources: _containers.RepeatedScalarFieldContainer[str]
    tail: int
    follow: bool
    after_seq: _containers.ScalarMap[str, int]
    def __init__(self, sources: _Optional[_Iterable[str]] = ..., tail: _Optional[int] = ..., follow: _Optional[bool] = ..., after_seq: _Optional[_Mapping[str, int]] = ...) -> None: ...

class StreamLogsResponse(_message.Message):
    __slots__ = ("source", "seq", "time", "level", "text", "dropped")
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    SEQ_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    DROPPED_FIELD_NUMBER: _ClassVar[int]
    source: str
    seq: int
    time: _timestamp_pb2.Timestamp
    level: str
    text: str
    dropped: int
    def __init__(self, source: _Optional[str] = ..., seq: _Optional[int] = ..., time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., level: _Optional[str] = ..., text: _Optional[str] = ..., dropped: _Optional[int] = ...) -> None: ...

class LogSource(_message.Message):
    __slots__ = ("name", "running", "size_bytes")
    NAME_FIELD_NUMBER: _ClassVar[int]
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    name: str
    running: bool
    size_bytes: int
    def __init__(self, name: _Optional[str] = ..., running: _Optional[bool] = ..., size_bytes: _Optional[int] = ...) -> None: ...

class ListLogSourcesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListLogSourcesResponse(_message.Message):
    __slots__ = ("sources",)
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    sources: _containers.RepeatedCompositeFieldContainer[LogSource]
    def __init__(self, sources: _Optional[_Iterable[_Union[LogSource, _Mapping]]] = ...) -> None: ...
