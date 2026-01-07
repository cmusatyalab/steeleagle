"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/remote_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dservices/remote_service.proto\x12+steeleagle.protocol.services.remote_service\x1a\x0ccommon.proto\x1a\x19google/protobuf/any.proto",\n\x15CompileMissionRequest\x12\x13\n\x0bdsl_content\x18\x01 \x01(\t"n\n\x16CompileMissionResponse\x12\x1c\n\x14compiled_dsl_content\x18\x01 \x01(\t\x126\n\x08response\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Response"\xa4\x01\n\x0eCommandRequest\x12\x1c\n\x0fsequence_number\x18\x01 \x01(\rH\x00\x88\x01\x01\x12%\n\x07request\x18\x02 \x01(\x0b2\x14.google.protobuf.Any\x12\x13\n\x0bmethod_name\x18\x03 \x01(\t\x12\x10\n\x08identity\x18\x04 \x01(\t\x12\x12\n\nvehicle_id\x18\x05 \x01(\tB\x12\n\x10_sequence_number"b\n\x0fCommandResponse\x12\x17\n\x0fsequence_number\x18\x01 \x01(\r\x126\n\x08response\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Response2\x98\x02\n\x06Remote\x12p\n\x07Command\x12;.steeleagle.protocol.services.remote_service.CommandRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12\x9b\x01\n\x0eCompileMission\x12B.steeleagle.protocol.services.remote_service.CompileMissionRequest\x1aC.steeleagle.protocol.services.remote_service.CompileMissionResponse"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.remote_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_COMPILEMISSIONREQUEST']._serialized_start = 119
    _globals['_COMPILEMISSIONREQUEST']._serialized_end = 163
    _globals['_COMPILEMISSIONRESPONSE']._serialized_start = 165
    _globals['_COMPILEMISSIONRESPONSE']._serialized_end = 275
    _globals['_COMMANDREQUEST']._serialized_start = 278
    _globals['_COMMANDREQUEST']._serialized_end = 442
    _globals['_COMMANDRESPONSE']._serialized_start = 444
    _globals['_COMMANDRESPONSE']._serialized_end = 542
    _globals['_REMOTE']._serialized_start = 545
    _globals['_REMOTE']._serialized_end = 825