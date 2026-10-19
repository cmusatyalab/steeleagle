from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class TransferFileRequest(_message.Message):
    __slots__ = ("chunk", "number", "total")
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    chunk: bytes
    number: int
    total: int
    def __init__(self, chunk: _Optional[bytes] = ..., number: _Optional[int] = ..., total: _Optional[int] = ...) -> None: ...

class TransferFileResponse(_message.Message):
    __slots__ = ("received",)
    RECEIVED_FIELD_NUMBER: _ClassVar[int]
    received: int
    def __init__(self, received: _Optional[int] = ...) -> None: ...

class TransferModelRequest(_message.Message):
    __slots__ = ("chunk", "number", "total")
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    chunk: bytes
    number: int
    total: int
    def __init__(self, chunk: _Optional[bytes] = ..., number: _Optional[int] = ..., total: _Optional[int] = ...) -> None: ...

class TransferModelResponse(_message.Message):
    __slots__ = ("received",)
    RECEIVED_FIELD_NUMBER: _ClassVar[int]
    received: int
    def __init__(self, received: _Optional[int] = ...) -> None: ...
