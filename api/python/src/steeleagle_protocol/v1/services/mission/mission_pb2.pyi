from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class StartMissionRequest(_message.Message):
    __slots__ = ("uri",)
    URI_FIELD_NUMBER: _ClassVar[int]
    uri: str
    def __init__(self, uri: _Optional[str] = ...) -> None: ...

class StartMissionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StopMissionRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StopMissionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
