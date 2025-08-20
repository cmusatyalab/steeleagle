import asyncio
import os
import zmq
import zmq.asyncio
import time
import grpc
import json
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.message_factory import GetMessages
from google.protobuf.json_format import ParseDict
from google.protobuf import any_pb2
# Utility imports
from util.log import get_logger
from util.config import query_config
from util.rpc import reflective_grpc_call, generate_response, generate_request
# Protocol import
from python_bindings.remote_control_pb2 import RemoteControlRequest, RemoteControlResponse
# Law import
from core.laws import LawAuthority, Failsafe

logger = get_logger('core/remote_control_handler')

class RemoteControlHandler:
    '''
    Handles all remote input from the server and external vehicles.
    '''
    def __init__(self, law_authority, command_socket):
        self._law_authority = law_authority
        self._command_socket = command_socket
        self._main_loop_task = None
    
    async def start(self, failsafe_timeout=1):
        self._main_loop_task = asyncio.create_task(self._handle_remote_input(failsafe_timeout)) 

    async def wait_for_termination(self):
        await self._main_loop_task
    
    async def _send_results(self, command):
        '''
        Send command and then relay its results over ZeroMQ.
        '''
        results = await self._law_authority._send_commands([command], identity=command.identity)
        # Only get one result back
        result = results[0]
        logger.proto(result)
        result_msg = RemoteControlResponse(
                sequence_number=command.sequence_number,
                identity=command.identity
                )
        # Pack the result
        result_msg.control_response.Pack(result)
        await self._command_socket.send(result_msg.SerializeToString())

    async def _handle_remote_input(self, timeout):
        '''
        Multiplexes incoming remote input commands to the appropriate
        service and returns responses to the sender.
        '''
        # Build the ZeroMQ poller which will poll for new messages
        poller = zmq.asyncio.Poller()
        poller.register(self._command_socket, zmq.POLLIN)
        
        # Track the last time we heard from the Swarm Controller
        last_manual_command_ts = None

        # Main handle loop
        try:
            while True:
                poll = dict(await poller.poll(timeout=0.5))
    
                # Skip our checks if no messages were delivered. However, if no
                # commands were recieved and we are in __REMOTE__ law, go into 
                # failsafe
                if not len(poll):
                    if timeout \
                        and last_manual_command_ts \
                        and time.time() - last_manual_command_ts >= timeout \
                        and (await self._law_authority.get_law())[0] == '__REMOTE__':
                        logger.warning("FAILSAFE ACTIVATED!")
                        await self._law_authority.failsafe(Failsafe.DC_SERVER)
                        last_manual_command_ts = None
                    continue

                last_manual_command_ts = time.time()
                message = await self._command_socket.recv()
                request = RemoteControlRequest()
                request.ParseFromString(message)
                asyncio.create_task(self._send_results(request))
        except Exception as e:
            logger.error(f'Terminated due to exception: {e}')
            return
