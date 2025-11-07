"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'messages/telemetry.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
from google.protobuf import duration_pb2 as google_dot_protobuf_dot_duration__pb2
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x18messages/telemetry.proto\x12&steeleagle.protocol.messages.telemetry\x1a\x0ccommon.proto\x1a\x1egoogle/protobuf/duration.proto\x1a\x1fgoogle/protobuf/timestamp.proto"r\n\x13TelemetryStreamInfo\x12\x19\n\x11current_frequency\x18\x01 \x01(\r\x12\x15\n\rmax_frequency\x18\x02 \x01(\r\x12)\n\x06uptime\x18\x03 \x01(\x0b2\x19.google.protobuf.Duration"!\n\x0bBatteryInfo\x12\x12\n\npercentage\x18\x01 \x01(\r"\x1d\n\x07GPSInfo\x12\x12\n\nsatellites\x18\x01 \x01(\r"\x0b\n\tCommsInfo"\xe2\x02\n\x0bVehicleInfo\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\r\n\x05model\x18\x02 \x01(\t\x12\x14\n\x0cmanufacturer\x18\x03 \x01(\t\x12K\n\rmotion_status\x18\x04 \x01(\x0e24.steeleagle.protocol.messages.telemetry.MotionStatus\x12I\n\x0cbattery_info\x18\x05 \x01(\x0b23.steeleagle.protocol.messages.telemetry.BatteryInfo\x12A\n\x08gps_info\x18\x06 \x01(\x0b2/.steeleagle.protocol.messages.telemetry.GPSInfo\x12E\n\ncomms_info\x18\x07 \x01(\x0b21.steeleagle.protocol.messages.telemetry.CommsInfo"\xdb\x02\n\x0cSetpointInfo\x12@\n\x10position_body_sp\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.PositionH\x00\x12?\n\x0fposition_enu_sp\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.PositionH\x00\x129\n\tglobal_sp\x18\x03 \x01(\x0b2$.steeleagle.protocol.common.LocationH\x00\x12@\n\x10velocity_body_sp\x18\x04 \x01(\x0b2$.steeleagle.protocol.common.VelocityH\x00\x12?\n\x0fvelocity_enu_sp\x18\x05 \x01(\x0b2$.steeleagle.protocol.common.VelocityH\x00B\n\n\x08setpoint"\x88\x03\n\x0cPositionInfo\x122\n\x04home\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Location\x12=\n\x0fglobal_position\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Location\x12?\n\x11relative_position\x18\x03 \x01(\x0b2$.steeleagle.protocol.common.Position\x12:\n\x0cvelocity_enu\x18\x04 \x01(\x0b2$.steeleagle.protocol.common.Velocity\x12;\n\rvelocity_body\x18\x05 \x01(\x0b2$.steeleagle.protocol.common.Velocity\x12K\n\rsetpoint_info\x18\x06 \x01(\x0b24.steeleagle.protocol.messages.telemetry.SetpointInfo"\x83\x01\n\x0cGimbalStatus\x12\n\n\x02id\x18\x01 \x01(\r\x123\n\tpose_body\x18\x02 \x01(\x0b2 .steeleagle.protocol.common.Pose\x122\n\x08pose_enu\x18\x03 \x01(\x0b2 .steeleagle.protocol.common.Pose"h\n\nGimbalInfo\x12\x13\n\x0bnum_gimbals\x18\x01 \x01(\r\x12E\n\x07gimbals\x18\x02 \x03(\x0b24.steeleagle.protocol.messages.telemetry.GimbalStatus"\xb5\x02\n\x13ImagingSensorStatus\x12\n\n\x02id\x18\x01 \x01(\r\x12G\n\x04type\x18\x02 \x01(\x0e29.steeleagle.protocol.messages.telemetry.ImagingSensorType\x12\x0e\n\x06active\x18\x03 \x01(\x08\x12\x1a\n\x12supports_secondary\x18\x04 \x01(\x08\x12\x13\n\x0bcurrent_fps\x18\x05 \x01(\r\x12\x0f\n\x07max_fps\x18\x06 \x01(\r\x12\r\n\x05h_res\x18\x07 \x01(\r\x12\r\n\x05v_res\x18\x08 \x01(\r\x12\x10\n\x08channels\x18\t \x01(\r\x12\r\n\x05h_fov\x18\n \x01(\r\x12\r\n\x05v_fov\x18\x0b \x01(\r\x12\x16\n\x0egimbal_mounted\x18\x0c \x01(\x08\x12\x11\n\tgimbal_id\x18\r \x01(\r"v\n\x19ImagingSensorStreamStatus\x12\x17\n\x0fstream_capacity\x18\x01 \x01(\r\x12\x13\n\x0bnum_streams\x18\x02 \x01(\r\x12\x13\n\x0bprimary_cam\x18\x03 \x01(\r\x12\x16\n\x0esecondary_cams\x18\x04 \x03(\r"\xbb\x01\n\x11ImagingSensorInfo\x12X\n\rstream_status\x18\x01 \x01(\x0b2A.steeleagle.protocol.messages.telemetry.ImagingSensorStreamStatus\x12L\n\x07sensors\x18\x02 \x03(\x0b2;.steeleagle.protocol.messages.telemetry.ImagingSensorStatus"\xa8\x03\n\tAlertInfo\x12O\n\x0fbattery_warning\x18\x01 \x01(\x0e26.steeleagle.protocol.messages.telemetry.BatteryWarning\x12G\n\x0bgps_warning\x18\x02 \x01(\x0e22.steeleagle.protocol.messages.telemetry.GPSWarning\x12Y\n\x14magnetometer_warning\x18\x03 \x01(\x0e2;.steeleagle.protocol.messages.telemetry.MagnetometerWarning\x12U\n\x12connection_warning\x18\x04 \x01(\x0e29.steeleagle.protocol.messages.telemetry.ConnectionWarning\x12O\n\x0fcompass_warning\x18\x05 \x01(\x0e26.steeleagle.protocol.messages.telemetry.CompassWarning"\x9c\x04\n\x0fDriverTelemetry\x12-\n\ttimestamp\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12Z\n\x15telemetry_stream_info\x18\x02 \x01(\x0b2;.steeleagle.protocol.messages.telemetry.TelemetryStreamInfo\x12I\n\x0cvehicle_info\x18\x03 \x01(\x0b23.steeleagle.protocol.messages.telemetry.VehicleInfo\x12K\n\rposition_info\x18\x04 \x01(\x0b24.steeleagle.protocol.messages.telemetry.PositionInfo\x12G\n\x0bgimbal_info\x18\x05 \x01(\x0b22.steeleagle.protocol.messages.telemetry.GimbalInfo\x12V\n\x13imaging_sensor_info\x18\x06 \x01(\x0b29.steeleagle.protocol.messages.telemetry.ImagingSensorInfo\x12E\n\nalert_info\x18\x07 \x01(\x0b21.steeleagle.protocol.messages.telemetry.AlertInfo"\x8f\x01\n\x05Frame\x12-\n\ttimestamp\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12\x0c\n\x04data\x18\x02 \x01(\x0c\x12\r\n\x05h_res\x18\x03 \x01(\x04\x12\r\n\x05v_res\x18\x04 \x01(\x04\x12\r\n\x05d_res\x18\x05 \x01(\x04\x12\x10\n\x08channels\x18\x06 \x01(\x04\x12\n\n\x02id\x18\x07 \x01(\x04"\xb4\x01\n\x0bMissionInfo\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0c\n\x04hash\x18\x02 \x01(\x03\x12\'\n\x03age\x18\x03 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12L\n\nexec_state\x18\x04 \x01(\x0e28.steeleagle.protocol.messages.telemetry.MissionExecState\x12\x12\n\ntask_state\x18\x05 \x01(\t"\xe8\x01\n\x10MissionTelemetry\x12-\n\ttimestamp\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12Z\n\x15telemetry_stream_info\x18\x02 \x01(\x0b2;.steeleagle.protocol.messages.telemetry.TelemetryStreamInfo\x12I\n\x0cmission_info\x18\x03 \x03(\x0b23.steeleagle.protocol.messages.telemetry.MissionInfo*E\n\x0cMotionStatus\x12\x0e\n\nMOTORS_OFF\x10\x00\x12\x0b\n\x07RAMPING\x10\x01\x12\x08\n\x04IDLE\x10\x02\x12\x0e\n\nIN_TRANSIT\x10\x03*\x8a\x01\n\x11ImagingSensorType\x12\x1f\n\x1bUNKNOWN_IMAGING_SENSOR_TYPE\x10\x00\x12\x07\n\x03RGB\x10\x01\x12\n\n\x06STEREO\x10\x02\x12\x0b\n\x07THERMAL\x10\x03\x12\t\n\x05NIGHT\x10\x04\x12\t\n\x05LIDAR\x10\x05\x12\x08\n\x04RGBD\x10\x06\x12\x07\n\x03TOF\x10\x07\x12\t\n\x05RADAR\x10\x08*1\n\x0eBatteryWarning\x12\x08\n\x04NONE\x10\x00\x12\x07\n\x03LOW\x10\x01\x12\x0c\n\x08CRITICAL\x10\x02*=\n\nGPSWarning\x12\x12\n\x0eNO_GPS_WARNING\x10\x00\x12\x0f\n\x0bWEAK_SIGNAL\x10\x01\x12\n\n\x06NO_FIX\x10\x02*D\n\x13MagnetometerWarning\x12\x1b\n\x17NO_MAGNETOMETER_WARNING\x10\x00\x12\x10\n\x0cPERTURBATION\x10\x01*U\n\x11ConnectionWarning\x12\x19\n\x15NO_CONNECTION_WARNING\x10\x00\x12\x10\n\x0cDISCONNECTED\x10\x01\x12\x13\n\x0fWEAK_CONNECTION\x10\x02*T\n\x0eCompassWarning\x12\x16\n\x12NO_COMPASS_WARNING\x10\x00\x12\x15\n\x11WEAK_HEADING_LOCK\x10\x01\x12\x13\n\x0fNO_HEADING_LOCK\x10\x02*W\n\x10MissionExecState\x12\t\n\x05READY\x10\x00\x12\x0f\n\x0bIN_PROGRESS\x10\x01\x12\n\n\x06PAUSED\x10\x03\x12\r\n\tCOMPLETED\x10\x04\x12\x0c\n\x08CANCELED\x10\x05b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'messages.telemetry_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_MOTIONSTATUS']._serialized_start = 3840
    _globals['_MOTIONSTATUS']._serialized_end = 3909
    _globals['_IMAGINGSENSORTYPE']._serialized_start = 3912
    _globals['_IMAGINGSENSORTYPE']._serialized_end = 4050
    _globals['_BATTERYWARNING']._serialized_start = 4052
    _globals['_BATTERYWARNING']._serialized_end = 4101
    _globals['_GPSWARNING']._serialized_start = 4103
    _globals['_GPSWARNING']._serialized_end = 4164
    _globals['_MAGNETOMETERWARNING']._serialized_start = 4166
    _globals['_MAGNETOMETERWARNING']._serialized_end = 4234
    _globals['_CONNECTIONWARNING']._serialized_start = 4236
    _globals['_CONNECTIONWARNING']._serialized_end = 4321
    _globals['_COMPASSWARNING']._serialized_start = 4323
    _globals['_COMPASSWARNING']._serialized_end = 4407
    _globals['_MISSIONEXECSTATE']._serialized_start = 4409
    _globals['_MISSIONEXECSTATE']._serialized_end = 4496
    _globals['_TELEMETRYSTREAMINFO']._serialized_start = 147
    _globals['_TELEMETRYSTREAMINFO']._serialized_end = 261
    _globals['_BATTERYINFO']._serialized_start = 263
    _globals['_BATTERYINFO']._serialized_end = 296
    _globals['_GPSINFO']._serialized_start = 298
    _globals['_GPSINFO']._serialized_end = 327
    _globals['_COMMSINFO']._serialized_start = 329
    _globals['_COMMSINFO']._serialized_end = 340
    _globals['_VEHICLEINFO']._serialized_start = 343
    _globals['_VEHICLEINFO']._serialized_end = 697
    _globals['_SETPOINTINFO']._serialized_start = 700
    _globals['_SETPOINTINFO']._serialized_end = 1047
    _globals['_POSITIONINFO']._serialized_start = 1050
    _globals['_POSITIONINFO']._serialized_end = 1442
    _globals['_GIMBALSTATUS']._serialized_start = 1445
    _globals['_GIMBALSTATUS']._serialized_end = 1576
    _globals['_GIMBALINFO']._serialized_start = 1578
    _globals['_GIMBALINFO']._serialized_end = 1682
    _globals['_IMAGINGSENSORSTATUS']._serialized_start = 1685
    _globals['_IMAGINGSENSORSTATUS']._serialized_end = 1994
    _globals['_IMAGINGSENSORSTREAMSTATUS']._serialized_start = 1996
    _globals['_IMAGINGSENSORSTREAMSTATUS']._serialized_end = 2114
    _globals['_IMAGINGSENSORINFO']._serialized_start = 2117
    _globals['_IMAGINGSENSORINFO']._serialized_end = 2304
    _globals['_ALERTINFO']._serialized_start = 2307
    _globals['_ALERTINFO']._serialized_end = 2731
    _globals['_DRIVERTELEMETRY']._serialized_start = 2734
    _globals['_DRIVERTELEMETRY']._serialized_end = 3274
    _globals['_FRAME']._serialized_start = 3277
    _globals['_FRAME']._serialized_end = 3420
    _globals['_MISSIONINFO']._serialized_start = 3423
    _globals['_MISSIONINFO']._serialized_end = 3603
    _globals['_MISSIONTELEMETRY']._serialized_start = 3606
    _globals['_MISSIONTELEMETRY']._serialized_end = 3838