from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class RegisterRequest(_message.Message):
    __slots__ = ("daemon_name", "name", "port")
    DAEMON_NAME_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    daemon_name: str
    name: str
    port: int
    def __init__(self, daemon_name: _Optional[str] = ..., name: _Optional[str] = ..., port: _Optional[int] = ...) -> None: ...

class RegisterResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
