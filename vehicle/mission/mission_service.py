from bindings.python.services.mission_service_pb2_grpc import MissionServicer
from bindings.python.services import mission_service_pb2 as mission_proto

from util.rpc import generate_response
from util.log import get_logger

class MissionService(MIssionServicer):
    def __init__(self, socket, stubs)
        self.stubs = stubs
        self.mission = None
    def _load(url):
        pass
    
    def _unzip():
        pass


    async def Upload(self, request, context):
        """Upload a mission for execution
        """
        logger.info("upload mission from Swarm Controller")
        logge.proto(request)
        return mission_proto.Upload(response=generate_response(2))        

    async def Start(self, request, context):
        """Start an uploaded mission
        """
        await self.mssion.run()
        return mission_proto.Upload(response=generate_response(2))

    def Stop(self, request, context):
        """Stop the current mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Notify(self, request, context):
        """Send a notification to the current mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureTelemetryStream(self, request, context):
        """Set the mission telemetry stream parameters
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_MissionServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Upload': grpc.unary_unary_rpc_method_handler(
                    servicer.Upload,
                    request_deserializer=services_dot_mission__service__pb2.UploadRequest.FromString,
                    response_serializer=services_dot_mission__service__pb2.UploadResponse.SerializeToString,
            ),
            'Start': grpc.unary_unary_rpc_method_handler(
                    servicer.Start,
                    request_deserializer=services_dot_mission__service__pb2.StartRequest.FromString,
                    response_serializer=services_dot_mission__service__pb2.StartResponse.SerializeToString,
            ),
            'Stop': grpc.unary_unary_rpc_method_handler(
                    servicer.Stop,
                    request_deserializer=services_dot_mission__service__pb2.StopRequest.FromString,
                    response_serializer=services_dot_mission__service__pb2.StopResponse.SerializeToString,
            ),
            'Notify': grpc.unary_unary_rpc_method_handler(
                    servicer.Notify,
                    request_deserializer=services_dot_mission__service__pb2.NotifyRequest.FromString,
                    response_serializer=services_dot_mission__service__pb2.NotifyResponse.SerializeToString,
            ),
            'ConfigureTelemetryStream': grpc.unary_unary_rpc_method_handler(
                    servicer.ConfigureTelemetryStream,
                    request_deserializer=services_dot_mission__service__pb2.ConfigureTelemetryStreamRequest.FromString,
                    response_serializer=services_dot_mission__service__pb2.ConfigureTelemetryStreamResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'protocol.services.mission_service.Mission', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


