import asyncio
import contextlib
import json
from typing import Optional
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionServicer
from steeleagle_sdk.protocol.rpc_helpers import generate_response
from steeleagle_sdk.dsl.compiler.ir import MissionIR
from steeleagle_sdk.dsl.runtime.fsm import MissionFSM
from steeleagle_sdk.dsl.runtime import VEHICLE, COMPUTE, MAP
from dacite import from_dict
import logging

logger = logging.getLogger(__name__)


class MissionService(MissionServicer):
    def __init__(self, stubs):
        logger.info("Mission Service initialized")
        self.stubs= stubs
        self.mission: Optional[MissionIR] = None
        self.mission_routine: Optional[asyncio.Task] = None
        self.mission_map = None

    def _load(self, mission_content):
        json_data = json.loads(mission_content)
        mission_ir = from_dict(MissionIR, json_data)
        return mission_ir
    
    async def Upload(self, request, context):
        """Upload a mission for execution"""
        logger.info("upload mission from Swarm Controller")
        mission_content = request.mission.content
        mission_ir = self._load(mission_content)
        self.mission = mission_ir
        self.mission_map = request.mission.map
        logger.info(f"Loaded mission and map")
        return generate_response(2, "Mission uploaded")

    async def _start(self):
        fsm = MissionFSM(self.mission)
        mission_routine = asyncio.create_task(fsm.run())
        return mission_routine

    async def Start(self, request, context):
        """Start an uploaded mission"""
        logger.info("Starting mission")
        if self.mission is None:
            return generate_response(3, "No mission uploaded")
        elif self.mission_routine is not None and not self.mission_routine.done():
            return generate_response(3, "Mission already running")
        else:
            VEHICLE = self.stubs.get("control")
            COMPUTE = self.stubs.get("compute")
            MAP = self.mission_map
            self.mission_routine = await self._start()
            return generate_response(2)

    async def _stop(self):
        if self.mission_routine and not self.mission_routine.done():
            self.mission_routine.cancel()
        if self.mission_routine:
            with contextlib.suppress(asyncio.CancelledError):
                await self.mission_routine

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


