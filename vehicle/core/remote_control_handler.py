import asyncio
import os
import zmq
import zmq.asyncio
import time
import grpc
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
from core.laws import LawAuthority

logger = get_logger('core/remote_control_handler')

class RemoteControlHandler(LawAuthority):
    '''
    Handles all remote input from the server and external vehicles while
    also managing the global law for all entities. Has command authority
    to send state transition commands as specified in the law file.
    '''
    def __init__(self):
        super().__init__()
        self._channel = grpc.aio.insecure_channel(query_config('internal.services.core.endpoint'))
        # Create a descriptor pool which can look up services by name from
        # generated .desc file
        self._desc_pool = DescriptorPool()
        self._name_table = {}
        root = os.getenv('ROOTPATH')
        if not root:
            root = '../'
        with open(f"{root}protocol/services.desc", 'rb') as f:
            data = f.read()
            descriptor_set = FileDescriptorSet.FromString(data)
            for file_descriptor_proto in descriptor_set.file:
                self._desc_pool.Add(file_descriptor_proto)
                fname = file_descriptor_proto.name.split('.')[0]
                for service in file_descriptor_proto.service:
                    self._name_table[service.name] = f'protocol.{fname}.{service.name}'
            # Message class holder to support dynamic instantiation of messages
            self._message_classes = GetMessages(descriptor_set.file)

    async def _send_commands(self, command_list, identity='authority'):
        '''
        Overrides base function in LawAuthority.
        '''
        results = []
        for command in command_list:
            try:
                # Check if we are calling a JSON command or a proto object
                # command from a remote controller
                is_json_command = True if type(command) == list else False
                if is_json_command:
                    service, method = command[0].rsplit('.', 1)
                else:
                    full_name = command.method_name
                    service, method = full_name.rsplit('.', 1)
                # Fully qualify the name
                service = self._name_table[service]
                service_desc = self._desc_pool.FindServiceByName(service)
                method_desc = service_desc.FindMethodByName(method)
                # Build the request
                request = self._message_classes[method_desc.input_type.full_name]()
                request.request.ParseFromString(generate_request().SerializeToString())
                if is_json_command:
                    ParseDict(dict(command[1]), request, ignore_unknown_fields=True)
                else:
                    command.control_request.Unpack(request)
            except KeyError:
                logger.error(f'Command {method} ignored due to failed descriptor lookup!')
                response = self._message_classes[method_desc.output_type.full_name]()
                response.response.ParseFromString(
                        generate_response(5).SerializeToString() # Invalid argument
                        )
                results.append(response)
                continue
            metadata = [('identity', identity)]
            # Send in the correct classes to unmarshall from the channel
            classes = (
                    self._message_classes[method_desc.input_type.full_name],
                    self._message_classes[method_desc.output_type.full_name]
                    )
            try:
                results.append(
                        await reflective_grpc_call(
                            metadata,
                            f'/{service}/{method}',
                            method_desc,
                            request,
                            classes,
                            self._channel
                            )
                        )
            except grpc.aio.AioRpcError as e:
                logger.error(f'Encountered RPC error, {e.code()}: {e.details()}')
                response = self._message_classes[method_desc.output_type.full_name]()
                response.response.ParseFromString(
                        generate_response(e.code().value[0] + 2, resp_string=e.details()).SerializeToString()
                        )
                results.append(response)
        return results

    async def _send_results(self, command, command_socket):
        '''
        Send command and then relay its results over ZeroMQ.
        '''
        #logger.proto(command)
        results = await self._send_commands([command], identity=command.identity)
        # Only get one result back
        result = results[0]
        result_msg = RemoteControlResponse(
                sequence_number=command.sequence_number,
                identity=command.identity
                )
        # Pack the result
        result_msg.control_response.Pack(result)
        #logger.proto(result_msg)
        await command_socket.send(result_msg.SerializeToString())

    async def handle_remote_input(self, command_socket, timeout=1):
        '''
        Multiplexes incoming remote input commands to the appropriate
        service and returns responses to the sender.
        '''
        # Build the ZeroMQ poller which will poll for new messages
        poller = zmq.asyncio.Poller()
        poller.register(command_socket, zmq.POLLIN)
        
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
                    if timeout != None \
                        and last_manual_command_ts \
                        and time.time() - last_manual_command_ts >= timeout \
                        and self._state == '__REMOTE__':
                        logger.warning("FAILSAFE ACTIVATED!")
                        await self.set_law('__FAILSAFE__')
                        last_manual_command_ts = None
                    continue

                last_manual_command_ts = time.time()
                message = await command_socket.recv()
                request = RemoteControlRequest()
                request.ParseFromString(message)
                asyncio.create_task(self._send_results(request, command_socket))
        except Exception as e:
            logger.error(f'Terminated due to exception: {e}')
            return
