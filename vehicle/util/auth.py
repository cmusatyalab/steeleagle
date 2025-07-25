import grpc
from grpc_interceptor.exceptions import GrpcException
from grpc_interceptor.server import AsyncServerInterceptor
import inspect
# Protocol import
import python_bindings.control_pb2 as control_proto

class ControlAuth(AsyncServerInterceptor):
    def __init__(self, mode, logger):
        super().__init__()
        self._control_mode = mode
        self._logger = logger

    async def intercept(self, method, request, context, method_name):
        try:
            # Check to see if the control mode is autonomous
            # (the mission has vehicle authorization)
            if mode != control_proto.ControlMode.AUTONOMOUS: 
                self._logger.error("Command rejected due to invalid authorization")
                raise GrpcException("No active control authorization")
            if inspect.isasyncgenfunction(method):
                async for response in method(request, context):
                    yield response
            else:
                yield await method(request, context)
        except GrpcException as e:
            await context.set_code(e.status_code)
            await context.set_details(e.details)
            raise
