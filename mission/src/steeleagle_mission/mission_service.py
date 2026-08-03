import json
import logging

from dacite import from_dict
from steeleagle_sdk.dsl.compiler.ir import MissionIR
from steeleagle_sdk.protocol.rpc_helpers import generate_response
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionServicer

from .runtime import init as fsm_init
from .runtime import is_running as fsm_is_running
from .runtime import term as fsm_stop

logger = logging.getLogger(__name__)


class MissionService(MissionServicer):
    def __init__(self, name, address: dict):
        logger.info("Mission Service initialized")
        self.mission: MissionIR = None
        self.mission_map = None
        self.address = address
        self.name = name

    def _load(self, mission_content):
        json_data = json.loads(mission_content)
        mission_ir = from_dict(MissionIR, json_data)
        return mission_ir

    async def Upload(self, request, context):
        """Upload a mission for execution.
        Rejected while a mission is running
        """
        logger.info("upload mission from Swarm Controller")
        if fsm_is_running():
            msg = "Cannot upload while a mission is running; stop it first"
            logger.info(msg)
            return generate_response(3, msg)
        mission_content = request.mission.content
        self.mission = self._load(mission_content)
        self.mission_map = request.mission.map
        logger.info("Loaded mission and map")
        return generate_response(2, "Mission uploaded")

    async def _start(self) -> bool:
        vehicle_address = self.address.get("vehicle")
        tel_address = self.address.get("telemetry")
        results_address = self.address.get("results")
        map = self.mission_map
        return await fsm_init(
            self.name,
            self.mission,
            vehicle_address,
            tel_address,
            results_address,
            map,
        )

    async def Start(self, request, context):
        """Start an uploaded mission"""
        logger.info("Starting mission")
        if self.mission is None:
            msg = "No mission uploaded"
            logger.info(msg)
            return generate_response(3, msg)
        if not await self._start():
            msg = "Mission already running"
            logger.info(msg)
            return generate_response(3, msg)
        return generate_response(2)

    async def _stop(self):
        await fsm_stop()

    async def Stop(self, request, context):
        """Stop the current mission"""
        if self.mission is None:
            return generate_response(3, "No active mission")
        else:
            await self._stop()
            logger.info("Mission stopped")
            return generate_response(2)

