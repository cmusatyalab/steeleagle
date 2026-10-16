import datetime

from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as _telemetry_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

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
    position_info: _telemetry_pb2.PositionInfo
    gimbal_info: _telemetry_pb2.GimbalInfo
    camera_id: int
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., data: _Optional[bytes] = ..., h_res: _Optional[int] = ..., v_res: _Optional[int] = ..., d_res: _Optional[int] = ..., channels: _Optional[int] = ..., id: _Optional[int] = ..., position_info: _Optional[_Union[_telemetry_pb2.PositionInfo, _Mapping]] = ..., gimbal_info: _Optional[_Union[_telemetry_pb2.GimbalInfo, _Mapping]] = ..., camera_id: _Optional[int] = ...) -> None: ...

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
    gimbal_info: _telemetry_pb2.GimbalInfo
    position_info: _telemetry_pb2.PositionInfo
    camera_id: int
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., encoded_data: _Optional[bytes] = ..., id: _Optional[int] = ..., gimbal_info: _Optional[_Union[_telemetry_pb2.GimbalInfo, _Mapping]] = ..., position_info: _Optional[_Union[_telemetry_pb2.PositionInfo, _Mapping]] = ..., camera_id: _Optional[int] = ...) -> None: ...
