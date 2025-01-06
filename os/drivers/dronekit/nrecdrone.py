import math
import time
import collections

collections.MutableMapping = collections.abc.MutableMapping

from dronekit import connect, VehicleMode, LocationGlobalRelative
from pymavlink import mavutil
import logging
import asyncio

logger = logging.getLogger(__name__)

class ConnectionFailedException(Exception):
    pass

class NrecDrone():
    def __init__(self):
        self.vehicle = None
        self.VEL_TOL = 0.1
        self.ANG_VEL_TOL = 0.01
        self.RTH_ALT = 20

    ''' Connect methods '''
    async def connect(self, connection_string):
        logger.info(f"Connecting to drone at {connection_string}...")
        self.vehicle = await asyncio.to_thread(connect, connection_string, wait_ready=True)
        if not self.vehicle.is_armable:
            raise ConnectionFailedException("Drone is not armable.")
        logger.info("-- Connected to drone!")

    async def isConnected(self):
        return self.vehicle and self.vehicle.is_armable
    
    async def disconnect(self):
        if self.vehicle:
            await asyncio.to_thread(self.vehicle.close)
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
        except Exception as e:
            logger.error(f"Error in get_telemetry(): {e}")
        logger.debug(f"Telemetry data: {tel_dict}")
        return tel_dict

    async def getGPS(self):
        return await asyncio.to_thread(lambda: {
            "latitude": self.vehicle.location.global_frame.lat,
            "longitude": self.vehicle.location.global_frame.lon,
            "altitude": self.vehicle.location.global_frame.alt
        })

    async def getAltitudeRel(self):
        return await asyncio.to_thread(lambda: self.vehicle.location.global_relative_frame.alt)

    async def getAttitude(self):
        return await asyncio.to_thread(lambda: {
            "roll": self.vehicle.attitude.roll,
            "pitch": self.vehicle.attitude.pitch,
            "yaw": self.vehicle.attitude.yaw
        })

    async def getBatteryPercentage(self):
        return await asyncio.to_thread(lambda: self.vehicle.battery.level)

    async def getSatellites(self):
        return await asyncio.to_thread(lambda: self.vehicle.gps_0.satellites_visible)

    ''' Actuation methods '''
    async def takeOff(self, target_altitude):
        logger.info("-- Taking off")
        await asyncio.to_thread(setattr, self.vehicle, 'mode', VehicleMode("GUIDED"))
        await asyncio.to_thread(self.vehicle.arm, wait=True)
        await asyncio.to_thread(self.vehicle.simple_takeoff, target_altitude)

        while True:
            altitude = await self.getAltitudeRel()
            logger.info(f"Altitude: {altitude}")
            if altitude >= target_altitude * 0.95:
                logger.info("-- Target altitude reached")
                break
            await asyncio.sleep(1)

    async def land(self):
        logger.info("-- Landing")
        await asyncio.to_thread(setattr, self.vehicle, 'mode', VehicleMode("LAND"))
        while self.vehicle.armed:
            logger.info("Waiting for landing...")
            await asyncio.sleep(1)
        logger.info("-- Landed and disarmed")

    async def setGPSLocation(self, lat, lon, alt, bearing):
        target_location = LocationGlobalRelative(lat, lon, alt)
        await asyncio.to_thread(self.vehicle.simple_goto, target_location)
        await self.setBearing(bearing)
            
        while True:
            current_location = await self.getGPS()
            distance = self.getDistance(current_location, {"lat": lat, "lon": lon})
            logger.info(f"Distance to target: {distance} meters")
            if distance < 1.0:
                logger.info("-- Reached target location")
                break
            await asyncio.sleep(1)

    async def rth(self):
        logger.info("-- Returning to launch")
        await asyncio.to_thread(setattr, self.vehicle, 'mode', VehicleMode("RTL"))

    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info(f"-- Setting velocity: forward_vel={forward_vel}, right_vel={right_vel}, up_vel={up_vel}, angle_vel={angle_vel}")
        
        # MAVLink message for velocity and angular velocity control
        msg = self.vehicle.message_factory.set_position_target_local_ned_encode(
            0,       # time_boot_ms (not used)
            0, 0,    # target system, target component
            0b0000111111000111,  # type_mask (only velocities and yaw rate are enabled)
            0, 0, 0,  # x, y, z positions (not used)
            forward_vel, right_vel, up_vel,  # x, y, z velocity in m/s
            0, 0, 0,  # x, y, z acceleration (not supported)
            0, angle_vel  # yaw, yaw_rate in rad/s
        )
        
        # Send the message asynchronously
        await asyncio.to_thread(self.vehicle.send_mavlink, msg)
        # self.vehicle.flush()

    ''' Helper methods '''
    def getDistance(self, location1, location2):
        dlat = location2["lat"] - location1["latitude"]
        dlon = location2["lon"] - location1["longitude"]
        return math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
    
    async def setBearing(self, bearing):
        """
        Sets the yaw (bearing) of the drone.
        
        :param bearing: Desired yaw in degrees (0-360)
        """
        logger.info(f"-- Setting yaw to {bearing} degrees")
        msg = self.vehicle.message_factory.command_long_encode(
            0, 0,    # target system, target component
            mavutil.mavlink.MAV_CMD_CONDITION_YAW, # command
            0,       # confirmation
            bearing, # param1: Yaw angle in degrees
            0,       # param2: Yaw speed (0 = default)
            1,       # param3: Direction (-1: CCW, 1: CW)
            1,       # param4: Relative (1) or absolute (0)
            0, 0, 0  # param5 ~ 7 (unused)
        )
        await asyncio.to_thread(self.vehicle.send_mavlink, msg)


