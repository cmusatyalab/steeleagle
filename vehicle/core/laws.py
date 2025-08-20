from enum import Enum
import grpc
from grpc_interceptor.server import AsyncServerInterceptor
import json
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.message_factory import GetMessages
from google.protobuf.json_format import ParseDict
from google.protobuf import any_pb2
import toml
import os
from fnmatch import fnmatch
import aiorwlock
# Utility import
from util.log import get_logger
from util.config import query_config
from util.rpc import reflective_grpc_call, generate_response, generate_request

logger = get_logger('core/laws')

class Failsafe(Enum):
    DC_SERVER = 0
    DC_DRIVER = 1
    DC_MISSION = 2
    DC_REMOTE_COMPUTE = 3
    DC_LOCAL_COMPUTE = 4

class LawAuthority:
    '''
    Maintains a unified state of the current control law. Other entities
    can query to get the up-to-date law, or request a change. The
    remote control handler derives from this class and thus manages
    the law for all entities.
    '''
    def __init__(self):
        # Load in laws from the provided path
        path = os.getenv('LAWPATH')
        if not path:
            path = '.laws.toml'
        with open(path, 'r') as laws:
            self._spec = toml.load(laws)
            self._base = self._spec['__BASE__']
        self._state = None
        self._law = None
        self._lock = aiorwlock.RWLock()
        # Open a channel to connect to core services 
        self._channel = grpc.aio.insecure_channel(query_config('internal.services.core'))
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

    async def start(self):
        '''
        Call the start calls for the law scheme. Must be
        called before any other function!
        '''
        logger.info('Sending startup commands...')
        await self.set_law('__BASE__')

    async def allows(self, identity, command):
        '''
        Perform regex matching against law to see if command is
        authorized for this identity.
        '''
        if identity == 'authority':
            return True
        async with self._lock.reader_lock:
            for expr in (self._law['rules']['allowed'] + self._base['rules']['allowed']):
                if fnmatch(command, expr):
                    return True
            return False

    async def match(self, identity, command):
        '''
        Switch to the next control state if a regex match is found.
        '''
        if identity == 'authority':
            return
        next_state = None
        async with self._lock.reader_lock:
            # Always consider user conditions first, then apply base cases
            user_matches = []
            matches = self._base['rules']['match']
            if 'match' in self._law['rules']:
                user_matches = self._law['rules']['match']
            for expr in user_matches: # User specified
                if fnmatch(command, expr[0]):
                    next_state = expr[1]
                    break
            for expr in matches: # Base cases
                if fnmatch(command, expr[0]):
                    next_state = expr[1]
                    break
        if next_state and next_state != self._state:
            logger.info(
                    f'{command} matches match expression {expr}; switching law to {next_state}!'
                    )
            await self.set_law(next_state)

    async def failsafe(self, failsafe):
        pass

    async def set_law(self, state):
        '''
        Sets a new law and sends on enter commands.
        '''
        if state == self._state:
            return
        async with self._lock.writer_lock:
            if state not in self._spec:
                logger.error(f'State {state} is not in the law specification!')
                state = 'REMOTE' # Go into remote mode
            if self._spec[state]['enter']:
                await self._send_commands(self._spec[state]['enter'])
            self._update_law(state)

    async def get_law(self):
        '''
        Gets the current law.
        '''
        async with self._lock.reader_lock:
            return self._state, self._law 

    async def _send_commands(self, command_list, identity='authority'):
        '''
        Sends a list of commands, either JSON or a Protobuf, to the correct service
        in core and returns the results.
        '''
        results = []
        for command in command_list:
            try:
                # Check if we are calling a JSON command or a proto object
                # command from a remote controller
                is_json_command = True if type(command) == str else False
                if is_json_command:
                    splits = command.split('|')
                    if len(splits) > 1:
                        full_name, payload = splits
                    else:
                        full_name = splits[0]
                        payload = '{}'
                    service, method = full_name.rsplit('.', 1)
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
                    ParseDict(json.loads(payload), request, ignore_unknown_fields=True)
                else:
                    command.control_request.Unpack(request)
                logger.proto(request)
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
                response = await reflective_grpc_call(
                            metadata,
                            f'/{service}/{method}',
                            method_desc,
                            request,
                            classes,
                            self._channel
                            )
                results.append(response)
                logger.proto(response)
            except grpc.aio.AioRpcError as e:
                logger.error(f'Encountered RPC error, {e.code()}: {e.details()}')
                response = self._message_classes[method_desc.output_type.full_name]()
                response.response.ParseFromString(
                        generate_response(e.code().value[0] + 2, resp_string=e.details()).SerializeToString()
                        )
                results.append(response)
                logger.proto(response)
        return results
    
    def _update_law(self, state):
        '''
        Update the current law to the control state. NOTE: This should 
        only be called with a write lock!
        '''
        try:
            self._state = state
            self._law = self._spec[state]
            logger.info(f'Transitioned to law: {state}')
        except:
            raise ValueError(f'Law {state} not found!')

class LawInterceptor(AsyncServerInterceptor):
    '''
    A gRPC interceptor designed to check all core services against the 
    current control law. Commands that do not fit the law are rejected.
    '''
    def __init__(self, authority):
        super().__init__()
        self._authority = authority

    async def intercept(self, method, request_or_iterator, context, method_name):
        # Check if the command is allowed for the provided identity,
        # and if so, match to a matching state
        metadata = context.invocation_metadata()
        if not metadata or len(metadata) < 2:
            logger.error('No identity provided, command blocked!')
            await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    'No identity provided, command blocked!'
                    )
        service_url, method_name = method_name.rsplit('/', 1)
        service = service_url.rsplit('.', 2)[-1]
        identity = metadata[1][1]
        command = f'{identity}.{service}.{method_name}'
        if not identity or not await self._authority.allows(identity, command):
            logger.error(f'Command {command} rejected for identity {identity}!')
            await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Command {command} rejected for identity {identity}!"
                    )
        else:
            await self._authority.match(identity, command)

        response = method(request_or_iterator, context)

        # Check if response is an async generator (stream)
        if hasattr(response, '__aiter__'):
            async def async_generator_wrapper():
                async for item in response:
                    yield item
            return async_generator_wrapper()
        else:
            return await response            
