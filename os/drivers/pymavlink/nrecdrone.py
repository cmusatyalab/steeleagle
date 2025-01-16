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
        self.mode_mapping = None
        self.VEL_TOL = 0.1
        self.ANG_VEL_TOL = 0.01
        self.RTH_ALT = 20


    ''' Connect methods '''
    async def connect(self, connection_string):
        logger.info(f"Connecting to drone at {connection_string}...")
        self.vehicle = mavutil.mavlink_connection(connection_string)
        self.vehicle.wait_heartbeat()
        logger.info("-- Connected to drone!")
        self.mode_mapping = self.vehicle.mode_mapping()
        logger.info(f"Mode mapping: {self.mode_mapping}")

    async def isConnected(self):
        return self.vehicle is not None

    async def disconnect(self):
        if self.vehicle:
            self.vehicle.close()
            logger.info("-- Disconnected from drone")

    ''' Telemetry methods '''
    async def getTelemetry(self):
        tel_dict = {}
        try:
            tel_dict["name"] = await self.getName()
            tel_dict["gps"] = await self.getGPS()
            tel_dict["relAlt"] = await self.getAltitudeRel()
            tel_dict["attitude"] = await self.getAttitude()
            tel_dict["magnetometer"] = await self.getMagnetometerReading()
            tel_dict["imu"] = await self.getVelocityNEU()
            tel_dict["battery"] = await self.getBatteryPercentage()
            tel_dict["satellites"] = await self.getSatellites()
            tel_dict["heading"] = await self.getHeading()
        except Exception as e:
            logger.error(f"Error in getTelemetry(): {e}")
        logger.debug(f"Telemetry data: {tel_dict}")
        return tel_dict

    async def getName(self):
        drone_id = os.environ.get('DRONE_ID')
        logger.info(f"Starting driver for drone {drone_id}") 
        return drone_id
    
    async def getMagnetometerReading(self):
        logger.info("-- Getting magnetometer reading")
        # Magnetometer data is typically in the RAW_IMU message
        msg = self.vehicle.recv_match(type='RAW_IMU', blocking=True)
        if msg:
            mag_data = {
                "x": msg.xmag,
                "y": msg.ymag,
                "z": msg.zmag
            }
            logger.info(f"-- Magnetometer reading: {mag_data}")
            return mag_data
        else:
            logger.warning("-- Unable to retrieve magnetometer reading")
            return {"x": None, "y": None, "z": None}
    
    async def getGPS(self):
        msg = self.vehicle.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        return {
            "latitude": msg.lat / 1e7,
            "longitude": msg.lon / 1e7,
            "altitude": msg.alt / 1e3
        }

    async def getAltitudeRel(self):
        msg = self.vehicle.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        return msg.relative_alt / 1e3

    async def getAttitude(self):
        msg = self.vehicle.recv_match(type='ATTITUDE', blocking=True)
        return {
            "roll": msg.roll,
            "pitch": msg.pitch,
            "yaw": msg.yaw
        }

    async def getBatteryPercentage(self):
        msg = self.vehicle.recv_match(type='BATTERY_STATUS', blocking=True)
        return msg.battery_remaining

    async def getSatellites(self):
        msg = self.vehicle.recv_match(type='GPS_RAW_INT', blocking=True)
        return msg.satellites_visible

    async def getHeading(self):
        msg = self.vehicle.recv_match(type='VFR_HUD', blocking=True)
        return msg.heading

    async def getVelocityNEU(self):
        msg = self.vehicle.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        return {
            "forward": msg.vx / 100,  # North velocity in m/s
            "right": msg.vy / 100,  # East velocity in m/s
            "up": msg.vz / 100   # Down velocity in m/s
        }

    async def getVelocityBody(self):
        msg = self.vehicle.recv_match(type='LOCAL_POSITION_NED', blocking=True)
        return {
            "vx": msg.vx,  # Body-frame X velocity in m/s
            "vy": msg.vy,  # Body-frame Y velocity in m/s
            "vz": msg.vz   # Body-frame Z velocity in m/s
        }

    async def getRSSI(self):
        msg = self.vehicle.recv_match(type='RC_CHANNELS', blocking=True)
        return msg.rssi

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
        
        await self.wait_for_condition(
            self.is_altitude_reached(target_altitude),
            timeout=60,
            interval=1
        )
        
        logger.info("-- Target altitude reached")

    async def land(self):
        logger.info("-- Landing")
        if await self.switchMode(NrecDrone.FlightMode.LAND) == False:
            logger.error("Failed to set mode to LAND")
            return

        await self.wait_for_condition(
            self.is_disarmed,
            timeout=60,
            interval=1
        )
        
        logger.info("-- Landed and disarmed")

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

        await self.wait_for_condition(
            self.is_home_set,
            timeout=30,
            interval=0.1
        )
        
        logger.info("-- Home location set successfully")

    async def rth(self):
        logger.info("-- Returning to launch")
        if await self.switchMode(NrecDrone.FlightMode.RTL) == False:
            logger.error("Failed to set mode to RTL")
            return

        await self.wait_for_condition(
            self.is_disarmed,
            timeout=60,
            interval=1
        )
        
        logger.info("-- Returned to launch and disarmed")

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
        
        await self.wait_for_condition(
            self.is_at_target(lat, lon),
            timeout=60,
            interval=1
        )
        
        logger.info("-- Reached target GPS location")

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
        
        await self.wait_for_condition(
            self.is_at_target(target_lat, target_lon),
            timeout=60,
            interval=1
        )
        
        logger.info("-- Reached target translated location")

    async def setBearing(self, bearing):
        logger.info(f"-- Setting yaw to {bearing} degrees")
        
        if await self.switchMode(NrecDrone.FlightMode.GUIDED) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            0,
            bearing,
            0,
            1,
            1,
            0, 0, 0
        )
        
        await self.wait_for_condition(
            self.is_bearing_reached(bearing),
            timeout=30,
            interval=0.5
        )
        
        logger.info(f"-- Yaw successfully set to {bearing} degrees")

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


        return await self.wait_for_condition(
            self.is_armed,
            timeout=30,
            interval=1
        )

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

        return await self.wait_for_condition(
            self.is_disarmed,
            timeout=30,
            interval=1
        )

    ''' ACK methods'''
    async def is_altitude_reached(self, target_altitude):
            current_altitude = await self.getAltitudeRel()
            return current_altitude >= target_altitude * 0.95
    
    async def is_armed(self):
            return self.vehicle.recv_match(type="HEARTBEAT", blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
        
    async def is_disarmed(self):
            return not (self.vehicle.recv_match(type='HEARTBEAT', blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    async def is_home_set(self):
        msg = self.vehicle.recv_match(type='COMMAND_ACK', blocking=True)
        return msg and msg.command == mavutil.mavlink.MAV_CMD_DO_SET_HOME and msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED
    
    async def is_bearing_reached(self, bearing):
        yaw = math.degrees(self.vehicle.recv_match(type='ATTITUDE', blocking=True).yaw)
        current_yaw = (yaw + 360) % 360
        target_yaw = (bearing + 360) % 360
        return abs(current_yaw - target_yaw) <= 2
    
    async def is_mode_set(self, mode_key):
        current_mode = mavutil.mode_string_v10(self.vehicle.recv_match(type='HEARTBEAT', blocking=True))
        return current_mode == mode_key

    async def is_at_target(self, lat, lon):
            current_location = await self.getGPS()
            distance = self.getDistance(current_location, {"latitude": lat, "longitude": lon})
            return distance < 1.0
        
    ''' Helper methods '''
    async def wait_for_condition(self, condition_fn, timeout=30, interval=0.5):
        start_time = time.time()
        while True:
            if await condition_fn():
                return True
            if time.time() - start_time > timeout:
                logger.error("-- Timeout waiting for condition")
                return False
            await asyncio.sleep(interval)
            
    async def switchMode(self, mode):
        logger.info(f"Switching mode to {mode}")
        mode_key = mode.value
        logger.info(f"mode map: {self.mode_mapping}, mode_key: {mode_key}")
        if mode_key not in self.mode_mapping:
            logger.info(f"Mode {mode_key} not supported!")
            return False
        mode_id = self.mode_mapping[mode_key]
        self.vehicle.mav.set_mode_send(
            self.vehicle.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        
        return await self.wait_for_condition(
            self.is_mode_set(mode_key),
            timeout=30,
            interval=1
        )
        
    def getDistance(self, location1, location2):
        dlat = location2["latitude"] - location1["latitude"]
        dlon = location2["longitude"] - location1["longitude"]
        return math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5


    ''' Stream methods '''
    async def getGimbalPose(self):
        pass