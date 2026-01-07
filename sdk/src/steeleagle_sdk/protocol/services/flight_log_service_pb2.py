"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/flight_log_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n!services/flight_log_service.proto\x12/steeleagle.protocol.services.flight_log_service\x1a\x0ccommon.proto"\x9b\x01\n\nLogRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\r\n\x05topic\x18\x02 \x01(\t\x12H\n\x03log\x18\x03 \x01(\x0b2;.steeleagle.protocol.services.flight_log_service.LogMessage"a\n\nLogMessage\x12F\n\x04type\x18\x01 \x01(\x0e28.steeleagle.protocol.services.flight_log_service.LogType\x12\x0b\n\x03msg\x18\x02 \x01(\t"\xa6\x01\n\x0bReqRepProto\x126\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.RequestH\x00\x128\n\x08response\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.ResponseH\x00\x12\x0c\n\x04name\x18\x03 \x01(\t\x12\x0f\n\x07content\x18\x04 \x01(\tB\x06\n\x04type"\xaa\x01\n\x0fLogProtoRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\r\n\x05topic\x18\x02 \x01(\t\x12R\n\x0creqrep_proto\x18\x03 \x01(\x0b2<.steeleagle.protocol.services.flight_log_service.ReqRepProto*O\n\x07LogType\x12\t\n\x05DEBUG\x10\x00\x12\x08\n\x04INFO\x10\x01\x12\t\n\x05PROTO\x10\x02\x12\x0b\n\x07WARNING\x10\x03\x12\t\n\x05ERROR\x10\x04\x12\x0c\n\x08CRITICAL\x10\x052\xed\x01\n\tFlightLog\x12j\n\x03Log\x12;.steeleagle.protocol.services.flight_log_service.LogRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12t\n\x08LogProto\x12@.steeleagle.protocol.services.flight_log_service.LogProtoRequest\x1a$.steeleagle.protocol.common.Response"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.flight_log_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_LOGTYPE']._serialized_start = 699
    _globals['_LOGTYPE']._serialized_end = 778
    _globals['_LOGREQUEST']._serialized_start = 101
    _globals['_LOGREQUEST']._serialized_end = 256
    _globals['_LOGMESSAGE']._serialized_start = 258
    _globals['_LOGMESSAGE']._serialized_end = 355
    _globals['_REQREPPROTO']._serialized_start = 358
    _globals['_REQREPPROTO']._serialized_end = 524
    _globals['_LOGPROTOREQUEST']._serialized_start = 527
    _globals['_LOGPROTOREQUEST']._serialized_end = 697
    _globals['_FLIGHTLOG']._serialized_start = 781
    _globals['_FLIGHTLOG']._serialized_end = 1018