"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from .. import common_pb2 as common__pb2
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
    Used for low-level control of a vehicle.

    This service is hosted by the driver module and represents the global
    control interface for the vehicle. Most methods called here will result
    in actuation of the vehicle if it is armed (be careful!). Some methods,
    like TakeOff, may take some time to complete. For this reason, it is
    not advisable to set a timeout/deadline on the RPC call. However, to
    ensure that the service is progressing, a client can either check
    telemetry or listen for `IN_PROGRESS` response heartbeats which are
    streamed back from the RPC while executing an operation.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Connect = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Connect', request_serializer=services_dot_control__service__pb2.ConnectRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Disconnect = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Disconnect', request_serializer=services_dot_control__service__pb2.DisconnectRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Arm = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Arm', request_serializer=services_dot_control__service__pb2.ArmRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Disarm = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Disarm', request_serializer=services_dot_control__service__pb2.DisarmRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Joystick = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/Joystick', request_serializer=services_dot_control__service__pb2.JoystickRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.TakeOff = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/TakeOff', request_serializer=services_dot_control__service__pb2.TakeOffRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Land = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/Land', request_serializer=services_dot_control__service__pb2.LandRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Hold = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/Hold', request_serializer=services_dot_control__service__pb2.HoldRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Kill = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/Kill', request_serializer=services_dot_control__service__pb2.KillRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.SetHome = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/SetHome', request_serializer=services_dot_control__service__pb2.SetHomeRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.ReturnToHome = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/ReturnToHome', request_serializer=services_dot_control__service__pb2.ReturnToHomeRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.SetGlobalPosition = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetGlobalPosition', request_serializer=services_dot_control__service__pb2.SetGlobalPositionRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.SetRelativePosition = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetRelativePosition', request_serializer=services_dot_control__service__pb2.SetRelativePositionRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.SetVelocity = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetVelocity', request_serializer=services_dot_control__service__pb2.SetVelocityRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.SetHeading = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetHeading', request_serializer=services_dot_control__service__pb2.SetHeadingRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.SetGimbalPose = channel.unary_stream('/steeleagle.protocol.services.control_service.Control/SetGimbalPose', request_serializer=services_dot_control__service__pb2.SetGimbalPoseRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.ConfigureImagingSensorStream = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/ConfigureImagingSensorStream', request_serializer=services_dot_control__service__pb2.ConfigureImagingSensorStreamRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.ConfigureTelemetryStream = channel.unary_unary('/steeleagle.protocol.services.control_service.Control/ConfigureTelemetryStream', request_serializer=services_dot_control__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)

