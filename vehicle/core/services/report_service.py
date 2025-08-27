# Protocol import
from bindings.python.services.report_service_pb2_grpc import ReportServicer
from bindings.python.services import report_service_pb2 as report_proto
# Utility import
from util.rpc import generate_response
from util.log import get_logger

logger = get_logger('core/services/report_service')

class ReportService(ReportServicer):
    '''
    Implementation of the report service.
    '''
    def __init__(self, socket):
        self._socket = socket

    async def SendReport(self, request, context):
        logger.info("Sent report to Swarm Controller!")
        logger.proto(request)
        self._socket.send(request.SerializeToString())
        return report_proto.SendReportResponse(
                response=generate_response(2)
                )
