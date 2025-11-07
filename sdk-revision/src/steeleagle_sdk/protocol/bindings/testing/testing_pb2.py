"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'testing/testing.proto')
_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x15testing/testing.proto\x12\x1bsteeleagle.protocol.testing"Q\n\x0cServiceReady\x12A\n\x0freadied_service\x18\x01 \x01(\x0e2(.steeleagle.protocol.testing.ServiceType*f\n\x0bServiceType\x12\x11\n\rCORE_SERVICES\x10\x00\x12\x13\n\x0fSTREAM_SERVICES\x10\x01\x12\x13\n\x0fMISSION_SERVICE\x10\x02\x12\x1a\n\x16DRIVER_CONTROL_SERVICE\x10\x03b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'testing.testing_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_SERVICETYPE']._serialized_start = 137
    _globals['_SERVICETYPE']._serialized_end = 239
    _globals['_SERVICEREADY']._serialized_start = 54
    _globals['_SERVICEREADY']._serialized_end = 135