import asyncio
import logging
import math
import os
import threading
import time
from enum import Enum

import cv2
from pymavlink import mavutil

logger = logging.getLogger(__name__)


class ModalAISeekerDrone():
    
    class FlightMode(Enum):
        LAND = 'LAND'
        RTL = 'RTL'
        LOITER = 'LOITER'
        TAKEOFF = 'TAKEOFF'
        ALT_HOLD = 'ALT_HOLD'
        OFFBOARD = 'OFFBOARD'
        
    def __init__(self):
        self.vehicle = None
        self.mode = None
        self.mode_mapping = None
        self.listener_task = None
        self.gps_disabled = False

    ''' Connect methods '''
    async def connect(self, connection_string):
        # connect to drone
        logger.info(f"Connecting to drone at {connection_string}...")
        self.vehicle = mavutil.mavlink_connection(connection_string)
        self.vehicle.wait_heartbeat()
        logger.info("-- Connected to drone!")
        self.mode_mapping = self.vehicle.mode_mapping()
        logger.debug(f"Mode mapping: {self.mode_mapping}")
        
        # register telemetry streams
        await self.register_telemetry_streams()
        asyncio.create_task(self._message_listener())
        
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
                self.request_message_interval(message_id, frequency_hz)
                logger.info(f"Registered telemetry stream: {message_name} (ID: {message_id})")

            except Exception as e:
                logger.error(f"Failed to register telemetry stream {message_name}: {e}")

    def request_message_interval(self, message_id: int, frequency_hz: float):
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            message_id, # The MAVLink message ID
            1e6 / frequency_hz, # The interval between two messages in microseconds. Set to -1 to disable and 0 to request default rate.
            0, 0, 0, 0, # Unused parameters
            0, # Target address of message stream (if message has target address fields). 0: Flight-stack default (recommended), 1: address of requestor, 2: broadcast.
        )
        
    async def isConnected(self):
        return self.vehicle is not None

    async def disconnect(self):
        if self.listener_task:
            self.listener_task.cancel()
            await asyncio.sleep(0.1)  # Allow task cancellation

        if self.vehicle:
            self.vehicle.close()
            logger.info("-- Disconnected from drone")

    ''' Telemetry methods '''
    async def getTelemetry(self):
        try:
            tel_dict = {}
            tel_dict['name'] = self.getName()
            tel_dict['gps'] = self.getGPS()
            tel_dict['relAlt'] = self.getAltitudeRel()
            tel_dict['attitude'] = self.getAttitude()
            tel_dict['magnetometer'] = self.getMagnetometerReading()
            tel_dict['imu'] = self.getVelocityNEU()
            tel_dict['battery'] = self.getBatteryPercentage()
            tel_dict['satellites'] = self.getSatellites()
            tel_dict['heading'] = self.getHeading()
            logger.debug(f"Telemetry data: {tel_dict}")
            return tel_dict

        except Exception as e:
            logger.error(f"Error in getTelemetry(): {e}")
            return {}

    def getName(self):
        drone_id = os.environ.get('DRONE_ID')
        return drone_id

    def getGPS(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return {
            "latitude": gps_msg.lat / 1e7,
            "longitude": gps_msg.lon / 1e7,
            "altitude": gps_msg.alt / 1e3
        }

    def getAltitudeRel(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return gps_msg.relative_alt / 1e3

    def getAttitude(self):
        attitude_msg = self._get_cached_message("ATTITUDE")
        if not attitude_msg:
            return None
        return {
            "roll": attitude_msg.roll,
            "pitch": attitude_msg.pitch,
            "yaw": attitude_msg.yaw
        }

    def getMagnetometerReading(self):
        imu_msg = self._get_cached_message("RAW_IMU")
        if not imu_msg:
            return {"x": None, "y": None, "z": None}
        return {
            "x": imu_msg.xmag,
            "y": imu_msg.ymag,
            "z": imu_msg.zmag
        }

    def getBatteryPercentage(self):
        battery_msg = self._get_cached_message("BATTERY_STATUS")
        if not battery_msg:
            return None
        return battery_msg.battery_remaining

    def getSatellites(self):
        satellites_msg = self._get_cached_message("GPS_RAW_INT")
        if not satellites_msg:
            return None
        return satellites_msg.satellites_visible

    def getHeading(self):
        heading_msg = self._get_cached_message("VFR_HUD")
        if not heading_msg:
            return None
        return heading_msg.heading

    def getVelocityNEU(self):
        gps_msg = self._get_cached_message("GLOBAL_POSITION_INT")
        if not gps_msg:
            return None
        return {
            "forward": gps_msg.vx / 100,
            "right": gps_msg.vy / 100,
            "up": gps_msg.vz / 100
        }
        
    def getVelocityBody(self):
        velocity_msg = self._get_cached_message("LOCAL_POSITION_NED")
        if not velocity_msg:
            return None
        return {
            "vx": velocity_msg.vx,  # Body-frame X velocity in m/s
            "vy": velocity_msg.vy,  # Body-frame Y velocity in m/s
            "vz": velocity_msg.vz   # Body-frame Z velocity in m/s
        }

    def getRSSI(self):
        rssi_msg = self._get_cached_message("RC_CHANNELS")
        if not rssi_msg:
            return None
        return rssi_msg.rssi

    ''' Actuation methods '''
    async def hover(self):
        logger.info("-- Hovering")
        await self.setVelocity(0.0, 0.0, 0.0, 0.0)

    async def takeOff(self, target_altitude):
        logger.info("-- Taking off")
       
        await self.arm()
        await self.switchMode(ModalAISeekerDrone.FlightMode.TAKEOFF)
        
        # Take off at the current GPS location
        gps = self.getGPS()
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, # target system
            self.vehicle.target_component, # target component
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, # command
            0, # confirmation
            0, 0, 0, 0, gps['latitude'], gps['longitude'], gps['altitude'] + 2.5) # param 1 ~ 7 (param 7 is the target altitude)
       
        result = await self._wait_for_condition(
            lambda: self.is_mode_set(ModalAISeekerDrone.FlightMode.LOITER),
            interval=1
        )

        if result:
            logger.info("-- Takeoff success")
        else:   
            logger.error("-- Takeoff failed")
        
        return result

    async def land(self):
        logger.info("-- Landing")
        await self.switchMode(ModalAISeekerDrone.FlightMode.LAND)

        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0, 0, 0, 0, 0, 0, 0, 0)

        result = await self._wait_for_condition(
            lambda: self.is_disarmed(),
            interval=1
        )
        if result:
            logger.info("-- Landed and disarmed")
        else:   
            logger.error("-- Landing failed")
        
        return result

    async def setHome(self, lat, lng, alt):
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
            lambda: self.is_home_set(),
            timeout=5,
            interval=0.1
        )
        
        if result:
            logger.info("-- Home location set successfully")
        else:
            logger.error("-- Failed to set home location")
        
        return result
    
    async def rth(self):
        logger.info("-- Returning to launch")
        if await self.switchMode(ModalAISeekerDrone.FlightMode.RTL) == False:
            logger.error("Failed to set mode to RTL")
            return

        result = await self._wait_for_condition(
            lambda: self.is_disarmed(),
            interval=1
        )
        
        if result:
            logger.info("-- Returned to launch and disarmed")
        else:   
            logger.error("-- RTL failed")
            
    async def manual_control(self, forward_vel, right_vel, up_vel, angle_vel):
        if self.gps_disabled:
            if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
                logger.error("Failed to set mode to GUIDED_NOGPS")
                return
            # if await self.switchMode(ModalAISeekerDrone.FlightMode.ALT_HOLD) == False:
            #     logger.error("Failed to set mode to GUIDED_NOGPS")
            #     return
        else:
            if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
                logger.error("Failed to set mode to GUIDED")
                return
        logger.info(f"Sending manual control: forward={forward_vel}, right={right_vel}, up={up_vel}, yaw={angle_vel}")

        # Ensure values are within MAVLink range (-1000 to 1000)
        def clamp(value, min_val, max_val):
            return max(min_val, min(max_val, int(value)))  # Ensure integer conversion

        x = clamp(forward_vel * 1000, -1000, 1000)  # Forward/backward movement
        y = clamp(right_vel * 1000, -1000, 1000)    # Left/right movement
        z = clamp(up_vel * 1000, 0, 1000)           # Throttle (0=lowest, 1000=full thrust)
        r = clamp(angle_vel * 1000, -1000, 1000)    # Yaw rotation

        buttons = 0  # No buttons pressed
        buttons2 = 0  # No additional buttons
        enabled_extensions = 0  # No extra axis enabled
        s, t, aux1, aux2, aux3, aux4, aux5, aux6 = 0, 0, 0, 0, 0, 0, 0, 0  # Unused fields

        try:
            self.vehicle.mav.manual_control_send(
                self.vehicle.target_system,
                x, y, z, r,
                buttons,
                buttons2,
                enabled_extensions,
                s, t, aux1, aux2, aux3, aux4, aux5, aux6
            )
            logger.info("Manual control command sent successfully!")
        except Exception as e:
            logger.error(f"Failed to send manual control: {e}")
        
        
    async def setAttitude(self, pitch, roll, thrust, yaw):
        logger.info(f"-- Setting attitude: pitch={pitch}, roll={roll}, thrust={thrust}, yaw={yaw}")

        if self.gps_disabled:
            if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
                logger.error("Failed to set mode to GUIDED_NOGPS")
                return
            # if await self.switchMode(ModalAISeekerDrone.FlightMode.ALT_HOLD) == False:
            #     logger.error("Failed to set mode to GUIDED_NOGPS")
            #     return
        else:
            if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
                logger.error("Failed to set mode to GUIDED")
                return
        
        # Convert Euler angles to quaternion (w, x, y, z)
        def to_quaternion(roll=0.0, pitch=0.0, yaw=0.0):
            roll, pitch, yaw = map(math.radians, [roll, pitch, yaw])
            cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
            cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
            cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)

            return [cr * cp * cy + sr * sp * sy,  # w
                    sr * cp * cy - cr * sp * sy,  # x
                    cr * sp * cy + sr * cp * sy,  # y
                    cr * cp * sy - sr * sp * cy]  # z

        q = to_quaternion(roll, pitch, yaw)

        base_thrust = 0.6
        
        self.vehicle.mav.set_attitude_target_send(
            0,  # time_boot_ms
            self.vehicle.target_system,
            self.vehicle.target_component,
            0b00000000,  # type_mask
            q,  # Quaternion
            0, 0, 0,  # Body angular rates
            base_thrust + thrust  # Throttle
        )
        logger.info("-- setAttitude sent successfully")
        #  continuous control: no blocking wait

    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info(f"-- Setting velocity: forward_vel={forward_vel}, right_vel={right_vel}, up_vel={up_vel}, angle_vel={angle_vel}")
        
        if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        self.vehicle.mav.set_position_target_local_ned_send(
            0,  # time_boot_ms
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,  # frame
            0b010111000111,  # type_mask
            0, 0, 0,  # x, y, z positions
            forward_vel, right_vel, -up_vel,  # x, y, z velocity
            0, 0, 0,  # x, y, z acceleration
            0, angle_vel  # yaw, yaw_rate
        )
        logger.info("-- setVelocity sent successfully")

    async def setGPSLocation(self, lat, lon, alt, bearing):
        logger.info(f"-- Setting GPS location: lat={lat}, lon={lon}, alt={alt}, bearing={bearing}")
        
        if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
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
        current_location = self.getGPS()
        current_lat = current_location["latitude"]
        current_lon = current_location["longitude"]
        if bearing is None:
            bearing = self.calculate_bearing(current_lat, current_lon, lat, lon)
            logger.info(f"-- Calculated bearing: {bearing}")
        
        await self.setBearing(bearing)
        
        result = await self._wait_for_condition(
            lambda: self.is_at_target(lat, lon),
            interval=1
        )
        
        if result:  
            logger.info("-- Reached target GPS location")
        else:  
            logger.info("-- Failed to reach target GPS location")
        
        return result

    async def setTranslatedLocation(self, forward, right, up, angle):
        logger.info(f"-- Translating location: forward={forward}, right={right}, up={up}, angle={angle}")
        
        if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        current_location =  self.getGPS()
        current_heading =  self.getHeading()

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
        
        if angle is not None: await self.setBearing(angle)
        
        result = await self._wait_for_condition(
            lambda: self.is_at_target(target_lat, target_lon),
            interval=1
        )
        
        if  result:
            logger.info("-- Reached target translated location")
        else:
            logger.error("-- Failed to reach target translated location")
        
        return result

    async def setBearing(self, bearing):
        logger.info(f"-- Setting yaw to {bearing} degrees")
        
        if await self.switchMode(ModalAISeekerDrone.FlightMode.OFFBOARD) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        yaw_speed = 25 # deg/s
        direction = 0 # 1: clockwise, -1: counter-clockwise 0: most quickly direction
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
            lambda: self.is_bearing_reached(bearing),
            interval=0.5
        )
        
        result = True
        
        if result:
            logger.info(f"-- Yaw successfully set to {bearing} degrees")
        else:
            logger.error(f"-- Failed to set yaw to {bearing} degrees")
        
        return result

    async def arm(self):
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
            lambda: self.is_armed(),
            timeout=5,
            interval=1
        )
        
        if result:
            logger.info("-- Armed successfully")
        else:
            logger.error("-- Arm failed")
        return result

    async def disarm(self):
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
            lambda: self.is_disarmed(),
            timeout=5,
            interval=1
        )
        
        if result:
            self.mode = None
            logger.info("-- Disarmed successfully")
        else:
            logger.error("-- Disarm failed")
            
        return result  

    async def switchMode(self, mode):
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
        logger.info(f"Mode ID Triplet: {mode_id}")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
            mode_id[0], mode_id[1], mode_id[2], 0, 0, 0, 0)
        
        if mode is not ModalAISeekerDrone.FlightMode.OFFBOARD:
            result = await self._wait_for_condition(
                lambda: self.is_mode_set(mode),
                timeout=5,
                interval=1
            )
            
            if result:
                self.mode = mode
                logger.info(f"Mode switched to {mode_target}")

            return result
        else:
            logger.info("Priming for OFFBOARD mode")
            return True
    
    async def disableGPS(self):
        # logger.info("-- Disabling GPS")

        # # Set EKF_GPS_TYPE to 3 (Indoor Mode)
        # self.vehicle.mav.param_set_send(
        #     self.vehicle.target_system,
        #     self.vehicle.target_component,
        #     b'EKF_GPS_TYPE',  # Parameter name
        #     3,  # 3 = No GPS (indoor mode)
        #     mavutil.mavlink.MAV_PARAM_TYPE_INT32
        # )
        
        # result =  await self._wait_for_condition(
        #     lambda: self.is_GPS_disabled()
        # )
        
        # if result:
        #     logger.info("-- GPS disabled")
        # else:
        #     logger.error("-- Failed to disable GPS")    
            # Wait and print received parameter messages
        # return result
        
        self.gps_disabled = True
        
   
           
    ''' ACK methods'''    
    def is_armed(self):
        return self.vehicle.recv_match(type="HEARTBEAT", blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
        
    def is_disarmed(self):
        return not (self.vehicle.recv_match(type='HEARTBEAT', blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def is_mode_set(self, mode):
        current_mode = mavutil.mode_string_v10(self.vehicle.recv_match(type='HEARTBEAT', blocking=True))
        return current_mode == mode.value
    
    def is_home_set(self):
        msg = self.vehicle.recv_match(type='COMMAND_ACK', blocking=True)
        return msg and msg.command == mavutil.mavlink.MAV_CMD_DO_SET_HOME and msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED

    def is_altitude_reached(self, target_altitude):
        current_altitude = self.getAltitudeRel()
        return current_altitude >= target_altitude * 0.95
    
    def is_bearing_reached(self, bearing):
        logger.info(f"Checking if bearing is reached: {bearing}")
        attitude = self.getAttitude()
        if not attitude:
            return False  # Return False if attitude data is unavailable

        current_yaw = (math.degrees(attitude["yaw"]) + 360) % 360
        target_yaw = (bearing + 360) % 360
        return abs(current_yaw - target_yaw) <= 2
    

    def is_at_target(self, lat, lon):
        current_location = self.getGPS()
        if not current_location:
            return False
        dlat = lat - current_location["latitude"]
        dlon = lon - current_location["longitude"]
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance < 1.0
        
    ''' Helper methods '''
    # azimuth calculation for bearing
    def calculate_bearing(self, lat1, lon1, lat2, lon2):
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

    ''' Stream methods '''
    async def getGimbalPose(self):
        pass
    
    async def startStreaming(self):
  
        self.streamingThread = StreamingThread(self.vehicle)
        self.streamingThread.start()

    async def getVideoFrame(self):
        if self.streamingThread:
            return [self.streamingThread.grabFrame().tobytes(), self.streamingThread.getFrameShape()]

    async def stopStreaming(self):
        self.streamingThread.stop()
        

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
            
        self.cap = cv2.VideoCapture(url)
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
