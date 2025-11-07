"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/control_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
from google.protobuf import duration_pb2 as google_dot_protobuf_dot_duration__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1eservices/control_service.proto\x12,steeleagle.protocol.services.control_service\x1a\x0ccommon.proto\x1a\x1egoogle/protobuf/duration.proto"F\n\x0eConnectRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"I\n\x11DisconnectRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"B\n\nArmRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"E\n\rDisarmRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"\xac\x01\n\x0fJoystickRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08velocity\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Velocity\x12+\n\x08duration\x18\x03 \x01(\x0b2\x19.google.protobuf.Duration"a\n\x0eTakeOffRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x19\n\x11take_off_altitude\x18\x02 \x01(\x02"C\n\x0bLandRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"C\n\x0bHoldRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"C\n\x0bKillRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"~\n\x0eSetHomeRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08location\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Location"K\n\x13ReturnToHomeRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"\xab\x03\n\x18SetGlobalPositionRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08location\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Location\x12T\n\x0cheading_mode\x18\x04 \x01(\x0e29.steeleagle.protocol.services.control_service.HeadingModeH\x00\x88\x01\x01\x12V\n\raltitude_mode\x18\x05 \x01(\x0e2:.steeleagle.protocol.services.control_service.AltitudeModeH\x01\x88\x01\x01\x12?\n\x0cmax_velocity\x18\x06 \x01(\x0b2$.steeleagle.protocol.common.VelocityH\x02\x88\x01\x01B\x0f\n\r_heading_modeB\x10\n\x0e_altitude_modeB\x0f\n\r_max_velocity"\xb8\x02\n\x1aSetRelativePositionRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08position\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Position\x12?\n\x0cmax_velocity\x18\x03 \x01(\x0b2$.steeleagle.protocol.common.VelocityH\x00\x88\x01\x01\x12P\n\x05frame\x18\x04 \x01(\x0e2<.steeleagle.protocol.services.control_service.ReferenceFrameH\x01\x88\x01\x01B\x0f\n\r_max_velocityB\x08\n\x06_frame"\xde\x01\n\x12SetVelocityRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08velocity\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Velocity\x12P\n\x05frame\x18\x03 \x01(\x0e2<.steeleagle.protocol.services.control_service.ReferenceFrameH\x00\x88\x01\x01B\x08\n\x06_frame"\xe8\x01\n\x11SetHeadingRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08location\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Location\x12T\n\x0cheading_mode\x18\x05 \x01(\x0e29.steeleagle.protocol.services.control_service.HeadingModeH\x00\x88\x01\x01B\x0f\n\r_heading_mode"\xc9\x02\n\x14SetGimbalPoseRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x11\n\tgimbal_id\x18\x02 \x01(\r\x12.\n\x04pose\x18\x03 \x01(\x0b2 .steeleagle.protocol.common.Pose\x12N\n\tpose_mode\x18\x04 \x01(\x0e26.steeleagle.protocol.services.control_service.PoseModeH\x00\x88\x01\x01\x12P\n\x05frame\x18\x05 \x01(\x0e2<.steeleagle.protocol.services.control_service.ReferenceFrameH\x01\x88\x01\x01B\x0c\n\n_pose_modeB\x08\n\x06_frame"N\n\x1aImagingSensorConfiguration\x12\n\n\x02id\x18\x01 \x01(\r\x12\x13\n\x0bset_primary\x18\x02 \x01(\x08\x12\x0f\n\x07set_fps\x18\x03 \x01(\r"\xbd\x01\n#ConfigureImagingSensorStreamRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12`\n\x0econfigurations\x18\x02 \x03(\x0b2H.steeleagle.protocol.services.control_service.ImagingSensorConfiguration"j\n\x1fConfigureTelemetryStreamRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x11\n\tfrequency\x18\x02 \x01(\r**\n\x0cAltitudeMode\x12\x0c\n\x08ABSOLUTE\x10\x00\x12\x0c\n\x08RELATIVE\x10\x01*/\n\x0bHeadingMode\x12\r\n\tTO_TARGET\x10\x00\x12\x11\n\rHEADING_START\x10\x01*#\n\x0eReferenceFrame\x12\x08\n\x04BODY\x10\x00\x12\x07\n\x03NEU\x10\x01*/\n\x08PoseMode\x12\t\n\x05ANGLE\x10\x00\x12\n\n\x06OFFSET\x10\x01\x12\x0c\n\x08VELOCITY\x10\x022\x9b\x11\n\x07Control\x12o\n\x07Connect\x12<.steeleagle.protocol.services.control_service.ConnectRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12u\n\nDisconnect\x12?.steeleagle.protocol.services.control_service.DisconnectRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12g\n\x03Arm\x128.steeleagle.protocol.services.control_service.ArmRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12m\n\x06Disarm\x12;.steeleagle.protocol.services.control_service.DisarmRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12q\n\x08Joystick\x12=.steeleagle.protocol.services.control_service.JoystickRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12q\n\x07TakeOff\x12<.steeleagle.protocol.services.control_service.TakeOffRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12k\n\x04Land\x129.steeleagle.protocol.services.control_service.LandRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12k\n\x04Hold\x129.steeleagle.protocol.services.control_service.HoldRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12k\n\x04Kill\x129.steeleagle.protocol.services.control_service.KillRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12o\n\x07SetHome\x12<.steeleagle.protocol.services.control_service.SetHomeRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12{\n\x0cReturnToHome\x12A.steeleagle.protocol.services.control_service.ReturnToHomeRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12\x85\x01\n\x11SetGlobalPosition\x12F.steeleagle.protocol.services.control_service.SetGlobalPositionRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12\x89\x01\n\x13SetRelativePosition\x12H.steeleagle.protocol.services.control_service.SetRelativePositionRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12y\n\x0bSetVelocity\x12@.steeleagle.protocol.services.control_service.SetVelocityRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12w\n\nSetHeading\x12?.steeleagle.protocol.services.control_service.SetHeadingRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12}\n\rSetGimbalPose\x12B.steeleagle.protocol.services.control_service.SetGimbalPoseRequest\x1a$.steeleagle.protocol.common.Response"\x000\x01\x12\x99\x01\n\x1cConfigureImagingSensorStream\x12Q.steeleagle.protocol.services.control_service.ConfigureImagingSensorStreamRequest\x1a$.steeleagle.protocol.common.Response"\x00\x12\x91\x01\n\x18ConfigureTelemetryStream\x12M.steeleagle.protocol.services.control_service.ConfigureTelemetryStreamRequest\x1a$.steeleagle.protocol.common.Response"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.control_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_ALTITUDEMODE']._serialized_start = 3015
    _globals['_ALTITUDEMODE']._serialized_end = 3057
    _globals['_HEADINGMODE']._serialized_start = 3059
    _globals['_HEADINGMODE']._serialized_end = 3106
    _globals['_REFERENCEFRAME']._serialized_start = 3108
    _globals['_REFERENCEFRAME']._serialized_end = 3143
    _globals['_POSEMODE']._serialized_start = 3145
    _globals['_POSEMODE']._serialized_end = 3192
    _globals['_CONNECTREQUEST']._serialized_start = 126
    _globals['_CONNECTREQUEST']._serialized_end = 196
    _globals['_DISCONNECTREQUEST']._serialized_start = 198
    _globals['_DISCONNECTREQUEST']._serialized_end = 271
    _globals['_ARMREQUEST']._serialized_start = 273
    _globals['_ARMREQUEST']._serialized_end = 339
    _globals['_DISARMREQUEST']._serialized_start = 341
    _globals['_DISARMREQUEST']._serialized_end = 410
    _globals['_JOYSTICKREQUEST']._serialized_start = 413
    _globals['_JOYSTICKREQUEST']._serialized_end = 585
    _globals['_TAKEOFFREQUEST']._serialized_start = 587
    _globals['_TAKEOFFREQUEST']._serialized_end = 684
    _globals['_LANDREQUEST']._serialized_start = 686
    _globals['_LANDREQUEST']._serialized_end = 753
    _globals['_HOLDREQUEST']._serialized_start = 755
    _globals['_HOLDREQUEST']._serialized_end = 822
    _globals['_KILLREQUEST']._serialized_start = 824
    _globals['_KILLREQUEST']._serialized_end = 891
    _globals['_SETHOMEREQUEST']._serialized_start = 893
    _globals['_SETHOMEREQUEST']._serialized_end = 1019
    _globals['_RETURNTOHOMEREQUEST']._serialized_start = 1021
    _globals['_RETURNTOHOMEREQUEST']._serialized_end = 1096
    _globals['_SETGLOBALPOSITIONREQUEST']._serialized_start = 1099
    _globals['_SETGLOBALPOSITIONREQUEST']._serialized_end = 1526
    _globals['_SETRELATIVEPOSITIONREQUEST']._serialized_start = 1529
    _globals['_SETRELATIVEPOSITIONREQUEST']._serialized_end = 1841
    _globals['_SETVELOCITYREQUEST']._serialized_start = 1844
    _globals['_SETVELOCITYREQUEST']._serialized_end = 2066
    _globals['_SETHEADINGREQUEST']._serialized_start = 2069
    _globals['_SETHEADINGREQUEST']._serialized_end = 2301
    _globals['_SETGIMBALPOSEREQUEST']._serialized_start = 2304
    _globals['_SETGIMBALPOSEREQUEST']._serialized_end = 2633
    _globals['_IMAGINGSENSORCONFIGURATION']._serialized_start = 2635
    _globals['_IMAGINGSENSORCONFIGURATION']._serialized_end = 2713
    _globals['_CONFIGUREIMAGINGSENSORSTREAMREQUEST']._serialized_start = 2716
    _globals['_CONFIGUREIMAGINGSENSORSTREAMREQUEST']._serialized_end = 2905
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_start = 2907
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_end = 3013
    _globals['_CONTROL']._serialized_start = 3195
    _globals['_CONTROL']._serialized_end = 5398