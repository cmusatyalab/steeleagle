# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import threading
from interfaces import DroneItf
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.rth import set_custom_location, return_to_home
from olympe.messages.ardrone3.PilotingState import moveToChanged
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
from olympe.messages.wifi import rssi_changed
from olympe.messages.battery import capacity
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
import olympe.enums.move as move_mode
import olympe.enums.gimbal as gimbal_mode
import math


class ParrotAnafiDrone(DroneItf.DroneItf):
    
    def __init__(self, **kwargs):
        if 'sim' in kwargs:
            self.ip = '10.202.0.1'
        else:
            self.ip = '192.168.42.1'
        self.drone = Drone(self.ip)
        self.active = False

    ''' Awaiting methods '''

    async def hovering(self, timeout=None):
        # Let the task start before checking for hover state.
        await asyncio.sleep(3)
        start = None
        if timeout is not None:
            start = time.time()
        while True:
            if self.drone(FlyingStateChanged(state="hovering", _policy="check")).success():
                break
            elif start is not None and time.time() - start < timeout:
                break
            else:
                await asyncio.sleep(1)

    ''' Connection methods '''

    async def connect(self):
        self.drone.connect()
        self.active = True

    async def isConnected(self):
        return self.drone.connection_state()

    async def disconnect(self):
        self.drone.disconnect()
        self.active = False

    ''' Streaming methods '''

    async def startStreaming(self, **kwargs):
        self.streamingThread = StreamingThread(self.drone, self.ip)
        self.streamingThread.start()

    async def getVideoFrame(self):
        if self.streamingThread:
            return self.streamingThread.grabFrame()

    async def stopStreaming(self):
        self.streamingThread.stop()

    ''' Take off / Landing methods '''

    async def takeOff(self):
        self.drone(TakeOff())
        await self.hovering()

    async def land(self):
        self.drone(Landing()).wait().success()

    async def setHome(self, lat, lng, alt):
        self.drone(set_custom_location(lat, lng, alt)).wait().success()

    async def rth(self):
        self.hover()
        self.drone(return_to_home())

    ''' Movement methods '''

    async def PCMD(self, roll, pitch, yaw, gaz):
        self.drone(
            PCMD(1, roll, pitch, yaw, gaz, timestampAndSeqNum=0)
        )

    async def moveTo(self, lat, lng, alt):
        self.drone(
            moveTo(lat, lng, alt, move_mode.orientation_mode.to_target, 0.0)
        )
        await self.hovering()

    async def moveBy(self, x, y, z, t):
        self.drone(
            moveBy(x, y, z, t) 
        )
        await self.hovering()

    async def rotateTo(self, theta):
        # TODO: Rotate to exact heading
        pass

    async def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        # The Anafi does not support yaw or roll on its gimbal, thus these
        # parameters are discarded without effect.
        self.drone(set_target(
            gimbal_id=0,
            control_mode="position",
            yaw_frame_of_reference="none",
            yaw=yaw_theta,
            pitch_frame_of_reference="absolute",
            pitch=pitch_theta,
            roll_frame_of_reference="none",
            roll=roll_theta,)
        )

    async def hover(self):
        await self.PCMD(0, 0, 0, 0)

    ''' Photography methods '''

    async def takePhoto(self):
        # TODO: Take a photo and save it to the local drone folder
        pass

    async def toggleThermal(self, on):
        from olympe.messages.thermal import set_mode
        if on:
            self.drone(set_mode(mode="blended")).wait().success()
        else:
            self.drone(set_mode(mode="disabled")).wait().success()

    ''' Status methods '''

    async def getName(self):
        return self.drone._device_name

    async def getLat(self):
        return self.drone.get_state(GpsLocationChanged)["latitude"]

    async def getLng(self):
        return self.drone.get_state(GpsLocationChanged)["longitude"]

    async def getHeading(self):
        return self.drone.get_state(AttitudeChanged)["yaw"] * (180 / math.pi)

    async def getRelAlt(self):
        return self.drone.get_state(AltitudeChanged)["altitude"]

    async def getExactAlt(self):
        pass

    async def getRSSI(self):
        return self.drone.get_state(rssi_changed)["rssi"]

    async def getBatteryPercentage(self):
        return self.drone.get_state(BatteryStateChanged)["percent"]

    async def getMagnetometerReading(self):
        return self.drone.get_state(MagnetoCalibrationRequiredState)["required"] 
    
    async def getGimbalPitch(self):
        return self.drone.get_state(attitude)[0]["pitch_absolute"]
    
    async def getSatellites(self):
        return self.drone.get_state(NumberOfSatelliteChanged)["numberOfSatellite"] 

    async def kill(self):
        self.active = False


import cv2
import numpy as np
import os

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