class ControlServicer(object):
    """
    Used for low-level control of a vehicle.

    This service is hosted by the driver module and represents the global
    control interface for the vehicle. Most methods called here will result
    in actuation of the vehicle if it is armed (be careful!). Some methods,
    like TakeOff, may take some time to complete. For this reason, it is
    not advisable to set a timeout/deadline on the RPC call. However, to
    ensure that the service is progressing, a client can either check
    telemetry or listen for `IN_PROGRESS` response heartbeats which are
    streamed back from the RPC while executing an operation.
    """

    def Connect(self, request, context):
        """
        Connect to the vehicle.

        Connects to the underlying vehicle hardware. Generally, this 
        method is called by the law authority on startup and is not
        called by user code.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Disconnect(self, request, context):
        """
        Disconnect from the vehicle.

        Disconnects from the underlying vehicle hardware. Generally,
        this method is called by the law authority when it attempts
        a driver restart and is not called by user code.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Arm(self, request, context):
        """
        Order the vehicle to arm.

        Arms the vehicle. This is required before any other commands
        are run, otherwise the methods will return `FAILED_PRECONDITION`.
        Once the vehicle is armed, all subsequent actuation methods
        _will move the vehicle_. Make sure to go over the manufacturer
        recommended vehicle-specific pre-operation checklist before arming.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Disarm(self, request, context):
        """
        Order the vehicle to disarm.

        Disarms the vehicle. Prevents any further actuation methods
        from executing, unless the vehicle is re-armed.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Joystick(self, request, context):
        """
        Send a joystick command to the vehicle.

        Causes the vehicle to accelerate towards a provided velocity
        setpoint over a provided duration. This is useful for fine-grained 
        control based on streamed datasink results or for tele-operating 
        the vehicle from a remote commander.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def TakeOff(self, request, context):
        """
        Order the vehicle to take off.

        Causes the vehicle to take off to a specified take off altitude.
        If the vehicle is not a UAV, this method will be unimplemented.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Land(self, request, context):
        """
        Order the vehicle to land.

        Causes the vehicle to land at its current location. If the 
        vehicle is not a UAV, this method will be unimplemented.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Hold(self, request, context):
        """
        Order the vehicle to hold/loiter.

        Causes the vehicle to hold at its current location and to
        cancel any ongoing movement commands (`ReturnToHome` e.g.).
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Kill(self, request, context):
        """
        Orders an emergency shutdown of the vehicle motors.

        Causes the vehicle to immediately turn off its motors. _If the 
        vehicle is a UAV, this will result in a freefall_. Use this
        method only in emergency situations.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetHome(self, request, context):
        """
        Set the home location of the vehicle.

        Changes the home location of the vehicle. Future `ReturnToHome`
        commands will move the vehicle to the provided location instead
        of its starting position.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ReturnToHome(self, request, context):
        """
        Order the vehicle to return to its home position.

        Causes the vehicle to return to its home position. If the home position 
        has not been explicitly set, this will be its start position (defined 
        as its takeoff position for UAVs). If the home position has been 
        explicitly set, by `SetHome`, the vehicle will return to that 
        position instead.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetGlobalPosition(self, request, context):
        """
        Order the vehicle to move to a global position.

        Causes the vehicle to transit to the provided global position. The vehicle
        will interpret the heading of travel according to `heading_mode`:
        - `TO_TARGET` -> turn to face the target position bearing
        - `HEADING_START` -> turn to face the provided heading in the global position object. 

        This will be the heading the vehicle maintains for the duration of transit. 
        Generally only UAVs will support `HEADING_START`.

        The vehicle will move towards the target at the specified maximum velocity 
        until the vehicle has reached its destination. Error tolerance is determined 
        by the driver. Maximum velocity is interpreted from `max_velocity` as follows:
        - `x_vel` -> maximum _horizontal_ velocity
        - `y_vel` -> ignored
        - `z_vel` -> maximum _vertical_ velocity _(UAV only)_

        If no maximum velocity is provided, the driver will use a preset speed usually 
        determined by the manufacturer or hardware settings.

        _(UAV only)_ During motion, the vehicle will also ascend or descend towards the 
        target altitude, linearly interpolating this movement over the duration of
        travel. The vehicle will interpret altitude from `altitude_mode` as follows:
        - `ABSOLUTE` -> altitude is relative to MSL (Mean Sea Level)
        - `RELATIVE` -> altitude is relative to take off position
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetRelativePosition(self, request, context):
        """
        Order the vehicle to move to a relative position.

        Causes the vehicle to transit to the provided relative position. The vehicle
        will interpret the input position according to `frame` as follows:
        - `BODY` -> (`x`, `y`, `z`) = (forward offset, right offset, up offset) _from current position_
        - `NEU` -> (`x`, `y`, `z`) = (north offset, east offset, up offset) _from start position_

        The vehicle will move towards the target at the specified maximum velocity 
        until the vehicle has reached its destination. Error tolerance is determined 
        by the driver. Maximum velocity is interpreted from `max_velocity` as follows:
        - `x_vel` -> maximum _horizontal_ velocity
        - `y_vel` -> ignored
        - `z_vel` -> maximum _vertical_ velocity _(UAV only)_

        If no maximum velocity is provided, the driver will use a preset speed usually 
        determined by the manufacturer or hardware settings.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetVelocity(self, request, context):
        """
        Order the vehicle to accelerate to a velocity.

        Causes the vehicle to accelerate until it reaches a provided velocity.
        Error tolerance is determined by the driver. The vehicle will interpret 
        the input velocity according to `frame` as follows:
        - `BODY` -> (`x_vel`, `y_vel`, `z_vel`) = (forward velocity, right velocity, up velocity)
        - `NEU` -> (`x_vel`, `y_vel`, `z_vel`) = (north velocity, east velocity, up velocity)
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetHeading(self, request, context):
        """
        Order the vehicle to set a new heading.

        Causes the vehicle to turn to face the provided global position. The vehicle
        will interpret the final heading according to `heading_mode`:
        - `TO_TARGET` -> turn to face the target position bearing
        - `HEADING_START` -> turn to face the provided heading in the global position object. 
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetGimbalPose(self, request, context):
        """
        Order the vehicle to set the pose of a gimbal.

        Causes the vehicle to actuate a gimbal to a new pose. The vehicle
        will interpret the new pose type from `pose_mode` as follows: 
        - `ABSOLUTE` -> absolute angle
        - `RELATIVE` -> angle relative to current position
        - `VELOCITY` -> angular velocities

        The vehicle will interpret the new pose angles according to `frame` 
        as follows:
        - `BODY` -> (`pitch`, `roll`, `yaw`) = (body pitch, body roll, body yaw)
        - `NEU` -> (`pitch`, `roll`, `yaw`) = (body pitch, body roll, global yaw)
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureImagingSensorStream(self, request, context):
        """
        Configure the vehicle imaging stream.

        Sets which imaging sensors are streaming and sets their target
        frame rates.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureTelemetryStream(self, request, context):
        """
        Configure the vehicle telemetry stream.

        Sets the frequency of the telemetry stream.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_ControlServicer_to_server(servicer, server):
    rpc_method_handlers = {'Connect': grpc.unary_unary_rpc_method_handler(servicer.Connect, request_deserializer=services_dot_control__service__pb2.ConnectRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Disconnect': grpc.unary_unary_rpc_method_handler(servicer.Disconnect, request_deserializer=services_dot_control__service__pb2.DisconnectRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Arm': grpc.unary_unary_rpc_method_handler(servicer.Arm, request_deserializer=services_dot_control__service__pb2.ArmRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Disarm': grpc.unary_unary_rpc_method_handler(servicer.Disarm, request_deserializer=services_dot_control__service__pb2.DisarmRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Joystick': grpc.unary_unary_rpc_method_handler(servicer.Joystick, request_deserializer=services_dot_control__service__pb2.JoystickRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'TakeOff': grpc.unary_stream_rpc_method_handler(servicer.TakeOff, request_deserializer=services_dot_control__service__pb2.TakeOffRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Land': grpc.unary_stream_rpc_method_handler(servicer.Land, request_deserializer=services_dot_control__service__pb2.LandRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Hold': grpc.unary_stream_rpc_method_handler(servicer.Hold, request_deserializer=services_dot_control__service__pb2.HoldRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Kill': grpc.unary_stream_rpc_method_handler(servicer.Kill, request_deserializer=services_dot_control__service__pb2.KillRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'SetHome': grpc.unary_unary_rpc_method_handler(servicer.SetHome, request_deserializer=services_dot_control__service__pb2.SetHomeRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'ReturnToHome': grpc.unary_stream_rpc_method_handler(servicer.ReturnToHome, request_deserializer=services_dot_control__service__pb2.ReturnToHomeRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'SetGlobalPosition': grpc.unary_stream_rpc_method_handler(servicer.SetGlobalPosition, request_deserializer=services_dot_control__service__pb2.SetGlobalPositionRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'SetRelativePosition': grpc.unary_stream_rpc_method_handler(servicer.SetRelativePosition, request_deserializer=services_dot_control__service__pb2.SetRelativePositionRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'SetVelocity': grpc.unary_stream_rpc_method_handler(servicer.SetVelocity, request_deserializer=services_dot_control__service__pb2.SetVelocityRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'SetHeading': grpc.unary_stream_rpc_method_handler(servicer.SetHeading, request_deserializer=services_dot_control__service__pb2.SetHeadingRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'SetGimbalPose': grpc.unary_stream_rpc_method_handler(servicer.SetGimbalPose, request_deserializer=services_dot_control__service__pb2.SetGimbalPoseRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'ConfigureImagingSensorStream': grpc.unary_unary_rpc_method_handler(servicer.ConfigureImagingSensorStream, request_deserializer=services_dot_control__service__pb2.ConfigureImagingSensorStreamRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'ConfigureTelemetryStream': grpc.unary_unary_rpc_method_handler(servicer.ConfigureTelemetryStream, request_deserializer=services_dot_control__service__pb2.ConfigureTelemetryStreamRequest.FromString, response_serializer=common__pb2.Response.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.control_service.Control', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.control_service.Control', rpc_method_handlers)

class Control(object):
    """
    Used for low-level control of a vehicle.

    This service is hosted by the driver module and represents the global
    control interface for the vehicle. Most methods called here will result
    in actuation of the vehicle if it is armed (be careful!). Some methods,
    like TakeOff, may take some time to complete. For this reason, it is
    not advisable to set a timeout/deadline on the RPC call. However, to
    ensure that the service is progressing, a client can either check
    telemetry or listen for `IN_PROGRESS` response heartbeats which are
    streamed back from the RPC while executing an operation.
    """

    @staticmethod
    def Connect(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Connect', services_dot_control__service__pb2.ConnectRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Disconnect(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Disconnect', services_dot_control__service__pb2.DisconnectRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Arm(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Arm', services_dot_control__service__pb2.ArmRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Disarm(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Disarm', services_dot_control__service__pb2.DisarmRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Joystick(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/Joystick', services_dot_control__service__pb2.JoystickRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def TakeOff(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/TakeOff', services_dot_control__service__pb2.TakeOffRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Land(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/Land', services_dot_control__service__pb2.LandRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Hold(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/Hold', services_dot_control__service__pb2.HoldRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Kill(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/Kill', services_dot_control__service__pb2.KillRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetHome(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/SetHome', services_dot_control__service__pb2.SetHomeRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ReturnToHome(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/ReturnToHome', services_dot_control__service__pb2.ReturnToHomeRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetGlobalPosition(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetGlobalPosition', services_dot_control__service__pb2.SetGlobalPositionRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetRelativePosition(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetRelativePosition', services_dot_control__service__pb2.SetRelativePositionRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetVelocity(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetVelocity', services_dot_control__service__pb2.SetVelocityRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetHeading(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetHeading', services_dot_control__service__pb2.SetHeadingRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetGimbalPose(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.control_service.Control/SetGimbalPose', services_dot_control__service__pb2.SetGimbalPoseRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureImagingSensorStream(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/ConfigureImagingSensorStream', services_dot_control__service__pb2.ConfigureImagingSensorStreamRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureTelemetryStream(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.control_service.Control/ConfigureTelemetryStream', services_dot_control__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)