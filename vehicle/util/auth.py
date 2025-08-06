from enum import Enum
import grpc
from grpc_interceptor.exceptions import GrpcException
from grpc_interceptor.server import AsyncServerInterceptor
import inspect

class ControlMode(Enum):
    REMOTE = 0
    LOCAL = 1
    RC = 2

class ControlAuth(AsyncServerInterceptor):
    def __init__(self, logger):
        super().__init__()
        self._mode = ControlMode.REMOTE
        self._logger = logger

    def set_mode(self, mode):
        self._logger.info("Changing control mode from {self._mode} to {mode}")
        self._mode = mode

    def get_mode(self):
        return self._mode

    async def intercept(self, method, request, context, method_name):
        try:
            # Check to see if the control mode is LOCAL
            # (the mission has vehicle authorization)
            if self._mode != ControlMode.LOCAL: 
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
