# General import
import asyncio
import logging

# Streaming imports
# Protocol imports
import common_pb2 as common_protocol

# Interface import
from multicopter.autopilots.ardupilot import ArduPilotDrone

# SDK import (MAVLink)
from pymavlink import mavutil

logger = logging.getLogger(__name__)


class Spirit(ArduPilotDrone):
    # default multicopter mappings
    mode_mapping_acm = {
        "STABILIZE": 0,
        "ACRO": 1,
        "ALT_HOLD": 2,
        "AUTO": 3,
        "GUIDED": 4,
        "LOITER": 5,
        "RTL": 6,
        "CIRCLE": 7,
        "POSITION": 8,
        "LAND": 9,
        "OF_LOITER": 10,
        "DRIFT": 11,
        "SPORT": 13,
        "FLIP": 14,
        "AUTOTUNE": 15,
        "POSHOLD": 16,
        "BRAKE": 17,
        "THROW": 18,
        "AVOID_ADSB": 19,
        "GUIDED_NOGPS": 20,
        "SMART_RTL": 21,
        "FLOWHOLD": 22,
        "FOLLOW": 23,
        "ZIGZAG": 24,
        "SYSTEMID": 25,
        "AUTOROTATE": 26,
        "AUTO_RTL": 27,
    }

    def __init__(self, drone_id, **drone_args):
        super().__init__(drone_id)

    """ Interface Methods """

    async def get_type(self):
        return "Ascent AeroSytems Spirit"

    async def set_gimbal_pose(self, pose):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def connect(self, connection_string):
        # Connect to drone
        self.vehicle = mavutil.mavlink_connection(connection_string)
        # Wait to connect until we have a mode mapping
        while self._mode_mapping is None:
            self.vehicle.wait_heartbeat()
            self._mode_mapping = self.vehicle.mode_mapping()
            await asyncio.sleep(0.1)

        # override the mode mapping because the mav_type is not reported properly
        # and we end up getting the mappings for a fixed wing
        self._mode_mapping = self.mode_mapping_acm
        # Register telemetry streams
        await self._register_telemetry_streams()
        asyncio.create_task(self._message_listener())
        return True
