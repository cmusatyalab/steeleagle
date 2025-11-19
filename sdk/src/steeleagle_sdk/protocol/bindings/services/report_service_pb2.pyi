import common_pb2 as _common_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union
DESCRIPTOR: _descriptor.FileDescriptor

class ReportMessage(_message.Message):
    __slots__ = ('report_code',)
    REPORT_CODE_FIELD_NUMBER: _ClassVar[int]
    report_code: int

    def __init__(self, report_code: _Optional[int]=...) -> None:
        ...

class SendReportRequest(_message.Message):
    __slots__ = ('request', 'report')
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    REPORT_FIELD_NUMBER: _ClassVar[int]
    request: _common_pb2.Request
    report: ReportMessage

    def __init__(self, request: _Optional[_Union[_common_pb2.Request, _Mapping]]=..., report: _Optional[_Union[ReportMessage, _Mapping]]=...) -> None:
        ...

class SendReportResponse(_message.Message):
    __slots__ = ('response',)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: _common_pb2.Response

    def __init__(self, response: _Optional[_Union[_common_pb2.Response, _Mapping]]=...) -> None:
        ...