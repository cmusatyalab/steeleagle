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
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1eservices/control_service.proto\x12,steeleagle.protocol.services.control_service\x1a\x0ccommon.proto\x1a\x1egoogle/protobuf/duration.proto"F\n\x0eConnectRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"I\n\x0fConnectResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"I\n\x11DisconnectRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"L\n\x12DisconnectResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"B\n\nArmRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"E\n\x0bArmResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"E\n\rDisarmRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"H\n\x0eDisarmResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"\xbe\x01\n\x0fJoystickRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08velocity\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Velocity\x120\n\x08duration\x18\x03 \x01(\x0b2\x19.google.protobuf.DurationH\x00\x88\x01\x01B\x0b\n\t_duration"J\n\x10JoystickResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"a\n\x0eTakeOffRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x19\n\x11take_off_altitude\x18\x02 \x01(\x02"I\n\x0fTakeOffResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"C\n\x0bLandRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"F\n\x0cLandResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"C\n\x0bHoldRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"F\n\x0cHoldResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"C\n\x0bKillRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"F\n\x0cKillResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"~\n\x0eSetHomeRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08location\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Location"I\n\x0fSetHomeResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"K\n\x13ReturnToHomeRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"N\n\x14ReturnToHomeResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"\xab\x03\n\x18SetGlobalPositionRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08location\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Location\x12V\n\raltitude_mode\x18\x04 \x01(\x0e2:.steeleagle.protocol.services.control_service.AltitudeModeH\x00\x88\x01\x01\x12T\n\x0cheading_mode\x18\x05 \x01(\x0e29.steeleagle.protocol.services.control_service.HeadingModeH\x01\x88\x01\x01\x12?\n\x0cmax_velocity\x18\x06 \x01(\x0b2$.steeleagle.protocol.common.VelocityH\x02\x88\x01\x01B\x10\n\x0e_altitude_modeB\x0f\n\r_heading_modeB\x0f\n\r_max_velocity"S\n\x19SetGlobalPositionResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"\xb8\x02\n\x1aSetRelativePositionRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08position\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Position\x12?\n\x0cmax_velocity\x18\x03 \x01(\x0b2$.steeleagle.protocol.common.VelocityH\x00\x88\x01\x01\x12P\n\x05frame\x18\x04 \x01(\x0e2<.steeleagle.protocol.services.control_service.ReferenceFrameH\x01\x88\x01\x01B\x0f\n\r_max_velocityB\x08\n\x06_frame"U\n\x1bSetRelativePositionResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"\xde\x01\n\x12SetVelocityRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08velocity\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Velocity\x12P\n\x05frame\x18\x03 \x01(\x0e2<.steeleagle.protocol.services.control_service.ReferenceFrameH\x00\x88\x01\x01B\x08\n\x06_frame"M\n\x13SetVelocityResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"\xe8\x01\n\x11SetHeadingRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x126\n\x08location\x18\x02 \x01(\x0b2$.steeleagle.protocol.common.Location\x12T\n\x0cheading_mode\x18\x05 \x01(\x0e29.steeleagle.protocol.services.control_service.HeadingModeH\x00\x88\x01\x01B\x0f\n\r_heading_mode"L\n\x12SetHeadingResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"\xe3\x01\n\x14SetGimbalPoseRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x11\n\tgimbal_id\x18\x02 \x01(\r\x12.\n\x04pose\x18\x03 \x01(\x0b2 .steeleagle.protocol.common.Pose\x12I\n\x04mode\x18\x04 \x01(\x0e26.steeleagle.protocol.services.control_service.PoseModeH\x00\x88\x01\x01B\x07\n\x05_mode"O\n\x15SetGimbalPoseResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"N\n\x1aImagingSensorConfiguration\x12\n\n\x02id\x18\x01 \x01(\r\x12\x13\n\x0bset_primary\x18\x02 \x01(\x08\x12\x0f\n\x07set_fps\x18\x03 \x01(\r"\xbd\x01\n#ConfigureImagingSensorStreamRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12`\n\x0econfigurations\x18\x02 \x03(\x0b2H.steeleagle.protocol.services.control_service.ImagingSensorConfiguration"^\n$ConfigureImagingSensorStreamResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response"j\n\x1fConfigureTelemetryStreamRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x11\n\tfrequency\x18\x02 \x01(\r"Z\n ConfigureTelemetryStreamResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response**\n\x0cAltitudeMode\x12\x0c\n\x08ABSOLUTE\x10\x00\x12\x0c\n\x08RELATIVE\x10\x01*/\n\x0bHeadingMode\x12\r\n\tTO_TARGET\x10\x00\x12\x11\n\rHEADING_START\x10\x01*#\n\x0eReferenceFrame\x12\x08\n\x04BODY\x10\x00\x12\x07\n\x03ENU\x10\x01*/\n\x08PoseMode\x12\t\n\x05ANGLE\x10\x00\x12\n\n\x06OFFSET\x10\x01\x12\x0c\n\x08VELOCITY\x10\x022\xae\x15\n\x07Control\x12\x88\x01\n\x07Connect\x12<.steeleagle.protocol.services.control_service.ConnectRequest\x1a=.steeleagle.protocol.services.control_service.ConnectResponse"\x00\x12\x91\x01\n\nDisconnect\x12?.steeleagle.protocol.services.control_service.DisconnectRequest\x1a@.steeleagle.protocol.services.control_service.DisconnectResponse"\x00\x12|\n\x03Arm\x128.steeleagle.protocol.services.control_service.ArmRequest\x1a9.steeleagle.protocol.services.control_service.ArmResponse"\x00\x12\x85\x01\n\x06Disarm\x12;.steeleagle.protocol.services.control_service.DisarmRequest\x1a<.steeleagle.protocol.services.control_service.DisarmResponse"\x00\x12\x8b\x01\n\x08Joystick\x12=.steeleagle.protocol.services.control_service.JoystickRequest\x1a>.steeleagle.protocol.services.control_service.JoystickResponse"\x00\x12\x8a\x01\n\x07TakeOff\x12<.steeleagle.protocol.services.control_service.TakeOffRequest\x1a=.steeleagle.protocol.services.control_service.TakeOffResponse"\x000\x01\x12\x81\x01\n\x04Land\x129.steeleagle.protocol.services.control_service.LandRequest\x1a:.steeleagle.protocol.services.control_service.LandResponse"\x000\x01\x12\x81\x01\n\x04Hold\x129.steeleagle.protocol.services.control_service.HoldRequest\x1a:.steeleagle.protocol.services.control_service.HoldResponse"\x000\x01\x12\x81\x01\n\x04Kill\x129.steeleagle.protocol.services.control_service.KillRequest\x1a:.steeleagle.protocol.services.control_service.KillResponse"\x000\x01\x12\x88\x01\n\x07SetHome\x12<.steeleagle.protocol.services.control_service.SetHomeRequest\x1a=.steeleagle.protocol.services.control_service.SetHomeResponse"\x00\x12\x99\x01\n\x0cReturnToHome\x12A.steeleagle.protocol.services.control_service.ReturnToHomeRequest\x1aB.steeleagle.protocol.services.control_service.ReturnToHomeResponse"\x000\x01\x12\xa8\x01\n\x11SetGlobalPosition\x12F.steeleagle.protocol.services.control_service.SetGlobalPositionRequest\x1aG.steeleagle.protocol.services.control_service.SetGlobalPositionResponse"\x000\x01\x12\xae\x01\n\x13SetRelativePosition\x12H.steeleagle.protocol.services.control_service.SetRelativePositionRequest\x1aI.steeleagle.protocol.services.control_service.SetRelativePositionResponse"\x000\x01\x12\x96\x01\n\x0bSetVelocity\x12@.steeleagle.protocol.services.control_service.SetVelocityRequest\x1aA.steeleagle.protocol.services.control_service.SetVelocityResponse"\x000\x01\x12\x93\x01\n\nSetHeading\x12?.steeleagle.protocol.services.control_service.SetHeadingRequest\x1a@.steeleagle.protocol.services.control_service.SetHeadingResponse"\x000\x01\x12\x9c\x01\n\rSetGimbalPose\x12B.steeleagle.protocol.services.control_service.SetGimbalPoseRequest\x1aC.steeleagle.protocol.services.control_service.SetGimbalPoseResponse"\x000\x01\x12\xc7\x01\n\x1cConfigureImagingSensorStream\x12Q.steeleagle.protocol.services.control_service.ConfigureImagingSensorStreamRequest\x1aR.steeleagle.protocol.services.control_service.ConfigureImagingSensorStreamResponse"\x00\x12\xbb\x01\n\x18ConfigureTelemetryStream\x12M.steeleagle.protocol.services.control_service.ConfigureTelemetryStreamRequest\x1aN.steeleagle.protocol.services.control_service.ConfigureTelemetryStreamResponse"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.control_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_ALTITUDEMODE']._serialized_start = 4349
    _globals['_ALTITUDEMODE']._serialized_end = 4391
    _globals['_HEADINGMODE']._serialized_start = 4393
    _globals['_HEADINGMODE']._serialized_end = 4440
    _globals['_REFERENCEFRAME']._serialized_start = 4442
    _globals['_REFERENCEFRAME']._serialized_end = 4477
    _globals['_POSEMODE']._serialized_start = 4479
    _globals['_POSEMODE']._serialized_end = 4526
    _globals['_CONNECTREQUEST']._serialized_start = 126
    _globals['_CONNECTREQUEST']._serialized_end = 196
    _globals['_CONNECTRESPONSE']._serialized_start = 198
    _globals['_CONNECTRESPONSE']._serialized_end = 271
    _globals['_DISCONNECTREQUEST']._serialized_start = 273
    _globals['_DISCONNECTREQUEST']._serialized_end = 346
    _globals['_DISCONNECTRESPONSE']._serialized_start = 348
    _globals['_DISCONNECTRESPONSE']._serialized_end = 424
    _globals['_ARMREQUEST']._serialized_start = 426
    _globals['_ARMREQUEST']._serialized_end = 492
    _globals['_ARMRESPONSE']._serialized_start = 494
    _globals['_ARMRESPONSE']._serialized_end = 563
    _globals['_DISARMREQUEST']._serialized_start = 565
    _globals['_DISARMREQUEST']._serialized_end = 634
    _globals['_DISARMRESPONSE']._serialized_start = 636
    _globals['_DISARMRESPONSE']._serialized_end = 708
    _globals['_JOYSTICKREQUEST']._serialized_start = 711
    _globals['_JOYSTICKREQUEST']._serialized_end = 901
    _globals['_JOYSTICKRESPONSE']._serialized_start = 903
    _globals['_JOYSTICKRESPONSE']._serialized_end = 977
    _globals['_TAKEOFFREQUEST']._serialized_start = 979
    _globals['_TAKEOFFREQUEST']._serialized_end = 1076
    _globals['_TAKEOFFRESPONSE']._serialized_start = 1078
    _globals['_TAKEOFFRESPONSE']._serialized_end = 1151
    _globals['_LANDREQUEST']._serialized_start = 1153
    _globals['_LANDREQUEST']._serialized_end = 1220
    _globals['_LANDRESPONSE']._serialized_start = 1222
    _globals['_LANDRESPONSE']._serialized_end = 1292
    _globals['_HOLDREQUEST']._serialized_start = 1294
    _globals['_HOLDREQUEST']._serialized_end = 1361
    _globals['_HOLDRESPONSE']._serialized_start = 1363
    _globals['_HOLDRESPONSE']._serialized_end = 1433
    _globals['_KILLREQUEST']._serialized_start = 1435
    _globals['_KILLREQUEST']._serialized_end = 1502
    _globals['_KILLRESPONSE']._serialized_start = 1504
    _globals['_KILLRESPONSE']._serialized_end = 1574
    _globals['_SETHOMEREQUEST']._serialized_start = 1576
    _globals['_SETHOMEREQUEST']._serialized_end = 1702
    _globals['_SETHOMERESPONSE']._serialized_start = 1704
    _globals['_SETHOMERESPONSE']._serialized_end = 1777
    _globals['_RETURNTOHOMEREQUEST']._serialized_start = 1779
    _globals['_RETURNTOHOMEREQUEST']._serialized_end = 1854
    _globals['_RETURNTOHOMERESPONSE']._serialized_start = 1856
    _globals['_RETURNTOHOMERESPONSE']._serialized_end = 1934
    _globals['_SETGLOBALPOSITIONREQUEST']._serialized_start = 1937
    _globals['_SETGLOBALPOSITIONREQUEST']._serialized_end = 2364
    _globals['_SETGLOBALPOSITIONRESPONSE']._serialized_start = 2366
    _globals['_SETGLOBALPOSITIONRESPONSE']._serialized_end = 2449
    _globals['_SETRELATIVEPOSITIONREQUEST']._serialized_start = 2452
    _globals['_SETRELATIVEPOSITIONREQUEST']._serialized_end = 2764
    _globals['_SETRELATIVEPOSITIONRESPONSE']._serialized_start = 2766
    _globals['_SETRELATIVEPOSITIONRESPONSE']._serialized_end = 2851
    _globals['_SETVELOCITYREQUEST']._serialized_start = 2854
    _globals['_SETVELOCITYREQUEST']._serialized_end = 3076
    _globals['_SETVELOCITYRESPONSE']._serialized_start = 3078
    _globals['_SETVELOCITYRESPONSE']._serialized_end = 3155
    _globals['_SETHEADINGREQUEST']._serialized_start = 3158
    _globals['_SETHEADINGREQUEST']._serialized_end = 3390
    _globals['_SETHEADINGRESPONSE']._serialized_start = 3392
    _globals['_SETHEADINGRESPONSE']._serialized_end = 3468
    _globals['_SETGIMBALPOSEREQUEST']._serialized_start = 3471
    _globals['_SETGIMBALPOSEREQUEST']._serialized_end = 3698
    _globals['_SETGIMBALPOSERESPONSE']._serialized_start = 3700
    _globals['_SETGIMBALPOSERESPONSE']._serialized_end = 3779
    _globals['_IMAGINGSENSORCONFIGURATION']._serialized_start = 3781
    _globals['_IMAGINGSENSORCONFIGURATION']._serialized_end = 3859
    _globals['_CONFIGUREIMAGINGSENSORSTREAMREQUEST']._serialized_start = 3862
    _globals['_CONFIGUREIMAGINGSENSORSTREAMREQUEST']._serialized_end = 4051
    _globals['_CONFIGUREIMAGINGSENSORSTREAMRESPONSE']._serialized_start = 4053
    _globals['_CONFIGUREIMAGINGSENSORSTREAMRESPONSE']._serialized_end = 4147
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_start = 4149
    _globals['_CONFIGURETELEMETRYSTREAMREQUEST']._serialized_end = 4255
    _globals['_CONFIGURETELEMETRYSTREAMRESPONSE']._serialized_start = 4257
    _globals['_CONFIGURETELEMETRYSTREAMRESPONSE']._serialized_end = 4347
    _globals['_CONTROL']._serialized_start = 4529
    _globals['_CONTROL']._serialized_end = 7263