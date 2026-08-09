import datetime

from steeleagle_protocol.v1.common import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BoundingBox(_message.Message):
    __slots__ = ("y_min", "x_min", "y_max", "x_max")
    Y_MIN_FIELD_NUMBER: _ClassVar[int]
    X_MIN_FIELD_NUMBER: _ClassVar[int]
    Y_MAX_FIELD_NUMBER: _ClassVar[int]
    X_MAX_FIELD_NUMBER: _ClassVar[int]
    y_min: float
    x_min: float
    y_max: float
    x_max: float
    def __init__(self, y_min: _Optional[float] = ..., x_min: _Optional[float] = ..., y_max: _Optional[float] = ..., x_max: _Optional[float] = ...) -> None: ...

class Detection(_message.Message):
    __slots__ = ("class_name", "score", "bbox")
    CLASS_NAME_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    BBOX_FIELD_NUMBER: _ClassVar[int]
    class_name: str
    score: float
    bbox: BoundingBox
    def __init__(self, class_name: _Optional[str] = ..., score: _Optional[float] = ..., bbox: _Optional[_Union[BoundingBox, _Mapping]] = ...) -> None: ...

class DetectionResult(_message.Message):
    __slots__ = ("detections",)
    DETECTIONS_FIELD_NUMBER: _ClassVar[int]
    detections: _containers.RepeatedCompositeFieldContainer[Detection]
    def __init__(self, detections: _Optional[_Iterable[_Union[Detection, _Mapping]]] = ...) -> None: ...

class GuidanceResult(_message.Message):
    __slots__ = ("trajectory",)
    TRAJECTORY_FIELD_NUMBER: _ClassVar[int]
    trajectory: _common_pb2.Velocity
    def __init__(self, trajectory: _Optional[_Union[_common_pb2.Velocity, _Mapping]] = ...) -> None: ...

class SlamResult(_message.Message):
    __slots__ = ("relative_position", "global_position")
    RELATIVE_POSITION_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_POSITION_FIELD_NUMBER: _ClassVar[int]
    relative_position: _common_pb2.RelativePosition
    global_position: _common_pb2.GlobalPosition
    def __init__(self, relative_position: _Optional[_Union[_common_pb2.RelativePosition, _Mapping]] = ..., global_position: _Optional[_Union[_common_pb2.GlobalPosition, _Mapping]] = ...) -> None: ...

class ComputeResult(_message.Message):
    __slots__ = ("timestamp", "detection_result", "guidance_result", "slam_result", "generic_result")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DETECTION_RESULT_FIELD_NUMBER: _ClassVar[int]
    GUIDANCE_RESULT_FIELD_NUMBER: _ClassVar[int]
    SLAM_RESULT_FIELD_NUMBER: _ClassVar[int]
    GENERIC_RESULT_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    detection_result: DetectionResult
    guidance_result: GuidanceResult
    slam_result: SlamResult
    generic_result: bytes
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., detection_result: _Optional[_Union[DetectionResult, _Mapping]] = ..., guidance_result: _Optional[_Union[GuidanceResult, _Mapping]] = ..., slam_result: _Optional[_Union[SlamResult, _Mapping]] = ..., generic_result: _Optional[bytes] = ...) -> None: ...
