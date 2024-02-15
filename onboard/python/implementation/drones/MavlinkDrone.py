# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
from interfaces import DroneItf
import math
from mavsdk import System
from mavsdk.offboard import (OffboardError, PositionNedYaw, VelocityBodyYawspeed, PositionGlobalYaw)
import time
import numpy as np
import math as m
import logging

logger = logging.getLogger()

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
    return np.matrix([[m.cos(theta), -m.sin(theta), 0], [m.sin(theta), m.cos(theta), 0], [0, 0, 1]])


class MavlinkDrone(DroneItf.DroneItf):

    VEL_TOL = 0.1
    ANG_VEL_TOL = 0.01
    RTH_ALT = 20

    def __init__(self, **kwargs):
        self.drone = System()
        self.active = False

    ''' Awaiting methods '''
    
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
        
    async def telemetry_subscriber(self):
        async def pos(self):
            await self.drone.telemetry.set_rate_position(1)
            async for position in self.drone.telemetry.position():
                self.telemetry['lat'] = position.latitude_deg
                self.telemetry['lng'] = position.longitude_deg
                self.telemetry['alt'] = position.absolute_altitude_m
                self.telemetry['rel-alt'] = position.relative_altitude_m
        async def head(self):
            async for heading in self.drone.telemetry.heading():
                self.telemetry['head'] = heading.heading_deg
        async def battery(self):
            await self.drone.telemetry.set_rate_battery(1)
            async for battery in self.drone.telemetry.battery():
                self.telemetry['battery'] = battery.remaining_percent
        async def mag(self):
            async for health in self.drone.telemetry.health():
                self.telemetry['mag'] = health.is_magnetometer_calibration_ok
        async def sat(self):
            await self.drone.telemetry.set_rate_gps_info(1)
            async for info in self.drone.telemetry.gps_info():
                self.telemetry['sat'] = info.num_satellites

        asyncio.gather(pos(self), head(self), battery(self), mag(self), sat(self))

    ''' Connection methods '''

    async def connect(self):
        await self.drone.connect()
        # Set max speed for use by PCMD
        self.max_speed = await self.drone.action.get_maximum_speed()
        self.active = True
        self.telemetry = {'battery': 100, 'rssi': 0, 'mag': 0, 'heading': 0, 'sat': 0, 
                'lat': 0, 'lng': 0, 'alt': 0, 'rel-alt': 0}
        asyncio.create_task(self.telemetry_subscriber())

    async def isConnected(self):
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                return True
            else:
                return False

    async def disconnect(self):
        await self.drone.action.disarm()
        self.active = False

    ''' Streaming methods '''

    async def startStreaming(self, **kwargs):
        pass

    async def getVideoFrame(self):
        pass

    async def stopStreaming(self):
        pass

    ''' Take off / Landing methods '''

    async def takeOff(self):
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
        try:
            await self.drone.offboard.stop()
        except OffboardError as error:
            pass
        await self.drone.action.land()
        await self.drone.action.disarm()

    async def setHome(self, lat, lng, alt):
        raise NotImplemented()

    async def rth(self):
        await self.drone.action.set_return_to_launch_altitude(self.RTH_ALT)
        await self.drone.action.return_to_launch()

    ''' Movement methods '''

    async def PCMD(self, roll, pitch, yaw, gaz):
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed((pitch/100)*self.max_speed, (roll/100)*self.max_speed, (-1 * gaz/100)*self.max_speed, float(yaw)))

    async def moveTo(self, lat, lng, alt):
        # Get bearing to target
        currentLat = await self.getLat()
        currentLng = await self.getLng()
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
        h = self.get_heading()
        R = get_rot_mat(h)
        res = np.matmul(R, v)
        await self.drone.offboard.set_position_ned(PositionNed(res[0], res[1], -1 * res[2], h + t))
        await self.hovering()

    async def rotateTo(self, theta):
        await self.moveBy(0.0, 0.0, 0.0, theta) 

    async def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        pass

    async def hover(self):
        self.drone.action.hold()

    ''' Photography methods '''

    async def takePhoto(self):
        raise NotImplemented()

    async def toggleThermal(self, on):
        raise NotImplemented()

    ''' Status methods '''

    async def getName(self):
        try:
            product = await self.drone.info.get_product()
            if product.product_name is not None and product.product_name != 'undefined':
                return product.product_name
        except Exception:
            pass

        return "MavlinkDrone"

    async def getLat(self):
        return self.telemetry['lat']

    async def getLng(self):
        return self.telemetry['lng']

    async def getHeading(self):
        return self.telemetry['head']

    async def getRelAlt(self):
        return self.telemetry['rel-alt']

    async def getExactAlt(self):
        return self.telemetry['alt']
    
    async def getRSSI(self):
        return 0

    async def getBatteryPercentage(self):
        return round(self.telemetry['battery'] * 100)

    async def getMagnetometerReading(self):
        return self.telemetry['mag']

    async def getSatellites(self):
        return self.telemetry['sat']

    async def kill(self):
        self.active = False


import cv2
import numpy as np
import os
import threading

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
            while(self.isRunning):
                ret, self.currentFrame = self.cap.read()
        except Exception as e:
            print(e)

    def grabFrame(self):
        try:
            frame = self.currentFrame.copy()
            return frame
        except Exception as e:
            # Send a blank frame
            return np.zeros((720, 1280, 3), np.uint8) 

    def stop(self):
        self.isRunning = False
