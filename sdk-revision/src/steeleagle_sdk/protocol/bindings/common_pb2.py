"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'common.proto')
_sym_db = _symbol_database.Default()
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0ccommon.proto\x12\x1asteeleagle.protocol.common\x1a\x1fgoogle/protobuf/timestamp.proto"8\n\x07Request\x12-\n\ttimestamp\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp"\xa7\x01\n\x08Response\x12:\n\x06status\x18\x01 \x01(\x0e2*.steeleagle.protocol.common.ResponseStatus\x12\x1c\n\x0fresponse_string\x18\x02 \x01(\tH\x00\x88\x01\x01\x12-\n\ttimestamp\x18\x03 \x01(\x0b2\x1a.google.protobuf.TimestampB\x12\n\x10_response_string"Z\n\x04Pose\x12\x12\n\x05pitch\x18\x01 \x01(\x01H\x00\x88\x01\x01\x12\x11\n\x04roll\x18\x02 \x01(\x01H\x01\x88\x01\x01\x12\x10\n\x03yaw\x18\x03 \x01(\x01H\x02\x88\x01\x01B\x08\n\x06_pitchB\x07\n\x05_rollB\x06\n\x04_yaw"\x8e\x01\n\x08Velocity\x12\x12\n\x05x_vel\x18\x01 \x01(\x01H\x00\x88\x01\x01\x12\x12\n\x05y_vel\x18\x02 \x01(\x01H\x01\x88\x01\x01\x12\x12\n\x05z_vel\x18\x03 \x01(\x01H\x02\x88\x01\x01\x12\x18\n\x0bangular_vel\x18\x04 \x01(\x01H\x03\x88\x01\x01B\x08\n\x06_x_velB\x08\n\x06_y_velB\x08\n\x06_z_velB\x0e\n\x0c_angular_vel"j\n\x08Position\x12\x0e\n\x01x\x18\x01 \x01(\x01H\x00\x88\x01\x01\x12\x0e\n\x01y\x18\x02 \x01(\x01H\x01\x88\x01\x01\x12\x0e\n\x01z\x18\x03 \x01(\x01H\x02\x88\x01\x01\x12\x12\n\x05angle\x18\x04 \x01(\x01H\x03\x88\x01\x01B\x04\n\x02_xB\x04\n\x02_yB\x04\n\x02_zB\x08\n\x06_angle"\x9a\x01\n\x08Location\x12\x15\n\x08latitude\x18\x01 \x01(\x01H\x00\x88\x01\x01\x12\x16\n\tlongitude\x18\x02 \x01(\x01H\x01\x88\x01\x01\x12\x15\n\x08altitude\x18\x03 \x01(\x01H\x02\x88\x01\x01\x12\x14\n\x07heading\x18\x04 \x01(\x01H\x03\x88\x01\x01B\x0b\n\t_latitudeB\x0c\n\n_longitudeB\x0b\n\t_altitudeB\n\n\x08_heading*\xe1\x02\n\x0eResponseStatus\x12\x06\n\x02OK\x10\x00\x12\x0f\n\x0bIN_PROGRESS\x10\x01\x12\r\n\tCOMPLETED\x10\x02\x12\r\n\tCANCELLED\x10\x03\x12\x0b\n\x07UNKNOWN\x10\x04\x12\x14\n\x10INVALID_ARGUMENT\x10\x05\x12\x15\n\x11DEADLINE_EXCEEDED\x10\x06\x12\r\n\tNOT_FOUND\x10\x07\x12\x12\n\x0eALREADY_EXISTS\x10\x08\x12\x15\n\x11PERMISSION_DENIED\x10\t\x12\x16\n\x12RESOURCE_EXHAUSTED\x10\n\x12\x17\n\x13FAILED_PRECONDITION\x10\x0b\x12\x0b\n\x07ABORTED\x10\x0c\x12\x10\n\x0cOUT_OF_RANGE\x10\r\x12\x11\n\rUNIMPLEMENTED\x10\x0e\x12\x0c\n\x08INTERNAL\x10\x0f\x12\x0f\n\x0bUNAVAILABLE\x10\x10\x12\r\n\tDATA_LOSS\x10\x11\x12\x13\n\x0fUNAUTHENTICATED\x10\x12b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'common_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_RESPONSESTATUS']._serialized_start = 808
    _globals['_RESPONSESTATUS']._serialized_end = 1161
    _globals['_REQUEST']._serialized_start = 77
    _globals['_REQUEST']._serialized_end = 133
    _globals['_RESPONSE']._serialized_start = 136
    _globals['_RESPONSE']._serialized_end = 303
    _globals['_POSE']._serialized_start = 305
    _globals['_POSE']._serialized_end = 395
    _globals['_VELOCITY']._serialized_start = 398
    _globals['_VELOCITY']._serialized_end = 540
    _globals['_POSITION']._serialized_start = 542
    _globals['_POSITION']._serialized_end = 648
    _globals['_LOCATION']._serialized_start = 651
    _globals['_LOCATION']._serialized_end = 805