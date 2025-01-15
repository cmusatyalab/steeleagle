import math
import time
import asyncio
import logging
from pymavlink import mavutil

logger = logging.getLogger(__name__)

class ConnectionFailedException(Exception):
    pass

class NrecDrone():
    def __init__(self):
        self.master = None
        self.VEL_TOL = 0.1
        self.ANG_VEL_TOL = 0.01
        self.RTH_ALT = 20

    ''' Connect methods '''
    async def connect(self, connection_string):
        logger.info(f"Connecting to drone at {connection_string}...")
        self.master = mavutil.mavlink_connection(connection_string)
        self.master.wait_heartbeat()
        logger.info("-- Connected to drone!")

    async def isConnected(self):
        return self.master is not None

    async def disconnect(self):
        if self.master:
            self.master.close()
            logger.info("-- Disconnected from drone")

    ''' Telemetry methods '''
    async def getTelemetry(self):
        tel_dict = {}
        try:
            tel_dict["gps"] = await self.getGPS()
            tel_dict["relAlt"] = await self.getAltitudeRel()
            tel_dict["attitude"] = await self.getAttitude()
            tel_dict["battery"] = await self.getBatteryPercentage()
            tel_dict["satellites"] = await self.getSatellites()
            tel_dict["heading"] = await self.getHeading()
        except Exception as e:
            logger.error(f"Error in getTelemetry(): {e}")
        logger.debug(f"Telemetry data: {tel_dict}")
        return tel_dict

    async def getGPS(self):
        msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        return {
            "latitude": msg.lat / 1e7,
            "longitude": msg.lon / 1e7,
            "altitude": msg.alt / 1e3
        }

    async def getAltitudeRel(self):
        msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        return msg.relative_alt / 1e3

    async def getAttitude(self):
        msg = self.master.recv_match(type='ATTITUDE', blocking=True)
        return {
            "roll": msg.roll,
            "pitch": msg.pitch,
            "yaw": msg.yaw
        }

    async def getBatteryPercentage(self):
        msg = self.master.recv_match(type='BATTERY_STATUS', blocking=True)
        return msg.battery_remaining

    async def getSatellites(self):
        msg = self.master.recv_match(type='GPS_RAW_INT', blocking=True)
        return msg.satellites_visible

    async def getHeading(self):
        msg = self.master.recv_match(type='VFR_HUD', blocking=True)
        return msg.heading

    async def getVelocityNEU(self):
        msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        return {
            "vx": msg.vx / 100,  # North velocity in m/s
            "vy": msg.vy / 100,  # East velocity in m/s
            "vz": msg.vz / 100   # Down velocity in m/s
        }

    async def getVelocityBody(self):
        msg = self.master.recv_match(type='LOCAL_POSITION_NED', blocking=True)
        return {
            "vx": msg.vx,  # Body-frame X velocity in m/s
            "vy": msg.vy,  # Body-frame Y velocity in m/s
            "vz": msg.vz   # Body-frame Z velocity in m/s
        }

    async def getRSSI(self):
        msg = self.master.recv_match(type='RC_CHANNELS', blocking=True)
        return msg.rssi

    ''' Actuation methods '''
    async def hover(self):
        logger.info("-- Hovering")
        self.setMode("LOITER")
        while not self.master.recv_match(type='HEARTBEAT', blocking=True).custom_mode == 5:
            logger.info("Waiting for LOITER mode...")
            await asyncio.sleep(1)
        logger.info("-- Drone is now in LOITER mode")

    async def takeOff(self, target_altitude):
        logger.info("-- Taking off")
        self.setMode("GUIDED")
        self.arm()
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0,
            0, 0, target_altitude
        )
        while True:
            altitude = await self.getAltitudeRel()
            logger.info(f"Altitude: {altitude}")
            if altitude >= target_altitude * 0.95:
                logger.info("-- Target altitude reached")
                break
            await asyncio.sleep(1)

    async def land(self):
        logger.info("-- Landing")
        self.setMode("LAND")
        while self.master.recv_match(type='HEARTBEAT', blocking=True).base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            logger.info("Waiting for landing...")
            await asyncio.sleep(1)
        logger.info("-- Landed and disarmed")

    async def setHome(self, lat, lng, alt):
        logger.info(f"-- Setting home location to {lat}, {lng}, {alt}")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_HOME,
            1,
            0, 0, 0, 0,
            lat, lng, alt
        )

    async def rth(self):
        logger.info("-- Returning to launch")
        self.setMode("RTL")

    async def setAttitude(self, pitch, roll, thrust, yaw):
        logger.info(f"-- Setting attitude: pitch={pitch}, roll={roll}, thrust={thrust}, yaw={yaw}")

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

        self.master.mav.set_attitude_target_send(
            0,  # time_boot_ms
            self.master.target_system,
            self.master.target_component,
            0b00000000,  # type_mask
            q,  # Quaternion
            0, 0, 0,  # Body angular rates
            thrust  # Throttle
        )

    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info(f"-- Setting velocity: forward_vel={forward_vel}, right_vel={right_vel}, up_vel={up_vel}, angle_vel={angle_vel}")
        self.master.mav.set_position_target_local_ned_send(
            0,  # time_boot_ms
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,  # frame
            0b010111000111,  # type_mask
            0, 0, 0,  # x, y, z positions
            forward_vel, right_vel, -up_vel,  # x, y, z velocity
            0, 0, 0,  # x, y, z acceleration
            0, angle_vel  # yaw, yaw_rate
        )

    async def setGPSLocation(self, lat, lon, alt, bearing):
        self.setMode("GUIDED")
        self.sendGoto(lat, lon, alt)
        await self.setBearing(bearing)
        await self.arrived(lat, lon)

    async def setTranslatedLocation(self, forward, right, up, angle):
        logger.info(f"-- Translating location: forward={forward}, right={right}, up={up}, angle={angle}")
        self.setMode("GUIDED")
        current_location = await self.getGPS()
        current_heading = await self.getHeading()

        dx = forward * math.cos(math.radians(current_heading)) - right * math.sin(math.radians(current_heading))
        dy = forward * math.sin(math.radians(current_heading)) + right * math.cos(math.radians(current_heading))
        dz = -up

        target_lat = current_location["latitude"] + (dx / 111320)
        target_lon = current_location["longitude"] + (dy / (111320 * math.cos(math.radians(current_location["latitude"]))))
        target_alt = current_location["altitude"] + dz

        self.sendGoto(target_lat, target_lon, target_alt)
        if angle is not None:
            await self.setBearing(angle)
        await self.arrived(target_lat, target_lon)

    async def setBearing(self, bearing):
        logger.info(f"-- Setting yaw to {bearing} degrees")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            0,
            bearing,
            0,
            1,
            1,
            0, 0, 0
        )

    ''' Helper methods '''
    def setMode(self, mode):
        self.master.set_mode(mode)

    def arm(self):
        self.master.arducopter_arm()
        logger.info("-- Armed")

    def getDistance(self, location1, location2):
        dlat = location2["latitude"] - location1["latitude"]
        dlon = location2["longitude"] - location1["longitude"]
        return math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5

    async def arrived(self, lat, lon):
        while True:
            current_location = await self.getGPS()
            distance = self.getDistance(current_location, {"latitude": lat, "longitude": lon})
            logger.info(f"Distance to target: {distance} meters")
            if distance < 1.0:
                logger.info("-- Reached target location")
                break
            await asyncio.sleep(1)

    def sendGoto(self, lat, lon, alt):
        self.master.mav.set_position_target_global_int_send(
            0,
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )
