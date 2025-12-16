import logging
# Protocol import
from steeleagle_sdk.protocol.services import compute_service_pb2_grpc as compute_proto
from steeleagle_sdk.protocol.services import compute_service_pb2 as compute_pb2
# Utility import
from steeleagle_sdk.protocol.rpc_helpers import generate_response
from collections import defaultdict

logger = logging.getLogger('kernel/services/compute_service')

class ComputeService(compute_proto.ComputeServicer):
    '''
    Implementation of the compute service.
    '''
    def __init__(self, stream_handler):
        self._stream_handler = stream_handler
        # Mapping from compute_proto.InputSource to datasinks corresponding
        # to that input source
        self._datasinks = defaultdict(set)

    async def AddDatasinks(self, request, context):
        for datasink in request.datasinks:
            new_datasinks = set()
            location = 'local:' if datasink.location else 'remote:'
            sources = [compute_pb2.InputSource.Name(s) for s in datasink.sources]
            logger.info(f'Adding datasink {location}{datasink.id} to {sources}!')
            new_datasinks.add(f'{location}{datasink.id}')

            for source in datasink.sources:
                self._datasinks[source].update(new_datasinks)

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
