"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from .. import common_pb2 as common__pb2
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
    Used to configure datasinks for sensor streams.

    This service is used to configure datasink endpoints for frames and 
    telemetry post-processing. It maintains an internal consumer list of 
    datasinks that the kernel broadcasts frames and telemetry to. RPC 
    methods within this service allow for manipulation of this list.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.AddDatasinks = channel.unary_unary('/steeleagle.protocol.services.compute_service.Compute/AddDatasinks', request_serializer=services_dot_compute__service__pb2.AddDatasinksRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.SetDatasinks = channel.unary_unary('/steeleagle.protocol.services.compute_service.Compute/SetDatasinks', request_serializer=services_dot_compute__service__pb2.SetDatasinksRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.RemoveDatasinks = channel.unary_unary('/steeleagle.protocol.services.compute_service.Compute/RemoveDatasinks', request_serializer=services_dot_compute__service__pb2.RemoveDatasinksRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)

class ComputeServicer(object):
    """
    Used to configure datasinks for sensor streams.

    This service is used to configure datasink endpoints for frames and 
    telemetry post-processing. It maintains an internal consumer list of 
    datasinks that the kernel broadcasts frames and telemetry to. RPC 
    methods within this service allow for manipulation of this list.
    """

    def AddDatasinks(self, request, context):
        """
        Add datasinks to consumer list.

        Takes a list of datasinks and adds them to the current consumer list.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetDatasinks(self, request, context):
        """
        Set the datasink consumer list.

        Takes a list of datasinks and replaces the current consumer list with them.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def RemoveDatasinks(self, request, context):
        """
        Remove datasinks from consumer list.

        Takes a list of datasinks and removes them from the current consumer list.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_ComputeServicer_to_server(servicer, server):
    rpc_method_handlers = {'AddDatasinks': grpc.unary_unary_rpc_method_handler(servicer.AddDatasinks, request_deserializer=services_dot_compute__service__pb2.AddDatasinksRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'SetDatasinks': grpc.unary_unary_rpc_method_handler(servicer.SetDatasinks, request_deserializer=services_dot_compute__service__pb2.SetDatasinksRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'RemoveDatasinks': grpc.unary_unary_rpc_method_handler(servicer.RemoveDatasinks, request_deserializer=services_dot_compute__service__pb2.RemoveDatasinksRequest.FromString, response_serializer=common__pb2.Response.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.compute_service.Compute', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.compute_service.Compute', rpc_method_handlers)

class Compute(object):
    """
    Used to configure datasinks for sensor streams.

    This service is used to configure datasink endpoints for frames and 
    telemetry post-processing. It maintains an internal consumer list of 
    datasinks that the kernel broadcasts frames and telemetry to. RPC 
    methods within this service allow for manipulation of this list.
    """

    @staticmethod
    def AddDatasinks(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.compute_service.Compute/AddDatasinks', services_dot_compute__service__pb2.AddDatasinksRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def SetDatasinks(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.compute_service.Compute/SetDatasinks', services_dot_compute__service__pb2.SetDatasinksRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def RemoveDatasinks(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.compute_service.Compute/RemoveDatasinks', services_dot_compute__service__pb2.RemoveDatasinksRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)