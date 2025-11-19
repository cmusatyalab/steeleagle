"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from ..services import control_service_pb2 as services_dot_control__service__pb2
GRPC_GENERATED_VERSION = '1.71.2'
GRPC_VERSION = grpc.__version__
_version_not_supported = False
try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True
if _version_not_supported:
    raise RuntimeError(f'The grpc package installed is at version {GRPC_VERSION},' + f' but the generated code in services/control_service_pb2_grpc.py depends on' + f' grpcio>={GRPC_GENERATED_VERSION}.' + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}' + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.')

class ControlStub(object):
    """
    Used for low-level control of a vehicle
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Connect = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Connect', request_serializer=services_dot_control__service__pb2.ConnectRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.ConnectResponse.FromString, _registered_method=True)
        self.Disconnect = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Disconnect', request_serializer=services_dot_control__service__pb2.DisconnectRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.DisconnectResponse.FromString, _registered_method=True)
        self.Arm = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Arm', request_serializer=services_dot_control__service__pb2.ArmRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.ArmResponse.FromString, _registered_method=True)
        self.Disarm = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Disarm', request_serializer=services_dot_control__service__pb2.DisarmRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.DisarmResponse.FromString, _registered_method=True)
        self.Joystick = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Joystick', request_serializer=services_dot_control__service__pb2.JoystickRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.JoystickResponse.FromString, _registered_method=True)
        self.TakeOff = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/TakeOff', request_serializer=services_dot_control__service__pb2.TakeOffRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.TakeOffResponse.FromString, _registered_method=True)
        self.Land = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/Land', request_serializer=services_dot_control__service__pb2.LandRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.LandResponse.FromString, _registered_method=True)
        self.Hold = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/Hold', request_serializer=services_dot_control__service__pb2.HoldRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.HoldResponse.FromString, _registered_method=True)
        self.Kill = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/Kill', request_serializer=services_dot_control__service__pb2.KillRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.KillResponse.FromString, _registered_method=True)
        self.SetHome = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/SetHome', request_serializer=services_dot_control__service__pb2.SetHomeRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.SetHomeResponse.FromString, _registered_method=True)
        self.ReturnToHome = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/ReturnToHome', request_serializer=services_dot_control__service__pb2.ReturnToHomeRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.ReturnToHomeResponse.FromString, _registered_method=True)
        self.SetGlobalPosition = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetGlobalPosition', request_serializer=services_dot_control__service__pb2.SetGlobalPositionRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.SetGlobalPositionResponse.FromString, _registered_method=True)
        self.SetRelativePosition = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetRelativePosition', request_serializer=services_dot_control__service__pb2.SetRelativePositionRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.SetRelativePositionResponse.FromString, _registered_method=True)
        self.SetVelocity = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetVelocity', request_serializer=services_dot_control__service__pb2.SetVelocityRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.SetVelocityResponse.FromString, _registered_method=True)
        self.SetHeading = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetHeading', request_serializer=services_dot_control__service__pb2.SetHeadingRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.SetHeadingResponse.FromString, _registered_method=True)
        self.SetGimbalPose = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetGimbalPose', request_serializer=services_dot_control__service__pb2.SetGimbalPoseRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.SetGimbalPoseResponse.FromString, _registered_method=True)
        self.ConfigureImagingSensorStream = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/ConfigureImagingSensorStream', request_serializer=services_dot_control__service__pb2.ConfigureImagingSensorStreamRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.ConfigureImagingSensorStreamResponse.FromString, _registered_method=True)
        self.ConfigureTelemetryStream = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/ConfigureTelemetryStream', request_serializer=services_dot_control__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, response_deserializer=services_dot_control__service__pb2.ConfigureTelemetryStreamResponse.FromString, _registered_method=True)

class ControlServicer(object):
    """
    Used for low-level control of a vehicle
    """

    def Connect(self, request, context):
        """Connects to the vehicle
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Disconnect(self, request, context):
        """Disconnects from the vehicle
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Arm(self, request, context):
        """Order the vehicle to arm
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Disarm(self, request, context):
        """Order the vehicle to disarm
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Joystick(self, request, context):
        """Send a joystick velocity target that the vehicle will actuate
        towards, along with an actuation duration
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def TakeOff(self, request, context):
        """Order the vehicle to take off
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Land(self, request, context):
        """Land the vehicle at its current position
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Hold(self, request, context):
        """Order the vehicle to hold/loiter
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Kill(self, request, context):
        """Emergency shutdown of the vehicle motors
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetHome(self, request, context):
        """Changes the home destination for the vehicle
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ReturnToHome(self, request, context):
        """Return to the vehicle home destination
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetGlobalPosition(self, request, context):
        """Transit the vehicle to a target global position, expressed
        in global coordinates
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetRelativePosition(self, request, context):
        """Transit the vehicle to a target position relative to
        the global ENU (East, North, Up) or vehicle frame of 
        reference, in meters
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetVelocity(self, request, context):
        """Transit the vehicle at a target velocity in the global
        ENU (East, North, Up) or vehicle frame of reference, 
        in meters per second
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetHeading(self, request, context):
        """Sets the heading of the vehicle
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetGimbalPose(self, request, context):
        """Set the pose of the target gimbal
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureImagingSensorStream(self, request, context):
        """Set the vehicle video stream parameters
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureTelemetryStream(self, request, context):
        """Set the vehicle telemetry stream parameters
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_ControlServicer_to_server(servicer, server):
    rpc_method_handlers = {'Connect': grpc.unary_unary_rpc_method_handler(servicer.Connect, request_deserializer=services_dot_control__service__pb2.ConnectRequest.FromString, response_serializer=services_dot_control__service__pb2.ConnectResponse.SerializeToString), 'Disconnect': grpc.unary_unary_rpc_method_handler(servicer.Disconnect, request_deserializer=services_dot_control__service__pb2.DisconnectRequest.FromString, response_serializer=services_dot_control__service__pb2.DisconnectResponse.SerializeToString), 'Arm': grpc.unary_unary_rpc_method_handler(servicer.Arm, request_deserializer=services_dot_control__service__pb2.ArmRequest.FromString, response_serializer=services_dot_control__service__pb2.ArmResponse.SerializeToString), 'Disarm': grpc.unary_unary_rpc_method_handler(servicer.Disarm, request_deserializer=services_dot_control__service__pb2.DisarmRequest.FromString, response_serializer=services_dot_control__service__pb2.DisarmResponse.SerializeToString), 'Joystick': grpc.unary_unary_rpc_method_handler(servicer.Joystick, request_deserializer=services_dot_control__service__pb2.JoystickRequest.FromString, response_serializer=services_dot_control__service__pb2.JoystickResponse.SerializeToString), 'TakeOff': grpc.unary_stream_rpc_method_handler(servicer.TakeOff, request_deserializer=services_dot_control__service__pb2.TakeOffRequest.FromString, response_serializer=services_dot_control__service__pb2.TakeOffResponse.SerializeToString), 'Land': grpc.unary_stream_rpc_method_handler(servicer.Land, request_deserializer=services_dot_control__service__pb2.LandRequest.FromString, response_serializer=services_dot_control__service__pb2.LandResponse.SerializeToString), 'Hold': grpc.unary_stream_rpc_method_handler(servicer.Hold, request_deserializer=services_dot_control__service__pb2.HoldRequest.FromString, response_serializer=services_dot_control__service__pb2.HoldResponse.SerializeToString), 'Kill': grpc.unary_stream_rpc_method_handler(servicer.Kill, request_deserializer=services_dot_control__service__pb2.KillRequest.FromString, response_serializer=services_dot_control__service__pb2.KillResponse.SerializeToString), 'SetHome': grpc.unary_unary_rpc_method_handler(servicer.SetHome, request_deserializer=services_dot_control__service__pb2.SetHomeRequest.FromString, response_serializer=services_dot_control__service__pb2.SetHomeResponse.SerializeToString), 'ReturnToHome': grpc.unary_stream_rpc_method_handler(servicer.ReturnToHome, request_deserializer=services_dot_control__service__pb2.ReturnToHomeRequest.FromString, response_serializer=services_dot_control__service__pb2.ReturnToHomeResponse.SerializeToString), 'SetGlobalPosition': grpc.unary_stream_rpc_method_handler(servicer.SetGlobalPosition, request_deserializer=services_dot_control__service__pb2.SetGlobalPositionRequest.FromString, response_serializer=services_dot_control__service__pb2.SetGlobalPositionResponse.SerializeToString), 'SetRelativePosition': grpc.unary_stream_rpc_method_handler(servicer.SetRelativePosition, request_deserializer=services_dot_control__service__pb2.SetRelativePositionRequest.FromString, response_serializer=services_dot_control__service__pb2.SetRelativePositionResponse.SerializeToString), 'SetVelocity': grpc.unary_stream_rpc_method_handler(servicer.SetVelocity, request_deserializer=services_dot_control__service__pb2.SetVelocityRequest.FromString, response_serializer=services_dot_control__service__pb2.SetVelocityResponse.SerializeToString), 'SetHeading': grpc.unary_stream_rpc_method_handler(servicer.SetHeading, request_deserializer=services_dot_control__service__pb2.SetHeadingRequest.FromString, response_serializer=services_dot_control__service__pb2.SetHeadingResponse.SerializeToString), 'SetGimbalPose': grpc.unary_stream_rpc_method_handler(servicer.SetGimbalPose, request_deserializer=services_dot_control__service__pb2.SetGimbalPoseRequest.FromString, response_serializer=services_dot_control__service__pb2.SetGimbalPoseResponse.SerializeToString), 'ConfigureImagingSensorStream': grpc.unary_unary_rpc_method_handler(servicer.ConfigureImagingSensorStream, request_deserializer=services_dot_control__service__pb2.ConfigureImagingSensorStreamRequest.FromString, response_serializer=services_dot_control__service__pb2.ConfigureImagingSensorStreamResponse.SerializeToString), 'ConfigureTelemetryStream': grpc.unary_unary_rpc_method_handler(servicer.ConfigureTelemetryStream, request_deserializer=services_dot_control__service__pb2.ConfigureTelemetryStreamRequest.FromString, response_serializer=services_dot_control__service__pb2.ConfigureTelemetryStreamResponse.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.control_service.Control', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.control_service.Control', rpc_method_handlers)

class Control(object):
    """
    Used for low-level control of a vehicle
    """

    @staticmethod
    def Connect(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Connect', services_dot_control__service__pb2.ConnectRequest.SerializeToString, services_dot_control__service__pb2.ConnectResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Disconnect(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Disconnect', services_dot_control__service__pb2.DisconnectRequest.SerializeToString, services_dot_control__service__pb2.DisconnectResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Arm(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Arm', services_dot_control__service__pb2.ArmRequest.SerializeToString, services_dot_control__service__pb2.ArmResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Disarm(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Disarm', services_dot_control__service__pb2.DisarmRequest.SerializeToString, services_dot_control__service__pb2.DisarmResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Joystick(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Joystick', services_dot_control__service__pb2.JoystickRequest.SerializeToString, services_dot_control__service__pb2.JoystickResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def TakeOff(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/TakeOff', services_dot_control__service__pb2.TakeOffRequest.SerializeToString, services_dot_control__service__pb2.TakeOffResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Land(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/Land', services_dot_control__service__pb2.LandRequest.SerializeToString, services_dot_control__service__pb2.LandResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Hold(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/Hold', services_dot_control__service__pb2.HoldRequest.SerializeToString, services_dot_control__service__pb2.HoldResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Kill(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/Kill', services_dot_control__service__pb2.KillRequest.SerializeToString, services_dot_control__service__pb2.KillResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetHome(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/SetHome', services_dot_control__service__pb2.SetHomeRequest.SerializeToString, services_dot_control__service__pb2.SetHomeResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ReturnToHome(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/ReturnToHome', services_dot_control__service__pb2.ReturnToHomeRequest.SerializeToString, services_dot_control__service__pb2.ReturnToHomeResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetGlobalPosition(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetGlobalPosition', services_dot_control__service__pb2.SetGlobalPositionRequest.SerializeToString, services_dot_control__service__pb2.SetGlobalPositionResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetRelativePosition(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetRelativePosition', services_dot_control__service__pb2.SetRelativePositionRequest.SerializeToString, services_dot_control__service__pb2.SetRelativePositionResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetVelocity(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetVelocity', services_dot_control__service__pb2.SetVelocityRequest.SerializeToString, services_dot_control__service__pb2.SetVelocityResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetHeading(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetHeading', services_dot_control__service__pb2.SetHeadingRequest.SerializeToString, services_dot_control__service__pb2.SetHeadingResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetGimbalPose(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetGimbalPose', services_dot_control__service__pb2.SetGimbalPoseRequest.SerializeToString, services_dot_control__service__pb2.SetGimbalPoseResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureImagingSensorStream(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/ConfigureImagingSensorStream', services_dot_control__service__pb2.ConfigureImagingSensorStreamRequest.SerializeToString, services_dot_control__service__pb2.ConfigureImagingSensorStreamResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureTelemetryStream(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/ConfigureTelemetryStream', services_dot_control__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, services_dot_control__service__pb2.ConfigureTelemetryStreamResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)