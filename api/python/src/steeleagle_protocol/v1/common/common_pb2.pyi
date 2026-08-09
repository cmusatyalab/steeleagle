from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Pose(_message.Message):
    __slots__ = ("pitch", "roll", "yaw")
    PITCH_FIELD_NUMBER: _ClassVar[int]
    ROLL_FIELD_NUMBER: _ClassVar[int]
    YAW_FIELD_NUMBER: _ClassVar[int]
    pitch: float
    roll: float
    yaw: float
    def __init__(self, pitch: _Optional[float] = ..., roll: _Optional[float] = ..., yaw: _Optional[float] = ...) -> None: ...

class Velocity(_message.Message):
    __slots__ = ("x_vel", "y_vel", "z_vel", "angular_vel")
    X_VEL_FIELD_NUMBER: _ClassVar[int]
    Y_VEL_FIELD_NUMBER: _ClassVar[int]
    Z_VEL_FIELD_NUMBER: _ClassVar[int]
    ANGULAR_VEL_FIELD_NUMBER: _ClassVar[int]
    x_vel: float
    y_vel: float
    z_vel: float
    angular_vel: float
    def __init__(self, x_vel: _Optional[float] = ..., y_vel: _Optional[float] = ..., z_vel: _Optional[float] = ..., angular_vel: _Optional[float] = ...) -> None: ...

class GlobalPosition(_message.Message):
    __slots__ = ("latitude", "longitude", "altitude", "heading")
    LATITUDE_FIELD_NUMBER: _ClassVar[int]
    LONGITUDE_FIELD_NUMBER: _ClassVar[int]
    ALTITUDE_FIELD_NUMBER: _ClassVar[int]
    HEADING_FIELD_NUMBER: _ClassVar[int]
    latitude: float
    longitude: float
    altitude: float
    heading: float
    def __init__(self, latitude: _Optional[float] = ..., longitude: _Optional[float] = ..., altitude: _Optional[float] = ..., heading: _Optional[float] = ...) -> None: ...

class RelativePosition(_message.Message):
    __slots__ = ("x", "y", "z", "angle")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    ANGLE_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    z: float
    angle: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., z: _Optional[float] = ..., angle: _Optional[float] = ...) -> None: ...

class VehicleInfo(_message.Message):
    __slots__ = ("vehicle_id", "model")
    VEHICLE_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    vehicle_id: str
    model: str
    def __init__(self, vehicle_id: _Optional[str] = ..., model: _Optional[str] = ...) -> None: ...
