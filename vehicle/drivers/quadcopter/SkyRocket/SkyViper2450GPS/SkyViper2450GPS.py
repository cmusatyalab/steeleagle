from enum import Enum
import math
import os
import time
import asyncio
import logging
from pymavlink import mavutil
from quadcopter.quadcopter_interface import QuadcopterItf
from protocol.steeleagle import controlplane_pb2 as cnc_protocol
from protocol.steeleagle import dataplane_pb2 as data_protocol
import protocol.steeleagle.common_pb2 as common_protocol


logger = logging.getLogger(__name__)

class ConnectionFailedException(Exception):
    pass

class SkyViper2450GPSDrone(QuadcopterItf):
    
    class FlightMode(Enum):
        LAND = 'LAND'
        RTL = 'RTL'
        LOITER = 'LOITER'
        GUIDED = 'GUIDED'
        ALT_HOLD = 'ALT_HOLD'
        
    def __init__(self, drone_id):
        self.vehicle = None
        self.mode = None
        self.mode_mapping = None
        self.listener_task = None
        self.drone_id = drone_id
        


    '''Interface Methods'''
    async def connect(self, connection_string):
        # connect to drone
        logger.info(f"Connecting to drone at {connection_string}...")
        self.vehicle = mavutil.mavlink_connection(connection_string)
        self.vehicle.wait_heartbeat()
        logger.info("-- Connected to drone!")
        self.mode_mapping = self.vehicle.mode_mapping()
        logger.info(f"Mode mapping: {self.mode_mapping}")
        
        # register telemetry streams
        await self._register_telemetry_streams()
        asyncio.create_task(self._message_listener())
        
        await self._startStreaming()

    
    async def is_connected(self):
        return self.vehicle is not None

    async def disconnect(self):
        if self.listener_task:
            self.listener_task.cancel()
            await asyncio.sleep(0.1)  # Allow task cancellation

        if self.vehicle:
            self.vehicle.close()
            logger.info("-- Disconnected from drone")
        
        self._stopStreaming()
        
    async def take_off(self):
            logger.info("-- Taking off")
            target_altitude = 3  # meters
            
            if await self._switchMode(SkyViper2450GPSDrone.FlightMode.GUIDED) == False:
                logger.error("Failed to set mode to GUIDED")
                return common_protocol.ResponseStatus.FAILED
            
            if await self._arm() == False:
                logger.error("Failed to arm the drone")
                return common_protocol.ResponseStatus.FAILED
            
            self.vehicle.mav.command_long_send(
                self.vehicle.target_system,
                self.vehicle.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0, 0, 0, 0,
                0, 0, target_altitude
            )
            
            result = await self._wait_for_condition(
                lambda: self._is_altitude_reached(target_altitude),
                timeout=60,
                interval=1
            )
            if result:
                logger.info("-- Altitude reached")
                return common_protocol.ResponseStatus.OK
            else:
                logger.error("-- Failed to reach target altitude")
                return common_protocol.ResponseStatus.FAILED

    async def land(self):
        logger.info("-- Landing")
        if await self._switchMode(SkyViper2450GPSDrone.FlightMode.LAND) == False:
            logger.error("Failed to set mode to LAND")
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._is_disarmed(),
            timeout=60,
            interval=1
        )
        if result:
            logger.info("-- Landed and disarmed")
            return common_protocol.ResponseStatus.OK
        else:   
            logger.error("-- Landing failed")
            return common_protocol.ResponseStatus.FAILED
        
    
    async def hover(self):
        if await self._switchMode(SkyViper2450GPSDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return common_protocol.ResponseStatus.FAILED
        else:
            logger.info("-- Hovering")
            return common_protocol.ResponseStatus.OK
    
    async def kill(self):
        logger.info("-- Killing drone")
        logger.info("-- Killing not supported")
        return common_protocol.ResponseStatus.NOTSUPPORTED


    async def set_home(self, lat, lng, alt):
        logger.info(f"-- Setting home location to {lat}, {lng}, {alt}")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_HOME,
            1,
            0, 0, 0, 0,
            lat, lng, alt
        )

        result = await self._wait_for_condition(
            lambda: self._is_home_set(),
            timeout=30,
            interval=0.1
        )
        
        if result:
            logger.info("-- Home location set OKfully")
            return common_protocol.ResponseStatus.OK
        else:
            logger.error("-- Failed to set home location")
            return common_protocol.ResponseStatus.FAILED
    
    async def rth(self):
        logger.info("-- Returning to launch")
        if await self._switchMode(SkyViper2450GPSDrone.FlightMode.RTL) == False:
            logger.error("Failed to set mode to RTL")
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._is_disarmed(),
            timeout=60,
            interval=1
        )
        
        if result:
            logger.info("-- Returned to launch and disarmed")
            return common_protocol.ResponseStatus.OK
        else:   
            logger.error("-- RTL failed")
            return common_protocol.ResponseStatus.FAILED
    
    async def set_velocity(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        angular_vel = velocity.angular_vel
        logger.info(f"-- Setting velocity: forward_vel={forward_vel}, right_vel={right_vel}, up_vel={up_vel}, angular_vel={angular_vel}")
        if await self._switchMode(SkyViper2450GPSDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return common_protocol.ResponseStatus.FAILED
        
        self.vehicle.mav.set_position_target_local_ned_send(
            0,  # time_boot_ms
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,  # frame
            0b010111000111,  # type_mask
            0, 0, 0,  # x, y, z positions
            forward_vel, right_vel, -up_vel,  # x, y, z velocity
            0, 0, 0,  # x, y, z acceleration
            float('nan'), angular_vel  # yaw, yaw_rate
        )
        logger.info("-- setVelocity sent")
        #  continuous control: no blocking wait
        return common_protocol.ResponseStatus.OK

    async def set_global_position(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        bearing = location.bearing
        logger.info(f"-- Setting GPS location: lat={lat}, lon={lon}, alt={alt}, bearing={bearing}")
        
        if await self._switchMode(SkyViper2450GPSDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return common_protocol.ResponseStatus.FAILED
        
        self.vehicle.mav.set_position_target_global_int_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )
            # Calculate bearing if not provided
        current_location = self._getGPS()
        current_lat = current_location["latitude"]
        current_lon = current_location["longitude"]
        if bearing is None:
            bearing = self._calculate_bearing(current_lat, current_lon, lat, lon)
            logger.info(f"-- Calculated bearing: {bearing}")
        
        await self._setBearing(bearing)
        
        result = await self._wait_for_condition(
            lambda: self._is_at_target(lat, lon),
            timeout=60,
            interval=1
        )
        
        if result:  
            logger.info("-- Reached target GPS location")
            return common_protocol.ResponseStatus.OK
        else:  
            logger.info("-- Failed to reach target GPS location")
            return common_protocol.ResponseStatus.FAILED

    async def set_relative_position(self, position):
        forward = position.forward
        right = position.right
        up = position.up
        angle = position.angle
        logger.info(f"-- Translating location: forward={forward}, right={right}, up={up}, angle={angle}")
        
        if await self._switchMode(SkyViper2450GPSDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return common_protocol.ResponseStatus.FAILED
        
        current_location =  self._getGPS()
        current_heading =  self._getHeading()

        dx = forward * math.cos(math.radians(current_heading)) - right * math.sin(math.radians(current_heading))
        dy = forward * math.sin(math.radians(current_heading)) + right * math.cos(math.radians(current_heading))
        dz = -up

        target_lat = current_location["latitude"] + (dx / 111320)
        target_lon = current_location["longitude"] + (dy / (111320 * math.cos(math.radians(current_location["latitude"]))))
        target_alt = current_location["altitude"] + dz

        self.vehicle.mav.set_position_target_global_int_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,
            int(target_lat * 1e7),
            int(target_lon * 1e7),
            target_alt,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )
        
        if angle is not None: await self._setBearing(angle)
        
        result = await self._wait_for_condition(
            lambda: self._is_at_target(target_lat, target_lon),
            timeout=60,
            interval=1
        )
        
        if  result:
            logger.info("-- Reached target translated location")
            return common_protocol.ResponseStatus.OK
        else:
            logger.error("-- Failed to reach target translated location")
            return common_protocol.ResponseStatus.FAILED
        
    async def stream_telemetry(self, tel_sock):
        logger.debug('Starting telemetry stream')
        await asyncio.sleep(1) # solving for some contention issue with connecting to drone
        while await self.is_connected():
            logger.debug('HI from telemetry stream')
            try:
                tel_message = data_protocol.Telemetry()
                telDict = await self._getTelemetry()
                tel_message.drone_name = telDict["name"]
                tel_message.battery = telDict["battery"]
                tel_message.drone_attitude.pose.yaw = telDict["attitude"]["yaw"]
                tel_message.drone_attitude.pose.pitch = telDict["attitude"]["pitch"]
                tel_message.drone_attitude.pose.roll = telDict["attitude"]["roll"]
                tel_message.satellites = telDict["satellites"]
                tel_message.relative_position.up = telDict["relAlt"]
                tel_message.global_position.latitude = telDict["gps"]["latitude"]
                tel_message.global_position.longitude = telDict["gps"]["longitude"]
                tel_message.global_position.altitude = telDict["gps"]["altitude"]
                tel_message.global_position.bearing = telDict["heading"]
                tel_message.velocity.forward_vel = telDict["imu"]["forward"]
                tel_message.velocity.right_vel = telDict["imu"]["right"]
                tel_message.velocity.up_vel = telDict["imu"]["up"]
                logger.debug(f"Telemetry: {telDict}")
                tel_sock.send(tel_message.SerializeToString())
                logger.debug('Sent telemetry')
            except Exception as e:
                logger.error(f'Failed to get telemetry, error: {e}')
            await asyncio.sleep(0.01)
            logger.debug("Telemetry stream ended, disconnected from drone")
                    
    async def stream_video(self, cam_sock):
        logger.info('Starting camera stream')
        frame_id = 0
        while await self.is_connected():
            try:
                cam_message = data_protocol.Frame()
                frame, frame_shape = await self._getVideoFrame()
                
                if frame is None:
                    logger.error('Failed to get video frame')
                    continue
                
                cam_message.data = frame
                cam_message.height = frame_shape[0]
                cam_message.width = frame_shape[1]
                cam_message.channels = frame_shape[2]
                cam_message.id = frame_id
                cam_sock.send(cam_message.SerializeToString())
                logger.debug(f'Camera stream: sent frame {frame_id}, shape: {frame_shape}')
                frame_id = frame_id + 1
            except Exception as e:
                logger.error(f'Failed to get video frame, error: {e}')
            await asyncio.sleep(0.033)
        logger.info("Camera stream ended, disconnected from drone")


    ''' Connect methods '''
    async def _register_telemetry_streams(self, frequency_hz: float = 10.0):
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
            message_id, # The MAVLink message ID
            1e6 / frequency_hz, # The interval between two messages in microseconds. Set to -1 to disable and 0 to request default rate.
            0, 0, 0, 0, # Unused parameters
            0, # Target address of message stream (if message has target address fields). 0: Flight-stack default (recommended), 1: address of requestor, 2: broadcast.
        )
        
    ''' Telemetry methods '''
    async def _getTelemetry(self):
        try:
            tel_dict = {}
            tel_dict['name'] = self._getName()
            tel_dict['gps'] = self._getGPS()
            tel_dict['relAlt'] = self._getAltitudeRel()
            tel_dict['attitude'] = self._getAttitude()
            tel_dict['magnetometer'] = self._getMagnetometerReading()
            tel_dict['imu'] = self._getVelocityNEU()
            tel_dict['battery'] = self._getBatteryPercentage()
            tel_dict['satellites'] = self._getSatellites()
            tel_dict['heading'] = self._getHeading()
            logger.debug(f"Telemetry data: {tel_dict}")
            return tel_dict

        except Exception as e:
            logger.error(f"Error in _getTelemetry(): {e}")
            return {}

    def _getName(self):
        return self.drone_id

    def _getGPS(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return {
            "latitude": gps_msg.lat / 1e7,
            "longitude": gps_msg.lon / 1e7,
            "altitude": gps_msg.alt / 1e3
        }

    def _getAltitudeRel(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return gps_msg.relative_alt / 1e3

    def _getAttitude(self):
        attitude_msg = self._get_cached_message("ATTITUDE")
        if not attitude_msg:
            return None
        return {
            "roll": attitude_msg.roll,
            "pitch": attitude_msg.pitch,
            "yaw": attitude_msg.yaw
        }

    def _getMagnetometerReading(self):
        imu_msg = self._get_cached_message("RAW_IMU")
        if not imu_msg:
            return {"x": None, "y": None, "z": None}
        return {
            "x": imu_msg.xmag,
            "y": imu_msg.ymag,
            "z": imu_msg.zmag
        }

    def _getBatteryPercentage(self):
        battery_msg = self._get_cached_message("BATTERY_STATUS")
        if not battery_msg:
            return None
        return battery_msg.battery_remaining

    def _getSatellites(self):
        satellites_msg = self._get_cached_message("GPS_RAW_INT")
        if not satellites_msg:
            return None
        return satellites_msg.satellites_visible

    def _getHeading(self):
        heading_msg = self._get_cached_message("VFR_HUD")
        if not heading_msg:
            return None
        return heading_msg.heading

    def _getVelocityNEU(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return {
            "forward": gps_msg.vx / 100,
            "right": gps_msg.vy / 100,
            "up": gps_msg.vz / 100
        }
        
    def _getVelocityBody(self):
        velocity_msg = self._get_cached_message("LOCAL_POSITION_NED")
        if not velocity_msg:
            return None
        return {
            "vx": velocity_msg.vx,  # Body-frame X velocity in m/s
            "vy": velocity_msg.vy,  # Body-frame Y velocity in m/s
            "vz": velocity_msg.vz   # Body-frame Z velocity in m/s
        }

    def _getRSSI(self):
        rssi_msg = self._get_cached_message("RC_CHANNELS")
        if not rssi_msg:
            return None
        return rssi_msg.rssi

    ''' Actuation methods '''    
    async def _setBearing(self, bearing):
        logger.info(f"-- Setting yaw to {bearing} degrees")
        
        if await self._switchMode(SkyViper2450GPSDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return False
        
        yaw_speed=30
        direction=0
        relative_flag = 0

        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            0,  # Confirmation
            bearing,  # param1: Yaw angle
            yaw_speed,   # param2: Yaw speed in deg/s
            direction,   # param3: -1=CCW, 1=CW, 0=fastest (only for absolute yaw)
            relative_flag,  # param4: 0=Absolute, 1=Relative
            0, 0, 0  # param5, param6, param7 (Unused)
        )
        
        result =  await self._wait_for_condition(
            lambda: self._is_bearing_reached(bearing),
            timeout=30,
            interval=0.5
        )
        
        if result:
            logger.info(f"-- Yaw OKfully set to {bearing} degrees")
            
        else:
            logger.error(f"-- Failed to set yaw to {bearing} degrees")
        
        return result

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
            timeout=30,
            interval=1
        )
        
        if result:
            logger.info("-- Armed OKfully")
        else:
            logger.error("-- Arm failed")
        return result

    async def _disarm(self):
        logger.info("-- disarming")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,
            0, 0, 0, 0, 0, 0
        )
        logger.info("-- disarm command sent")

        result =  await self._wait_for_condition(
            lambda: self._is_disarmed(),
            timeout=30,
            interval=1
        )
        
        if result:
            self.mode = None
            logger.info("-- disarmed OKfully")
        else:
            logger.error("-- disarm failed")
            
        return result
    
    async def _switchMode(self, mode):
        logger.info(f"Switching mode to {mode}")
        mode_target = mode.value
        curr_mode = self.mode.value if self.mode else None
        logger.info(f"mode map: {self.mode_mapping}, target mode: {mode_target}, current mode: {curr_mode}")
        
        if self.mode == mode:
            logger.info(f"Already in mode {mode_target}")
            return True
        
        # switch mode
        if mode_target not in self.mode_mapping:
            logger.info(f"Mode {mode_target} not supported!")
            return False
        
        mode_id = self.mode_mapping[mode_target]
        self.vehicle.mav.set_mode_send(
            self.vehicle.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        
        result = await self._wait_for_condition(
            lambda: self._is_mode_set(mode_target),
            timeout=30,
            interval=1
        )
        
        if result:
            self.mode = mode
            logger.info(f"Mode switched to {mode_target}")
        
        return result
           
    ''' ACK methods'''
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
        
    async def _wait_for_condition(self, condition_fn, timeout=30, interval=0.5):
        start_time = time.time()
        while True:
            try:
                if condition_fn():
                    logger.info("-- Condition met")
                    return True
            except Exception as e:
                logger.error(f"-- Error evaluating condition: {e}")
            if time.time() - start_time > timeout:
                logger.error("-- Timeout waiting for condition")
                return False
            await asyncio.sleep(interval)
            
    def _is_armed(self):
        return self.vehicle.recv_match(type="HEARTBEAT", blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
        
    def _is_disarmed(self):
        return not (self.vehicle.recv_match(type='HEARTBEAT', blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def _is_mode_set(self, mode_target):
        current_mode = mavutil.mode_string_v10(self.vehicle.recv_match(type='HEARTBEAT', blocking=True))
        return current_mode == mode_target
    
    def _is_home_set(self):
        msg = self.vehicle.recv_match(type='COMMAND_ACK', blocking=True)
        return msg and msg.command == mavutil.mavlink.MAV_CMD_DO_SET_HOME and msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED

    def _is_altitude_reached(self, target_altitude):
        current_altitude = self._getAltitudeRel()
        return current_altitude >= target_altitude * 0.95
    
    def _is_bearing_reached(self, bearing):
        logger.info(f"Checking if bearing is reached: {bearing}")
        
        current_heading = self._getHeading()  # Returns heading in degrees [0..359], or None
        if current_heading is None:
            logger.info("No VFR_HUD heading data available; cannot verify bearing.")
            return False
        
        # Normalize the target bearing into [0..359]
        
        target_bearing = (bearing + 360) % 360
        diff = self._circular_difference_deg(current_heading, target_bearing)
        logger.info(f"Current heading: {current_heading}, Target bearing: {target_bearing}")
        return abs(diff) <= 5

    def _is_at_target(self, lat, lon):
        logger.info(f"Checking if at target GPS location: {lat}, {lon}")
        current_location = self._getGPS()
        if not current_location:
            return False
        dlat = lat - current_location["latitude"]
        dlon = lon - current_location["longitude"]
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance < 1.0
        
    ''' Math methods '''
    def _circular_difference_deg(self, a, b):
        diff = (a - b) % 360.0
        if diff > 180.0:
            diff -= 360.0
        return diff
    
    # azimuth calculation for bearing
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

    ''' Stream methods '''
    async def _getGimbalPose(self):
        pass
    
    async def _startStreaming(self):
        self.streamingThread = StreamingThread(self.vehicle)
        self.streamingThread.start()

    async def _getVideoFrame(self):
        if self.streamingThread:
            return [self.streamingThread.grabFrame().tobytes(), self.streamingThread.getFrameShape()]

    async def _stopStreaming(self):
        self.streamingThread.stop()
        
import cv2
import numpy as np
import os
import threading

class StreamingThread(threading.Thread):

    def __init__(self, drone):
        threading.Thread.__init__(self)
        self.currentFrame = None
        self.drone = drone
        url_sim = os.environ.get('STREAM_SIM_URL')
        url_mini = os.environ.get('STREAM_MINI_URL')
        self.sim = os.environ.get('SIMULATION')
        
        if (self.sim == 'true'):
            url = url_sim
        else:
            url = url_mini
        
        logger.info(f"url used: {url}")
        self.cap = cv2.VideoCapture(url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        self.isRunning = True

    def run(self):
        try:
            while(self.isRunning):
                
                ret, self.currentFrame = self.cap.read()
        except Exception as e:
            logger.error(e)
            
    def getFrameShape(self):
        return self.currentFrame.shape
    
    def grabFrame(self):
        try:
            frame = self.currentFrame.copy()
            return frame
        except Exception as e:
            # Send a blank frame
            return None

    def stop(self):
        self.isRunning = False



