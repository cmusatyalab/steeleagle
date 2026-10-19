import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FallbackBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FALLBACK_BEHAVIOR_UNSPECIFIED: _ClassVar[FallbackBehavior]
    FALLBACK_BEHAVIOR_HOLD: _ClassVar[FallbackBehavior]
    FALLBACK_BEHAVIOR_RTH: _ClassVar[FallbackBehavior]
    FALLBACK_BEHAVIOR_MISSION_HOLD: _ClassVar[FallbackBehavior]
    FALLBACK_BEHAVIOR_MISSION_RTH: _ClassVar[FallbackBehavior]
FALLBACK_BEHAVIOR_UNSPECIFIED: FallbackBehavior
FALLBACK_BEHAVIOR_HOLD: FallbackBehavior
FALLBACK_BEHAVIOR_RTH: FallbackBehavior
FALLBACK_BEHAVIOR_MISSION_HOLD: FallbackBehavior
FALLBACK_BEHAVIOR_MISSION_RTH: FallbackBehavior

class ConfigureDMSRequest(_message.Message):
    __slots__ = ("timeout",)
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    timeout: _duration_pb2.Duration
    def __init__(self, timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class ConfigureDMSResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Geofence(_message.Message):
    __slots__ = ("polygon", "geojson")
    POLYGON_FIELD_NUMBER: _ClassVar[int]
    GEOJSON_FIELD_NUMBER: _ClassVar[int]
    polygon: str
    geojson: bytes
    def __init__(self, polygon: _Optional[str] = ..., geojson: _Optional[bytes] = ...) -> None: ...

class SetGeofenceRequest(_message.Message):
    __slots__ = ("off", "geofence")
    OFF_FIELD_NUMBER: _ClassVar[int]
    GEOFENCE_FIELD_NUMBER: _ClassVar[int]
    off: bool
    geofence: Geofence
    def __init__(self, off: _Optional[bool] = ..., geofence: _Optional[_Union[Geofence, _Mapping]] = ...) -> None: ...

class SetGeofenceResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetMissionGeofenceRequest(_message.Message):
    __slots__ = ("off", "geofence")
    OFF_FIELD_NUMBER: _ClassVar[int]
    GEOFENCE_FIELD_NUMBER: _ClassVar[int]
    off: bool
    geofence: Geofence
    def __init__(self, off: _Optional[bool] = ..., geofence: _Optional[_Union[Geofence, _Mapping]] = ...) -> None: ...

class SetMissionGeofenceResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetFallbackBehaviorRequest(_message.Message):
    __slots__ = ("behavior",)
    BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
    behavior: FallbackBehavior
    def __init__(self, behavior: _Optional[_Union[FallbackBehavior, str]] = ...) -> None: ...

class SetFallbackBehaviorResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
