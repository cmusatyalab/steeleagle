

from mavsdk import System
import asyncio
import logging
logger = logging.getLogger(__name__)



class ConnectionFailedException(Exception):
    pass

class NrecDrone():
    def __init__(self):
        # Init the drone
        self.drone = System()


    async def connect(self):
        await self.drone.connect(system_address="udp://:14550")
    
    async def isConnected(self):
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                print(f"-- Connected to drone!")
                return True
    
        
    async def getTelemetry(self):
        telDict = {}
        try:
            # telDict["gps"] = await self.getGPS()
            # telDict["relAlt"] = await self.getAltitudeRel()
            telDict["attitude"] = await self.getAttitude()
            telDict["magnetometer"] = await self.getMagnetometerReading()
            # telDict["imu"] = await self.getVelocityBody()
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
        return battery.remaining_percent

    async def takeOff(self):
        print("-- Taking off")
        await self.drone.action.takeoff()
        
    async def land(self):
        print("-- Landing")
        await self.drone.action.land()
        