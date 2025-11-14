"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/mission_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1eservices/mission_service.proto\x12,steeleagle.protocol.services.mission_service\x1a\x0ccommon.proto\x1a\x19google/protobuf/any.proto"\x1e\n\x0bMissionData\x12\x0f\n\x07content\x18\x01 \x01(\t"\x91\x01\n\rUploadRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12J\n\x07mission\x18\x02 \x01(\x0b29.steeleagle.protocol.services.mission_service.MissionData"H\n\x0eUploadResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"D\n\x0cStartRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"G\n\rStartResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"C\n\x0bStopRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"F\n\x0cStopResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"\x9a\x01\n\rNotifyRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x13\n\x0bnotify_code\x18\x02 \x01(\x05\x12.\n\x0bnotify_data\x18\x03 \x01(\x0b2\x14.google.protobuf.AnyH\x00\x88\x01\x01B\x0e\n\x0c_notify_data"H\n\x0eNotifyResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"j\n\x1fConfigureTelemetryStreamRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x11\n\tfrequency\x18\x02 \x01(\r"Z\n ConfigureTelemetryStreamResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response2\xdd\x05\n\x07Mission\x12\x85\x01\n\x06Upload\x12;.steeleagle.protocol.services.mission_service.UploadRequest\x1a<.steeleagle.protocol.services.mission_service.UploadResponse"\x00\x12\x82\x01\n\x05Start\x12:.steeleagle.protocol.services.mission_service.StartRequest\x1a;.steeleagle.protocol.services.mission_service.StartResponse"\x00\x12\x7f\n\x04Stop\x129.steeleagle.protocol.services.mission_service.StopRequest\x1a:.steeleagle.protocol.services.mission_service.StopResponse"\x00\x12\x85\x01\n\x06Notify\x12;.steeleagle.protocol.services.mission_service.NotifyRequest\x1a<.steeleagle.protocol.services.mission_service.NotifyResponse"\x00\x12\xbb\x01\n\x18ConfigureTelemetryStream\x12M.steeleagle.protocol.services.mission_service.ConfigureTelemetryStreamRequest\x1aN.steeleagle.protocol.services.mission_service.ConfigureTelemetryStreamResponse"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.mission_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_MISSIONDATA']._serialized_start = 121
    _globals['_MISSIONDATA']._serialized_end = 151
    _globals['_UPLOADREQUEST']._serialized_start = 154
    _globals['_UPLOADREQUEST']._serialized_end = 299
    _globals['_UPLOADRESPONSE']._serialized_start = 301
    _globals['_UPLOADRESPONSE']._serialized_end = 373
    _globals['_STARTREQUEST']._serialized_start = 375
    _globals['_STARTREQUEST']._serialized_end = 443
    _globals['_STARTRESPONSE']._serialized_start = 445
    _globals['_STARTRESPONSE']._serialized_end = 516
    _globals['_STOPREQUEST']._serialized_start = 518
    _globals['_STOPREQUEST']._serialized_end = 585
    _globals['_STOPRESPONSE']._serialized_start = 587
    _globals['_STOPRESPONSE']._serialized_end = 657
    _globals['_NOTIFYREQUEST']._serialized_start = 660
    _globals['_NOTIFYREQUEST']._serialized_end = 814
    _globals['_NOTIFYRESPONSE']._serialized_start = 816
    _globals['_NOTIFYRESPONSE']._serialized_end = 888
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_start = 890
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_end = 996
    _globals['_CONFIGURETELEMETRYSTREAMRESPONSE']._serialized_start = 998
    _globals['_CONFIGURETELEMETRYSTREAMRESPONSE']._serialized_end = 1088
    _globals['_MISSION']._serialized_start = 1091
    _globals['_MISSION']._serialized_end = 1824