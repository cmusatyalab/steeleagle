import datetime

from steeleagle_protocol.v1.common import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Mode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MODE_UNSPECIFIED: _ClassVar[Mode]
    MODE_TAKEOFF: _ClassVar[Mode]
    MODE_LAND: _ClassVar[Mode]
    MODE_LOITER: _ClassVar[Mode]
    MODE_GUIDED: _ClassVar[Mode]
    MODE_RETURN_TO_HOME: _ClassVar[Mode]
    MODE_EMERGENCY: _ClassVar[Mode]

class MotionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MOTION_STATUS_UNSPECIFIED: _ClassVar[MotionStatus]
    MOTION_STATUS_HOLDING: _ClassVar[MotionStatus]
    MOTION_STATUS_IN_TRANSIT: _ClassVar[MotionStatus]
    MOTION_STATUS_STOPPED: _ClassVar[MotionStatus]
MODE_UNSPECIFIED: Mode
MODE_TAKEOFF: Mode
MODE_LAND: Mode
MODE_LOITER: Mode
MODE_GUIDED: Mode
MODE_RETURN_TO_HOME: Mode
MODE_EMERGENCY: Mode
MOTION_STATUS_UNSPECIFIED: MotionStatus
MOTION_STATUS_HOLDING: MotionStatus
MOTION_STATUS_IN_TRANSIT: MotionStatus
MOTION_STATUS_STOPPED: MotionStatus

class BatteryInfo(_message.Message):
    __slots__ = ("percentage",)
    PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    percentage: int
    def __init__(self, percentage: _Optional[int] = ...) -> None: ...

class GpsInfo(_message.Message):
    __slots__ = ("satellites",)
    SATELLITES_FIELD_NUMBER: _ClassVar[int]
    satellites: int
    def __init__(self, satellites: _Optional[int] = ...) -> None: ...

class PositionInfo(_message.Message):
    __slots__ = ("home", "global_position", "relative_position", "velocity_body", "velocity_neu", "setpoint")
    HOME_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_POSITION_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_POSITION_FIELD_NUMBER: _ClassVar[int]
    VELOCITY_BODY_FIELD_NUMBER: _ClassVar[int]
    VELOCITY_NEU_FIELD_NUMBER: _ClassVar[int]
    SETPOINT_FIELD_NUMBER: _ClassVar[int]
    home: _common_pb2.GlobalPosition
    global_position: _common_pb2.GlobalPosition
    relative_position: _common_pb2.RelativePosition
    velocity_body: _common_pb2.Velocity
    velocity_neu: _common_pb2.Velocity
    setpoint: _any_pb2.Any
    def __init__(self, home: _Optional[_Union[_common_pb2.GlobalPosition, _Mapping]] = ..., global_position: _Optional[_Union[_common_pb2.GlobalPosition, _Mapping]] = ..., relative_position: _Optional[_Union[_common_pb2.RelativePosition, _Mapping]] = ..., velocity_body: _Optional[_Union[_common_pb2.Velocity, _Mapping]] = ..., velocity_neu: _Optional[_Union[_common_pb2.Velocity, _Mapping]] = ..., setpoint: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...) -> None: ...

class GimbalInfo(_message.Message):
    __slots__ = ("pose_body", "pose_neu", "angular_velocity_body", "angular_velocity_neu", "gimbal_setpoint")
    POSE_BODY_FIELD_NUMBER: _ClassVar[int]
    POSE_NEU_FIELD_NUMBER: _ClassVar[int]
    ANGULAR_VELOCITY_BODY_FIELD_NUMBER: _ClassVar[int]
    ANGULAR_VELOCITY_NEU_FIELD_NUMBER: _ClassVar[int]
    GIMBAL_SETPOINT_FIELD_NUMBER: _ClassVar[int]
    pose_body: _common_pb2.Pose
    pose_neu: _common_pb2.Pose
    angular_velocity_body: _common_pb2.PoseVelocity
    angular_velocity_neu: _common_pb2.PoseVelocity
    gimbal_setpoint: _any_pb2.Any
    def __init__(self, pose_body: _Optional[_Union[_common_pb2.Pose, _Mapping]] = ..., pose_neu: _Optional[_Union[_common_pb2.Pose, _Mapping]] = ..., angular_velocity_body: _Optional[_Union[_common_pb2.PoseVelocity, _Mapping]] = ..., angular_velocity_neu: _Optional[_Union[_common_pb2.PoseVelocity, _Mapping]] = ..., gimbal_setpoint: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...) -> None: ...

