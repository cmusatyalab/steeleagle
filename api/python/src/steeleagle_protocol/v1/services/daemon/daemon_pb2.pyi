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
    SERVICE_CATEGORY_COMMANDER: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_SIMULATOR: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_EXTRA: _ClassVar[ServiceCategory]
SERVICE_CATEGORY_UNSPECIFIED: ServiceCategory
SERVICE_CATEGORY_VEHICLE: ServiceCategory
SERVICE_CATEGORY_ENGINE: ServiceCategory
SERVICE_CATEGORY_MONITOR: ServiceCategory
SERVICE_CATEGORY_COMMANDER: ServiceCategory
SERVICE_CATEGORY_SIMULATOR: ServiceCategory
SERVICE_CATEGORY_EXTRA: ServiceCategory

class RegisterOrchestratorRequest(_message.Message):
    __slots__ = ("vehicles", "port")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    port: int
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., port: _Optional[int] = ...) -> None: ...

class RegisterOrchestratorResponse(_message.Message):
    __slots__ = ("cert", "port")
    CERT_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    cert: str
    port: int
    def __init__(self, cert: _Optional[str] = ..., port: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("config_toml", "plugin_tomls")
    class PluginTomlsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: bytes
        def __init__(self, key: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...
    CONFIG_TOML_FIELD_NUMBER: _ClassVar[int]
    PLUGIN_TOMLS_FIELD_NUMBER: _ClassVar[int]
    config_toml: bytes
    plugin_tomls: _containers.ScalarMap[str, bytes]
    def __init__(self, config_toml: _Optional[bytes] = ..., plugin_tomls: _Optional[_Mapping[str, bytes]] = ...) -> None: ...

class Service(_message.Message):
    __slots__ = ("name", "category")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    name: str
    category: ServiceCategory
    def __init__(self, name: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ...) -> None: ...

class ActiveService(_message.Message):
    __slots__ = ("srv", "plugin", "url", "running", "uptime", "error")
    SRV_FIELD_NUMBER: _ClassVar[int]
    PLUGIN_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    srv: Service
    plugin: str
    url: str
    running: bool
    uptime: _duration_pb2.Duration
    error: str
    def __init__(self, srv: _Optional[_Union[Service, _Mapping]] = ..., plugin: _Optional[str] = ..., url: _Optional[str] = ..., running: _Optional[bool] = ..., uptime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., error: _Optional[str] = ...) -> None: ...

class ListServicesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListServicesResponse(_message.Message):
    __slots__ = ("services",)
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[ActiveService]
    def __init__(self, services: _Optional[_Iterable[_Union[ActiveService, _Mapping]]] = ...) -> None: ...

class RestartServicesRequest(_message.Message):
    __slots__ = ("services",)
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[Service]
    def __init__(self, services: _Optional[_Iterable[_Union[Service, _Mapping]]] = ...) -> None: ...

class RestartServicesResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InstallPackageRequest(_message.Message):
    __slots__ = ("url", "tag")
    URL_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    url: str
    tag: str
    def __init__(self, url: _Optional[str] = ..., tag: _Optional[str] = ...) -> None: ...

class InstallPackageResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Package(_message.Message):
    __slots__ = ("url", "tag", "plugins", "modified")
    class PluginsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: bytes
        def __init__(self, key: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...
    URL_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    PLUGINS_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_FIELD_NUMBER: _ClassVar[int]
    url: str
    tag: str
    plugins: _containers.ScalarMap[str, bytes]
    modified: _timestamp_pb2.Timestamp
    def __init__(self, url: _Optional[str] = ..., tag: _Optional[str] = ..., plugins: _Optional[_Mapping[str, bytes]] = ..., modified: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListPackagesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListPackagesResponse(_message.Message):
    __slots__ = ("packages",)
    PACKAGES_FIELD_NUMBER: _ClassVar[int]
    packages: _containers.RepeatedCompositeFieldContainer[Package]
    def __init__(self, packages: _Optional[_Iterable[_Union[Package, _Mapping]]] = ...) -> None: ...

class RemovePackageRequest(_message.Message):
    __slots__ = ("url",)
    URL_FIELD_NUMBER: _ClassVar[int]
    url: str
    def __init__(self, url: _Optional[str] = ...) -> None: ...

class RemovePackageResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
