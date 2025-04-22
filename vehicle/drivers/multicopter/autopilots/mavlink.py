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
from multicopter.multicopter_interface import MulticopterItf
# Protocol imports
import dataplane_pb2 as data_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class MAVLinkDrone(MulticopterItf):

    class FlightMode(Enum):
        LAND = 'LAND'
        RTL = 'RTL'
        LOITER = 'LOITER'
        TAKEOFF = 'TAKEOFF'
        ALT_HOLD = 'ALT_HOLD'
        # These are the same mode but have different names
        # depending on the autopilot software
        OFFBOARD = 'OFFBOARD' # PX4
        GUIDED = 'GUIDED' # ArduPilot
    
    def __init__(self, drone_id):
        self.drone_id = drone_id
        self.vehicle = None
        self.mode = None
        self._mode_mapping = None
        self._listener_task = None

    ''' Interface methods '''
    async def get_type(self):
        return "MAVLink Drone"

    async def connect(self, connection_string):
        # Connect to drone
        self.vehicle = mavutil.mavlink_connection(connection_string)
        # Wait to connect until we have a mode mapping
        while self._mode_mapping is None:
            self.vehicle.wait_heartbeat()
            self._mode_mapping = self.vehicle.mode_mapping()
            await asyncio.sleep(0.1)
        
        # Register telemetry streams
        await self._register_telemetry_streams()
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
        # TODO: This is arbitrarily chosen for now, in future
        # this could be part of the API
        target_altitude = 3
        await self._arm()
        await self._switch_mode(MAVLinkDrone.FlightMode.TAKEOFF)
        
        # Take off at current position to target altitude
        gps = self._get_global_position()
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0, 0,
            gps['latitude'], gps['longitude'], gps['absolute_altitude'] + target_altitude)
       
        result = await self._wait_for_condition(
            lambda: self._is_mode_set(MAVLinkDrone.FlightMode.LOITER),
            interval=1
        )
 
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def land(self):
        await self._switch_mode(MAVLinkDrone.FlightMode.LAND)

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
        velocity = common_protocol.VelocityBody()
        velocity.forward_vel = 0.0
        velocity.right_vel = 0.0
        velocity.up_vel = 0.0
        velocity.angular_vel = 0.0
        return await self.set_velocity_body(velocity)

    async def kill(self):
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION,
            0, 0, 0, 0, 0, 0
        )
        
        result = await self._wait_for_condition(
            lambda: self._is_disarmed(),
            interval=1
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_home(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.absolute_altitude

        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_HOME,
            1, 0, 0, 0, 0,
            lat, lon, alt
        )

        result = await self._wait_for_condition(
            lambda: self._is_home_set(),
            timeout=5,
            interval=0.1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED
    
    async def rth(self):
        if not await \
                self._switch_mode(MAVLinkDrone.FlightMode.RTL):
            return common_protocol.ResponseStatus.FAILED

        # TODO: This might need to be an await hover, should
        # we mandate that all drones hover after RTL? If not
        # should we block for disarm or for hover?
        result = await self._wait_for_condition(
            lambda: self._is_disarmed(),
            interval=1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED        
    
    async def set_global_position(self, location):
        # Need to implement video streaming on a per-drone basis
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_relative_position_enu(self, position):
        # Need to implement video streaming on a per-drone basis
        return common_protocol.ResponseStatus.NOTSUPPORTED
    
    async def set_relative_position_body(self, position):
        # Need to implement video streaming on a per-drone basis
        return common_protocol.ResponseStatus.NOTSUPPORTED
    
    async def set_velocity_enu(self, velocity):
        # Need to implement video streaming on a per-drone basis
        return common_protocol.ResponseStatus.NOTSUPPORTED
    
    async def set_velocity_body(self, velocity):
        # Need to implement video streaming on a per-drone basis
        return common_protocol.ResponseStatus.NOTSUPPORTED
    
    async def set_heading(self, location):
        # Need to implement video streaming on a per-drone basis
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_gimbal_pose(self):
        # TODO: Support gimbal commands by using MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def stream_telemetry(self, tel_sock, rate_hz):
        logger.info('Starting telemetry stream')
        # Wait a second to avoid contention issues
        await asyncio.sleep(1) 
        while await self.is_connected():
            try:
                tel_message = data_protocol.Telemetry()
                tel_message.drone_name = self._get_name()
                tel_message.battery = self._get_battery_percentage()
                tel_message.satellites = self._get_satellites()
                tel_message.global_position.latitude = \
                        self._get_global_position()["latitude"]
                tel_message.global_position.longitude = \
                        self._get_global_position()["longitude"]
                tel_message.global_position.absolute_altitude = \
                        self._get_global_position()["absolute_altitude"]
                tel_message.global_position.relative_altitude = \
                        self._get_global_position()["relative_altitude"]
                tel_message.global_position.heading = \
                        self._get_global_position()["heading"]
                tel_message.velocity_enu.north_vel = \
                        self._get_velocity_enu()["north"]
                tel_message.velocity_enu.east_vel = \
                        self._get_velocity_enu()["east"]
                tel_message.velocity_enu.up_vel = \
                        self._get_velocity_enu()["up"]
                tel_message.velocity_body.forward_vel = \
                        self._get_velocity_body()["forward"]
                tel_message.velocity_body.right_vel = \
                        self._get_velocity_body()["right"]
                tel_message.velocity_body.up_vel = \
                        self._get_velocity_body()["up"]
                tel_sock.send(tel_message.SerializeToString())
            except Exception as e:
                logger.error(f'Failed to get telemetry, error: {e}')
            await asyncio.sleep(1 / rate_hz)
                    
    async def stream_video(self, cam_sock, rate_hz):
        # Need to implement video streaming on a per-drone basis
        return common_protocol.ResponseStatus.NOTSUPPORTED
    
    ''' Connect methods '''
    async def _register_telemetry_streams(self, frequency_hz: float = 10.0):
        # TODO: Make frequency of commands parameterizable
        # and correlated with stream_telemetry

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
            "absolute_altitude": gps_msg.alt / 1e3,
            "relative_altitude": gps_msg.relative_alt / 1e3,
            "heading": gps_msg.hdg / 1e2 # convert the centidegree to degrees
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

    def _get_velocity_enu(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return {
            "north": gps_msg.vx / 100,
            "east": gps_msg.vy / 100,
            "up": gps_msg.vz * -1 / 100
        }
        
    def _get_velocity_body(self):
        # TODO: This reference frame is incorrect
        velocity_msg = self._get_cached_message("LOCAL_POSITION_NED")
        if not velocity_msg:
            return None
        return {
            "forward": velocity_msg.vx,  # Body-frame X velocity in m/s
            "right": velocity_msg.vy,  # Body-frame Y velocity in m/s
            "up": velocity_msg.vz * -1   # Body-frame Z velocity in m/s
        }

    def _get_rssi(self):
        rssi_msg = self._get_cached_message("RC_CHANNELS")
        if not rssi_msg:
            return None
        return rssi_msg.rssi

    ''' Actuation methods '''
    async def _arm(self):
        logger.info("Arming drone...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 1, 0, 0, 0, 0, 0, 0
        )

        result =  await self._wait_for_condition(
            lambda: self._is_armed(),
            timeout=5,
            interval=1
        )
        
        if result:
            logger.info("Armed successfully")
        else:
            logger.error("Arm failed")
        return result

    async def _disarm(self):
        logger.info("Disarming drone...")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 0, 0, 0, 0, 0, 0, 0
        )

        result =  await self._wait_for_condition(
            lambda: self._is_disarmed(),
            timeout=5,
            interval=1
        )
        
        if result:
            self.mode = None
            logger.info("Disarmed successfully")
        else:
            logger.error("Disarm failed")
            
        return result  

    async def _switch_mode(self, mode):
        mode_target = mode.value
        curr_mode = self.mode.value if self.mode else None
        
        if self.mode == mode:
            logger.info(f"Already in mode {mode_target}")
            return True
        
        if mode_target not in self._mode_mapping:
            logger.info(f"Mode {mode_target} not supported!")
            return False
        
        mode_id = self._mode_mapping[mode_target]
        if type(mode_id) == int:
            # ArduPilot has a single ID for each mode
            self.vehicle.mav.set_mode_send(
                self.vehicle.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                mode_id
            )
        elif type(mode_id) == list or type(mode_id) == tuple:
            # PX4 has a three digit ID for each mode
            self.vehicle.mav.command_long_send(
                self.vehicle.target_system,
                self.vehicle.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
                mode_id[0], mode_id[1], mode_id[2],
                0, 0, 0, 0
            )
            
            # TODO: Why do we have to do this?
            # Avoid waiting for mode condition in OFFBOARD to prevent hanging
            if not self.mode == MAVLinkDrone.FlightMode.OFFBOARD:
                return True
        
        result = await self._wait_for_condition(
            lambda: self._is_mode_set(mode),
            timeout=5,
            interval=1
        )
        
        if result:
            self.mode = mode
            logger.info(f"Mode switched to {mode_target}")

        return result
        
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

    def _is_global_position_reached(self, lat, lon, alt):
        if self._is_at_target(lat, lon) and self._is_abs_altitude_reached(alt):
            return True
        return False

    def _is_abs_altitude_reached(self, target_altitude):
        current_altitude = self._get_global_position()["absolute_altitude"]
        logger.info(f"Current altitude: {current_altitude}, Target altitude: {target_altitude}")
        return current_altitude >= target_altitude * 0.95
    
    def _is_rel_altitude_reached(self, target_altitude):
        current_altitude = self._get_global_position()["relative_altitude"]
        return current_altitude >= target_altitude * 0.95
   
    def _is_heading_reached(self, heading):
        current_heading = self._get_global_position()["heading"]
        if not current_heading:
            return False  # Return False if heading data is unavailable
        logger.info(f"Current heading: {current_heading}, Target heading: {heading}")
        diff = (heading - current_heading + 540) % 360 - 180
        return abs(diff) <= 1
    
    def _is_at_target(self, lat, lon):
        current_location = self._get_global_position()
        if not current_location:
            return False
        dlat = lat - current_location["latitude"]
        dlon = lon - current_location["longitude"]
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance < 1.0
        
    ''' Helper methods '''
    def _calculate_heading(self, lat1, lon1, lat2, lon2):
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, \
                [lat1, lon1, lat2, lon2])
        
        delta_lon = lon2 - lon1

        # heading calculation
        x = math.sin(delta_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
        
        initial_heading = math.atan2(x, y)

        # Convert heading from radians to degrees
        initial_heading = math.degrees(initial_heading)

        # Normalize to 0-360 degrees
        converted_heading = (initial_heading + 360) % 360

        return converted_heading
        
    def _to_quaternion(self, roll = 0.0, pitch = 0.0, yaw = 0.0):
        t0 = math.cos(math.radians(yaw * 0.5))
        t1 = math.sin(math.radians(yaw * 0.5))
        t2 = math.cos(math.radians(roll * 0.5))
        t3 = math.sin(math.radians(roll * 0.5))
        t4 = math.cos(math.radians(pitch * 0.5))
        t5 = math.sin(math.radians(pitch * 0.5))

        w = t0 * t2 * t4 + t1 * t3 * t5
        x = t0 * t3 * t4 - t1 * t2 * t5
        y = t0 * t2 * t5 + t1 * t3 * t4
        z = t1 * t2 * t4 - t0 * t3 * t5

        return [w, x, y, z]

    async def _message_listener(self):
        logger.info("Starting message listener")
        try:
            while True:
                msg = await asyncio.to_thread(self.vehicle.recv_match, blocking=True)
                if msg:
                    message_type = msg.get_type()
                    logger.debug(f"Received message type: {message_type}")
        except asyncio.CancelledError:
            logger.info("Message listener stopped")
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
    
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
                    logger.info("Condition met")
                    return True
            except Exception as e:
                logger.error(f"Error evaluating condition: {e}")
            if timeout is not None and time.time() - start_time > timeout:
                logger.error("Timeout waiting for condition")
                return False
            await asyncio.sleep(interval)
