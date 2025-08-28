# General imports
import logging
from enum import Enum

# Protocol imports
import common_pb2 as common_protocol

# Interface import
from multicopter.autopilots.mavlink import MAVLinkDrone

# SDK import (MAVLink)
from pymavlink import mavutil

logger = logging.getLogger(__name__)


class ArduPilotDrone(MAVLinkDrone):
    class FlightMode(Enum):
        LAND = "LAND"
        RTL = "RTL"
        LOITER = "LOITER"
        GUIDED = "GUIDED"
        ALT_HOLD = "ALT_HOLD"

    def __init__(self, drone_id):
        self.drone_id = drone_id
        self.vehicle = None
        self.mode = None
        self._mode_mapping = None
        self._listener_task = None
        self._rel_altitude = 3

    """Interface Methods"""

    async def take_off(self):
        if not await self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED

        if not await self._arm():
            return common_protocol.ResponseStatus.FAILED

        gps = self._get_global_position()
        rel_altitude = self._rel_altitude
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            rel_altitude,
        )

        result = await self._wait_for_condition(
            lambda: self._is_rel_altitude_reached(rel_altitude),
            interval=1,
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def hover(self):
        # TODO: Implement hover:
        # issues: The hover command in the mavlink by setting velocity body to 0 will
        # interrupt any other flying command like land, takeoff, etc. This is due to
        # streamlit continuously sending the hover command in a high frequency.
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_global_position(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        bearing = location.heading
        alt_mode = location.altitude_mode
        hdg_mode = location.heading_mode
        max_velocity = location.max_velocity

        if alt_mode == common_protocol.LocationAltitudeMode.ABSOLUTE:
            altitude = alt
        else:
            altitude = self._get_global_position()["absolute_altitude"] + alt

        if not await self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED

        self.vehicle.mav.set_position_target_global_int_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
            0b100111111000,
            int(lat * 1e7),
            int(lon * 1e7),
            altitude,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )

        result = await self._wait_for_condition(
            lambda: self._is_at_target(lat, lon), timeout=60, interval=1
        )

        await self.set_heading(location)

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_velocity_global(self, velocity_global):
        north_vel = velocity_global.north_vel
        east_vel = velocity_global.east_vel
        up_vel = velocity_global.up_vel
        angular_vel = velocity_global.angular_vel

        if not await self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED

        self.vehicle.mav.set_position_target_local_ned_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b010111000111,
            0,
            0,
            0,
            north_vel,
            east_vel,
            -up_vel,
            0,
            0,
            0,
            float("nan"),
            angular_vel,
        )

        return common_protocol.ResponseStatus.COMPLETED

    async def set_velocity_body(self, velocity_body):
        forward_vel = velocity_body.forward_vel
        right_vel = velocity_body.right_vel
        up_vel = velocity_body.up_vel
        angular_vel = velocity_body.angular_vel

        if not await self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED

        self.vehicle.mav.set_position_target_local_ned_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b010111000111,
            0,
            0,
            0,
            forward_vel,
            right_vel,
            -up_vel,
            0,
            0,
            0,
            float("nan"),
            angular_vel,
        )

        return common_protocol.ResponseStatus.COMPLETED

    async def set_heading(self, location):
        if not await self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED
        lat = location.latitude
        lon = location.longitude
        heading = location.heading
        logger.info(f"Set heading to {lat=}, {lon=}, {heading=}")
        # Calculate heading if not provided
        if heading is None:
            current_location = self._get_global_position()
            current_lat = current_location["latitude"]
            current_lon = current_location["longitude"]
            heading = self._calculate_heading(current_lat, current_lon, lat, lon)

        yaw_speed = 20
        direction = 0
        relative_flag = 0
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            0,  # Confirmation
            heading,  # param1: Yaw angle
            yaw_speed,  # param2: Yaw speed in deg/s
            direction,  # param3: -1=CCW, 1=CW, 0=fastest (only for absolute yaw)
            relative_flag,  # param4: 0=Absolute, 1=Relative
            0,
            0,
            0,  # param5, param6, param7 (Unused)
        )

        result = await self._wait_for_condition(
            lambda: self._is_heading_reached(heading), timeout=30, interval=0.5
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED
