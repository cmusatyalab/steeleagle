# Utility import
from util.rpc import unary_unary_request, unary_stream_request
# Protocol import
import python_bindings.driver_service_pb2_grpc as driver_proto

class ControlProxyService(driver_proto.DriverServicer):
    '''
    Proxy service to handle mission actuation requests and
    redirect them to the drone server, while performing
    intermediate validation checks (ATC, permissions e.g.).
    Validation is typically performed via a gRPC interceptor.
    '''
    def __init__(self, stub, logger):
        self._stub = stub
        self._logger = logger
    
    async def Connect(self, request, context):
         return unary_unary_request(
                 self._stub.Connect,
                 request,
                 self._logger
                 )

   async def IsConnected(self, request, context):
         return unary_unary_request(
                 self._stub.Connect,
                 request,
                 self._logger
                 )

   async def Disconnect(self, request, context):
         return unary_unary_request(
                 self._stub.Disconnect,
                 request,
                 self._logger
                 )

   async def Arm(self, request, context):
         return unary_unary_request(
                 self._stub.Arm,
                 request,
                 self._logger
                 )
    
    async def SpinUp(self, request, context):
        async for response in unary_stream_request(
                self._stub.SpinUp,
                request,
                self._logger
                ):
            yield response
        
    async def SpinDown(self, request, context):
        async for response in unary_stream_request(
                self._stub.SpinDown,
                request,
                self._logger
                ):
            yield response

    async def Hold(self, request, context):
        async for response in unary_stream_request(
                self._stub.Hold,
                request,
                self._logger
                ):
            yield response

    async def Kill(self, request, context):
         return unary_unary_request(
                 self._stub.Kill,
                 request,
                 self._logger
                 )
    
    async def SetHome(self, request, context):
         return unary_unary_request(
                 self._stub.SetHome,
                 request,
                 self._logger
                 )
    
    async def ReturnToHome(self, request, context):
        async for response in unary_stream_request(
                self._stub.ReturnToHome,
                request,
                self._logger
                ):
            yield response
    
    async def SetGlobalPosition(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetGlobalPosition,
                request,
                self._logger
                ):
            yield response
    
    async def SetRelativePositionENU(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetRelativePositionENU,
                request,
                self._logger
                ):
            yield response
    
    async def SetRelativePositionBody(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetRelativePositionBody,
                request,
                self._logger
                ):
            yield response
    
    async def SetVelocityENU(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetVelocityENU,
                request,
                self._logger
                ):
            yield response
    
    async def SetVelocityBody(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetVelocityBody,
                request,
                self._logger
                ):
            yield response
    
    async def SetHeading(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetHeading,
                request,
                self._logger
                ):
            yield response
    
    async def SetGimbalPoseENU(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetGimbalPoseENU,
                request,
                self._logger
                ):
            yield response
    
    async def SetGimbalPoseBody(self, request, context):
        async for response in unary_stream_request(
                self._stub.SetGimbalPoseBody,
                request,
                self._logger
                ):
            yield response
    
    async def ConfigureImagingSensorStream(self, request, context):
         return unary_unary_request(
                 self._stub.ConfigureImagingSensorStream,
                 request,
                 self._logger
                 )
    
    async def ConfigureTelemetryStream(self, request, context):
         return unary_unary_request(
                 self._stub.ConfigureTelemetryStream,
                 request,
                 self._logger
                 )
