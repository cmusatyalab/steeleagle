"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from .. import common_pb2 as common__pb2
from ..services import mission_service_pb2 as services_dot_mission__service__pb2
GRPC_GENERATED_VERSION = '1.71.2'
GRPC_VERSION = grpc.__version__
_version_not_supported = False
try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True
if _version_not_supported:
    raise RuntimeError(f'The grpc package installed is at version {GRPC_VERSION},' + f' but the generated code in services/mission_service_pb2_grpc.py depends on' + f' grpcio>={GRPC_GENERATED_VERSION}.' + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}' + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.')

class MissionStub(object):
    """
    Used to start a new mission or stop an active mission
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Upload = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Upload', request_serializer=services_dot_mission__service__pb2.UploadRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Start = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Start', request_serializer=services_dot_mission__service__pb2.StartRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Stop = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Stop', request_serializer=services_dot_mission__service__pb2.StopRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Notify = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Notify', request_serializer=services_dot_mission__service__pb2.NotifyRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.ConfigureTelemetryStream = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/ConfigureTelemetryStream', request_serializer=services_dot_mission__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)

class MissionServicer(object):
    """
    Used to start a new mission or stop an active mission
    """

    def Upload(self, request, context):
        """Upload a mission for execution
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Start(self, request, context):
        """Start an uploaded mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Stop(self, request, context):
        """Stop the current mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Notify(self, request, context):
        """Send a notification to the current mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureTelemetryStream(self, request, context):
        """Set the mission telemetry stream parameters
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_MissionServicer_to_server(servicer, server):
    rpc_method_handlers = {'Upload': grpc.unary_unary_rpc_method_handler(servicer.Upload, request_deserializer=services_dot_mission__service__pb2.UploadRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Start': grpc.unary_unary_rpc_method_handler(servicer.Start, request_deserializer=services_dot_mission__service__pb2.StartRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Stop': grpc.unary_unary_rpc_method_handler(servicer.Stop, request_deserializer=services_dot_mission__service__pb2.StopRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Notify': grpc.unary_unary_rpc_method_handler(servicer.Notify, request_deserializer=services_dot_mission__service__pb2.NotifyRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'ConfigureTelemetryStream': grpc.unary_unary_rpc_method_handler(servicer.ConfigureTelemetryStream, request_deserializer=services_dot_mission__service__pb2.ConfigureTelemetryStreamRequest.FromString, response_serializer=common__pb2.Response.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.mission_service.Mission', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.mission_service.Mission', rpc_method_handlers)

class Mission(object):
    """
    Used to start a new mission or stop an active mission
    """

    @staticmethod
    def Upload(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Upload', services_dot_mission__service__pb2.UploadRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Start(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Start', services_dot_mission__service__pb2.StartRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Stop(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Stop', services_dot_mission__service__pb2.StopRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Notify(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Notify', services_dot_mission__service__pb2.NotifyRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureTelemetryStream(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/ConfigureTelemetryStream', services_dot_mission__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)