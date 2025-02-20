from enum import Enum
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
    
    class FlightMode(Enum):
        LAND = 'LAND'
        RTL = 'RTL'
        LOITER = 'LOITER'
        GUIDED = 'GUIDED'
        
    def __init__(self):
        self.vehicle = None
        self.VEL_TOL = 0.1
        self.ANG_VEL_TOL = 0.01
        self.RTH_ALT = 20
        self.flightmode = None

    def showPIDParams(self):
        # Get rate controller parameters
        roll_p = self.vehicle.parameters['ATC_RAT_RLL_P']
        roll_d = self.vehicle.parameters['ATC_RAT_RLL_D']
        pitch_p = self.vehicle.parameters['ATC_RAT_PIT_P']
        pitch_d = self.vehicle.parameters['ATC_RAT_PIT_D']
        yaw_p = self.vehicle.parameters['ATC_RAT_YAW_P']
        logger.info(f"Roll P: {roll_p}, Roll D: {roll_d}")
        logger.info(f"Pitch P: {pitch_p}, Pitch D: {pitch_d}")
        logger.info(f"Yaw P: {yaw_p}")

    ''' Connect methods '''
    async def connect(self, connection_string):
        logger.info(f"Connecting to drone at {connection_string}...")
        self.vehicle = await asyncio.to_thread(connect, connection_string, wait_ready=True)
        if not self.vehicle.is_armable:
            raise ConnectionFailedException("Drone is not armable.")
        logger.info("-- Connected to drone!")

        # Get rate controller parameters
        logger.info("show original PID params")
        self.showPIDParams()	
        self.vehicle.parameters['ATC_RAT_RLL_P'] = 0.4
        self.vehicle.parameters['ATC_RAT_PIT_P'] = 0.6
        self.vehicle.parameters['ATC_ACCEL_P_MAX'] = 100000
        self.vehicle.parameters['ATC_ACCEL_R_MAX'] = 100000
        self.vehicle.parameters['ATC_ACCEL_Y_MAX'] = 80000

        self.vehicle.parameters['ATC_RAT_RLL_D'] = 0.005
        self.vehicle.parameters['ATC_RAT_PIT_D'] = 0.005

        self.vehicle.parameters['ATC_RAT_YAW_P'] = 0.4
        logger.info("after update PID params")
        self.showPIDParams()

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

    async def getName(self):
        pass

    async def getSatellites(self):
        return await asyncio.to_thread(lambda: self.vehicle.gps_0.satellites_visible)
        
    async def getHeading(self):
        return await asyncio.to_thread(lambda: self.vehicle.heading)
    
    async def getVelocityNEU(self):
        pass
    
    async def getVelocityBody(self):
        pass
    
    async def getRSSI(self):
        pass
    
    async def getBatteryPercentage(self):
        return await asyncio.to_thread(lambda: self.vehicle.battery.level)
        
    async def getAltitudeRel(self):
        return await asyncio.to_thread(lambda: self.vehicle.location.global_relative_frame.alt)

    async def getAttitude(self):
        return await asyncio.to_thread(lambda: {
            "roll": self.vehicle.attitude.roll,
            "pitch": self.vehicle.attitude.pitch,
            "yaw": self.vehicle.attitude.yaw
        })


    ''' Actuation methods '''
    async def hover(self):
        logger.info("-- Hovering")
        
        await asyncio.to_thread(setattr, self.vehicle, 'mode', VehicleMode(NrecDrone.FlightMode.LOITER))

        # Monitor the mode until it's successfully set
        while not self.vehicle.mode.name == "LOITER":
            logger.info("Waiting for LOITER mode...")
            await asyncio.sleep(1)

        logger.info("-- Drone is now in LOITER mode")
    
    async def takeOff(self, target_altitude):
        logger.info("-- Taking off")
        await self.switchMode(NrecDrone.FlightMode.GUIDED)
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
        await self.switchMode(NrecDrone.FlightMode.LAND)
        while self.vehicle.armed:
            logger.info("Waiting for landing...")
            await asyncio.sleep(1)
        logger.info("-- Landed and disarmed")
    
    async def setHome(self, lat, lng, alt):
        logger.info(f"-- Setting home location to {lat}, {lng}, {alt}")
        await asyncio.to_thread(self.vehicle.home_location, LocationGlobalRelative(lat, lng, alt))
        
    async def rth(self):
        logger.info("-- Returning to launch")
        await self.switchMode(NrecDrone.FlightMode.RTL)

    
    async def setAttitude(self, pitch, roll, thrust, yaw):
        logger.info(f"-- Setting attitude: pitch={pitch}, roll={roll}, thrust={thrust}, yaw={yaw}")
        await self.switchMode(NrecDrone.FlightMode.GUIDED)
        # Convert the attitude to a quaternion
        def to_quaternion(roll = 0.0, pitch = 0.0, yaw = 0.0):
            """
            Convert degrees to quaternions
            """
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

        # Create the quaternion for the desired attitude
        q = to_quaternion(roll, pitch, yaw)

        # Create the MAVLink SET_ATTITUDE_TARGET message
        msg = self.vehicle.message_factory.set_attitude_target_encode(
            0,  # time_boot_ms (not used)
            0, 0,  # target_system, target_component
            0b00000000,  # type_mask (all fields are enabled)
            q,  # Quaternion representing the attitude
            0, 0, 0,  # Body angular rates (not used)
            thrust  # Throttle (0 to 1)
        )

        # Send the message
        self.vehicle.send_mavlink(msg)
        self.vehicle.flush()
        
    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info(f"-- Setting velocity: forward_vel={forward_vel}, right_vel={right_vel}, up_vel={up_vel}, angle_vel={angle_vel}")
        await self.switchMode(NrecDrone.FlightMode.GUIDED)
        # MAVLink message for velocity and angular velocity control
        msg = self.vehicle.message_factory.set_position_target_local_ned_encode(
            0,       # time_boot_ms (not used)
            0, 0,    # target system, target component
	    mavutil.mavlink.MAV_FRAME_BODY_NED, # frame
            0b010111000111,  # type_mask (only velocities and yaw rate are enabled)
            0, 0, 0,  # x, y, z positions (not used)
            forward_vel, right_vel, -1 * up_vel,  # x, y, z velocity in m/s
            0, 0, 0,  # x, y, z acceleration (not supported)
	    0, angle_vel  # yaw, yaw_rate in rad/s
        )
        
        # Send the message asynchronously
        self.vehicle.send_mavlink(msg)
        self.vehicle.flush()

        
    async def setGPSLocation(self, lat, lon, alt, bearing):
        target_location = LocationGlobalRelative(lat, lon, alt)
        await self.switchMode(NrecDrone.FlightMode.GUIDED)
        await asyncio.to_thread(self.vehicle.simple_goto, target_location)
        await self.setBearing(bearing)

        await self.arrived(lat, lon)


    async def setTranslatedLocation(self, forward, right, up, angle):
        logger.info(f"-- Translating location: forward={forward}, right={right}, up={up}, angle={angle}")
        await self.switchMode(NrecDrone.FlightMode.GUIDED)
        # Get current location and heading
        current_location = await asyncio.to_thread(lambda: self.vehicle.location.global_relative_frame)
        current_heading = await asyncio.to_thread(lambda: self.vehicle.heading)

        # Convert translation to NED frame based on current heading
        dx = forward * math.cos(math.radians(current_heading)) - right * math.sin(math.radians(current_heading))
        dy = forward * math.sin(math.radians(current_heading)) + right * math.cos(math.radians(current_heading))
        dz = -up  # Positive up means negative altitude in NED

        # Calculate new target location
        target_lat = current_location.lat + (dx / 111320)  # Convert meters to degrees latitude
        target_lon = current_location.lon + (dy / (111320 * math.cos(math.radians(current_location.lat))))  # Convert meters to degrees longitude
        target_alt = current_location.alt + dz

        # Create target location
        target_location = LocationGlobalRelative(target_lat, target_lon, target_alt)

        # Move the drone to the target location
        logger.info(f"-- Moving to target location: lat={target_lat}, lon={target_lon}, alt={target_alt}")
        await asyncio.to_thread(self.vehicle.simple_goto, target_location)

        # Optionally, set yaw angle
        if angle is not None:
            await self.setBearing(angle)

        await self.arrived(target_lat, target_lon)
    
    
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
        
    ''' Helper methods '''
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

    async def switchMode(self, mode):
        if self.flightmode == mode:
            return
        await asyncio.to_thread(setattr, self.vehicle, 'mode', VehicleMode(mode))

