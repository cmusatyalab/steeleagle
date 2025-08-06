import inspect
import importlib
import asyncio
import grpc
# Utility import
from util.rpc import generate_request, async_unary_unary_request, async_unary_stream_request 
from util.proto import read_any
# Protocol imports
from google.protobuf import any_pb2
from python_bindings import swarm_control_pb2 as swarm_control_proto

class CommandMultiplexer:
    '''
    Reads messages from the Swarm Controller and relays
    them to the corresponding stubs.
    '''
    def __init__(self, auth, socket, call_table, failsafe, logger):
        self._socket = socket
        self._call_table = call_table
        # Failsafe triggered when the swarm controller disconnects
        self._failsafe = failsafe
        self._logger = logger

    async def _next_control_state(self, method):
        pass

    async def _handle_stream_request(self, func, request, seq_num):
        async for resp in async_unary_stream_request(func, request, self._logger):
            response = swarm_control_proto.SwarmControlResponse()
            response.sequence_number = seq_num
            response.control_response.Pack(resp)
            asyncio.create_task(self._socket.send(response.SerializeToString()))
    
    async def _handle_unary_request(self, func, request, seq_num):
        resp = await async_unary_unary_request(func, request, self._logger)
        response = swarm_control_proto.SwarmControlResponse()
        response.sequence_number = seq_num
        response.control_response.Pack(resp)
        await self._socket.send(response.SerializeToString())

    async def _send_request(self, method, request, seq_num):
        '''
        Multiplexes a SwarmControlRequest message between allowed stubs.
        '''
        try:
            func = self._call_table[method]
            # Switch mode based on internal state machine
            await self._next_control_state(method)
            # Only accepts Unary->Unary and Unary->Stream methods
            if isinstance(func, grpc.aio._channel.UnaryStreamMultiCallable):
                asyncio.create_task(self._handle_stream_request(func, request, seq_num))
            else:
                asyncio.create_task(self._handle_unary_request(func, request, seq_num))
        except KeyError:
            self._logger.error("Request not in call table!")
            raise TypeError("Command has unknown type!")

    async def failsafe(self): 
        '''
        Orders the vehicle to execute a failsafe in case of remote disconnection.
        '''
        try:
            request, method = self._failsafe
            asyncio.create_task(self._send_request(method, request))
        except:
            raise ValueError("Invalid failsafe!")
        
    async def __call__(self, message):
        '''
        Easy interface to send requests and receive responses.
        '''
        # Message is expected to be a SwarmControlRequest 
        try:
            control = swarm_control_proto.SwarmControlRequest()
            control.ParseFromString(message)
            self._logger.info_proto(control)
        except:
            self._logger.error('Could not read request!')
            # TODO: Make sure we return a blank SCR object
            return
        # Get the message name from the type URL
        _, service, name = control.control_request.type_url.rsplit('.', 2)
        name = name.replace('Request', '')
        method = f'{service}.{name}'
        request = read_any(control.control_request)
        try:
            await self._send_request(method, request, control.sequence_number)
            return
        except Exception as e:
            self._logger.error(f'Could not make request, reason: {e}')
            # TODO: Make sure we return a blank SCR object
            return

