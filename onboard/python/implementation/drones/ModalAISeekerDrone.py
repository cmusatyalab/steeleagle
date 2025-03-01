# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import logging
import math
import math as m
import os
import threading
import time

import cv2
import numpy as np
from interfaces import DroneItf
from mavsdk import System
from mavsdk.offboard import (
    OffboardError,
    PositionGlobalYaw,
    PositionNedYaw,
    VelocityBodyYawspeed,
)

logger = logging.getLogger(__name__)
logging.basicConfig()
logger.setLevel(logging.INFO)


def bearing(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination

    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    rlon1 = math.radians(lon1)
    rlon2 = math.radians(lon2)
    dlon = math.radians(lon2 - lon1)

    b = math.atan2(
        math.sin(dlon) * math.cos(rlat2),
        math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon),
    )
    bd = math.degrees(b)
    br, bn = divmod(bd + 360, 360)

    return bn


def get_rot_mat(theta):
    return np.matrix([[m.cos(theta), -m.sin(theta), 0], [m.sin(theta), m.cos(theta), 0], [0, 0, 1]])


class ModalAISeekerDrone(DroneItf.DroneItf):
    VEL_TOL = 0.1
    ANG_VEL_TOL = 0.01
    RTH_ALT = 20

    def __init__(self, **kwargs):
        self.server_address = kwargs["server_address"]
        self.drone = System(mavsdk_server_address=self.server_address, port=50051)
        self.active = False

    """ Awaiting methods """

    async def hovering(self, timeout=None):
        start = time.time()
        # Allow previous command to take effect
        await asyncio.sleep(1)
        async for odometry in self.drone.telemetry.odometry():
            velocity = odometry.velocity_body
            ang_velocity = odometry.angular_velocity_body
            logger.debug(
                f"[MavlinkDrone]: Current velocity: {velocity.x_m_s} {velocity.y_m_s} {velocity.z_m_s} {ang_velocity.yaw_rad_s}"
            )
            if (
                velocity.x_m_s < self.VEL_TOL
                and velocity.y_m_s < self.VEL_TOL
                and velocity.z_m_s < self.VEL_TOL
                and ang_velocity.yaw_rad_s < self.ANG_VEL_TOL
            ):
                break  # We are now hovering!
            else:
                if timeout and time.time() - start > timeout:  # Break with timeout
                    break

    async def telemetry_subscriber(self):
        async def pos(self):
            async for position in self.drone.telemetry.position():
                self.telemetry["lat"] = position.latitude_deg
                self.telemetry["lng"] = position.longitude_deg
                self.telemetry["alt"] = position.absolute_altitude_m
                self.telemetry["rel-alt"] = position.relative_altitude_m

        async def head(self):
            async for heading in self.drone.telemetry.heading():
                self.telemetry["head"] = heading.heading_deg

        async def battery(self):
            async for battery in self.drone.telemetry.battery():
                self.telemetry["battery"] = battery.remaining_percent

        async def mag(self):
            async for health in self.drone.telemetry.health():
                self.telemetry["mag"] = health.is_magnetometer_calibration_ok

        async def sat(self):
            async for info in self.drone.telemetry.gps_info():
                self.telemetry["sat"] = info.num_satellites

        try:
            await asyncio.gather(pos(self), head(self), battery(self), mag(self), sat(self))
        except Exception as e:
            logger.error(f"Exception: {e}")

    """ Connection methods """

    async def connect(self):
        system_address = f"udp://{self.server_address}:14550"
        logger.info(f"Connecting to server at address {system_address}")

        await self.drone.connect(system_address=f"udp://{self.server_address}:14550")
        # Set max speed for use by PCMD
        # self.max_speed = await self.drone.action.get_maximum_speed()
        self.active = True
        self.telemetry = {
            "battery": 100,
            "rssi": 0,
            "mag": 0,
            "heading": 0,
            "sat": 0,
            "lat": 0,
            "lng": 0,
            "alt": 0,
            "rel-alt": 0,
        }
        self.telemetry_task = asyncio.create_task(self.telemetry_subscriber())

    async def isConnected(self):
        async for state in self.drone.core.connection_state():
            return bool(state.is_connected)

    async def disconnect(self):
        await self.drone.action.disarm()
        self.active = False

    """ Streaming methods """

    async def startStreaming(self, **kwargs):
        self.streamingThread = StreamingThread(self.drone, "127.0.0.1:8900")
        self.streamingThread.start()

    async def getVideoFrame(self):
        return self.streamingThread.grabFrame()

    async def stopStreaming(self):
        self.streamingThread.stop()

    async def startOffboardMode(self):
        # Initial setpoint for offboard control
        # await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
        await self.drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, 0.0, 0.0))
        try:
            await self.drone.offboard.start()
        except OffboardError as e:
            logger.error(e)
            logger.info("Landing...")
            await self.land()

    """ Take off / Landing methods """

    async def takeOff(self):
        logger.info("Takeoff: Arming")
        await self.drone.action.arm()
        logger.info("Takeoff: Armed")
        await self.drone.action.takeoff()
        logger.info("Takeoff: Take off done")
        await asyncio.sleep(5)
        await self.hovering()
        # Initial setpoint for offboard control
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
        try:
            await self.drone.offboard.start()
        except Exception as e:
            logger.error(e)
            await self.land()

    async def land(self):
        try:
            await self.drone.offboard.stop()
        except OffboardError:
            pass
        await self.drone.action.land()
        await self.drone.action.disarm()

    async def setHome(self, lat, lng, alt):
        raise NotImplementedError()

    async def rth(self):
        await self.drone.action.set_return_to_launch_altitude(self.RTH_ALT)
        await self.drone.action.return_to_launch()

    """ Movement methods """

    async def PCMD(self, roll, pitch, yaw, gaz):
        await self.drone.offboard.set_velocity_body(
            VelocityBodyYawspeed(
                (pitch / 100) * self.max_speed,
                (roll / 100) * self.max_speed,
                (-1 * gaz / 100) * self.max_speed,
                float(yaw),
            )
        )

    async def moveTo(self, lat, lng, alt):
        # Get bearing to target
        currentLat = await self.getLat()
        currentLng = await self.getLng()
        b = bearing((currentLat, currentLng), (lat, lng))
        try:
            await self.drone.offboard.set_position_global(
                PositionGlobalYaw(lat, lng, alt, b, PositionGlobalYaw.AltitudeType(0))
            )
        except OffboardError as e:
            logger.error(f"[MavlinkDrone] Offboard command failed: {e.result}")
        logger.info("[MavlinkDrone] Awaiting hover state")
        await self.hovering()
        logger.info("[MavlinkDrone] Got to hover state")

    async def moveBy(self, x, y, z, t):
        v = np.array([x, y, z])
        h = await self.getHeading()
        R = get_rot_mat(h)
        res = np.matmul(R, v)

        logger.info(f"Move by: setting position: {res}")
        await self.drone.offboard.set_position_ned(
            PositionNedYaw(res[0, 0], res[0, 1], -1 * res[0, 2], h + t)
        )

        logger.info("Waiting for hovering")
        await self.hovering()
        logger.info("Move by complete")

    async def setVelocity(self, vx, vy, vz, t):
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(vx, vy, vz, t))

    async def rotateTo(self, theta):
        await self.moveBy(0.0, 0.0, 0.0, theta)

    async def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        pass

    async def getGimbalPitch(self):
        pass

    async def getSpeedNED(self):
        pass

    async def getSpeedRel(self):
        pass

    async def hover(self):
        await self.drone.action.hold()

    """ Photography methods """

    async def takePhoto(self):
        raise NotImplementedError()

    async def toggleThermal(self, on):
        raise NotImplementedError()

    """ Status methods """

    async def getName(self):
        return "ModalAISeekerDrone"

    async def getLat(self):
        return self.telemetry["lat"]

    async def getLng(self):
        return self.telemetry["lng"]

    async def getHeading(self):
        return self.telemetry["heading"]

    async def getRelAlt(self):
        return self.telemetry["rel-alt"]

    async def getExactAlt(self):
        return self.telemetry["alt"]

    async def getRSSI(self):
        return 0

    async def getBatteryPercentage(self):
        return round(self.telemetry["battery"] * 100)

    async def getMagnetometerReading(self):
        return self.telemetry["mag"]

    async def getSatellites(self):
        return self.telemetry["sat"]

    # async def getPositionNed(self):
    #    return self.telemetry['

    async def kill(self):
        self.active = False


class StreamingThread(threading.Thread):
    def __init__(self, drone, ip):
        threading.Thread.__init__(self)
        self.currentFrame = None
        self.drone = drone
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
        self.cap = cv2.VideoCapture(f"rtsp://{ip}/live", cv2.CAP_FFMPEG)
        self.isRunning = True

    def run(self):
        try:
            while self.isRunning:
                ret, frame = self.cap.read()
                if len(frame.shape) < 3:  # Grayscale
                    self.currentFrame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else:
                    self.currentFrame = frame
        except Exception as e:
            print(e)

    def grabFrame(self):
        try:
            frame = self.currentFrame.copy()
            return frame
        except Exception:
            # Send a blank frame
            return np.zeros((720, 1280, 3), np.uint8)

    def stop(self):
        self.isRunning = False