class AlertInfo(_message.Message):
    __slots__ = ("battery_warning", "gps_warning", "magnetometer_warning", "connection_warning", "compass_warning")
    class BatteryWarning(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BATTERY_WARNING_UNSPECIFIED: _ClassVar[AlertInfo.BatteryWarning]
        BATTERY_WARNING_LOW: _ClassVar[AlertInfo.BatteryWarning]
        BATTERY_WARNING_CRITICAL: _ClassVar[AlertInfo.BatteryWarning]
    BATTERY_WARNING_UNSPECIFIED: AlertInfo.BatteryWarning
    BATTERY_WARNING_LOW: AlertInfo.BatteryWarning
    BATTERY_WARNING_CRITICAL: AlertInfo.BatteryWarning
    class GpsWarning(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        GPS_WARNING_UNSPECIFIED: _ClassVar[AlertInfo.GpsWarning]
        GPS_WARNING_WEAK_SIGNAL: _ClassVar[AlertInfo.GpsWarning]
        GPS_WARNING_NO_FIX: _ClassVar[AlertInfo.GpsWarning]
    GPS_WARNING_UNSPECIFIED: AlertInfo.GpsWarning
    GPS_WARNING_WEAK_SIGNAL: AlertInfo.GpsWarning
    GPS_WARNING_NO_FIX: AlertInfo.GpsWarning
    class MagnetometerWarning(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        MAGNETOMETER_WARNING_UNSPECIFIED: _ClassVar[AlertInfo.MagnetometerWarning]
        MAGNETOMETER_WARNING_PERTURBATIONS: _ClassVar[AlertInfo.MagnetometerWarning]
    MAGNETOMETER_WARNING_UNSPECIFIED: AlertInfo.MagnetometerWarning
    MAGNETOMETER_WARNING_PERTURBATIONS: AlertInfo.MagnetometerWarning
    class ConnectionWarning(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        CONNECTION_WARNING_UNSPECIFIED: _ClassVar[AlertInfo.ConnectionWarning]
        CONNECTION_WARNING_DISCONNECTED: _ClassVar[AlertInfo.ConnectionWarning]
        CONNECTION_WARNING_WEAK_CONNECTION: _ClassVar[AlertInfo.ConnectionWarning]
    CONNECTION_WARNING_UNSPECIFIED: AlertInfo.ConnectionWarning
    CONNECTION_WARNING_DISCONNECTED: AlertInfo.ConnectionWarning
    CONNECTION_WARNING_WEAK_CONNECTION: AlertInfo.ConnectionWarning
    class CompassWarning(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        COMPASS_WARNING_UNSPECIFIED: _ClassVar[AlertInfo.CompassWarning]
        COMPASS_WARNING_WEAK_LOCK: _ClassVar[AlertInfo.CompassWarning]
        COMPASS_WARNING_NO_LOCK: _ClassVar[AlertInfo.CompassWarning]
    COMPASS_WARNING_UNSPECIFIED: AlertInfo.CompassWarning
    COMPASS_WARNING_WEAK_LOCK: AlertInfo.CompassWarning
    COMPASS_WARNING_NO_LOCK: AlertInfo.CompassWarning
    BATTERY_WARNING_FIELD_NUMBER: _ClassVar[int]
    GPS_WARNING_FIELD_NUMBER: _ClassVar[int]
    MAGNETOMETER_WARNING_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_WARNING_FIELD_NUMBER: _ClassVar[int]
    COMPASS_WARNING_FIELD_NUMBER: _ClassVar[int]
    battery_warning: AlertInfo.BatteryWarning
    gps_warning: AlertInfo.GpsWarning
    magnetometer_warning: AlertInfo.MagnetometerWarning
    connection_warning: AlertInfo.ConnectionWarning
    compass_warning: AlertInfo.CompassWarning
    def __init__(self, battery_warning: _Optional[_Union[AlertInfo.BatteryWarning, str]] = ..., gps_warning: _Optional[_Union[AlertInfo.GpsWarning, str]] = ..., magnetometer_warning: _Optional[_Union[AlertInfo.MagnetometerWarning, str]] = ..., connection_warning: _Optional[_Union[AlertInfo.ConnectionWarning, str]] = ..., compass_warning: _Optional[_Union[AlertInfo.CompassWarning, str]] = ...) -> None: ...

class Telemetry(_message.Message):
    __slots__ = ("timestamp", "battery_info", "gps_info", "position_info", "gimbal_info", "alert_info", "mode", "motion_status")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BATTERY_INFO_FIELD_NUMBER: _ClassVar[int]
    GPS_INFO_FIELD_NUMBER: _ClassVar[int]
    POSITION_INFO_FIELD_NUMBER: _ClassVar[int]
    GIMBAL_INFO_FIELD_NUMBER: _ClassVar[int]
    ALERT_INFO_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    MOTION_STATUS_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    battery_info: BatteryInfo
    gps_info: GpsInfo
    position_info: PositionInfo
    gimbal_info: GimbalInfo
    alert_info: AlertInfo
    mode: Mode
    motion_status: MotionStatus
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., battery_info: _Optional[_Union[BatteryInfo, _Mapping]] = ..., gps_info: _Optional[_Union[GpsInfo, _Mapping]] = ..., position_info: _Optional[_Union[PositionInfo, _Mapping]] = ..., gimbal_info: _Optional[_Union[GimbalInfo, _Mapping]] = ..., alert_info: _Optional[_Union[AlertInfo, _Mapping]] = ..., mode: _Optional[_Union[Mode, str]] = ..., motion_status: _Optional[_Union[MotionStatus, str]] = ...) -> None: ...

class RawFrame(_message.Message):
    __slots__ = ("timestamp", "data", "h_res", "v_res", "d_res", "channels", "id", "position_info", "gimbal_info", "camera_id")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    H_RES_FIELD_NUMBER: _ClassVar[int]
    V_RES_FIELD_NUMBER: _ClassVar[int]
    D_RES_FIELD_NUMBER: _ClassVar[int]
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    POSITION_INFO_FIELD_NUMBER: _ClassVar[int]
    GIMBAL_INFO_FIELD_NUMBER: _ClassVar[int]
    CAMERA_ID_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    data: bytes
    h_res: int
    v_res: int
    d_res: int
    channels: int
    id: int
    position_info: PositionInfo
    gimbal_info: GimbalInfo
    camera_id: int
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., data: _Optional[bytes] = ..., h_res: _Optional[int] = ..., v_res: _Optional[int] = ..., d_res: _Optional[int] = ..., channels: _Optional[int] = ..., id: _Optional[int] = ..., position_info: _Optional[_Union[PositionInfo, _Mapping]] = ..., gimbal_info: _Optional[_Union[GimbalInfo, _Mapping]] = ..., camera_id: _Optional[int] = ...) -> None: ...

class EncodedFrame(_message.Message):
    __slots__ = ("timestamp", "encoded_data", "id", "gimbal_info", "position_info", "camera_id")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ENCODED_DATA_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    GIMBAL_INFO_FIELD_NUMBER: _ClassVar[int]
    POSITION_INFO_FIELD_NUMBER: _ClassVar[int]
    CAMERA_ID_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    encoded_data: bytes
    id: int
    gimbal_info: GimbalInfo
    position_info: PositionInfo
    camera_id: int
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., encoded_data: _Optional[bytes] = ..., id: _Optional[int] = ..., gimbal_info: _Optional[_Union[GimbalInfo, _Mapping]] = ..., position_info: _Optional[_Union[PositionInfo, _Mapping]] = ..., camera_id: _Optional[int] = ...) -> None: ...
