"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from .. import common_pb2 as common__pb2
from ..services import flight_log_service_pb2 as services_dot_flight__log__service__pb2
GRPC_GENERATED_VERSION = '1.71.2'
GRPC_VERSION = grpc.__version__
_version_not_supported = False
try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True
if _version_not_supported:
    raise RuntimeError(f'The grpc package installed is at version {GRPC_VERSION},' + f' but the generated code in services/flight_log_service_pb2_grpc.py depends on' + f' grpcio>={GRPC_GENERATED_VERSION}.' + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}' + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.')

class FlightLogStub(object):
    """
    Used to log to a flight log.

    This service is hosted by a logger instance and is responsible
    for writing all system logs to an MCAP file for mission playback.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Log = channel.unary_unary('/steeleagle.protocol.services.flight_log_service.FlightLog/Log', request_serializer=services_dot_flight__log__service__pb2.LogRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.LogProto = channel.unary_unary('/steeleagle.protocol.services.flight_log_service.FlightLog/LogProto', request_serializer=services_dot_flight__log__service__pb2.LogProtoRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)

class FlightLogServicer(object):
    """
    Used to log to a flight log.

    This service is hosted by a logger instance and is responsible
    for writing all system logs to an MCAP file for mission playback.
    """

    def Log(self, request, context):
        """
        Basic log endpoint.

        Behaves identically to most log endpoints, but writes the data to
        an MCAP file instead of the console.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def LogProto(self, request, context):
        """
        Protobuf log endpoint.

        Accepts Protobuf Request/Response types, and writes the data to
        an MCAP file. Useful for playback of gRPC calls.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_FlightLogServicer_to_server(servicer, server):
    rpc_method_handlers = {'Log': grpc.unary_unary_rpc_method_handler(servicer.Log, request_deserializer=services_dot_flight__log__service__pb2.LogRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'LogProto': grpc.unary_unary_rpc_method_handler(servicer.LogProto, request_deserializer=services_dot_flight__log__service__pb2.LogProtoRequest.FromString, response_serializer=common__pb2.Response.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.flight_log_service.FlightLog', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.flight_log_service.FlightLog', rpc_method_handlers)

class FlightLog(object):
    """
    Used to log to a flight log.

    This service is hosted by a logger instance and is responsible
    for writing all system logs to an MCAP file for mission playback.
    """

    @staticmethod
    def Log(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.flight_log_service.FlightLog/Log', services_dot_flight__log__service__pb2.LogRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def LogProto(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.flight_log_service.FlightLog/LogProto', services_dot_flight__log__service__pb2.LogProtoRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)