# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: steeleagle/controlplane.proto
# Protobuf Python Version: 4.25.3
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from steeleagle import common_pb2 as steeleagle_dot_common__pb2
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2
from google.protobuf import field_mask_pb2 as google_dot_protobuf_dot_field__mask__pb2
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dsteeleagle/controlplane.proto\x12\x17steeleagle.controlplane\x1a\x17steeleagle/common.proto\x1a\x1bgoogle/protobuf/empty.proto\x1a google/protobuf/field_mask.proto\x1a\x1fgoogle/protobuf/timestamp.proto\"\xfd\x01\n\x07Request\x12\x0e\n\x06seqNum\x18\x01 \x01(\x03\x12-\n\ttimestamp\x18\x02 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x35\n\x03man\x18\x03 \x01(\x0b\x32&.steeleagle.controlplane.ManualControlH\x00\x12:\n\x04\x61uto\x18\x04 \x01(\x0b\x32*.steeleagle.controlplane.AutonomousControlH\x00\x12\x38\n\x03\x63pt\x18\x05 \x01(\x0b\x32).steeleagle.controlplane.ConfigureComputeH\x00\x42\x06\n\x04type\"z\n\x08Response\x12\x0e\n\x06seqNum\x18\x01 \x01(\x03\x12-\n\ttimestamp\x18\x02 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12/\n\x04resp\x18\x03 \x01(\x0e\x32!.steeleagle.shared.ResponseStatus\"\x99\x02\n\rManualControl\x12/\n\x08\x61ttitude\x18\x01 \x01(\x0b\x32\x1b.steeleagle.shared.AttitudeH\x00\x12/\n\x08location\x18\x02 \x01(\x0b\x32\x1b.steeleagle.shared.LocationH\x00\x12/\n\x08velocity\x18\x03 \x01(\x0b\x32\x1b.steeleagle.shared.VelocityH\x00\x12\'\n\x04pose\x18\x04 \x01(\x0b\x32\x17.steeleagle.shared.PoseH\x00\x12/\n\x08position\x18\x05 \x01(\x0b\x32\x1b.steeleagle.shared.PositionH\x00\x12\x12\n\x08\x63\x61meraId\x18\x06 \x01(\x0fH\x00\x42\x07\n\x05param\"f\n\x11\x41utonomousControl\x12\x0c\n\x04UUID\x18\x01 \x01(\t\x12\x0b\n\x03URL\x18\x02 \x01(\t\x12\x36\n\x06\x61\x63tion\x18\x03 \x01(\x0e\x32&.steeleagle.controlplane.MissionAction\"\x8c\x01\n\x10\x43onfigureCompute\x12\r\n\x05model\x18\x01 \x01(\t\x12*\n\nlowerBound\x18\x02 \x01(\x0b\x32\x16.steeleagle.shared.HSV\x12*\n\nupperBound\x18\x03 \x01(\x0b\x32\x16.steeleagle.shared.HSV\x12\x11\n\tthreshold\x18\x04 \x01(\x02*]\n\rMissionAction\x12\x12\n\x0eUNKNOWN_ACTION\x10\x00\x12\t\n\x05START\x10\x01\x12\x08\n\x04STOP\x10\x02\x12\t\n\x05PAUSE\x10\x03\x12\n\n\x06RESUME\x10\x04\x12\x0c\n\x08\x44OWNLOAD\x10\x05\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'steeleagle.controlplane_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_MISSIONACTION']._serialized_start=1090
  _globals['_MISSIONACTION']._serialized_end=1183
  _globals['_REQUEST']._serialized_start=180
  _globals['_REQUEST']._serialized_end=433
  _globals['_RESPONSE']._serialized_start=435
  _globals['_RESPONSE']._serialized_end=557
  _globals['_MANUALCONTROL']._serialized_start=560
  _globals['_MANUALCONTROL']._serialized_end=841
  _globals['_AUTONOMOUSCONTROL']._serialized_start=843
  _globals['_AUTONOMOUSCONTROL']._serialized_end=945
  _globals['_CONFIGURECOMPUTE']._serialized_start=948
  _globals['_CONFIGURECOMPUTE']._serialized_end=1088
# @@protoc_insertion_point(module_scope)
