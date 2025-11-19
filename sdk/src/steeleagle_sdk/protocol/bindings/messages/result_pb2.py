"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'messages/result.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x15messages/result.proto\x12#steeleagle.protocol.messages.result\x1a\x0ccommon.proto\x1a\x1fgoogle/protobuf/timestamp.proto"q\n\x0bBoundingBox\x12\r\n\x05y_min\x18\x01 \x01(\x01\x12\r\n\x05x_min\x18\x02 \x01(\x01\x12\r\n\x05y_max\x18\x03 \x01(\x01\x12\r\n\x05x_max\x18\x04 \x01(\x01\x12\x12\n\nclass_name\x18\x05 \x01(\t\x12\x12\n\nconfidence\x18\x06 \x01(\x02"&\n\x03HSV\x12\t\n\x01h\x18\x01 \x01(\r\x12\t\n\x01s\x18\x02 \x01(\r\x12\t\n\x01v\x18\x03 \x01(\r"\x9f\x01\n\tDetection\x12\x14\n\x0cdetection_id\x18\x01 \x01(\x04\x12\x12\n\nclass_name\x18\x02 \x01(\t\x12\r\n\x05score\x18\x03 \x01(\x01\x12>\n\x04bbox\x18\x04 \x01(\x0b20.steeleagle.protocol.messages.result.BoundingBox\x12\x19\n\x11hsv_filter_passed\x18\x05 \x01(\x08"U\n\x0fDetectionResult\x12B\n\ndetections\x18\x01 \x03(\x0b2..steeleagle.protocol.messages.result.Detection"+\n\x0fAvoidanceResult\x12\x18\n\x10actuation_vector\x18\x01 \x01(\x01"\x9c\x01\n\nSLAMResult\x12A\n\x11relative_position\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.PositionH\x00\x12?\n\x0fglobal_position\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.LocationH\x00B\n\n\x08position"\xe1\x02\n\rComputeResult\x12-\n\ttimestamp\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12\x13\n\x0bengine_name\x18\x02 \x01(\t\x12P\n\x10detection_result\x18\x03 \x01(\x0b24.steeleagle.protocol.messages.result.DetectionResultH\x00\x12P\n\x10avoidance_result\x18\x04 \x01(\x0b24.steeleagle.protocol.messages.result.AvoidanceResultH\x00\x12F\n\x0bslam_result\x18\x05 \x01(\x0b2/.steeleagle.protocol.messages.result.SLAMResultH\x00\x12\x18\n\x0egeneric_result\x18\x06 \x01(\tH\x00B\x06\n\x04type"q\n\x0bFrameResult\x12\x0c\n\x04type\x18\x01 \x01(\t\x12\x10\n\x08frame_id\x18\x02 \x01(\x04\x12B\n\x06result\x18\x03 \x03(\x0b22.steeleagle.protocol.messages.result.ComputeResultb\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'messages.result_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_BOUNDINGBOX']._serialized_start = 109
    _globals['_BOUNDINGBOX']._serialized_end = 222
    _globals['_HSV']._serialized_start = 224
    _globals['_HSV']._serialized_end = 262
    _globals['_DETECTION']._serialized_start = 265
    _globals['_DETECTION']._serialized_end = 424
    _globals['_DETECTIONRESULT']._serialized_start = 426
    _globals['_DETECTIONRESULT']._serialized_end = 511
    _globals['_AVOIDANCERESULT']._serialized_start = 513
    _globals['_AVOIDANCERESULT']._serialized_end = 556
    _globals['_SLAMRESULT']._serialized_start = 559
    _globals['_SLAMRESULT']._serialized_end = 715
    _globals['_COMPUTERESULT']._serialized_start = 718
    _globals['_COMPUTERESULT']._serialized_end = 1071
    _globals['_FRAMERESULT']._serialized_start = 1073
    _globals['_FRAMERESULT']._serialized_end = 1186