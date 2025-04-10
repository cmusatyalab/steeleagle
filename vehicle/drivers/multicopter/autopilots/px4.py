# General imports
from enum import Enum
import math
import os
import time
import asyncio
import logging
# SDK import (MAVLink)
from pymavlink import mavutil
# Interface import
from multicopter.autopilots.mavlink import MAVLinkDrone
# Protocol imports
from protocol import dataplane_pb2 as data_protocol
from protocol import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class PX4Drone(MAVLinkDrone):

    class OffboardHeartbeatMode(Enum):
        VELOCITY = 'VELOCITY'
        RELATIVE = 'RELATIVE'
        GLOBAL = 'GLOBAL'
        
    def __init__(self, drone_id):
        super().__init__(drone_id)
        self.offboard_mode = PX4Drone.OffboardHeartbeatMode.VELOCITY
        self._setpoint = (0.0, 0.0, 0.0, 0.0)
        self._setpoint_task = None

    ''' Interface methods '''
    async def get_type(self):
        return "PX4 Drone"

    async def set_velocity(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        angular_vel = velocity.angular_vel
        
        # Switch to offboard mode
        if not await self._switch_mode(MAVLinkDrone.FlightMode.OFFBOARD):
            logger.error("Failed to set mode to OFFBOARD")
            return common_protocol.ResponseStatus.FAILED
        self.offboard_mode = \
                PX4Drone.OffboardHeartbeatMode.VELOCITY 
        if not self._setpoint_task:
            self._setpoint_task = \
                    asyncio.create_task(self._setpoint_heartbeat())
        self._setpoint = (forward_vel, right_vel, up_vel, angular_vel) 
    
        return common_protocol.ResponseStatus.COMPLETED

    async def set_global_position(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        bearing = location.bearing
       
        # Set heading to designated bearing
        await self.set_heading(location)
        
        # Switch to offboard mode
        if not await self._switch_mode(MAVLinkDrone.FlightMode.OFFBOARD):
            logger.error("Failed to set mode to OFFBOARD")
            return common_protocol.ResponseStatus.FAILED
        self.offboard_mode = \
                PX4Drone.OffboardHeartbeatMode.GLOBAL
        if not self._setpoint_task:
            self._setpoint_task = \
                    asyncio.create_task(self._setpoint_heartbeat())
        self._setpoint = (lat, lon, alt, bearing)
    
        result = await self._wait_for_condition(
            lambda: self._is_global_position_reached(lat, lon, alt, bearing),
            interval=1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_heading(self, location):
        lat = location.latitude
        lon = location.longitude
        bearing = location.bearing
       
        # Calculate bearing if not provided
        current_location = self._get_global_position()
        current_lat = current_location["latitude"]
        logger.info(f"current_lat: {current_lat}")
        current_lon = current_location["longitude"]
        if bearing is None:
            bearing = self._calculate_bearing(current_lat, current_lon, lat, lon)
            
        yaw_speed = 25 # Degrees/s

        # Switch to offboard mode
        if not await self._switch_mode(MAVLinkDrone.FlightMode.OFFBOARD):
            logger.error("Failed to set mode to OFFBOARD")
            return common_protocol.ResponseStatus.FAILED
        self.offboard_mode = \
                PX4Drone.OffboardHeartbeatMode.VELOCITY 
        if not self._setpoint_task:
            self._setpoint_task = \
                    asyncio.create_task(self._setpoint_heartbeat())
        self._setpoint = (0.0, 0.0, 0.0, yaw_speed) 
        
        result =  await self._wait_for_condition(
            lambda: self._is_bearing_reached(bearing),
            interval=0.2
        )
        
        if  result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    ''' Coroutine methods '''
    async def _setpoint_heartbeat(self):
        # Send frequent setpoints to keep the drone in offboard mode
        while True:
            if self.offboard_mode == PX4Drone.OffboardHeartbeatMode.VELOCITY:
                self.vehicle.mav.set_position_target_local_ned_send(
                    0,
                    self.vehicle.target_system,
                    self.vehicle.target_component,
                    mavutil.mavlink.MAV_FRAME_BODY_NED,
                    0b010111000111,
                    0, 0, 0,
                    self._setpoint[0], self._setpoint[1], -self._setpoint[2],
                    0, 0, 0,
                    0, math.radians(self._setpoint[3]) # Radians/s
                )
            elif self.offboard_mode == PX4Drone.OffboardHeartbeatMode.GLOBAL:
                self.vehicle.mav.set_position_target_global_int_send(
                    0,
                    self.vehicle.target_system,
                    self.vehicle.target_component,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
                    0b110111111000,
                    int(self._setpoint[0] * 1e7),
                    int(self._setpoint[1] * 1e7),
                    self._setpoint[2],
                    0, 0, 0,
                    0, 0, 0,
                    0, 0
                )

            await asyncio.sleep(0.05)
