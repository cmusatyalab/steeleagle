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

class GetConfigurationRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetConfigurationResponse(_message.Message):
    __slots__ = ("config_toml", "caps", "plugins")
    class CapsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: bytes
        def __init__(self, key: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...
    class PluginsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: bytes
        def __init__(self, key: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...
    CONFIG_TOML_FIELD_NUMBER: _ClassVar[int]
    CAPS_FIELD_NUMBER: _ClassVar[int]
    PLUGINS_FIELD_NUMBER: _ClassVar[int]
    config_toml: bytes
    caps: _containers.ScalarMap[str, bytes]
    plugins: _containers.ScalarMap[str, bytes]
    def __init__(self, config_toml: _Optional[bytes] = ..., caps: _Optional[_Mapping[str, bytes]] = ..., plugins: _Optional[_Mapping[str, bytes]] = ...) -> None: ...

class ActiveService(_message.Message):
    __slots__ = ("name", "category", "running", "uptime")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    name: str
    category: ServiceCategory
    running: bool
    uptime: _duration_pb2.Duration
    def __init__(self, name: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ..., running: _Optional[bool] = ..., uptime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class ListServicesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListServicesResponse(_message.Message):
    __slots__ = ("services",)
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[ActiveService]
    def __init__(self, services: _Optional[_Iterable[_Union[ActiveService, _Mapping]]] = ...) -> None: ...

class ServiceRequest(_message.Message):
    __slots__ = ("name", "category")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    name: str
    category: ServiceCategory
    def __init__(self, name: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ...) -> None: ...

class RestartServicesRequest(_message.Message):
    __slots__ = ("services",)
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[ServiceRequest]
    def __init__(self, services: _Optional[_Iterable[_Union[ServiceRequest, _Mapping]]] = ...) -> None: ...

class RestartServicesResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InstallPluginRequest(_message.Message):
    __slots__ = ("nickname", "url", "tag", "category")
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    nickname: str
    url: str
    tag: str
    category: ServiceCategory
    def __init__(self, nickname: _Optional[str] = ..., url: _Optional[str] = ..., tag: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ...) -> None: ...

class InstallPluginResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RemovePluginRequest(_message.Message):
    __slots__ = ("nickname", "category")
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    nickname: str
    category: ServiceCategory
    def __init__(self, nickname: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ...) -> None: ...

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
