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
    SERVICE_CATEGORY_SIMULATOR: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_VEHICLE: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_ENGINE: _ClassVar[ServiceCategory]
    SERVICE_CATEGORY_EXTRA: _ClassVar[ServiceCategory]

class Isolation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ISOLATION_UNSPECIFIED: _ClassVar[Isolation]
    ISOLATION_PROCESS: _ClassVar[Isolation]
    ISOLATION_SANDBOX: _ClassVar[Isolation]
    ISOLATION_CONTAINER: _ClassVar[Isolation]
SERVICE_CATEGORY_UNSPECIFIED: ServiceCategory
SERVICE_CATEGORY_SIMULATOR: ServiceCategory
SERVICE_CATEGORY_VEHICLE: ServiceCategory
SERVICE_CATEGORY_ENGINE: ServiceCategory
SERVICE_CATEGORY_EXTRA: ServiceCategory
ISOLATION_UNSPECIFIED: Isolation
ISOLATION_PROCESS: Isolation
ISOLATION_SANDBOX: Isolation
ISOLATION_CONTAINER: Isolation

class Service(_message.Message):
    __slots__ = ("name", "category", "plugin", "uri", "config", "isolation", "running", "auth")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    PLUGIN_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    ISOLATION_FIELD_NUMBER: _ClassVar[int]
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    AUTH_FIELD_NUMBER: _ClassVar[int]
    name: str
    category: ServiceCategory
    plugin: str
    uri: str
    config: bytes
    isolation: Isolation
    running: bool
    auth: str
    def __init__(self, name: _Optional[str] = ..., category: _Optional[_Union[ServiceCategory, str]] = ..., plugin: _Optional[str] = ..., uri: _Optional[str] = ..., config: _Optional[bytes] = ..., isolation: _Optional[_Union[Isolation, str]] = ..., running: _Optional[bool] = ..., auth: _Optional[str] = ...) -> None: ...

class Unavailable(_message.Message):
    __slots__ = ("ip", "hostname", "reason")
    IP_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    ip: str
    hostname: str
    reason: str
    def __init__(self, ip: _Optional[str] = ..., hostname: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class RegisterOrchestratorRequest(_message.Message):
    __slots__ = ("services", "hostname", "port", "arch", "os")
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    ARCH_FIELD_NUMBER: _ClassVar[int]
    OS_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[Service]
    hostname: str
    port: int
    arch: str
    os: str
    def __init__(self, services: _Optional[_Iterable[_Union[Service, _Mapping]]] = ..., hostname: _Optional[str] = ..., port: _Optional[int] = ..., arch: _Optional[str] = ..., os: _Optional[str] = ...) -> None: ...

class RegisterOrchestratorResponse(_message.Message):
    __slots__ = ("services", "hostname", "cert", "lcs_port")
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    CERT_FIELD_NUMBER: _ClassVar[int]
    LCS_PORT_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[Service]
    hostname: str
    cert: bytes
    lcs_port: int
    def __init__(self, services: _Optional[_Iterable[_Union[Service, _Mapping]]] = ..., hostname: _Optional[str] = ..., cert: _Optional[bytes] = ..., lcs_port: _Optional[int] = ...) -> None: ...

class GetConnectionStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetConnectionStatusResponse(_message.Message):
    __slots__ = ("connected",)
    CONNECTED_FIELD_NUMBER: _ClassVar[int]
    connected: bool
    def __init__(self, connected: _Optional[bool] = ...) -> None: ...

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
    __slots__ = ("config_toml",)
    CONFIG_TOML_FIELD_NUMBER: _ClassVar[int]
    config_toml: bytes
    def __init__(self, config_toml: _Optional[bytes] = ...) -> None: ...

class ListServicesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListServicesResponse(_message.Message):
    __slots__ = ("services", "unavailable")
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    UNAVAILABLE_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[Service]
    unavailable: _containers.RepeatedCompositeFieldContainer[Unavailable]
    def __init__(self, services: _Optional[_Iterable[_Union[Service, _Mapping]]] = ..., unavailable: _Optional[_Iterable[_Union[Unavailable, _Mapping]]] = ...) -> None: ...

class RestartServiceRequest(_message.Message):
    __slots__ = ("service_names",)
    SERVICE_NAMES_FIELD_NUMBER: _ClassVar[int]
    service_names: str
    def __init__(self, service_names: _Optional[str] = ...) -> None: ...

class RestartServiceResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InstallPackageRequest(_message.Message):
    __slots__ = ("uri",)
    URI_FIELD_NUMBER: _ClassVar[int]
    uri: str
    def __init__(self, uri: _Optional[str] = ...) -> None: ...

class InstallPackageResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Package(_message.Message):
    __slots__ = ("uri", "plugins", "modified")
    class PluginsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: bytes
        def __init__(self, key: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...
    URI_FIELD_NUMBER: _ClassVar[int]
    PLUGINS_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_FIELD_NUMBER: _ClassVar[int]
    uri: str
    plugins: _containers.ScalarMap[str, bytes]
    modified: _timestamp_pb2.Timestamp
    def __init__(self, uri: _Optional[str] = ..., plugins: _Optional[_Mapping[str, bytes]] = ..., modified: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListPackagesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListPackagesResponse(_message.Message):
    __slots__ = ("packages",)
    PACKAGES_FIELD_NUMBER: _ClassVar[int]
    packages: _containers.RepeatedCompositeFieldContainer[Package]
    def __init__(self, packages: _Optional[_Iterable[_Union[Package, _Mapping]]] = ...) -> None: ...

class RemovePackageRequest(_message.Message):
    __slots__ = ("uri",)
    URI_FIELD_NUMBER: _ClassVar[int]
    uri: str
    def __init__(self, uri: _Optional[str] = ...) -> None: ...

class RemovePackageResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
