"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/report_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dservices/report_service.proto\x12+steeleagle.protocol.services.report_service\x1a\x0ccommon.proto"$\n\rReportMessage\x12\x13\n\x0breport_code\x18\x01 \x01(\x05"\x95\x01\n\x11SendReportRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12J\n\x06report\x18\x02 \x01(\x0b2:.steeleagle.protocol.services.report_service.ReportMessage"L\n\x12SendReportResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response2\x9a\x01\n\x06Report\x12\x8f\x01\n\nSendReport\x12>.steeleagle.protocol.services.report_service.SendReportRequest\x1a?.steeleagle.protocol.services.report_service.SendReportResponse"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.report_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_REPORTMESSAGE']._serialized_start = 92
    _globals['_REPORTMESSAGE']._serialized_end = 128
    _globals['_SENDREPORTREQUEST']._serialized_start = 131
    _globals['_SENDREPORTREQUEST']._serialized_end = 280
    _globals['_SENDREPORTRESPONSE']._serialized_start = 282
    _globals['_SENDREPORTRESPONSE']._serialized_end = 358
    _globals['_REPORT']._serialized_start = 361
    _globals['_REPORT']._serialized_end = 515