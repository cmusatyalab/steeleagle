"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from ..services import compute_service_pb2 as services_dot_compute__service__pb2
GRPC_GENERATED_VERSION = '1.71.2'
GRPC_VERSION = grpc.__version__
_version_not_supported = False
try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True
if _version_not_supported:
    raise RuntimeError(f'The grpc package installed is at version {GRPC_VERSION},' + f' but the generated code in services/compute_service_pb2_grpc.py depends on' + f' grpcio>={GRPC_GENERATED_VERSION}.' + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}' + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.')

class ComputeStub(object):
    """
    Used to configure datasinks for sensor streams
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.GetAvailableDatasinks = channel.unary_unary('/steeleagle.protocol.services.compute_service.Compute/GetAvailableDatasinks', request_serializer=services_dot_compute__service__pb2.GetAvailableDatasinksRequest.SerializeToString, response_deserializer=services_dot_compute__service__pb2.GetAvailableDatasinksResponse.FromString, _registered_method=True)
        self.ConfigureDatasinks = channel.unary_unary('/steeleagle.protocol.services.compute_service.Compute/ConfigureDatasinks', request_serializer=services_dot_compute__service__pb2.ConfigureDatasinksRequest.SerializeToString, response_deserializer=services_dot_compute__service__pb2.ConfigureDatasinksResponse.FromString, _registered_method=True)

class ComputeServicer(object):
    """
    Used to configure datasinks for sensor streams
    """

    def GetAvailableDatasinks(self, request, context):
        """Get all available compute engines, both local and remote
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureDatasinks(self, request, context):
        """Configure compute preferences
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_ComputeServicer_to_server(servicer, server):
    rpc_method_handlers = {'GetAvailableDatasinks': grpc.unary_unary_rpc_method_handler(servicer.GetAvailableDatasinks, request_deserializer=services_dot_compute__service__pb2.GetAvailableDatasinksRequest.FromString, response_serializer=services_dot_compute__service__pb2.GetAvailableDatasinksResponse.SerializeToString), 'ConfigureDatasinks': grpc.unary_unary_rpc_method_handler(servicer.ConfigureDatasinks, request_deserializer=services_dot_compute__service__pb2.ConfigureDatasinksRequest.FromString, response_serializer=services_dot_compute__service__pb2.ConfigureDatasinksResponse.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.compute_service.Compute', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.compute_service.Compute', rpc_method_handlers)

class Compute(object):
    """
    Used to configure datasinks for sensor streams
    """

    @staticmethod
    def GetAvailableDatasinks(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.compute_service.Compute/GetAvailableDatasinks', services_dot_compute__service__pb2.GetAvailableDatasinksRequest.SerializeToString, services_dot_compute__service__pb2.GetAvailableDatasinksResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureDatasinks(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.compute_service.Compute/ConfigureDatasinks', services_dot_compute__service__pb2.ConfigureDatasinksRequest.SerializeToString, services_dot_compute__service__pb2.ConfigureDatasinksResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)