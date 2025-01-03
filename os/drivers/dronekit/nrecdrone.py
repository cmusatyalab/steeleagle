

import math
import time
import mavsdk
from mavsdk import System
from mavsdk.offboard import (OffboardError, PositionNedYaw, VelocityBodyYawspeed, PositionGlobalYaw)
import numpy as np
import asyncio
import logging
logger = logging.getLogger(__name__)


def bearing(origin, destination):
	lat1, lon1 = origin
	lat2, lon2 = destination

	rlat1 = math.radians(lat1)
	rlat2 = math.radians(lat2)
	rlon1 = math.radians(lon1)
	rlon2 = math.radians(lon2)
	dlon = math.radians(lon2-lon1)

	b = math.atan2(math.sin(dlon)*math.cos(rlat2),math.cos(rlat1)*math.sin(rlat2)-math.sin(rlat1)*math.cos(rlat2)*math.cos(dlon))
	bd = math.degrees(b)
	br,bn = divmod(bd+360,360)
	return bn

def get_rot_mat(theta):
    return np.matrix([[math.cos(theta), -math.sin(theta), 0], [math.sin(theta), math.cos(theta), 0], [0, 0, 1]])


class ConnectionFailedException(Exception):
    pass

class NrecDrone():
    def __init__(self):
        # Init the drone
        self.drone = System()

        self.VEL_TOL = 0.1
        self.ANG_VEL_TOL = 0.01
        self.RTH_ALT = 20

    ''' connect methods'''
    async def connect(self):
        # for the spirit drone (drone bridge), it uses the pull model, and requires to specify the ip address of the drone
        # for the simulator (mav proxy), it uses the push model, and requires to bind all addresses
        await self.drone.connect(system_address="udp://:14550")
        # need the workaround for maximum speed from ardupilot
        self.max_speed = 10 

    async def isConnected(self):
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logger.debug(f"-- Connected to drone!")
                return True
            else: 
                return False
    
    ''' Telemetry methods '''    
    async def getTelemetry(self):
        telDict = {}
        try:
            telDict["gps"] = await self.getGPS()
            telDict["relAlt"] = await self.getAltitudeRel()
            telDict["attitude"] = await self.getAttitude()
            telDict["magnetometer"] = await self.getMagnetometerReading()
            telDict["imu"] = await self.getVelocityBody()
            telDict["battery"] = await self.getBatteryPercentage()
            telDict["gimbalAttitude"] = await self.getGimbalPose()
            telDict["satellites"] = await self.getSatellites()
        except Exception as e:
            logger.error(f"Error in getTelemetry(): {e}")
        logger.debug(f"Telemetry data: {telDict}")
        return telDict
    
    async def getSatellites(self):
        gps = await anext(self.drone.telemetry.gps_info())
        return gps.num_satellites
    
    async def getGimbalPose(self):
        return "not implemented"
    
    async def getVelocityBody(self):
        imu = await anext(self.drone.telemetry.imu())
        angular_velocity_frd  = imu.angular_velocity_frd
        return {"forward": angular_velocity_frd.forward_rad_s, "right": angular_velocity_frd.right_rad_s, "up": -1 * angular_velocity_frd.down_m_s}
        
    async def getAttitude(self):
        angular_velocity_body = await anext(self.drone.telemetry.attitude_angular_velocity_body())
        return {"roll": angular_velocity_body.roll_rad_s, "pitch": angular_velocity_body.pitch_rad_s, "yaw": angular_velocity_body.yaw_rad_s}
    
    async def getMagnetometerReading(self):
        health = await anext(self.drone.telemetry.health())
        return health.is_magnetometer_calibration_ok
        
    async def getAltitudeRel(self):
        logger.info(f"Absolute altitude:")
        try:
            position = await anext(self.drone.telemetry.position())
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None
        
        logger.info(f"Relative altitude: {position.relative_altitude_m}")
        return position.relative_altitude_m
    
    async def getGPS(self):
        try:
            gps = await self.drone.telemetry.get_gps_global_origin()
            return {"latitude": gps.latitude_deg, "longitude": gps.longitude_deg, "altitude": gps.altitude_m}
        except Exception as e:
            logger.error(f"Failed to get GPS data: {e}")
            return None
        
        
    async def getBatteryPercentage(self):
        battery = await anext(self.drone.telemetry.battery())
        return int(battery.remaining_percent)
    
    async def getHeading(self):
        return (180 / math.pi)
    
    ''' Actuation methods '''
    async def hovering(self, timeout=None):
        start = time.time()
        # Allow previous command to take effect
        await asyncio.sleep(1)
        async for odometry in self.drone.telemetry.odometry():
            velocity = odometry.velocity_body
            ang_velocity = odometry.angular_velocity_body
            logger.info(f'[MavlinkDrone]: Current velocity: {velocity.x_m_s} {velocity.y_m_s} {velocity.z_m_s} {ang_velocity.yaw_rad_s}')
            if velocity.x_m_s < self.VEL_TOL and velocity.y_m_s < self.VEL_TOL and velocity.z_m_s < self.VEL_TOL and ang_velocity.yaw_rad_s < self.ANG_VEL_TOL:
                break # We are now hovering!
            else:
                if timeout and time.time() - start > timeout: # Break with timeout
                    break
    
    async def hover(self):
        self.drone.action.hold()
        
    async def takeOff(self):
        logger.debug("-- Taking off")
        await self.drone.action.arm()
        await self.drone.action.takeoff()
        await asyncio.sleep(5)
        await self.hovering()
        # Initial setpoint for offboard control
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
        try:
            await self.drone.offboard.start()
        except Exception as e:
            await self.land()

        
    async def land(self):
        logger.debug("-- Landing")
        try:
            await self.drone.offboard.stop()
        except OffboardError as error:
            pass
        await self.drone.action.land()
        await self.drone.action.disarm()

    async def PCMD(self, roll, pitch, yaw, gaz):
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed((pitch/100)*self.max_speed, (roll/100)*self.max_speed, (-1 * gaz/100)*self.max_speed, float(yaw)))

    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(forward_vel, right_vel, -1 * up_vel, angle_vel))
        
    async def moveTo(self, lat, lng, alt):
        # Get bearing to target
        currentLat = await self.getGPS()["latitude"]
        currentLng = await self.getGPS()["longitude"]
        b = bearing((currentLat, currentLng), (lat, lng))
        try:
            await self.drone.offboard.set_position_global(PositionGlobalYaw(lat, lng, alt, b, PositionGlobalYaw.AltitudeType(0)))
        except OffboardError as e:
            logger.error(f'[MavlinkDrone] Offboard command failed: {e.result}')
        logger.info('[MavlinkDrone] Awaiting hover state')
        await self.hovering()
        logger.info('[MavlinkDrone] Got to hover state')

    async def moveBy(self, x, y, z, t):
        v = np.array([x, y, z])
        h = self.getHeading()
        R = get_rot_mat(h)
        res = np.matmul(R, v)
        await self.drone.offboard.set_position_ned(PositionNedYaw(res[0], res[1], -1 * res[2], h + t))
        await self.hovering()

    async def rotateTo(self, theta):
        await self.moveBy(0.0, 0.0, 0.0, theta) 

    async def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        pass
        
    async def rth(self):
        await self.drone.action.set_return_to_launch_altitude(self.RTH_ALT)
        await self.drone.action.return_to_launch()

