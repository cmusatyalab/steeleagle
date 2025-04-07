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
from quadcopter.quadcopter_interface import QuadcopterItf
# Protocol imports
from protocol import dataplane_pb2 as data_protocol
from protocol import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class PX4Drone(QuadcopterItf):
    
    class FlightMode(Enum):
        LAND = 'LAND'
        RTL = 'RTL'
        LOITER = 'LOITER'
        TAKEOFF = 'TAKEOFF'
        ALT_HOLD = 'ALT_HOLD'
        OFFBOARD = 'OFFBOARD'

    class OffboardHeartbeatMode(Enum):
        VELOCITY = 'VELOCITY'
        RELATIVE = 'RELATIVE'
        GLOBAL = 'GLOBAL'
        
    def __init__(self, drone_id):
        self.drone_id = drone_id
        self.vehicle = None
        self.mode = None
        self.offboard_mode = PX4Drone.OffboardHeartbeatMode.VELOCITY
        self._mode_mapping = None
        self._listener_task = None
        self._setpoint = (0.0, 0.0, 0.0, 0.0)
        self._setpoint_task = None

    ''' Interface methods '''
    async def get_type(self):
        return "PX4 Drone"

    async def connect(self, connection_string):
        # Connect to drone
        self.vehicle = mavutil.mavlink_connection(connection_string)
        self.vehicle.wait_heartbeat()
        self._mode_mapping = self.vehicle.mode_mapping()
        
        # Register telemetry streams
        await self.register_telemetry_streams()
        asyncio.create_task(self._message_listener())
        
    async def is_connected(self):
        return self.vehicle is not None

    async def disconnect(self):
        if self._listener_task:
            self._listener_task.cancel()
            await asyncio.sleep(0.1)

        if self.vehicle:
            self.vehicle.close()
    
    async def take_off(self):
        target_altitude = 3
        await self._arm()
        await self._switch_mode(PX4Drone.FlightMode.TAKEOFF)
        
        gps = self._get_global_position()
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0, gps['latitude'], gps['longitude'], gps['altitude'] + target_altitude)
       
        result = await self._wait_for_condition(
            lambda: self._is_mode_set(PX4Drone.FlightMode.LOITER),
            interval=1
        )

        self._setpoint_task = asyncio.create_task(self._setpoint_heartbeat())

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def land(self):
        await self._switch_mode(PX4Drone.FlightMode.LAND)

        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0, 0, 0, 0, 0, 0, 0, 0)

        result = await self._wait_for_condition(
            lambda: self._is_disarmed(),
            interval=1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def hover(self):
        velocity = common_protocol.Velocity()
        velocity.forward_vel = 0.0
        velocity.right_vel = 0.0
        velocity.up_vel = 0.0
        velocity.angular_vel = 0.0
        return await self.set_velocity(velocity)

    async def kill(self):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_home(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_HOME,
            1,
            0, 0, 0, 0,
            lat, lng, alt
        )

        result = await self._wait_for_condition(
            lambda: self.is_home_set(),
            timeout=5,
            interval=0.1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED
    
    async def rth(self):
        if not await \
                self._switch_mode(PX4Drone.FlightMode.RTL):
            return

        result = await self._wait_for_condition(
            lambda: self._is_disarmed(),
            interval=1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED
            
    async def set_velocity(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        angular_vel = velocity.angular_vel
        self.offboard_mode = \
                PX4Drone.OffboardHeartbeatMode.VELOCITY 
        if not self._setpoint_task:
            self._setpoint_task = \
                    asyncio.create_task(self._setpoint_heartbeat())
        self._setpoint = (forward_vel, right_vel, up_vel, angular_vel) 
        
        return common_protocol.ResponseStatus.COMPLETED

    async def set_global_position(self, location):
        await self.set_bearing(location)
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        bearing = location.bearing
       
        self.offboard_mode = \
                PX4Drone.OffboardHeartbeatMode.GLOBAL
        if not self._setpoint_task:
            self._setpoint_task = \
                    asyncio.create_task(self._setpoint_heartbeat())
        self._setpoint = (lat, lon, alt, 0)

        result = await self._wait_for_condition(
            lambda: self.is_at_target(lat, lon),
            interval=1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_relative_position(self, position):
        pass
    
    async def set_heading(self, location):
        lat = location.latitude
        lon = location.longitude
        bearing = location.bearing
        # Calculate bearing if not provided
        current_location = self._get_global_position()
        current_lat = current_location["latitude"]
        current_lon = current_location["longitude"]
        if bearing is None:
            bearing = self.calculate_bearing(\
                    current_lat, current_lon, lat, lon)
        yaw_speed = 25
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
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_gimbal_pose(self):
        pass

    async def stream_telemetry(self, tel_sock):
        logger.info('Starting telemetry stream')
        # Wait a second to avoid contention issues
        await asyncio.sleep(1) 
        while await self.is_connected():
            try:
                tel_message = data_protocol.Telemetry()
                tel_message.drone_name = self._get_name()
                tel_message.battery = self._get_battery_percentage()
                tel_message.drone_attitude.pose.yaw = self._get_attitude()["yaw"]
                tel_message.drone_attitude.pose.pitch = \
                        self._get_attitude()["pitch"]
                tel_message.drone_attitude.pose.roll = \
                        self._get_attitude()["roll"]
                tel_message.satellites = self._get_satellites()
                tel_message.relative_position.up = self._get_altitude_rel()
                tel_message.global_position.latitude = \
                        self._get_global_position()["latitude"]
                tel_message.global_position.longitude = \
                        self._get_global_position()["longitude"]
                tel_message.global_position.altitude = \
                        self._get_global_position()["altitude"]
                tel_message.global_position.bearing = self._get_heading()
                tel_message.velocity.forward_vel = \
                        self._get_velocity_body()["forward"]
                tel_message.velocity.right_vel = \
                        self._get_velocity_body()["right"]
                tel_message.velocity.up_vel = \
                        self._get_velocity_body()["up"]
                tel_sock.send(tel_message.SerializeToString())
            except Exception as e:
                logger.error(f'Failed to get telemetry, error: {e}')
            await asyncio.sleep(0.01)
                    
    async def stream_video(self, cam_sock):
        return common_protocol.ResponseStatus.NOTSUPPORTED
    
    ''' Connect methods '''
    async def register_telemetry_streams(self, frequency_hz: float = 10.0):
        # Define the telemetry message names
        telemetry_message_names = [
            "HEARTBEAT",
            "GLOBAL_POSITION_INT",
            "ATTITUDE",
            "RAW_IMU",
            "BATTERY_STATUS",
            "GPS_RAW_INT",
            "VFR_HUD",
            "LOCAL_POSITION_NED",
            "RC_CHANNELS",
        ]

        logger.info(f"Registering telemetry streams at {frequency_hz} Hz...")
        for message_name in telemetry_message_names:
            try:
                message_id = getattr(mavutil.mavlink, f"MAVLINK_MSG_ID_{message_name}", None)
                if message_id is None:
                    logger.warning(f"Message name {message_name} is not found in MAVLink definitions.")
                    continue

                # Request the message interval
                self._request_message_interval(message_id, frequency_hz)
                logger.info(f"Registered telemetry stream: {message_name} (ID: {message_id})")

            except Exception as e:
                logger.error(f"Failed to register telemetry stream {message_name}: {e}")

    def _request_message_interval(self, message_id: int, frequency_hz: float):
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            message_id,
            1e6 / frequency_hz,
            0, 0, 0, 0,
            0, 
        )

    ''' Telemetry methods '''
    def _get_name(self):
        return self.drone_id

    def _get_global_position(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return {
            "latitude": gps_msg.lat / 1e7,
            "longitude": gps_msg.lon / 1e7,
            "altitude": gps_msg.alt / 1e3
        }

    def _get_altitude_rel(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return gps_msg.relative_alt / 1e3

    def _get_attitude(self):
        attitude_msg = self._get_cached_message("ATTITUDE")
        if not attitude_msg:
            return None
        return {
            "roll": attitude_msg.roll,
            "pitch": attitude_msg.pitch,
            "yaw": attitude_msg.yaw
        }

    def _get_magnetometer(self):
        imu_msg = self._get_cached_message("RAW_IMU")
        if not imu_msg:
            return {"x": None, "y": None, "z": None}
        return {
            "x": imu_msg.xmag,
            "y": imu_msg.ymag,
            "z": imu_msg.zmag
        }

    def _get_battery_percentage(self):
        battery_msg = self._get_cached_message("BATTERY_STATUS")
        if not battery_msg:
            return None
        return battery_msg.battery_remaining

    def _get_satellites(self):
        satellites_msg = self._get_cached_message("GPS_RAW_INT")
        if not satellites_msg:
            return None
        return satellites_msg.satellites_visible

    def _get_heading(self):
        heading_msg = self._get_cached_message("VFR_HUD")
        if not heading_msg:
            return None
        return heading_msg.heading

    def _get_velocity_neu(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return {
            "north": gps_msg.vx / 100,
            "east": gps_msg.vy / 100,
            "up": gps_msg.vz / 100
        }
        
    def _get_velocity_body(self):
        velocity_msg = self._get_cached_message("LOCAL_POSITION_NED")
        if not velocity_msg:
            return None
        return {
            "forward": velocity_msg.vx,  # Body-frame X velocity in m/s
            "right": velocity_msg.vy,  # Body-frame Y velocity in m/s
            "up": velocity_msg.vz   # Body-frame Z velocity in m/s
        }

    def _get_rssi(self):
        rssi_msg = self._get_cached_message("RC_CHANNELS")
        if not rssi_msg:
            return None
        return rssi_msg.rssi

    ''' Coroutine methods '''
    async def _setpoint_heartbeat(self):
        if await self._switch_mode(PX4Drone.FlightMode.OFFBOARD) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        # Send frequent setpoints to keep the drone in offboard mode.
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
                    0, self._setpoint[3]
                )
            elif self.offboard_mode == PX4Drone.OffboardHeartbeatMode.RELATIVE:
                pass
            elif self.offboard_mode == PX4Drone.OffboardHeartbeatMode.GLOBAL:
                self.vehicle.mav.set_position_target_global_int_send(
                    0,
                    self.vehicle.target_system,
                    self.vehicle.target_component,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    0b0000111111111000,
                    int(self._setpoint[0] * 1e7),
                    int(self._setpoint[1] * 1e7),
                    self._setpoint[2],
                    0, 0, 0,
                    0, 0, 0,
                    0, 0
                )
            await asyncio.sleep(0.05)

    ''' Actuation methods '''
    async def _arm(self):
        logger.info("-- Arming")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            0, 0, 0, 0, 0, 0
        )
        logger.info("-- Arm command sent")


        result =  await self._wait_for_condition(
            lambda: self._is_armed(),
            timeout=5,
            interval=1
        )
        
        if result:
            logger.info("-- Armed successfully")
        else:
            logger.error("-- Arm failed")
        return result

    async def _disarm(self):
        logger.info("-- Disarming")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,
            0, 0, 0, 0, 0, 0
        )
        logger.info("-- Disarm command sent")

        result =  await self._wait_for_condition(
            lambda: self._is_disarmed(),
            timeout=5,
            interval=1
        )
        
        if result:
            self.mode = None
            logger.info("-- Disarmed successfully")
        else:
            logger.error("-- Disarm failed")
            
        return result  

    async def _switch_mode(self, mode):
        mode_target = mode.value
        curr_mode = self.mode.value if self.mode else None
        
        if self.mode == mode:
            logger.info(f"Already in mode {mode_target}")
            return True
        
        # switch mode
        if mode_target not in self._mode_mapping:
            logger.info(f"Mode {mode_target} not supported!")
            return False
        
        mode_id = self._mode_mapping[mode_target]
        logger.info(f"Mode ID Triplet: {mode_id}")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
            mode_id[0], mode_id[1], mode_id[2], 0, 0, 0, 0)
        
        if mode is not PX4Drone.FlightMode.OFFBOARD:
            result = await self._wait_for_condition(
                lambda: self._is_mode_set(mode),
                timeout=5,
                interval=1
            )
            
            if result:
                self.mode = mode
                logger.info(f"Mode switched to {mode_target}")

            return result
        else:
            logger.info(f"Priming for OFFBOARD mode")
            return True
        
    ''' ACK methods'''    
    def _is_armed(self):
        return self.vehicle.recv_match(type="HEARTBEAT", blocking=True).base_mode & \
                mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
        
    def _is_disarmed(self):
        return not (self.vehicle.recv_match(type='HEARTBEAT', blocking=True).base_mode & \
                mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def _is_mode_set(self, mode):
        current_mode = mavutil.mode_string_v10(self.vehicle.recv_match(type='HEARTBEAT', blocking=True))
        return current_mode == mode.value
    
    def _is_home_set(self):
        msg = self.vehicle.recv_match(type='COMMAND_ACK', blocking=True)
        return msg and msg.command == mavutil.mavlink.MAV_CMD_DO_SET_HOME \
                and msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED

    def _is_altitude_reached(self, target_altitude):
        current_altitude = self._get_altitude_rel()
        return current_altitude >= target_altitude * 0.95
    
    def _is_bearing_reached(self, bearing):
        logger.info(f"Checking if bearing is reached: {bearing}")
        attitude = self._get_attitude()
        if not attitude:
            return False  # Return False if attitude data is unavailable

        current_yaw = (math.degrees(attitude["yaw"]) + 360) % 360
        target_yaw = (bearing + 360) % 360
        return abs(current_yaw - target_yaw) <= 2
    
    def _is_at_target(self, lat, lon):
        current_location = self._get_global_position()
        if not current_location:
            return False
        dlat = lat - current_location["latitude"]
        dlon = lon - current_location["longitude"]
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance < 1.0
        
    ''' Helper methods '''
    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        delta_lon = lon2 - lon1

        # Bearing calculation
        x = math.sin(delta_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
        
        initial_bearing = math.atan2(x, y)

        # Convert bearing from radians to degrees
        initial_bearing = math.degrees(initial_bearing)

        # Normalize to 0-360 degrees
        converted_bearing = (initial_bearing + 360) % 360

        return converted_bearing
        
    async def _message_listener(self):
        logger.info("-- Starting message listener")
        try:
            while True:
                msg = await asyncio.to_thread(self.vehicle.recv_match, blocking=True)
                if msg:
                    message_type = msg.get_type()
                    logger.debug(f"Received message type: {message_type}")
        except asyncio.CancelledError:
            logger.info("-- Message listener stopped")
        except Exception as e:
            logger.error(f"-- Error in message listener: {e}")
    
    def _get_cached_message(self, message_type):
        try:
            logger.debug(f"Currently connection message types: {list(self.vehicle.messages)}")
            return self.vehicle.messages[message_type]
        except KeyError:
            logger.error(f"Message type {message_type} not found in cache")
            return None
        
    async def _wait_for_condition(self, condition_fn, timeout=None, interval=0.5):
        start_time = time.time()
        while True:
            try:
                if condition_fn():
                    logger.info("-- Condition met")
                    return True
            except Exception as e:
                logger.error(f"-- Error evaluating condition: {e}")
            if timeout is not None and time.time() - start_time > timeout:
                logger.error("-- Timeout waiting for condition")
                return False
            await asyncio.sleep(interval)
