import common_pb2 as _common_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class AltitudeMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ABSOLUTE: _ClassVar[AltitudeMode]
    RELATIVE: _ClassVar[AltitudeMode]

class HeadingMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TO_TARGET: _ClassVar[HeadingMode]
    HEADING_START: _ClassVar[HeadingMode]

class ReferenceFrame(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BODY: _ClassVar[ReferenceFrame]
    ENU: _ClassVar[ReferenceFrame]

class PoseMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ANGLE: _ClassVar[PoseMode]
    OFFSET: _ClassVar[PoseMode]
    VELOCITY: _ClassVar[PoseMode]
ABSOLUTE: AltitudeMode
RELATIVE: AltitudeMode
TO_TARGET: HeadingMode
HEADING_START: HeadingMode
BODY: ReferenceFrame
ENU: ReferenceFrame
ANGLE: PoseMode
OFFSET: PoseMode
VELOCITY: PoseMode

class ConnectRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class ConnectResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class DisconnectRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class DisconnectResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class ArmRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class ArmResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class DisarmRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class DisarmResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class JoystickRequest(_message.Message):
    __slots__ = ('request', 'velocity', 'duration')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    VELOCITY_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    velocity: _common_pb2.Velocity
    duration: _duration_pb2.Duration

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., velocity: _Optional[_Union[_common_pb2.Velocity, _Mapping]]=..., duration: _Optional[_Union[_duration_pb2.Duration, _Mapping]]=...) -> None:
        ...

class JoystickResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class TakeOffRequest(_message.Message):
    __slots__ = ('request', 'take_off_altitude')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    TAKE_OFF_ALTITUDE_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    take_off_altitude: float

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., take_off_altitude: _Optional[float]=...) -> None:
        ...

class TakeOffResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class LandRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class LandResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class HoldRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class HoldResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class KillRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class KillResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class SetHomeRequest(_message.Message):
    __slots__ = ('request', 'location')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    location: _common_pb2.Location

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., location: _Optional[_Union[_common_pb2.Location, _Mapping]]=...) -> None:
        ...

class SetHomeResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class ReturnToHomeRequest(_message.Message):
    __slots__ = ('request',)
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=...) -> None:
        ...

class ReturnToHomeResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class SetGlobalPositionRequest(_message.Message):
    __slots__ = ('request', 'location', 'altitude_mode', 'heading_mode', 'max_velocity')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    ALTITUDE_MODE_FIELD_NUMBER: _ClassVar[int]
    HEADING_MODE_FIELD_NUMBER: _ClassVar[int]
    MAX_VELOCITY_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    location: _common_pb2.Location
    altitude_mode: AltitudeMode
    heading_mode: HeadingMode
    max_velocity: _common_pb2.Velocity

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., location: _Optional[_Union[_common_pb2.Location, _Mapping]]=..., altitude_mode: _Optional[_Union[AltitudeMode, str]]=..., heading_mode: _Optional[_Union[HeadingMode, str]]=..., max_velocity: _Optional[_Union[_common_pb2.Velocity, _Mapping]]=...) -> None:
        ...

class SetGlobalPositionResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class SetRelativePositionRequest(_message.Message):
    __slots__ = ('request', 'position', 'max_velocity', 'frame')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    MAX_VELOCITY_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    position: _common_pb2.Position
    max_velocity: _common_pb2.Velocity
    frame: ReferenceFrame

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., position: _Optional[_Union[_common_pb2.Position, _Mapping]]=..., max_velocity: _Optional[_Union[_common_pb2.Velocity, _Mapping]]=..., frame: _Optional[_Union[ReferenceFrame, str]]=...) -> None:
        ...

class SetRelativePositionResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class SetVelocityRequest(_message.Message):
    __slots__ = ('request', 'velocity', 'frame')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    VELOCITY_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    velocity: _common_pb2.Velocity
    frame: ReferenceFrame

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., velocity: _Optional[_Union[_common_pb2.Velocity, _Mapping]]=..., frame: _Optional[_Union[ReferenceFrame, str]]=...) -> None:
        ...

class SetVelocityResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class SetHeadingRequest(_message.Message):
    __slots__ = ('request', 'location', 'heading_mode')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    HEADING_MODE_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    location: _common_pb2.Location
    heading_mode: HeadingMode

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., location: _Optional[_Union[_common_pb2.Location, _Mapping]]=..., heading_mode: _Optional[_Union[HeadingMode, str]]=...) -> None:
        ...

class SetHeadingResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class SetGimbalPoseRequest(_message.Message):
    __slots__ = ('request', 'gimbal_id', 'pose', 'mode')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    GIMBAL_ID_FIELD_NUMBER: _ClassVar[int]
    POSE_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    gimbal_id: int
    pose: _common_pb2.Pose
    mode: PoseMode

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., gimbal_id: _Optional[int]=..., pose: _Optional[_Union[_common_pb2.Pose, _Mapping]]=..., mode: _Optional[_Union[PoseMode, str]]=...) -> None:
        ...

class SetGimbalPoseResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class ImagingSensorConfiguration(_message.Message):
    __slots__ = ('id', 'set_primary', 'set_fps')
    ID_FIELD_NUMBER: _ClassVar[int]
    SET_PRIMARY_FIELD_NUMBER: _ClassVar[int]
    SET_FPS_FIELD_NUMBER: _ClassVar[int]
    id: int
    set_primary: bool
    set_fps: int

    def __init__(self, id: _Optional[int]=..., set_primary: bool=..., set_fps: _Optional[int]=...) -> None:
        ...

class ConfigureImagingSensorStreamRequest(_message.Message):
    __slots__ = ('request', 'configurations')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    CONFIGURATIONS_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    configurations: _containers.RepeatedCompositeFieldContainer[ImagingSensorConfiguration]

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., configurations: _Optional[_Iterable[_Union[ImagingSensorConfiguration, _Mapping]]]=...) -> None:
        ...

class ConfigureImagingSensorStreamResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...

class ConfigureTelemetryStreamRequest(_message.Message):
    __slots__ = ('request', 'frequency')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    FREQUENCY_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    frequency: int

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., frequency: _Optional[int]=...) -> None:
        ...

class ConfigureTelemetryStreamResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...