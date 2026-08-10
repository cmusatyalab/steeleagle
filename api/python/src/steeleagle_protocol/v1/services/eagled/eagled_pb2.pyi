from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PluginCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PLUGIN_CATEGORY_UNSPECIFIED: _ClassVar[PluginCategory]
    PLUGIN_CATEGORY_DRIVER: _ClassVar[PluginCategory]
    PLUGIN_CATEGORY_MISSION: _ClassVar[PluginCategory]
    PLUGIN_CATEGORY_EXTRA: _ClassVar[PluginCategory]
PLUGIN_CATEGORY_UNSPECIFIED: PluginCategory
PLUGIN_CATEGORY_DRIVER: PluginCategory
PLUGIN_CATEGORY_MISSION: PluginCategory
PLUGIN_CATEGORY_EXTRA: PluginCategory

class ConfigureRequest(_message.Message):
    __slots__ = ("config_toml",)
    CONFIG_TOML_FIELD_NUMBER: _ClassVar[int]
    config_toml: str
    def __init__(self, config_toml: _Optional[str] = ...) -> None: ...

class ConfigureResponse(_message.Message):
    __slots__ = ("vehicles",)
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedCompositeFieldContainer[VehicleResult]
    def __init__(self, vehicles: _Optional[_Iterable[_Union[VehicleResult, _Mapping]]] = ...) -> None: ...

class StopVehiclesRequest(_message.Message):
    __slots__ = ("names",)
    NAMES_FIELD_NUMBER: _ClassVar[int]
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, names: _Optional[_Iterable[str]] = ...) -> None: ...

class StopVehiclesResponse(_message.Message):
    __slots__ = ("vehicles",)
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedCompositeFieldContainer[VehicleResult]
    def __init__(self, vehicles: _Optional[_Iterable[_Union[VehicleResult, _Mapping]]] = ...) -> None: ...

class RestartVehiclesRequest(_message.Message):
    __slots__ = ("names",)
    NAMES_FIELD_NUMBER: _ClassVar[int]
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, names: _Optional[_Iterable[str]] = ...) -> None: ...

class RestartVehiclesResponse(_message.Message):
    __slots__ = ("vehicles",)
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedCompositeFieldContainer[VehicleResult]
    def __init__(self, vehicles: _Optional[_Iterable[_Union[VehicleResult, _Mapping]]] = ...) -> None: ...

class ForgetVehiclesRequest(_message.Message):
    __slots__ = ("names",)
    NAMES_FIELD_NUMBER: _ClassVar[int]
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, names: _Optional[_Iterable[str]] = ...) -> None: ...

class ForgetVehiclesResponse(_message.Message):
    __slots__ = ("vehicles",)
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedCompositeFieldContainer[VehicleResult]
    def __init__(self, vehicles: _Optional[_Iterable[_Union[VehicleResult, _Mapping]]] = ...) -> None: ...

class VehicleResult(_message.Message):
    __slots__ = ("name", "ok", "error")
    NAME_FIELD_NUMBER: _ClassVar[int]
    OK_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    name: str
    ok: bool
    error: str
    def __init__(self, name: _Optional[str] = ..., ok: _Optional[bool] = ..., error: _Optional[str] = ...) -> None: ...

class InstallPluginRequest(_message.Message):
    __slots__ = ("name", "repo", "ref", "subpath", "category")
    NAME_FIELD_NUMBER: _ClassVar[int]
    REPO_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    SUBPATH_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    name: str
    repo: str
    ref: str
    subpath: str
    category: PluginCategory
    def __init__(self, name: _Optional[str] = ..., repo: _Optional[str] = ..., ref: _Optional[str] = ..., subpath: _Optional[str] = ..., category: _Optional[_Union[PluginCategory, str]] = ...) -> None: ...

class InstallPluginResponse(_message.Message):
    __slots__ = ("ok", "error")
    OK_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    error: str
    def __init__(self, ok: _Optional[bool] = ..., error: _Optional[str] = ...) -> None: ...

class GetInstalledPluginsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetInstalledPluginsResponse(_message.Message):
    __slots__ = ("plugins",)
    PLUGINS_FIELD_NUMBER: _ClassVar[int]
    plugins: _containers.RepeatedCompositeFieldContainer[InstalledPlugin]
    def __init__(self, plugins: _Optional[_Iterable[_Union[InstalledPlugin, _Mapping]]] = ...) -> None: ...

class InstalledPlugin(_message.Message):
    __slots__ = ("name", "ref", "category")
    NAME_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    name: str
    ref: str
    category: PluginCategory
    def __init__(self, name: _Optional[str] = ..., ref: _Optional[str] = ..., category: _Optional[_Union[PluginCategory, str]] = ...) -> None: ...

class ResetConfigRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ResetConfigResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartDaemonRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartDaemonResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetStatusResponse(_message.Message):
    __slots__ = ("configured", "config", "vehicles")
    CONFIGURED_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    configured: bool
    config: DaemonConfig
    vehicles: _containers.RepeatedCompositeFieldContainer[VehicleStatus]
    def __init__(self, configured: _Optional[bool] = ..., config: _Optional[_Union[DaemonConfig, _Mapping]] = ..., vehicles: _Optional[_Iterable[_Union[VehicleStatus, _Mapping]]] = ...) -> None: ...

class DaemonConfig(_message.Message):
    __slots__ = ("vpn", "vehicle_vpn", "port_base", "plugin_dir", "tailscale_hostname", "tailscale_authkey_env", "swarm_controller_address", "daemon_name", "gabriel_server_endpoint")
    VPN_FIELD_NUMBER: _ClassVar[int]
    VEHICLE_VPN_FIELD_NUMBER: _ClassVar[int]
    PORT_BASE_FIELD_NUMBER: _ClassVar[int]
    PLUGIN_DIR_FIELD_NUMBER: _ClassVar[int]
    TAILSCALE_HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    TAILSCALE_AUTHKEY_ENV_FIELD_NUMBER: _ClassVar[int]
    SWARM_CONTROLLER_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    DAEMON_NAME_FIELD_NUMBER: _ClassVar[int]
    GABRIEL_SERVER_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    vpn: bool
    vehicle_vpn: bool
    port_base: int
    plugin_dir: str
    tailscale_hostname: str
    tailscale_authkey_env: str
    swarm_controller_address: str
    daemon_name: str
    gabriel_server_endpoint: str
    def __init__(self, vpn: _Optional[bool] = ..., vehicle_vpn: _Optional[bool] = ..., port_base: _Optional[int] = ..., plugin_dir: _Optional[str] = ..., tailscale_hostname: _Optional[str] = ..., tailscale_authkey_env: _Optional[str] = ..., swarm_controller_address: _Optional[str] = ..., daemon_name: _Optional[str] = ..., gabriel_server_endpoint: _Optional[str] = ...) -> None: ...

class VehicleStatus(_message.Message):
    __slots__ = ("name", "driver", "running", "port")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DRIVER_FIELD_NUMBER: _ClassVar[int]
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    name: str
    driver: str
    running: bool
    port: int
    def __init__(self, name: _Optional[str] = ..., driver: _Optional[str] = ..., running: _Optional[bool] = ..., port: _Optional[int] = ...) -> None: ...
