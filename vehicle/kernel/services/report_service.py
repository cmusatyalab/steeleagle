import logging
# Protocol import
from steeleagle_sdk.protocol.services.report_service_pb2_grpc import ReportServicer
# Utility import
from steeleagle_sdk.protocol.rpc_helpers import generate_response

logger = logging.getLogger('kernel/services/report_service')

class ReportService(ReportServicer):
    '''
    Implementation of the report service.
    '''
    def __init__(self, socket):
        self._socket = socket

    async def SendReport(self, request, context):
        logger.info("Sent report to Swarm Controller!")
        self._socket.send(request.SerializeToString())
        return generate_response(2)
