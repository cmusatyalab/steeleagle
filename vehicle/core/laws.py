from enum import Enum
import grpc
from grpc_interceptor.server import AsyncServerInterceptor
import yaml
import os
from fnmatch import fnmatch
import aiorwlock
# Utility import
from util.log import get_logger

logger = get_logger('core/laws')

class LawAuthority:
    '''
    Maintains a unified state of the current control law. Other entities
    can query to get the up-to-date law, or request a change. The
    remote control handler derives from this class and thus manages
    the law for all entities.
    '''
    def __init__(self):
        path = os.getenv('LAWPATH')
        if not path:
            path = '.laws.yaml'
        with open(path, 'r') as laws:
            self._spec = yaml.safe_load(laws)
        self._state = None
        self._law = None
        self._lock = aiorwlock.RWLock()

    async def startup(self):
        '''
        Call the __onstart__ calls for the law scheme. Must be
        called before any other function!
        '''
        await self.set_law(self._spec['__first__'])
        logger.info('Sending startup commands...')
        await self._send_commands(self._spec['__onstart__'])

    async def allows(self, identity, command):
        '''
        Perform regex matching against law to see if command is
        authorized for this identity.
        '''
        if identity == 'server' or identity == 'authority':
            return True
        async with self._lock.reader_lock:
            for expr in self._law['allowed']:
                if fnmatch(command, expr):
                    return True
            return False

    async def transit(self, command):
        '''
        Transit to the next control state if a regex match is found.
        '''
        next_state = None
        async with self._lock.reader_lock:
            # Always consider user conditions first, then apply base cases
            user_transits = {}
            transits = self._law['__transit__']
            if 'transit' in self._law:
                user_transits = self._law['transit']
            for expr in user_transits: # User specified
                if fnmatch(command, expr):
                    next_state = user_transits[expr]
                    break
            for expr in transits: # Base cases
                if fnmatch(command, expr):
                    next_state = transits[expr]
                    break
        if next_state and next_state != self._state:
            logger.info(
                    f'{command} matches transit expression {expr}; switching law to {next_state}!'
                    )
            await self.set_law(next_state)

    async def set_law(self, state):
        '''
        Sets a new law and sends on enter commands.
        '''
        if state == self._state:
            return
        async with self._lock.writer_lock:
            if state not in self._spec:
                logger.error(f'State {state} is not in the law specification!')
                state = '__FAILSAFE__' # Go into failsafe mode
            if self._spec[state]['on_enter']:
                await self._send_commands(self._spec[state]['on_enter'])
            self._update_law(state)

    async def get_law(self):
        '''
        Gets the current law.
        '''
        async with self._lock.reader_lock:
            return self._state, self._law 

    async def _send_commands(self, command_list, identity='authority'):
        '''
        Send commands to the appropriate service.
        '''
        # NOTE: This must be implemented by a child class
        pass
    
    def _update_law(self, state):
        '''
        Update the current law to the control state. NOTE: This should 
        only be called with a write lock!
        '''
        try:
            self._state = state
            self._law = self._spec[state]
            # Always maintain base cases
            self._law.update({'__transit__' : self._spec['__transit__']})
            logger.info(f'Transitioned to law: {state}')
        except:
            raise ValueError(f'Law {target} not found!')

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
        # and if so, transit to a matching state
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
            await self._authority.transit(command)

        response = method(request_or_iterator, context)

        # Check if response is an async generator (stream)
        if hasattr(response, '__aiter__'):
            async def async_generator_wrapper():
                async for item in response:
                    yield item
            return async_generator_wrapper()
        else:
            return await response            
