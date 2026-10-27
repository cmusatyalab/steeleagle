import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FailsafeState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FAILSAFE_STATE_UNSPECIFIED: _ClassVar[FailsafeState]
    FAILSAFE_STATE_NONE: _ClassVar[FailsafeState]
    FAILSAFE_STATE_NO_CONTROL: _ClassVar[FailsafeState]
    FAILSAFE_STATE_NO_DATA: _ClassVar[FailsafeState]
    FAILSAFE_STATE_NO_CONTROL_NO_DATA: _ClassVar[FailsafeState]

class FailsafeBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FAILSAFE_BEHAVIOR_UNSPECIFIED: _ClassVar[FailsafeBehavior]
    FAILSAFE_BEHAVIOR_HOLD: _ClassVar[FailsafeBehavior]
    FAILSAFE_BEHAVIOR_RTH: _ClassVar[FailsafeBehavior]
    FAILSAFE_BEHAVIOR_MISSION: _ClassVar[FailsafeBehavior]
    FAILSAFE_BEHAVIOR_NONE: _ClassVar[FailsafeBehavior]
FAILSAFE_STATE_UNSPECIFIED: FailsafeState
FAILSAFE_STATE_NONE: FailsafeState
FAILSAFE_STATE_NO_CONTROL: FailsafeState
FAILSAFE_STATE_NO_DATA: FailsafeState
FAILSAFE_STATE_NO_CONTROL_NO_DATA: FailsafeState
FAILSAFE_BEHAVIOR_UNSPECIFIED: FailsafeBehavior
FAILSAFE_BEHAVIOR_HOLD: FailsafeBehavior
FAILSAFE_BEHAVIOR_RTH: FailsafeBehavior
FAILSAFE_BEHAVIOR_MISSION: FailsafeBehavior
FAILSAFE_BEHAVIOR_NONE: FailsafeBehavior

class GetFailsafeStateRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetFailsafeStateResponse(_message.Message):
    __slots__ = ("state", "time")
    STATE_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    state: FailsafeState
    time: _duration_pb2.Duration
    def __init__(self, state: _Optional[_Union[FailsafeState, str]] = ..., time: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class SetControlFailsafeBehaviorRequest(_message.Message):
    __slots__ = ("behavior",)
    BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
    behavior: FailsafeBehavior
    def __init__(self, behavior: _Optional[_Union[FailsafeBehavior, str]] = ...) -> None: ...

class SetControlFailsafeBehaviorResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetDataFailsafeBehaviorRequest(_message.Message):
    __slots__ = ("behavior",)
    BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
    behavior: FailsafeBehavior
    def __init__(self, behavior: _Optional[_Union[FailsafeBehavior, str]] = ...) -> None: ...

class SetDataFailsafeBehaviorResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
