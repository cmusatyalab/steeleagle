

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
        await self.drone.connect(system_address="udp://:14540")
    
    async def isConnected(self):
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                print(f"-- Connected to drone!")
                return True
    
    
    async def getTelemetry(self):
        telDict = {}
        telDict["gps"] = await self.getGPS()
        telDict["relAlt"] = await self.getAltitudeRel()
        telDict["attitude"] = await self.getAttitude()
        telDict["magnetometer"] = await self.getMagnetometerReading()
        telDict["imu"] = await self.getVelocityBody()
        telDict["battery"] = await self.getBatteryPercentage()
        telDict["gimbalAttitude"] = await self.getGimbalPose()
        telDict["satellites"] = await self.getSatellites()
        return telDict
    
    async def getSatellites(self):
        gps = await self.drone.telemetry.gps_info().__anext__()
        return gps.num_satellites
    
    async def getGimbalPose(self):
        return "not implemented"
    
    async def getVelocityBody(self):
        imu = self.drone.telemetry.imu().__anext__()
        angular_velocity_frd  = imu.imuangular_velocity_frd
        return {"forward": angular_velocity_frd.forward_rad_s, "right": angular_velocity_frd.right_rad_s, "up": -1 * angular_velocity_frd.down_m_s}
        
    async def getAttitude(self):
        angular_velocity_body = self.drone.telemetry.attitude_angular_velocity_body().__anext__()
        return [angular_velocity_body.roll_rad_s, angular_velocity_body.pitch_rad_s, angular_velocity_body.yaw_rad_s]
    
    async def getMagnetometerReading(self):
        health = await self.drone.telemetry.health().__anext__()
        return health.is_magnetometer_calibration_ok
        
    async def getAltitudeRel(self):
        position = await self.drone.telemetry.position().__anext__()
        return position.relative_altitude_m
 
    async def getGPS(self):
        gps = await self.drone.telemetry.gps_global_origin().__anext__()
        return [gps.latitude_deg, gps.longitude_deg, gps.absolute_altitude_m] 
        
        
    async def getBatteryPercentage(self):
        battery = await self.drone.telemetry.battery().__anext__()
        return battery.remaining_percent

    async def take_off(self):
        print("-- Taking off")
        await self.drone.action.takeoff()
        
    async def land(self):
        print("-- Landing")
        await self.drone.action.land()
        