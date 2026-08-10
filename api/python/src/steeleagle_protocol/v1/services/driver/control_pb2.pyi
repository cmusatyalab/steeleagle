from steeleagle_protocol.v1.common import common_pb2 as _common_pb2
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

class PoseMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    POSE_MODE_UNSPECIFIED: _ClassVar[PoseMode]
    POSE_MODE_ANGLE: _ClassVar[PoseMode]
    POSE_MODE_OFFSET: _ClassVar[PoseMode]
    POSE_MODE_VELOCITY: _ClassVar[PoseMode]
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
POSE_MODE_UNSPECIFIED: PoseMode
POSE_MODE_ANGLE: PoseMode
POSE_MODE_OFFSET: PoseMode
POSE_MODE_VELOCITY: PoseMode

class TakeOffRequest(_message.Message):
    __slots__ = ("altitude",)
    ALTITUDE_FIELD_NUMBER: _ClassVar[int]
    altitude: float
    def __init__(self, altitude: _Optional[float] = ...) -> None: ...

class TakeOffResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LandRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LandResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HoldRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HoldResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class KillRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class KillResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetHomeRequest(_message.Message):
    __slots__ = ("new_home",)
    NEW_HOME_FIELD_NUMBER: _ClassVar[int]
    new_home: _common_pb2.GlobalPosition
    def __init__(self, new_home: _Optional[_Union[_common_pb2.GlobalPosition, _Mapping]] = ...) -> None: ...

class SetHomeResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

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
    __slots__ = ()
    def __init__(self) -> None: ...

class GoToGlobalPositionRequest(_message.Message):
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

class GoToGlobalPositionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GoToRelativePositionRequest(_message.Message):
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

class GoToRelativePositionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetVelocityRequest(_message.Message):
    __slots__ = ("velocity", "frame")
    VELOCITY_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    velocity: _common_pb2.Velocity
    frame: ReferenceFrame
    def __init__(self, velocity: _Optional[_Union[_common_pb2.Velocity, _Mapping]] = ..., frame: _Optional[_Union[ReferenceFrame, str]] = ...) -> None: ...

class SetVelocityResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetGimbalPoseRequest(_message.Message):
    __slots__ = ("gimbal_id", "pose", "pose_mode", "frame")
    GIMBAL_ID_FIELD_NUMBER: _ClassVar[int]
    POSE_FIELD_NUMBER: _ClassVar[int]
    POSE_MODE_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    gimbal_id: int
    pose: _common_pb2.Pose
    pose_mode: PoseMode
    frame: ReferenceFrame
    def __init__(self, gimbal_id: _Optional[int] = ..., pose: _Optional[_Union[_common_pb2.Pose, _Mapping]] = ..., pose_mode: _Optional[_Union[PoseMode, str]] = ..., frame: _Optional[_Union[ReferenceFrame, str]] = ...) -> None: ...

class SetGimbalPoseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
