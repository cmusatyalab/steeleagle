import asyncio
import json

from fastapi import logger
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionServicer
from steeleagle_sdk.protocol.rpc_helpers import generate_response
from steeleagle_sdk.dsl.compiler.ir import MissionIR
from steeleagle_sdk.dsl import execute_mission
from dacite import from_dict
import logging

logger = logging.getLogger(__name__)


class MissionService(MissionServicer):
    def __init__(self, stubs):
        logger.info("Mission Service initialized")
        self.mission = None
        self.mission_routine = None
        self.stubs= stubs

    def _load(self, mission_content):
        json_data = json.loads(mission_content)
        mission_ir = from_dict(MissionIR, json_data)
        logger.info(f"Loaded mission: {mission_ir}")
        return mission_ir

    async def Upload(self, request, context):
        """Upload a mission for execution"""
        logger.info("upload mission from Swarm Controller")
        mission_content = request.mission.content
        logger.info(f"Mission content: {mission_content}")
        mission_ir = self._load(mission_content)
        self.mission = mission_ir
        return generate_response(2, "Mission uploaded")

    async def Start(self, request, context):
        """Start an uploaded mission"""
        logger.info("Starting mission")
        if self.mission is None:
            return generate_response(1, "No mission uploaded")
        elif self.mission_routine is not None and not self.mission_routine.done():
            return generate_response(1, "Mission already running")
        else:
            control = self.stubs.get("control")
            compute = self.stubs.get("compute")
            report = self.stubs.get("report")
            self.mission_routine = asyncio.create_task(execute_mission(self.mission, control, compute, report))
            return generate_response(2)

    async def Stop(self, request, context):
        """Stop the current mission"""
        if self.mission is None:
            return generate_response(1, "No active mission")
        else:
            await self.mission.stop()
            await self.mission_routine
            return generate_response(2)

    async def Notify(self, request, context):
        """Send a notification to the current mission"""
        pass

    async def ConfigureTelemetryStream(self, request, context):
        """Set the mission telemetry stream parameters"""
        pass


