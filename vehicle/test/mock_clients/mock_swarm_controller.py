import asyncio
import zmq
import zmq.asyncio
import logging
from google.protobuf.json_format import MessageToDict
# Utility import
from util.rpc import generate_request
from util.log import get_logger
from util.config import query_config
# Protocol import
from bindings.python.services import remote_control_service_pb2 as remote_control_proto
from google.protobuf import any_pb2
# Sequencer import
from message_sequencer import MessageSequencer, Topic

logger = get_logger('test/mock_swarm_controller')

class MockSwarmController:
    '''
    Provides a fake Swarm Controller to test messaging over ZeroMQ.
    '''
    def __init__(self, socket, messages):
        self._socket = socket
        self._seq_num = 0
        self._device = query_config('vehicle.name')
        self.sequencer = MessageSequencer(Topic.SWARM_CONTROLLER, messages)

    async def send_recv_command(self, req_obj):
        '''
        Calls a service on the vehicle given a method name, a request object,
        and an empty response prototype. NOTE: This function is not designed 
        to be called asynchronously alongside send_recv_command calls.
        '''
        self.sequencer.write(req_obj.request)
        any_object = any_pb2.Any()
        any_object.Pack(req_obj.request)
        self._seq_num += 1
        control_request = remote_control_proto.RemoteControlRequest(
                sequence_number=self._seq_num,
                control_request=any_object,
                method_name=req_obj.method_name,
                identity=req_obj.identity
                ) 

        logger.info("Sending...")
        await self._socket.send_multipart(
                [self._device.encode("utf-8"), control_request.SerializeToString()]
                )
        
        complete = False
        logger.info("Receiving...")
        identity, resp_bytes = await self._socket.recv_multipart()
        resp_obj = remote_control_proto.RemoteControlResponse()
        resp_obj.ParseFromString(resp_bytes)
        response = req_obj.response
        resp_obj.control_response.Unpack(response)
        logger.info(str(MessageToDict(response)))
        if response.response.status == req_obj.status:
            logger.info(f"Got correct status: {req_obj.status}!")
            complete = True
        self.sequencer.write(response)
        return complete
