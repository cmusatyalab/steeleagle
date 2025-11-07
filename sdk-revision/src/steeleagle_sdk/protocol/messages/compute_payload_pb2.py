"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'messages/compute_payload.proto')
_sym_db = _symbol_database.Default()
from ..messages import telemetry_pb2 as messages_dot_telemetry__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1emessages/compute_payload.proto\x12,steeleagle.protocol.messages.compute_payload\x1a\x18messages/telemetry.proto"\xc6\x01\n\x0eComputePayload\x12\x13\n\x0bregistering\x18\x01 \x01(\x08\x12N\n\rvehicle_telem\x18\x02 \x01(\x0b27.steeleagle.protocol.messages.telemetry.DriverTelemetry\x12O\n\rmission_telem\x18\x03 \x01(\x0b28.steeleagle.protocol.messages.telemetry.MissionTelemetryb\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'messages.compute_payload_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_COMPUTEPAYLOAD']._serialized_start = 107
    _globals['_COMPUTEPAYLOAD']._serialized_end = 305