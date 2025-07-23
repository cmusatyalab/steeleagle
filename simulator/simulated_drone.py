import asyncio
import logging
import math
import os
import numpy as np

import protocol.common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class SimulatedDrone():
    def __init__(self, ip):
        self._device_type = "Anafi Perfect"
        self.connection_ip = ip
        self._active_connection = False
        self._current_flight_state = "landed"
        self._state = {}

        # run event loop for state maintenance
    
    def connect(self):
        if self._active_connection == False:
            self._active_connection = True
            logger.info("Connection established with simulated digital drone")
        else:
            logger.warning("Attempted multiple connections on simulated drone object")

    def connection_state(self):
        return self._active_connection
    
    def disconnect(self):
        if self._active_connection:
            self._active_connection = False
            logger.info("Disconnected from simulated digital drone")
        else:
            logger.warning("Attempted to disconnect without active connection to simulated drone")
    
    def take_off(self):
        pass

    def land(self):
        pass

    def move_to(self, lat, lon, altitude, heading_mode, bearing):
        pass

    def extended_move_to(self, lat, lon, altitude, heading_mode, bearing, lateral_vel, up_vel, angular_vel):
        pass

    def set_target(self, gimbal_id, control_mode, yaw, pitch, roll):
        # based on angular velocity?
        pass

    def set_home_location(self, lat, lon, alt):
        self.home_location = {
            "lat": lat,
            "lon": lon,
            "alt": alt
        }
        logger.info(f"Home location updated to ({lon}, {lat}) at elevation {alt}")

    def _update_state(self, characteristic: str, value):
        if characteristic not in self._state:
            logger.info(f"Adding {characteristic} to internal state")
        self._state[characteristic] = value

    """ ACK methods """

    def check_flight_state(self, target_state: str):
        if target_state == self._current_flight_state:
            return True
        return False
    
    def get_current_position(self):
        try:
            return (
                self.current_position["lat"],
                self.current_position["lon"],
                self.current_position["alt"]
            )
        except:
            logger.error("Unable to retrieve current position")
            return None

    def get_home_location(self):
        try:
            return (
                self.home_location["lat"],
                self.home_location["lon"],
                self.home_location["alt"]
            )
        except:
            logger.error("Home location not set")
            return None
        
    def get_state(self, characteristic: str):
        if characteristic not in self._state:
            logger.error(f"{characteristic} not included in drone state. Unable to retrieve")
            return None
        return self._state[characteristic]
        
    """ Internal State Methods """

    def set_attitude(self, roll: float, pitch: float, yaw: float):
        attitude = {
            "pitch": pitch,
            "roll": roll,
            "yaw": yaw
        }
        self._update_state("attitude", attitude)
    
    def set_battery_percent(self, starting_charge: int):
        self._update_state("battery_percent", starting_charge)

    def set_current_position(self, lat: float, lon: float, alt: float):
        self.current_position = {
            "lat": lat,
            "lon": lon,
            "alt": alt
        }

    def set_flight_state(self, flight_state: common_protocol.FlightStatus):
        self._update_state("flight_state", flight_state)

    def set_gimbal_pose(self, pitch: float, roll: float, yaw: float):
        gimbal_pose = {
            "g_pitch": pitch,
            "g_roll": roll,
            "g_yaw": yaw
        }
        self._update_state("gimbal_pose", gimbal_pose)

    def set_magnetometer(self, condition_code: int):
        # 0 for good, 1 for calibration, 2 for perturbation
        self._update_state("magnetometer", condition_code)

    def set_name(self, drone_id: str):
        self._update_state("drone_id", drone_id)

    def set_velocity(self, vel_x: float, vel_y: float, vel_z: float):
        velocity = {
            "speedX": vel_x,
            "speedY": vel_y,
            "speedZ": vel_z
        }
        self._update_state("velocity", velocity)
    
    def set_satellites(self, satellite_count: int):
        self._update_state("satellite_count", satellite_count)
    

    