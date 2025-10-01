import logging
# Protocol import
from steeleagle_sdk.protocol.services import compute_service_pb2_grpc as compute_proto
# Utility import
from steeleagle_sdk.protocol.rpc_helpers import generate_response

logger = logging.getLogger('kernel/services/compute_service')

class ComputeService(compute_proto.ComputeServicer):
    '''
    Implementation of the compute service.
    '''
    def __init__(self, stream_handler):
        self._stream_handler = stream_handler
        self._datasinks = set([])

    async def AddDatasinks(self, request, context):
        new_datasinks = set([])
        for datasink in request.datasinks:
            location = 'local:' if datasink.location else 'remote:'
            logger.info(f'Adding datasink {location}{datasink.id}!')
            new_datasinks.add(f'{location}{datasink.id}')
        
        self._datasinks = self._datasinks.union(new_datasinks)
        self._stream_handler.update_target_engines(self._datasinks)
        
        return generate_response(2)

    async def SetDatasinks(self, request, context):
        new_datasinks = set([])
        for datasink in request.datasinks:
            location = 'local:' if datasink.location else 'remote:'
            logger.info(f'Adding datasink {location}{datasink.id}!')
            new_datasinks.add(f'{location}{datasink.id}')
        
        self._datasinks = new_datasinks
        self._stream_handler.update_target_engines(self._datasinks)
        
        return generate_response(2)

    async def RemoveDatasinks(self, request, context):
        new_datasinks = set([])
        for datasink in request.datasinks:
            location = 'local:' if datasink.location else 'remote:'
            logger.info(f'Removing datasink {location}{datasink.id}!')
            new_datasinks.add(f'{location}{datasink.id}')
        
        self._datasinks = self._datasinks.difference(new_datasinks)
        self._stream_handler.update_target_engines(self._datasinks)
        
        return generate_response(2)
