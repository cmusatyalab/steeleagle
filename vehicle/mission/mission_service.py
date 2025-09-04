from bindings.python.services.mission_service_pb2_grpc import MissionServicer
from bindings.python.services import mission_service_pb2 as mission_proto

from util.rpc import generate_response
from util.log import get_logger

class MissionService(MIssionServicer):
    def __init__(self, socket, stubs, mission_dir)
        self.stubs = stubs
        self.mission = None
        self.mission_dir = mission_dir
    
    def _load(url):
        # fetch and unzip
        resp = requests.get(uri)
        resp.raise_for_status()  # error if download failed
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            z.extractall(self.mission_dir) 
        
        # load mission
        from dsl.compiler.ir import MissionIR        
        with open("mission.json") as f:
            data = json.load(f)
            mission_ir = MissionIR(**data)

        return mission_ir

    async def Upload(self, request, context):
        """Upload a mission for execution
        """
        logger.info("upload mission from Swarm Controller")
        logger.proto(request)
        mission_url = request.misson.uri
        mission_ir = self._load(mission_url)
        from dsl.runtime.fsm import MissionFSM
        self.mission = MissionFSM(mission_ir)
        return mission_proto.Upload(response=generate_response(2))        

    async def Start(self, request, context):
        """Start an uploaded mission
        """
        await self.mssion.run()
        return mission_proto.Start(response=generate_response(2))

    async def Stop(self, request, context):
        """Stop the current mission
        """
        await self.mission.stop()
        return mission_proto.Stop(response=generate_response(2))

    async def Notify(self, request, context):
        """Send a notification to the current mission
        """
        pass

    async def ConfigureTelemetryStream(self, request, context):
        """Set the mission telemetry stream parameters
        """
        pass


