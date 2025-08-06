# Protocol import
from python_bindings import report_service_pb2_grpc as report_proto
# Utility import
from util.rpc import generate_response

class ReportService(report_proto.ReportServicer):
    '''
    Implementation of the report service.
    '''
    def __init__(self, socket, logger):
        self._socket = socket
        self._logger = logger

    async def SendReport(self, request, context):
        self._logger.info("Sent report to Swarm Controller!")
        self._logger.info_proto(request)
        self._socket.send(request.report_string)
        return report_proto.ReportResponse(
                response=generate_response(2)
                )
