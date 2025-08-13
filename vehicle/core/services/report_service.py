# Protocol import
from python_bindings import report_service_pb2_grpc as report_proto
# Utility import
from util.rpc import generate_response
from util.log import get_logger

logger = get_logger('core/report_service')

class ReportService(report_proto.ReportServicer):
    '''
    Implementation of the report service.
    '''
    def __init__(self, socket):
        self._socket = socket

    async def SendReport(self, request, context):
        logger.info("Sent report to Swarm Controller!")
        logger.request_proto(request)
        self._socket.send(request.report_string)
        return report_proto.ReportResponse(
                response=generate_response(2)
                )
