"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/remote_service.proto')
_sym_db = _symbol_database.Default()
from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dservices/remote_service.proto\x12+steeleagle.protocol.services.remote_service\x1a\x19google/protobuf/any.proto"\xa5\x01\n\x0eCommandRequest\x12\x1c\n\x0fsequence_number\x18\x01 \x01(\rH\x00\x88\x01\x01\x12%\n\x07request\x18\x02 \x01(\x0b2\x14.google.protobuf.Any\x12\x13\n\x0bmethod_name\x18\x03 \x01(\t\x12\x10\n\x08identity\x18\x04 \x01(\t\x12\x13\n\x0bvehicle_ids\x18\x05 \x03(\tB\x12\n\x10_sequence_number"v\n\x0fCommandResponse\x12\x17\n\x0fsequence_number\x18\x01 \x01(\r\x12+\n\x08response\x18\x02 \x01(\x0b2\x14.google.protobuf.AnyH\x00\x88\x01\x01\x12\x10\n\x08identity\x18\x03 \x01(\tB\x0b\n\t_response"2\n\x0eCompileRequest\x12\x0b\n\x03dsl\x18\x01 \x01(\t\x12\x13\n\x0bvehicle_ids\x18\x02 \x03(\t"_\n\x0fCompileResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x15\n\x08compiled\x18\x02 \x01(\x0cH\x00\x88\x01\x01\x12\x17\n\x0fresponse_string\x18\x03 \x01(\tB\x0b\n\t_compiled2\x9c\x02\n\x06Remote\x12\x88\x01\n\x07Command\x12;.steeleagle.protocol.services.remote_service.CommandRequest\x1a<.steeleagle.protocol.services.remote_service.CommandResponse"\x000\x01\x12\x86\x01\n\x07Compile\x12;.steeleagle.protocol.services.remote_service.CompileRequest\x1a<.steeleagle.protocol.services.remote_service.CompileResponse"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.remote_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_COMMANDREQUEST']._serialized_start = 106
    _globals['_COMMANDREQUEST']._serialized_end = 271
    _globals['_COMMANDRESPONSE']._serialized_start = 273
    _globals['_COMMANDRESPONSE']._serialized_end = 391
    _globals['_COMPILEREQUEST']._serialized_start = 393
    _globals['_COMPILEREQUEST']._serialized_end = 443
    _globals['_COMPILERESPONSE']._serialized_start = 445
    _globals['_COMPILERESPONSE']._serialized_end = 540
    _globals['_REMOTE']._serialized_start = 543
    _globals['_REMOTE']._serialized_end = 827