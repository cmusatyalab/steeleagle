import grpc
from grpc_interceptor.server import AsyncServerInterceptor
# Utility import
from util.log import get_logger

logger = get_logger('kernel/laws/interceptor')
    
class LawInterceptor(AsyncServerInterceptor):
    '''
    A gRPC interceptor designed to check all kernel services against the 
    current control law. Commands that do not fit the law are rejected.
    '''
    def __init__(self, authority):
        super().__init__()
        self._authority = authority

    async def intercept(self, method, request, context, method_name):
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
        if not identity:
            logger.error(f'Command {command} rejected because no identity was provided!')
            await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Command {command} rejected because no identity was provided!"
                    )
        elif identity == 'authority':
            pass # We ignore all checks for authority commands
        else:
            # Check if a command is allowed, then match it against the current law's
            # match statements
            if await self._authority.allows(command, request):
                await self._authority.match(command, request)
            else:
                logger.error(f'Command {command} rejected for identity {identity}!')
                await context.abort(
                        grpc.StatusCode.PERMISSION_DENIED,
                        f"Command {command} rejected for identity {identity}!"
                        )

        response = method(request, context)

        # Check if response is an async generator (stream)
        if hasattr(response, '__aiter__'):
            async def async_generator_wrapper():
                async for item in response:
                    yield item
            return async_generator_wrapper()
        else:
            return await response            
