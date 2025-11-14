"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/mission_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1eservices/mission_service.proto\x12,steeleagle.protocol.services.mission_service\x1a\x0ccommon.proto"+\n\x0bMissionData\x12\x0f\n\x07content\x18\x01 \x01(\t\x12\x0b\n\x03map\x18\x02 \x01(\x0c"\x91\x01\n\rUploadRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12J\n\x07mission\x18\x02 \x01(\x0b29.steeleagle.protocol.services.mission_service.MissionData"D\n\x0cStartRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"C\n\x0bStopRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"Z\n\rNotifyRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x13\n\x0bnotify_code\x18\x02 \x01(\x05"j\n\x1fConfigureTelemetryStreamRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x11\n\tfrequency\x18\x02 \x01(\r"Z\n ConfigureTelemetryStreamResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response2\xd3\x04\n\x07Mission\x12m\n\x06Upload\x12;.steeleagle.protocol.services.mission_service.UploadRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12k\n\x05Start\x12:.steeleagle.protocol.services.mission_service.StartRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12i\n\x04Stop\x129.steeleagle.protocol.services.mission_service.StopRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12m\n\x06Notify\x12;.steeleagle.protocol.services.mission_service.NotifyRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12\x91\x01\n\x18ConfigureTelemetryStream\x12M.steeleagle.protocol.services.mission_service.ConfigureTelemetryStreamRequest\x1a$.steeleagle.protocol.common.Response"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.mission_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_MISSIONDATA']._serialized_start = 94
    _globals['_MISSIONDATA']._serialized_end = 137
    _globals['_UPLOADREQUEST']._serialized_start = 140
    _globals['_UPLOADREQUEST']._serialized_end = 285
    _globals['_STARTREQUEST']._serialized_start = 287
    _globals['_STARTREQUEST']._serialized_end = 355
    _globals['_STOPREQUEST']._serialized_start = 357
    _globals['_STOPREQUEST']._serialized_end = 424
    _globals['_NOTIFYREQUEST']._serialized_start = 426
    _globals['_NOTIFYREQUEST']._serialized_end = 516
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_start = 518
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_end = 624
    _globals['_CONFIGURETELEMETRYSTREAMRESPONSE']._serialized_start = 626
    _globals['_CONFIGURETELEMETRYSTREAMRESPONSE']._serialized_end = 716
    _globals['_MISSION']._serialized_start = 719
    _globals['_MISSION']._serialized_end = 1314