import asyncio
import zmq
import zmq.asyncio
import logging
# Utility import
from util.rpc import generate_request
from util.config import query_config
from util.proto import read_any
# Protocol import
from python_bindings import swarm_control_pb2 as swarm_control_proto
from google.protobuf import any_pb2
# Test import
from message_sequencer import sequence_params

logger = logging.getLogger(__name__)

class MockSwarmController:
    '''
    Provides a fake Swarm Controller to test messaging over ZeroMQ.
    '''
    def __init__(self, socket, sequencer):
        self._socket = socket
        self._seq_num = 0
        self._device = query_config('vehicle.name')
        self.sequencer = sequencer

    @sequence_params
    async def send_recv_command(self, request):
        '''
        NOTE: This function is not designed to be called asynchronously
        alongside send_recv_command calls.
        '''
        any_object = any_pb2.Any()
        any_object.Pack(request)
        self._seq_num += 1
        control_request = swarm_control_proto.SwarmControlRequest(
                sequence_number=self._seq_num,
                control_request=any_object
                ) 

        await self._socket.send_multipart(
                [self._device.encode("utf-8"), control_request.SerializeToString()]
                )
        
        complete = False
        logger.info("Waiting for response")
        while not complete:
            logger.info("Receiving...")
            identity, resp_bytes = await self._socket.recv_multipart()
            resp_obj = swarm_control_proto.SwarmControlResponse()
            resp_obj.ParseFromString(resp_bytes)
            response = read_any(resp_obj.control_response)
            if response.response.status == 2:
                logger.info("Got 200 status code!")
                complete = True
            self.sequencer.write(read_any(resp_obj.control_response))
