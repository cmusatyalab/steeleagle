# General import
import logging

# Streaming imports
# Protocol imports
import common_pb2 as common_protocol

# Interface import
from multicopter.autopilots.ardupilot import ArduPilotDrone

logger = logging.getLogger(__name__)


class Spirit(ArduPilotDrone):
    def __init__(self, drone_id, **drone_args):
        super().__init__(drone_id)

    """ Interface Methods """

    async def get_type(self):
        return "Ascent AeroSytems Spirit"

    async def set_gimbal_pose(self, pose):
        return common_protocol.ResponseStatus.NOTSUPPORTED
