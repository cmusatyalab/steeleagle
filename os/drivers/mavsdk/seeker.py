# SPDX-FileCopyrightText: 2025 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
from mavsdk import System
from mavsdk.offboard import (OffboardError, PositionNedYaw, VelocityBodyYawspeed, PositionGlobalYaw)
import logging
import os

logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.INFO),
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class ModalAISeekerDrone:

    VEL_TOL = 0.1
    ANG_VEL_TOL = 0.01
    RTH_ALT = 20

    def __init__(self, **kwargs):
        self.server_address = kwargs['server_address']
        self.drone = System(mavsdk_server_address=self.server_address, port=50051)
        self.active = False

    async def telemetry_subscriber(self):
        async def pos(self):
            async for position in self.drone.telemetry.position():
                self.telemetry['lat'] = position.latitude_deg
                self.telemetry['lng'] = position.longitude_deg
                self.telemetry['alt'] = position.absolute_altitude_m
                self.telemetry['rel-alt'] = position.relative_altitude_m
        async def head(self):
            async for heading in self.drone.telemetry.heading():
                self.telemetry['head'] = heading.heading_deg
        async def battery(self):
            async for battery in self.drone.telemetry.battery():
                self.telemetry['battery'] = battery.remaining_percent
        async def mag(self):
            async for health in self.drone.telemetry.health():
                self.telemetry['mag'] = health.is_magnetometer_calibration_ok
        async def sat(self):
            async for info in self.drone.telemetry.gps_info():
                self.telemetry['sat'] = info.num_satellites

        try:
            await asyncio.gather(pos(self), head(self), battery(self), mag(self), sat(self))
        except Exception as e:
            logger.error(f"Exception: {e}")

    async def connect(self):
        system_address = f"udp://{self.server_address}:14550"
        logger.info(f"Connecting to server at address {system_address}")

        await self.drone.connect(system_address=f"udp://{self.server_address}:14550")
        # Set max speed for use by PCMD
        # self.max_speed = await self.drone.action.get_maximum_speed()
        self.active = True
        self.telemetry = {'battery': 100, 'rssi': 0, 'mag': 0, 'heading': 0, 'sat': 0,
                'lat': 0, 'lng': 0, 'alt': 0, 'rel-alt': 0}
        self.telemetry_task = asyncio.create_task(self.telemetry_subscriber())

    async def isConnected(self):
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logger.debug(f"-- Connected to drone!")
                return True
            else:
                return False

    async def takeOff(self):
        logger.info("Arming drone and taking off")
        await self.drone.action.arm()
        await self.drone.action.takeoff()
        await asyncio.sleep(5)

        logger.info("Waiting for hovering state")
        await self.hovering()

        logger.info("Switching to offboard mode")
        # Initial setpoint for offboard control
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
        try:
            await self.drone.offboard.start()
        except Exception as e:
            logger.error(f"{e}: landing drone")
            await self.land()

    async def land(self):
        logger.info("Landing and disarming drone")
        try:
            await self.drone.offboard.stop()
        except OffboardError as error:
            pass
        await self.drone.action.land()
        await self.drone.action.disarm()

    async def hover(self):
        await self.drone.action.hold()

    async def kill(self):
        self.active = False

    async def rth(self):
        await self.drone.action.set_return_to_launch_altitude(self.RTH_ALT)
        await self.drone.action.return_to_launch()

    async def setHome(self, lat, lng, alt):
        raise NotImplemented()

    async def getHome(self):
        raise NotImplemented()

    async def setVelocity(self, vx, vy, vz, t):
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(vx, vy, vz, t))

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
