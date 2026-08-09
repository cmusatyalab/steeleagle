from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CalibrateRequest(_message.Message):
    __slots__ = ("sensor", "id")
    class Sensor(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SENSOR_UNSPECIFIED: _ClassVar[CalibrateRequest.Sensor]
        SENSOR_MAGNETOMETER: _ClassVar[CalibrateRequest.Sensor]
        SENSOR_GIMBAL: _ClassVar[CalibrateRequest.Sensor]
        SENSOR_GYRO: _ClassVar[CalibrateRequest.Sensor]
    SENSOR_UNSPECIFIED: CalibrateRequest.Sensor
    SENSOR_MAGNETOMETER: CalibrateRequest.Sensor
    SENSOR_GIMBAL: CalibrateRequest.Sensor
    SENSOR_GYRO: CalibrateRequest.Sensor
    SENSOR_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    sensor: CalibrateRequest.Sensor
    id: int
    def __init__(self, sensor: _Optional[_Union[CalibrateRequest.Sensor, str]] = ..., id: _Optional[int] = ...) -> None: ...

class CalibrateResponse(_message.Message):
    __slots__ = ("next_instruction", "step", "total", "complete")
    NEXT_INSTRUCTION_FIELD_NUMBER: _ClassVar[int]
    STEP_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    COMPLETE_FIELD_NUMBER: _ClassVar[int]
    next_instruction: str
    step: int
    total: int
    complete: bool
    def __init__(self, next_instruction: _Optional[str] = ..., step: _Optional[int] = ..., total: _Optional[int] = ..., complete: _Optional[bool] = ...) -> None: ...
