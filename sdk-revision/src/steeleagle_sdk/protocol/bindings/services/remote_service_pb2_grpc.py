"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from ..services import remote_service_pb2 as services_dot_remote__service__pb2
GRPC_GENERATED_VERSION = '1.71.2'
GRPC_VERSION = grpc.__version__
_version_not_supported = False
try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True
if _version_not_supported:
    raise RuntimeError(f'The grpc package installed is at version {GRPC_VERSION},' + f' but the generated code in services/remote_service_pb2_grpc.py depends on' + f' grpcio>={GRPC_GENERATED_VERSION}.' + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}' + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.')

class RemoteStub(object):
    """
    Used to control a vehicle remotely over ZeroMQ, usually hosted
    on the server
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Command = channel.unary_stream('/steeleagle.protocol.services.remote_service.Remote/Command', request_serializer=services_dot_remote__service__pb2.CommandRequest.SerializeToString, response_deserializer=services_dot_remote__service__pb2.CommandResponse.FromString, _registered_method=True)
        self.Compile = channel.unary_unary('/steeleagle.protocol.services.remote_service.Remote/Compile', request_serializer=services_dot_remote__service__pb2.CompileRequest.SerializeToString, response_deserializer=services_dot_remote__service__pb2.CompileResponse.FromString, _registered_method=True)

class RemoteServicer(object):
    """
    Used to control a vehicle remotely over ZeroMQ, usually hosted
    on the server
    """

    def Command(self, request, context):
        """Sends a request to a vehicle core service (Control, Mission, etc.)
        over ZeroMQ and returns the response
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Compile(self, request, context):
        """Compiles an SDK DSL script and returns the bytes or returns
        an error
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_RemoteServicer_to_server(servicer, server):
    rpc_method_handlers = {'Command': grpc.unary_stream_rpc_method_handler(servicer.Command, request_deserializer=services_dot_remote__service__pb2.CommandRequest.FromString, response_serializer=services_dot_remote__service__pb2.CommandResponse.SerializeToString), 'Compile': grpc.unary_unary_rpc_method_handler(servicer.Compile, request_deserializer=services_dot_remote__service__pb2.CompileRequest.FromString, response_serializer=services_dot_remote__service__pb2.CompileResponse.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.remote_service.Remote', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.remote_service.Remote', rpc_method_handlers)

class Remote(object):
    """
    Used to control a vehicle remotely over ZeroMQ, usually hosted
    on the server
    """

    @staticmethod
    def Command(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.remote_service.Remote/Command', services_dot_remote__service__pb2.CommandRequest.SerializeToString, services_dot_remote__service__pb2.CommandResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Compile(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.remote_service.Remote/Compile', services_dot_remote__service__pb2.CompileRequest.SerializeToString, services_dot_remote__service__pb2.CompileResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)