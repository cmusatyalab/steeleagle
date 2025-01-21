from enum import Enum
import math
import os
import time
import asyncio
import logging
from pymavlink import mavutil

logger = logging.getLogger(__name__)

class ConnectionFailedException(Exception):
    pass

class NrecDrone():
    
    class FlightMode(Enum):
        LAND = 'LAND'
        RTL = 'RTL'
        LOITER = 'LOITER'
        GUIDED = 'GUIDED'
        
    def __init__(self):
        self.vehicle = None
        self.mode = None
        self.mode_mapping = None
        self.listener_task = None


    ''' Connect methods '''
    async def connect(self, connection_string):
        # connect to drone
        logger.info(f"Connecting to drone at {connection_string}...")
        self.vehicle = mavutil.mavlink_connection(connection_string)
        self.vehicle.wait_heartbeat()
        logger.info("-- Connected to drone!")
        self.mode_mapping = self.vehicle.mode_mapping()
        logger.info(f"Mode mapping: {self.mode_mapping}")
        
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
        # if await self.switchMode(NrecDrone.FlightMode.LOITER) == False:
        #     logger.error("Failed to set mode to LOITER")
        #     return
        # logger.info("-- Drone is now in LOITER mode")

    async def takeOff(self, target_altitude):
        logger.info("-- Taking off")
        
        if await self.switchMode(NrecDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        if await self.arm() == False:
            logger.error("Failed to arm the drone")
            return
        
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0,
            0, 0, target_altitude
        )
        
        result = await self._wait_for_condition(
            lambda: self.is_altitude_reached(target_altitude),
            timeout=60,
            interval=1
        )
        if result:
            logger.info("-- Altitude reached")
        else:
            logger.error("-- Failed to reach target altitude")

        return result

    async def land(self):
        logger.info("-- Landing")
        if await self.switchMode(NrecDrone.FlightMode.LAND) == False:
            logger.error("Failed to set mode to LAND")
            return

        result = await self._wait_for_condition(
            lambda: self.is_disarmed(),
            timeout=60,
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
            timeout=30,
            interval=0.1
        )
        
        if result:
            logger.info("-- Home location set successfully")
        else:
            logger.error("-- Failed to set home location")
        
        return result
    
    async def rth(self):
        logger.info("-- Returning to launch")
        if await self.switchMode(NrecDrone.FlightMode.RTL) == False:
            logger.error("Failed to set mode to RTL")
            return

        result = await self._wait_for_condition(
            lambda: self.is_disarmed(),
            timeout=60,
            interval=1
        )
        
        if result:
            logger.info("-- Returned to launch and disarmed")
        else:   
            logger.error("-- RTL failed")

    async def setAttitude(self, pitch, roll, thrust, yaw):
        logger.info(f"-- Setting attitude: pitch={pitch}, roll={roll}, thrust={thrust}, yaw={yaw}")

        if await self.switchMode(NrecDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        def to_quaternion(roll=0.0, pitch=0.0, yaw=0.0):
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

        q = to_quaternion(roll, pitch, yaw)

        self.vehicle.mav.set_attitude_target_send(
            0,  # time_boot_ms
            self.vehicle.target_system,
            self.vehicle.target_component,
            0b00000000,  # type_mask
            q,  # Quaternion
            0, 0, 0,  # Body angular rates
            thrust  # Throttle
        )
        logger.info("-- setAttitude sent successfully")
        #  continuous control: no blocking wait

    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info(f"-- Setting velocity: forward_vel={forward_vel}, right_vel={right_vel}, up_vel={up_vel}, angle_vel={angle_vel}")
        
        if await self.switchMode(NrecDrone.FlightMode.GUIDED) == False:
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
        #  continuous control: no blocking wait

    async def setGPSLocation(self, lat, lon, alt, bearing):
        logger.info(f"-- Setting GPS location: lat={lat}, lon={lon}, alt={alt}, bearing={bearing}")
        
        if await self.switchMode(NrecDrone.FlightMode.GUIDED) == False:
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
        
        if bearing is not None: await self.setBearing(bearing)
        
        result = await self._wait_for_condition(
            lambda: self.is_at_target(lat, lon),
            timeout=60,
            interval=1
        )
        
        if result:  
            logger.info("-- Reached target GPS location")
        else:  
            logger.info("-- Failed to reach target GPS location")
        
        return result

    async def setTranslatedLocation(self, forward, right, up, angle):
        logger.info(f"-- Translating location: forward={forward}, right={right}, up={up}, angle={angle}")
        
        if await self.switchMode(NrecDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        current_location = await self.getGPS()
        current_heading = await self.getHeading()

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
            timeout=60,
            interval=1
        )
        
        if  result:
            logger.info("-- Reached target translated location")
        else:
            logger.error("-- Failed to reach target translated location")
        
        return result

    async def setBearing(self, bearing):
        logger.info(f"-- Setting yaw to {bearing} degrees")
        
        if await self.switchMode(NrecDrone.FlightMode.GUIDED) == False:
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
            timeout=30,
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


        result =  self._wait_for_condition(
            lambda: self.is_armed(),
            timeout=30,
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
            timeout=30,
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
        self.vehicle.mav.set_mode_send(
            self.vehicle.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        
        result = await self._wait_for_condition(
            lambda: self.is_mode_set(mode_target),
            timeout=30,
            interval=1
        )
        
        if result:
            self.mode = mode
            logger.info(f"Mode switched to {mode_target}")
        
        return result
        
    ''' ACK methods'''    
    def is_armed(self):
        return self.vehicle.recv_match(type="HEARTBEAT", blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
        
    def is_disarmed(self):
        return not (self.vehicle.recv_match(type='HEARTBEAT', blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def is_mode_set(self, mode_target):
        current_mode = mavutil.mode_string_v10(self.vehicle.recv_match(type='HEARTBEAT', blocking=True))
        return current_mode == mode_target
    
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

    ''' Stream methods '''
    async def getGimbalPose(self):
        pass
