from steeleagle_protocol.v1.common import common_pb2 as _common_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as _telemetry_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ReturnToHomeEndBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RETURN_TO_HOME_END_BEHAVIOR_UNSPECIFIED: _ClassVar[ReturnToHomeEndBehavior]
    RETURN_TO_HOME_END_BEHAVIOR_HOVER: _ClassVar[ReturnToHomeEndBehavior]
    RETURN_TO_HOME_END_BEHAVIOR_LAND: _ClassVar[ReturnToHomeEndBehavior]

class AltitudeMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ALTITUDE_MODE_UNSPECIFIED: _ClassVar[AltitudeMode]
    ALTITUDE_MODE_RELATIVE: _ClassVar[AltitudeMode]
    ALTITUDE_MODE_ABSOLUTE: _ClassVar[AltitudeMode]

class HeadingMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HEADING_MODE_UNSPECIFIED: _ClassVar[HeadingMode]
    HEADING_MODE_TO_TARGET: _ClassVar[HeadingMode]
    HEADING_MODE_START: _ClassVar[HeadingMode]

class ReferenceFrame(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    REFERENCE_FRAME_UNSPECIFIED: _ClassVar[ReferenceFrame]
    REFERENCE_FRAME_BODY: _ClassVar[ReferenceFrame]
    REFERENCE_FRAME_NEU: _ClassVar[ReferenceFrame]

class AngleMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ANGLE_MODE_UNSPECIFIED: _ClassVar[AngleMode]
    ANGLE_MODE_ABSOLUTE: _ClassVar[AngleMode]
    ANGLE_MODE_OFFSET: _ClassVar[AngleMode]
RETURN_TO_HOME_END_BEHAVIOR_UNSPECIFIED: ReturnToHomeEndBehavior
RETURN_TO_HOME_END_BEHAVIOR_HOVER: ReturnToHomeEndBehavior
RETURN_TO_HOME_END_BEHAVIOR_LAND: ReturnToHomeEndBehavior
ALTITUDE_MODE_UNSPECIFIED: AltitudeMode
ALTITUDE_MODE_RELATIVE: AltitudeMode
ALTITUDE_MODE_ABSOLUTE: AltitudeMode
HEADING_MODE_UNSPECIFIED: HeadingMode
HEADING_MODE_TO_TARGET: HeadingMode
HEADING_MODE_START: HeadingMode
REFERENCE_FRAME_UNSPECIFIED: ReferenceFrame
REFERENCE_FRAME_BODY: ReferenceFrame
REFERENCE_FRAME_NEU: ReferenceFrame
ANGLE_MODE_UNSPECIFIED: AngleMode
ANGLE_MODE_ABSOLUTE: AngleMode
ANGLE_MODE_OFFSET: AngleMode

class TakeOffRequest(_message.Message):
    __slots__ = ("altitude",)
    ALTITUDE_FIELD_NUMBER: _ClassVar[int]
    altitude: float
    def __init__(self, altitude: _Optional[float] = ...) -> None: ...

class TakeOffResponse(_message.Message):
    __slots__ = ("expected_mode", "expected_status")
    EXPECTED_MODE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    expected_mode: _telemetry_pb2.Mode
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, expected_mode: _Optional[_Union[_telemetry_pb2.Mode, str]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class LandRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LandResponse(_message.Message):
    __slots__ = ("expected_mode", "expected_status")
    EXPECTED_MODE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    expected_mode: _telemetry_pb2.Mode
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, expected_mode: _Optional[_Union[_telemetry_pb2.Mode, str]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class HoldRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HoldResponse(_message.Message):
    __slots__ = ("expected_mode", "expected_status")
    EXPECTED_MODE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    expected_mode: _telemetry_pb2.Mode
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, expected_mode: _Optional[_Union[_telemetry_pb2.Mode, str]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class KillRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class KillResponse(_message.Message):
    __slots__ = ("expected_mode", "expected_status")
    EXPECTED_MODE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    expected_mode: _telemetry_pb2.Mode
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, expected_mode: _Optional[_Union[_telemetry_pb2.Mode, str]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class ReturnToHomeRequest(_message.Message):
    __slots__ = ("end_behavior", "min_return_altitude", "final_altitude")
    END_BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
    MIN_RETURN_ALTITUDE_FIELD_NUMBER: _ClassVar[int]
    FINAL_ALTITUDE_FIELD_NUMBER: _ClassVar[int]
    end_behavior: ReturnToHomeEndBehavior
    min_return_altitude: float
    final_altitude: float
    def __init__(self, end_behavior: _Optional[_Union[ReturnToHomeEndBehavior, str]] = ..., min_return_altitude: _Optional[float] = ..., final_altitude: _Optional[float] = ...) -> None: ...

class ReturnToHomeResponse(_message.Message):
    __slots__ = ("expected_mode", "expected_status")
    EXPECTED_MODE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    expected_mode: _telemetry_pb2.Mode
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, expected_mode: _Optional[_Union[_telemetry_pb2.Mode, str]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class SetGlobalPositionTargetRequest(_message.Message):
    __slots__ = ("position", "heading_mode", "altitude_mode", "speed", "angular_speed")
    POSITION_FIELD_NUMBER: _ClassVar[int]
    HEADING_MODE_FIELD_NUMBER: _ClassVar[int]
    ALTITUDE_MODE_FIELD_NUMBER: _ClassVar[int]
    SPEED_FIELD_NUMBER: _ClassVar[int]
    ANGULAR_SPEED_FIELD_NUMBER: _ClassVar[int]
    position: _common_pb2.GlobalPosition
    heading_mode: HeadingMode
    altitude_mode: AltitudeMode
    speed: float
    angular_speed: float
    def __init__(self, position: _Optional[_Union[_common_pb2.GlobalPosition, _Mapping]] = ..., heading_mode: _Optional[_Union[HeadingMode, str]] = ..., altitude_mode: _Optional[_Union[AltitudeMode, str]] = ..., speed: _Optional[float] = ..., angular_speed: _Optional[float] = ...) -> None: ...

class SetGlobalPositionTargetResponse(_message.Message):
    __slots__ = ("setpoint", "expected_status")
    SETPOINT_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    setpoint: _common_pb2.GlobalPosition
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, setpoint: _Optional[_Union[_common_pb2.GlobalPosition, _Mapping]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class SetRelativePositionTargetRequest(_message.Message):
    __slots__ = ("position", "speed", "angular_speed", "frame")
    POSITION_FIELD_NUMBER: _ClassVar[int]
    SPEED_FIELD_NUMBER: _ClassVar[int]
    ANGULAR_SPEED_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    position: _common_pb2.RelativePosition
    speed: float
    angular_speed: float
    frame: ReferenceFrame
    def __init__(self, position: _Optional[_Union[_common_pb2.RelativePosition, _Mapping]] = ..., speed: _Optional[float] = ..., angular_speed: _Optional[float] = ..., frame: _Optional[_Union[ReferenceFrame, str]] = ...) -> None: ...

class SetRelativePositionTargetResponse(_message.Message):
    __slots__ = ("setpoint", "expected_status")
    SETPOINT_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    setpoint: _common_pb2.RelativePosition
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, setpoint: _Optional[_Union[_common_pb2.RelativePosition, _Mapping]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class SetVelocityTargetRequest(_message.Message):
    __slots__ = ("velocity", "frame")
    VELOCITY_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    velocity: _common_pb2.Velocity
    frame: ReferenceFrame
    def __init__(self, velocity: _Optional[_Union[_common_pb2.Velocity, _Mapping]] = ..., frame: _Optional[_Union[ReferenceFrame, str]] = ...) -> None: ...

class SetVelocityTargetResponse(_message.Message):
    __slots__ = ("setpoint", "expected_status")
    SETPOINT_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_STATUS_FIELD_NUMBER: _ClassVar[int]
    setpoint: _common_pb2.Velocity
    expected_status: _telemetry_pb2.MotionStatus
    def __init__(self, setpoint: _Optional[_Union[_common_pb2.Velocity, _Mapping]] = ..., expected_status: _Optional[_Union[_telemetry_pb2.MotionStatus, str]] = ...) -> None: ...

class SetGimbalAngleTargetRequest(_message.Message):
    __slots__ = ("pose", "angle_mode")
    POSE_FIELD_NUMBER: _ClassVar[int]
    ANGLE_MODE_FIELD_NUMBER: _ClassVar[int]
    pose: _common_pb2.Pose
    angle_mode: AngleMode
    def __init__(self, pose: _Optional[_Union[_common_pb2.Pose, _Mapping]] = ..., angle_mode: _Optional[_Union[AngleMode, str]] = ...) -> None: ...

class SetGimbalAngleTargetResponse(_message.Message):
    __slots__ = ("setpoint",)
    SETPOINT_FIELD_NUMBER: _ClassVar[int]
    setpoint: _common_pb2.Pose
    def __init__(self, setpoint: _Optional[_Union[_common_pb2.Pose, _Mapping]] = ...) -> None: ...

class SetGimbalVelocityTargetRequest(_message.Message):
    __slots__ = ("pose_velocity", "frame")
    POSE_VELOCITY_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    pose_velocity: _common_pb2.PoseVelocity
    frame: ReferenceFrame
    def __init__(self, pose_velocity: _Optional[_Union[_common_pb2.PoseVelocity, _Mapping]] = ..., frame: _Optional[_Union[ReferenceFrame, str]] = ...) -> None: ...

class SetGimbalVelocityTargetResponse(_message.Message):
    __slots__ = ("setpoint",)
    SETPOINT_FIELD_NUMBER: _ClassVar[int]
    setpoint: _common_pb2.PoseVelocity
    def __init__(self, setpoint: _Optional[_Union[_common_pb2.PoseVelocity, _Mapping]] = ...) -> None: ...
