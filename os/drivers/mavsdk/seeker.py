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

async def anext(iter):
    iter = iter.__aiter__()
    result = await iter.__anext__()
    return result

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
            try:
                async for position in self.drone.telemetry.position():
                    self.telemetry['lat'] = position.latitude_deg
                    self.telemetry['lng'] = position.longitude_deg
                    self.telemetry['alt'] = position.absolute_altitude_m
                    self.telemetry['rel-alt'] = position.relative_altitude_m
            except Exception as e:
                logger.error(f"Failed to get position: {e}")

        async def head(self):
            try:
                async for heading in self.drone.telemetry.heading():
                    self.telemetry['head'] = heading.heading_deg
            except Exception as e:
                logger.error(f"Failed to get heading: {e}")

        async def battery(self):
            try:
                async for battery in self.drone.telemetry.battery():
                    self.telemetry['battery'] = battery.remaining_percent
            except Exception as e:
                logger.error(f"Failed to get battery: {e}")

        async def mag(self):
            try:
                async for health in self.drone.telemetry.health():
                    self.telemetry['mag'] = health.is_magnetometer_calibration_ok
            except Exception as e:
                logger.error(f"Failed to get magnetometer: {e}")

        async def sat(self):
            try:
                async for info in self.drone.telemetry.gps_info():
                    self.telemetry['sat'] = info.num_satellites
            except Exception as e:
                logger.error(f"Failed to get satellites: {e}")

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
        return True

    async def takeOff(self):
        try:
            logger.info("Arming drone and taking off")
            await self.drone.action.arm()
            await self.drone.action.takeoff()
            await asyncio.sleep(5)

            logger.info("Waiting for hovering state")
            await self.hovering()

            logger.info("Switching to offboard mode")
            # Initial setpoint for offboard control
            await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
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
        try:
            await self.drone.action.land()
            await self.drone.action.disarm()
        except Exception as e:
            logger.error(f"Land error: {e}")

    async def hover(self):
        try:
            await self.drone.action.hold()
        except Exception as e:
            logger.error(f"Hover error: {e}")

    async def kill(self):
        self.active = False

    async def rth(self):
        try:
            await self.drone.action.set_return_to_launch_altitude(self.RTH_ALT)
            await self.drone.action.return_to_launch()
        except Exception as e:
            logger.error(f"Rth error: {e}")

    async def setHome(self, lat, lng, alt):
        raise NotImplemented()

    async def getHome(self):
        raise NotImplemented()

    async def setVelocity(self, vx, vy, vz, t):
        try:
            await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(vx, vy, vz, t))
        except Exception as e:
            logger.error("Failed to set velocity: {e}")

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
        try:
            gps = await anext(self.drone.telemetry.gps_info())
            return gps.num_satellites
        except Exception as e:
            logger.error(f"Failed to get satellites: {e}")
            return -1

    async def getGimbalPose(self):
        return "not implemented"

    async def getVelocityBody(self):
        try:
            imu = await anext(self.drone.telemetry.imu())
            angular_velocity_frd  = imu.angular_velocity_frd
            return {"forward": angular_velocity_frd.forward_rad_s, "right": angular_velocity_frd.right_rad_s, "up": -1 * angular_velocity_frd.down_m_s}
        except Exception as e:
            logger.error(f"Failed to get velocity body: {e}")
            return {"forward": -1, "right": -1, "up": -1}

    async def getAttitude(self):
        try:
            angular_velocity_body = await anext(self.drone.telemetry.attitude_angular_velocity_body())
            return {"roll": angular_velocity_body.roll_rad_s, "pitch": angular_velocity_body.pitch_rad_s, "yaw": angular_velocity_body.yaw_rad_s}
        except Exception as e:
            logger.error(f"Failed to get attitude: {e}")
            return {"roll": -1, "pitch": -1, "yaw": -1}

    async def getMagnetometerReading(self):
        try:
            health = await anext(self.drone.telemetry.health())
            return health.is_magnetometer_calibration_ok
        except Exception as e:
            logger.error(f"Failed to get magnetometer reading: {e}")
            return False

    async def getAltitudeRel(self):
        try:
            position = await anext(self.drone.telemetry.position())
            return position.relative_altitude_m
        except Exception as e:
            logger.error(f"Failed to get relative altitude: {e}")
            return -1

    async def getGPS(self):
        try:
            gps = await self.drone.telemetry.get_gps_global_origin()
            return {"latitude": gps.latitude_deg, "longitude": gps.longitude_deg, "altitude": gps.altitude_m}
        except Exception as e:
            logger.error(f"Failed to get GPS data: {e}")
            return {"latitude": -1, "longitude": -1, "altitude": -1}

    async def getBatteryPercentage(self):
        try:
            battery = await anext(self.drone.telemetry.battery())
            return int(battery.remaining_percent)
        except Exception as e:
            logger.error(f"Failed to get battery percentage")
            return -1

    async def getHeading(self):
        return (180 / math.pi)
