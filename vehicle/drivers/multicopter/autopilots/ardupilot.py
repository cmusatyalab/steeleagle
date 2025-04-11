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

class ArduPilotDrone(MAVLinkDrone):
    
    class FlightMode(Enum):
        LAND = 'LAND'
        RTL = 'RTL'
        LOITER = 'LOITER'
        GUIDED = 'GUIDED'
        ALT_HOLD = 'ALT_HOLD'
        
    def __init__(self, drone_id):
        self.drone_id = drone_id
        self.vehicle = None
        self.mode = None
        self._mode_mapping = None
        self._listener_task = None

    '''Interface Methods'''
    async def set_global_position(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.absolute_altitude
        rel_alt = location.relative_altitude
        
        if not await \
                self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED
        
        # TODO: Check if absolute alt isn't set then use rel_alt instead!
        self.vehicle.mav.set_position_target_global_int_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
            0b0000111111111000,
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )
        
        result = await self._wait_for_condition(
            lambda: self._is_at_target(lat, lon),
            timeout=60,
            interval=1
        )
        
        await self.set_heading(location)
        
        if result:  
            return common_protocol.ResponseStatus.COMPLETED
        else:  
            return common_protocol.ResponseStatus.FAILED

    async def set_velocity_global(self, velocity):
        north_vel = velocity_global.north_vel
        east_vel = velocity_global.east_vel
        up_vel = velocity_global.up_vel
        angular_vel = velocity_global.angular_vel

        if not await \
                self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED
        
        self.vehicle.mav.set_position_target_local_ned_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b010111000111,
            0, 0, 0,
            north_vel, east_vel, -up_vel,
            0, 0, 0,
            float('nan'), angular_vel
        )
        
        return common_protocol.ResponseStatus.COMPLETED
    
    async def set_velocity_body(self, velocity):
        forward_vel = velocity_body.forward_vel
        right_vel = velocity_body.right_vel
        up_vel = velocity_body.up_vel
        angular_vel = velocity_body.angular_vel

        if not await \
                self._switch_mode(MAVLinkDrone.FlightMode.GUIDED):
            return common_protocol.ResponseStatus.FAILED
        
        self.vehicle.mav.set_position_target_local_ned_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b010111000111,
            0, 0, 0,
            forward_vel, right_vel, -up_vel,
            0, 0, 0,
            float('nan'), angular_vel
        )
        
        return common_protocol.ResponseStatus.COMPLETED

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
        direction = 0
        
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            0,
            bearing,
            yaw_speed,
            direction,
            0,
            0, 0, 0
        )
        
        result =  await self._wait_for_condition(
            lambda: self._is_bearing_reached(bearing),
            interval=0.5
        )
        
        if  result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED
