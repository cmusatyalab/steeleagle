import asyncio
import zmq
import zmq.asyncio
import logging
# Utility import
from util.rpc import generate_request
# Protocol import
from python_bindings import control_pb2 as control_proto
from google.protobuf import any_pb2
from python_bindings import driver_service_pb2 as driver_proto
from python_bindings import mission_service_pb2 as mission_proto
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
        control_request = control_proto.ControlRequest(
                sequence_number=self._seq_num,
                control_request=any_object
                ) 

        logger.info("Send command!")
        await self._socket.send(control_request.SerializeToString())
        logger.info("Finished send!")
        
        complete = False
        while not complete:
            logger.info("Receiving...")
            resp_obj = await self._socket.recv()
            type_url = resp_obj.control_response.getTypeUrl()
            if type_url.split('.')[-2] == "driver_service":
                response = getattr(
                        "driver_service_pb2",
                        type_url.split('.')[-1]
                        )
                self.sequencer.write(response)
            elif type_url.split('.')[-2] == "mission_service":
                response = getattr(
                        "mission_service_pb2",
                        type_url.split('.')[-1]
                        )
                self.sequencer.write(response)
            else:
                raise ValueError("Got unrecognized response type!")
            if response.status not in [0, 1, 6]:
                complete = True
            logger.info(f"Getting another resp, status = {response.status}")
