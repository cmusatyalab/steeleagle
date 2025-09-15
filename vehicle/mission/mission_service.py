import asyncio
import json
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionServicer
from steeleagle_sdk.protocol.services import mission_service_pb2 as mission_proto

from util.rpc import generate_response
from util.log import get_logger

from dsl.compiler.ir import MissionIR
from dsl.runtime.fsm import MissionFSM

import logging

logger = logging.getLogger(__name__)


class MissionService(MissionServicer):
    def __init__(self, stubs, mission_dir):
        self.mission = None
        self.mission_routine = None
        CONTROL_STUB = stubs.get("control")
        COMPUTE_STUB = stubs.get("compute")
        REPORT_STUB = stubs.get("report")

    def _load(mission_content):
        json_data = json.loads(mission_content)
        mission_ir = MissionIR(**json_data)
        return mission_ir

    async def Upload(self, request, context):
        """Upload a mission for execution"""
        logger.info("upload mission from Swarm Controller")
        logger.proto(request)
        mission_content = request.mission.content
        mission_ir = self._load(mission_content)
        self.mission = MissionFSM(mission_ir)
        return mission_proto.Upload(response=generate_response(2))        

    async def Start(self, request, context):
        """Start an uploaded mission"""
        if self.mission is None:
            return mission_proto.Start(response=generate_response(1, "No mission uploaded"))
        elif self.mission_routine is not None and not self.mission_routine.done():
            return mission_proto.Start(response=generate_response(1, "Mission already running"))
        else:
            self.mission_routine = asyncio.create_task(self.mission.run())
            return mission_proto.Start(response=generate_response(2))

    async def Stop(self, request, context):
        """Stop the current mission"""
        if self.mission is None:
            return mission_proto.Stop(response=generate_response(1, "No active mission"))
        else:
            await self.mission.stop()
            await self.mission_routine
            return mission_proto.Stop(response=generate_response(2))

    async def Notify(self, request, context):
        """Send a notification to the current mission"""
        pass

    async def ConfigureTelemetryStream(self, request, context):
        """Set the mission telemetry stream parameters"""
        pass


