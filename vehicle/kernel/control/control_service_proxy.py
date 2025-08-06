# Utility import
from util.rpc import async_unary_unary_request, async_unary_stream_request
# Protocol import
import python_bindings.control_service_pb2_grpc as control_proto

class ControlServiceProxy(control_proto.ControlServicer):
    '''
    Proxy service to handle mission actuation requests and
    redirect them to the control server, while performing
    intermediate validation checks (ATC, permissions e.g.).
    Validation is typically performed via a gRPC interceptor.
    '''
    def __init__(self, stub, logger):
        self._stub = stub
        self._logger = logger
    
    async def Connect(self, request, context):
        return await async_unary_unary_request(
                self._stub.Connect,
                request,
                self._logger
                )

    async def IsConnected(self, request, context):
        return await async_unary_unary_request(
            self._stub.IsConnected,
            request,
            self._logger
            )

    async def Disconnect(self, request, context):
        return await async_unary_unary_request(
            self._stub.Disconnect,
            request,
            self._logger
            )

    async def Arm(self, request, context):
        return await async_unary_unary_request(
            self._stub.Arm,
            request,
            self._logger
            )
    
    async def TakeOff(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.TakeOff,
                request,
                self._logger
                ):
            yield response
        
    async def Land(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.Land,
                request,
                self._logger
                ):
            yield response

    async def Hold(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.Hold,
                request,
                self._logger
                ):
            yield response

    async def Kill(self, request, context):
         return await async_unary_unary_request(
                 self._stub.Kill,
                 request,
                 self._logger
                 )
    
    async def SetHome(self, request, context):
         return await async_unary_unary_request(
                 self._stub.SetHome,
                 request,
                 self._logger
                 )
    
    async def ReturnToHome(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.ReturnToHome,
                request,
                self._logger
                ):
            yield response
    
    async def SetGlobalPosition(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.SetGlobalPosition,
                request,
                self._logger
                ):
            yield response
    
    async def SetRelativePosition(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.SetRelativePosition,
                request,
                self._logger
                ):
            yield response
    
    async def SetVelocity(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.SetVelocity,
                request,
                self._logger
                ):
            yield response
    
    async def SetHeading(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.SetHeading,
                request,
                self._logger
                ):
            yield response
    
    async def SetGimbalPose(self, request, context):
        async for response in async_unary_stream_request(
                self._stub.SetGimbalPose,
                request,
                self._logger
                ):
            yield response
    
    async def ConfigureImagingSensorStream(self, request, context):
         return await async_unary_unary_request(
                 self._stub.ConfigureImagingSensorStream,
                 request,
                 self._logger
                 )
    
    async def ConfigureTelemetryStream(self, request, context):
         return await async_unary_unary_request(
                 self._stub.ConfigureTelemetryStream,
                 request,
                 self._logger
                 )
