"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/compute_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1eservices/compute_service.proto\x12,steeleagle.protocol.services.compute_service\x1a\x0ccommon.proto"\xb8\x01\n\x0cDatasinkInfo\x12\n\n\x02id\x18\x01 \x01(\t\x12P\n\x08location\x18\x02 \x01(\x0e2>.steeleagle.protocol.services.compute_service.DatasinkLocation\x12J\n\x07sources\x18\x03 \x03(\x0e29.steeleagle.protocol.services.compute_service.InputSource"\x9a\x01\n\x13AddDatasinksRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12M\n\tdatasinks\x18\x02 \x03(\x0b2:.steeleagle.protocol.services.compute_service.DatasinkInfo"\x9a\x01\n\x13SetDatasinksRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12M\n\tdatasinks\x18\x02 \x03(\x0b2:.steeleagle.protocol.services.compute_service.DatasinkInfo"\x9d\x01\n\x16RemoveDatasinksRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12M\n\tdatasinks\x18\x02 \x03(\x0b2:.steeleagle.protocol.services.compute_service.DatasinkInfo*)\n\x10DatasinkLocation\x12\n\n\x06REMOTE\x10\x00\x12\t\n\x05LOCAL\x10\x01*_\n\x0bInputSource\x12\x16\n\x12SOURCE_UNSPECIFIED\x10\x00\x12\x14\n\x10DRIVER_TELEMETRY\x10\x01\x12\x15\n\x11MISSION_TELEMETRY\x10\x02\x12\x0b\n\x07IMAGERY\x10\x032\x80\x03\n\x07Compute\x12y\n\x0cAddDatasinks\x12A.steeleagle.protocol.services.compute_service.AddDatasinksRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12y\n\x0cSetDatasinks\x12A.steeleagle.protocol.services.compute_service.SetDatasinksRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12\x7f\n\x0fRemoveDatasinks\x12D.steeleagle.protocol.services.compute_service.RemoveDatasinksRequest\x1a$.steeleagle.protocol.common.Response"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.compute_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_DATASINKLOCATION']._serialized_start = 755
    _globals['_DATASINKLOCATION']._serialized_end = 796
    _globals['_INPUTSOURCE']._serialized_start = 798
    _globals['_INPUTSOURCE']._serialized_end = 893
    _globals['_DATASINKINFO']._serialized_start = 95
    _globals['_DATASINKINFO']._serialized_end = 279
    _globals['_ADDDATASINKSREQUEST']._serialized_start = 282
    _globals['_ADDDATASINKSREQUEST']._serialized_end = 436
    _globals['_SETDATASINKSREQUEST']._serialized_start = 439
    _globals['_SETDATASINKSREQUEST']._serialized_end = 593
    _globals['_REMOVEDATASINKSREQUEST']._serialized_start = 596
    _globals['_REMOVEDATASINKSREQUEST']._serialized_end = 753
    _globals['_COMPUTE']._serialized_start = 896
    _globals['_COMPUTE']._serialized_end = 1280