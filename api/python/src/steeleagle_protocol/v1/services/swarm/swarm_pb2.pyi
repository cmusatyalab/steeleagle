from steeleagle_protocol.v1.common import common_pb2 as _common_pb2
from steeleagle_protocol.v1.services.driver import control_pb2 as _control_pb2
from steeleagle_protocol.v1.services.mission import mission_pb2 as _mission_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SwarmTakeOffRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _control_pb2.TakeOffRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_control_pb2.TakeOffRequest, _Mapping]] = ...) -> None: ...

class SwarmTakeOffResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _control_pb2.TakeOffResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_control_pb2.TakeOffResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmLandRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _control_pb2.LandRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_control_pb2.LandRequest, _Mapping]] = ...) -> None: ...

class SwarmLandResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _control_pb2.LandResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_control_pb2.LandResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmHoldRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _control_pb2.HoldRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_control_pb2.HoldRequest, _Mapping]] = ...) -> None: ...

class SwarmHoldResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _control_pb2.HoldResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_control_pb2.HoldResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmKillRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _control_pb2.KillRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_control_pb2.KillRequest, _Mapping]] = ...) -> None: ...

class SwarmKillResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _control_pb2.KillResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_control_pb2.KillResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmReturnToHomeRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _control_pb2.ReturnToHomeRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_control_pb2.ReturnToHomeRequest, _Mapping]] = ...) -> None: ...

class SwarmReturnToHomeResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _control_pb2.ReturnToHomeResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_control_pb2.ReturnToHomeResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmSetVelocityRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _control_pb2.SetVelocityRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_control_pb2.SetVelocityRequest, _Mapping]] = ...) -> None: ...

class SwarmSetVelocityResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _control_pb2.SetVelocityResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_control_pb2.SetVelocityResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmSetGimbalPoseRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _control_pb2.SetGimbalPoseRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_control_pb2.SetGimbalPoseRequest, _Mapping]] = ...) -> None: ...

class SwarmSetGimbalPoseResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _control_pb2.SetGimbalPoseResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_control_pb2.SetGimbalPoseResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmUploadMissionRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _mission_pb2.UploadMissionRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_mission_pb2.UploadMissionRequest, _Mapping]] = ...) -> None: ...

class SwarmUploadMissionResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _mission_pb2.UploadMissionResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_mission_pb2.UploadMissionResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmStartMissionRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _mission_pb2.StartMissionRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_mission_pb2.StartMissionRequest, _Mapping]] = ...) -> None: ...

class SwarmStartMissionResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _mission_pb2.StartMissionResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_mission_pb2.StartMissionResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...

class SwarmStopMissionRequest(_message.Message):
    __slots__ = ("vehicles", "request")
    VEHICLES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    vehicles: _containers.RepeatedScalarFieldContainer[str]
    request: _mission_pb2.StopMissionRequest
    def __init__(self, vehicles: _Optional[_Iterable[str]] = ..., request: _Optional[_Union[_mission_pb2.StopMissionRequest, _Mapping]] = ...) -> None: ...

class SwarmStopMissionResponse(_message.Message):
    __slots__ = ("vehicle", "response", "code", "details")
    VEHICLE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    vehicle: str
    response: _mission_pb2.StopMissionResponse
    code: int
    details: str
    def __init__(self, vehicle: _Optional[str] = ..., response: _Optional[_Union[_mission_pb2.StopMissionResponse, _Mapping]] = ..., code: _Optional[int] = ..., details: _Optional[str] = ...) -> None: ...
