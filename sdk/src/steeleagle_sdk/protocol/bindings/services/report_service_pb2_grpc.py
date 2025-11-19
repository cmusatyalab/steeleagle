"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings
from ..services import report_service_pb2 as services_dot_report__service__pb2
GRPC_GENERATED_VERSION = '1.71.2'
GRPC_VERSION = grpc.__version__
_version_not_supported = False
try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True
if _version_not_supported:
    raise RuntimeError(f'The grpc package installed is at version {GRPC_VERSION},' + f' but the generated code in services/report_service_pb2_grpc.py depends on' + f' grpcio>={GRPC_GENERATED_VERSION}.' + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}' + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.')

class ReportStub(object):
    """
    Used to report messages to the Swarm Controller server
    or to other collaborative vehicles
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.SendReport = channel.unary_unary('/steeleagle.protocol.services.report_service.Report/SendReport', request_serializer=services_dot_report__service__pb2.SendReportRequest.SerializeToString, response_deserializer=services_dot_report__service__pb2.SendReportResponse.FromString, _registered_method=True)

class ReportServicer(object):
    """
    Used to report messages to the Swarm Controller server
    or to other collaborative vehicles
    """

    def SendReport(self, request, context):
        """Send a report to the server, or to an intended recipient
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_ReportServicer_to_server(servicer, server):
    rpc_method_handlers = {'SendReport': grpc.unary_unary_rpc_method_handler(servicer.SendReport, request_deserializer=services_dot_report__service__pb2.SendReportRequest.FromString, response_serializer=services_dot_report__service__pb2.SendReportResponse.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.report_service.Report', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.report_service.Report', rpc_method_handlers)

class Report(object):
    """
    Used to report messages to the Swarm Controller server
    or to other collaborative vehicles
    """

    @staticmethod
    def SendReport(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.report_service.Report/SendReport', services_dot_report__service__pb2.SendReportRequest.SerializeToString, services_dot_report__service__pb2.SendReportResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)