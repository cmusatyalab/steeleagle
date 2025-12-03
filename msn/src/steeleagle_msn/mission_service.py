import asyncio
import json
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionServicer
from steeleagle_sdk.protocol.rpc_helpers import generate_response
from steeleagle_sdk.dsl.compiler.ir import MissionIR
from .runtime import init as fsm_init
from .runtime import term as fsm_term
from dacite import from_dict
import logging
logger = logging.getLogger(__name__)

class MissionService(MissionServicer):
    def __init__(self, address: dict):
        logger.info("Mission Service initialized")
        self.mission: MissionIR = None
        self.mission_map = None
        self.address = address
        self.fsm = None
        self.fsm_routine: asyncio.Task = None

    def _load(self, mission_content):
        json_data = json.loads(mission_content)
        mission_ir = from_dict(MissionIR, json_data)
        return mission_ir
    
    async def Upload(self, request, context):
        """Upload a mission for execution"""
        logger.info("upload mission from Swarm Controller")
        mission_content = request.mission.content
        self.mission = self._load(mission_content)
        self.mission_map = request.mission.map
        logger.info(f"Loaded mission and map")
        return generate_response(2, "Mission uploaded")

    async def _start(self):
        vehicle_address = self.address.get("vehicle")
        tel_address = self.address.get("telemetry")
        results_address = self.address.get("results")
        map = self.mission_map
        await fsm_init(self.mission, vehicle_address, tel_address, results_address, map)

    async def Start(self, request, context):
        """Start an uploaded mission"""
        logger.info("Starting mission")
        if self.mission is None:
            return generate_response(3, "No mission uploaded")
        elif self.fsm_routine is not None and not self.fsm_routine.done():
            return generate_response(3, "Mission already running")
        else:
            await self._start()
            return generate_response(2)

    async def _stop(self):
        await fsm_term()

    async def Stop(self, request, context):
        """Stop the current mission"""
        if self.mission is None:
            return generate_response(3, "No active mission")
        else:
            await self._stop()
            logger.info("Mission stopped")
            return generate_response(2)
        

    async def Notify(self, request, context):
        """Send a notification to the current mission"""
        pass

    async def ConfigureTelemetryStream(self, request, context):
        """Set the mission telemetry stream parameters"""
        pass


