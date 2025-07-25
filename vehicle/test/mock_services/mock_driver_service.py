# Utility import
from util.rpc import generate_response
# Protocol import
from python_bindings import common_pb2 as common_proto
from python_bindings import telemetry_pb2 as telemetry_proto
from python_bindings import driver_service_pb2 as driver_proto
from python_bindings.driver_service_pb2_grpc import DriverServicer
# Test import
from message_sequencer import sequence_params

class MockDriverService(DriverServicer):
    '''
    Provides a fake drone driver service for testing gRPC plumbing.
    '''
    
    # The number of IN_PROGRESS replies sent for each of the
    # streaming functions
    IN_PROGRESS_COUNT = 3
    # Time to sleep between IN_PROGRESS replies
    SLEEP_TIME = 0.5
    
    def __init__(self, sequencer):
        self.sequencer = sequencer

    @sequence_params
    async def Connect(self, request, context):
        return driver_proto.ConnectResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def IsConnected(self, request, context):
        return driver_proto.IsConnectedResponse(
                response=generate_response(2),
                is_connected=self._connected
                )

    @sequence_params
    async def Disconnect(self, request, context):
        return driver_proto.DisconnectResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def Arm(self, request, context):
        return driver_proto.ArmResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def Disarm(self, request, context):
        return driver_proto.DisarmResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def TakeOff(self, request, context):
        yield driver_proto.TakeOffResponse(
                response=generate_response(0)
                )

        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.TakeOffResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)

        yield driver_proto.TakeOffResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def Land(self, request, context):
        yield driver_proto.LandResponse(
                response=generate_response(0)
                )

        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.LandResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)
        
        yield driver_proto.LandResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def Hold(self, request, context):
        yield driver_proto.HoldResponse(
                response=generate_response(0)
                )

        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.HoldResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)
        
        yield driver_proto.HoldResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def Kill(self, request, context):
        return driver_proto.KillResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def SetHome(self, request, context):
        return driver_proto.SetHomeResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def ReturnToHome(self, request, context):
        yield driver_proto.ReturnToHomeResponse(
                response=generate_response(0)
                )

        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.ReturnToHomeResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)

        yield driver_proto.ReturnToHomeResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def SetGlobalPosition(self, request, context):
        yield driver_proto.SetGlobalPositionResponse(
                response=generate_response(0)
                )

        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.SetGlobalPositionResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)
        
        yield driver_proto.SetGlobalPositionResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def SetRelativePosition(self, request, context):
        yield driver_proto.SetRelativePositionResponse(
                response=generate_response(0)
                )
        
        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.SetRelativePositionResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)

        yield driver_proto.SetRelativePositionResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def SetVelocity(self, request, context):
        yield driver_proto.SetVelocityResponse(
                response=generate_response(0)
                )
        
        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.SetVelocityResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)

        yield driver_proto.SetVelocityResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def SetHeading(self, request, context):
        yield driver_proto.SetHeadingResponse(
                response=generate_response(0)
                )

        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.SetHeadingResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)

        yield driver_proto.SetHeadingResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def SetGimbalPose(self, request, context):
        yield driver_proto.SetGimbalPoseResponse(
                response=generate_response(0)
                )

        for i in range(MockDriver.IN_PROGRESS_COUNT):
            yield driver_proto.SetGimbalPoseResponse(
                    response=generate_response(1)
                    )
            await asyncio.sleep(MockDriver.SLEEP_TIME)

        yield driver_proto.SetGimbalPoseResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def ConfigureImagingSensorStream(self, request, context):
        yield driver_proto.ConfigureImagingSensorStreamResponse(
                response=generate_response(2)
                )
        
    @sequence_params
    async def ConfigureTelemetryStream(self, request, context):
        yield driver_proto.ConfigureTelemetryStreamResponse(
                response=generate_response(2)
                )
    
