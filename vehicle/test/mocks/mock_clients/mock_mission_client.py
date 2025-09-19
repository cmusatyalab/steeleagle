import asyncio
import logging
import grpc
# Utility import
from util.log import get_logger
from util.config import query_config
# Sequencer import
from test.message_sequencer import Topic, MessageSequencer
# Protocol import
from steeleagle_sdk.protocol.services.control_service_pb2_grpc import ControlStub
from steeleagle_sdk.protocol.services.report_service_pb2_grpc import ReportStub
from steeleagle_sdk.protocol.services.compute_service_pb2_grpc import ComputeStub
from google.protobuf import any_pb2

logger = get_logger('test/mock_mission')

class MockMissionClient:
    '''
    Provides a fake mission client to test messaging over gRPC.
    '''
    def __init__(self, messages):
        self._channel = grpc.aio.insecure_channel(query_config('internal.services.kernel'))
        self._control_stub = ControlStub(self._channel)
        self._report_stub = ReportStub(self._channel)
        self._compute_stub = ComputeStub(self._channel)
        self._identity = 'internal'
        self.sequencer = MessageSequencer(Topic.MISSION_SERVICE, messages)

    async def send_recv_command(self, req_obj):
        '''
        Calls a service on the vehicle given a method name, a request object,
        and an empty response prototype.
        '''
        self.sequencer.write(req_obj.request)

        # Send message to the appropriate service
        service, method = req_obj.method_name.split('.')
        try:
            response = None
            stub = None
            if service == 'Control':
                stub = self._control_stub
            elif service == 'Report':
                stub = self._report_stub
            elif service == 'Compute':
                stub = self._compute_stub
            else:
                raise ValueError(f'Unknown stub type {service}!')
            method = getattr(stub, method)
            metadata = [
                ('identity', 'internal')
            ]
            call = method(req_obj.request, metadata=metadata)
            if hasattr(call, '__aiter__'):
                responses = []
                async for response in call:
                    responses.append(response)
                response = responses[-1]
            else:
                response = await call
        except grpc.aio.AioRpcError as e:
            logger.error(f'Exception occured for {req_obj.method_name}, {e}')
            response.status = e.code().value[0] + 2
        
        self.sequencer.write(response)
        return response.status == req_obj.status
