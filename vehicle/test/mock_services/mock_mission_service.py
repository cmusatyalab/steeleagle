# Utility import
from util.rpc import generate_response
# Protocol import
from python_bindings import common_pb2 as common_proto
from python_bindings import telemetry_pb2 as telemetry_proto
from python_bindings import mission_service_pb2 as mission_proto
from python_bindings.mission_service_pb2_grpc import MissionServicer
# Test import
from test.grpc_test import sequence_params

class MockMissionService(MissionServicer):
    '''
    Provides a fake mission service for testing gRPC plumbing.
    '''
    def __init__(self, sequencer):
        self.sequencer
    
    @sequence_params
    async def Upload(self, request, context):
        return mission_proto.UploadResponse(
                response=generate_response(2)
                )

    @sequence_params
    async def Start(self, request, context):
        return mission_proto.StartResponse(
                response=generate_response(2)
                )
    
    @sequence_params
    async def Stop(self, request, context):
        return mission_proto.StopResponse(
                response=generate_response(2)
                )
    
    @sequence_params
    async def Notify(self, request, context):
        return mission_proto.NotifyResponse(
                response=generate_response(2)
                )
    
    @sequence_params
    async def ConfigureTelemetryStream(self, request, context):
        return mission_proto.ConfigureTelemetryStreamResponse(
                response=generate_response(2)
                )
