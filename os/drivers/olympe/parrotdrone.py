# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import threading
import math
import logging

import olympe
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.rth import set_custom_location, return_to_home
from olympe.messages.ardrone3.PilotingState import moveToChanged
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.ardrone3.PilotingSettingsState import MaxTiltChanged, MaxVerticalSpeedChanged, MaxRotationSpeedChanged
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged, SpeedChanged
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
from olympe.messages.wifi import rssi_changed
from olympe.messages.battery import capacity
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
import olympe.enums.move as move_mode
import olympe.enums.gimbal as gimbal_mode

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ArgumentOutOfBoundsException(Exception):
    pass

class ConnectionFailedException(Exception):
    pass

class ParrotDrone():

    def __init__(self, **kwargs):
        # Handle special arguments
        self.ip = '192.168.42.1'
        if 'sim' in kwargs and kwargs['sim']:
            self.ip = '10.202.0.1'
        self.ffmpeg = False
        if 'ffmpeg' in kwargs and kwargs['ffmpeg']:
            self.ffmpeg = True
        # Create the drone object
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
        self.active = self.drone.connect()
        if not self.active:
            raise ConnectionFailedException("Cannot connect to drone")

    async def isConnected(self):
        return self.drone.connection_state()

    async def disconnect(self):
        self.drone.disconnect()
        self.active = False

    ''' Streaming methods '''

    async def startStreaming(self):
        if not self.ffmpeg:
            self.streamingThread = PDRAWStreamingThread(self.drone, self.ip)
        else:
            self.streamingThread = FFMPEGStreamingThread(self.drone, self.ip)
        self.streamingThread.start()

    async def getVideoFrame(self):
        if self.streamingThread:
            return self.streamingThread.grabFrame().tobytes()

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
        await self.hover()
        self.drone(return_to_home())
    
    async def toggleThermal(self, on):
        from olympe.messages.thermal import set_mode
        if on:
            self.drone(set_mode(mode="blended")).wait().success()
        else:
            self.drone(set_mode(mode="disabled")).wait().success()

    ''' Movement methods '''

    async def setAttitude(self, roll, pitch, gaz, omega):
        # Get attitude bounds from the drone
        tiltMax = self.drone.get_state(MaxTiltChanged)["max"]
        tiltMin = self.drone.get_state(MaxTiltChanged)["min"]
        rotMax = self.drone.get_state(MaxRotationSpeedChanged)["max"]
        rotMin = self.drone.get_state(MaxRotationSpeedChanged)["min"]
        vertMax = self.drone.get_state(MaxVerticalSpeedChanged)["max"]
        vertMin = self.drone.get_state(MaxVerticalSpeedChanged)["min"]

        if roll > tiltMax or pitch > tiltMax or roll < tiltMin or pitch < tiltMin:
            raise ArgumentOutOfBoundsException("Roll or pitch angle outside bounds")
        if omega > rotMax or omega < rotMin:
            raise ArgumentOutOfBoundsException("Rotation speed outside bound")
        if gaz > vertMax or gaz < vertMin:
            raise ArgumentOutOfBoundsException("Vertical speed outside bound")

        self.drone(
            PCMD(1, int((roll * 100) / tiltMax), int((pitch * 100) / tiltMax), 
                int((omega * 100) / rotMax), int((gaz * 100) / vertMax), timestampAndSeqNum=0)
        )

    async def setGlobalPosition(self, lat, lng, alt, theta):
        if theta is None:
            self.drone(
                moveTo(lat, lng, alt, move_mode.orientation_mode.to_target, 0.0)
            )
        else:
            self.drone(
                moveTo(lat, lng, alt, move_mode.orientation_mode.heading_during, theta)
            )
        await self.hovering()

    async def setTranslatedPosition(self, forward, right, down, theta):
        self.drone(
            moveBy(forward, right, down, theta)
        )
        await self.hovering()

    async def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        self.drone(set_target(
            gimbal_id=0,
            control_mode="position",
            yaw_frame_of_reference="absolute",
            yaw=yaw_theta,
            pitch_frame_of_reference="absolute",
            pitch=pitch_theta,
            roll_frame_of_reference="absolute",
            roll=roll_theta,)
        )

    async def hover(self):
        self.drone(PCMD(1, 0, 0, 0, 0, timestampAndSeqNum=0))
    
    ''' Status methods '''

    async def getTelemetry(self):
        telDict = {}
        telDict["gps"] = await self.getGPS()
        telDict["satellites"] = await self.getSatellites()
        telDict["attitude"] = await self.getAttitude()
        telDict["magnetometer"] = await self.getMagnetometerReading()
        telDict["imu"] = await self.getVelocityBody()
        telDict["battery"] = await self.getBatteryPercentage()
        telDict["gimbalAttitude"] = await self.getGimbalPose()
        
        return telDict

    async def getName(self):
        return self.drone._device_name
    
    async def getGPS(self):
        return (self.drone.get_state(GpsLocationChanged)["latitude"],
                self.drone.get_state(GpsLocationChanged)["longitude"])
    
    async def getSatellites(self):
        return self.drone.get_state(NumberOfSatelliteChanged)["numberOfSatellite"]

    async def getHeading(self):
        return self.drone.get_state(AttitudeChanged)["yaw"] * (180 / math.pi)

    async def getAltitudeRel(self):
        return self.drone.get_state(AltitudeChanged)["altitude"]

    async def getAltitudeAbs(self):
        return self.drone.get_state(GpsLocationChanged)["altitude"]

    async def getVelocityNED(self):
        return self.drone.get_state(SpeedChanged)

    async def getVelocityBody(self):
        NED = await self.getSpeedNED()
        vec = np.array([NED["speedX"], NED["speedY"]], dtype=float)
        vecf = np.array([0.0, 1.0], dtype=float)

        hd = (await self.getHeading()) + 90
        fw = np.radians(hd)
        c, s = np.cos(fw), np.sin(fw)
        R1 = np.array(((c, -s), (s, c)))
        vecf = np.dot(R1, vecf)

        vecr = np.array([0.0, 1.0], dtype=float)
        rt = np.radians(hd + 90)
        c, s = np.cos(rt), np.sin(rt)
        R2 = np.array(((c,-s), (s, c)))
        vecr = np.dot(R2, vecr)

        res = {"speedX": np.dot(vec, vecf) * -1, "speedY": np.dot(vec, vecr) * -1, "speedZ": NED["speedZ"]}
        return res

    async def getRSSI(self):
        return self.drone.get_state(rssi_changed)["rssi"]

    async def getBatteryPercentage(self):
        return self.drone.get_state(BatteryStateChanged)["percent"]

    async def getMagnetometerReading(self):
        return self.drone.get_state(MagnetoCalibrationRequiredState)["required"]

    async def getGimbalPose(self):
        return {"roll": 0.0, "pitch": self.drone.get_state(attitude)[0]["pitch_absolute"], "yaw": 0.0}

    async def getAttitude(self):
        att = self.drone.get_state(AttitudeChanged)
        rad_to_deg = 180 / math.pi
        return {"roll": att["roll"] * rad_to_deg, "pitch": att["pitch"] * rad_to_deg,
                "yaw": att["yaw"] * rad_to_deg}

    ''' Emergency methods '''

    async def kill(self):
        self.active = False


import cv2
import numpy as np
import os

class FFMPEGStreamingThread(threading.Thread):

    def __init__(self, drone, ip):
        threading.Thread.__init__(self)
        self.currentFrame = None
        self.drone = drone
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
        self.cap = cv2.VideoCapture(f"rtsp://{ip}/live", cv2.CAP_FFMPEG, (cv2.CAP_PROP_N_THREADS, 1))
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

import queue

class PDRAWStreamingThread(threading.Thread):

    def __init__(self, drone, ip, save_frames = False):
        threading.Thread.__init__(self)
        self.drone = drone
        self.frame_queue = queue.Queue()
        self.currentFrame = np.zeros((720, 1280, 3), np.uint8)
        self.save_frames = save_frames
        self.frames_recd = 0

        self.drone.streaming.set_callbacks(
            raw_cb=self.yuvFrameCb,
            h264_cb=self.h264FrameCb,
            start_cb=self.startCb,
            end_cb=self.endCb,
            flush_raw_cb=self.flushCb,
        )

    def run(self):
        self.isRunning = True
        self.drone.streaming.start()

        while self.isRunning:
            try:
                yuv_frame = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self.copyFrame(yuv_frame)
            yuv_frame.unref()

    def grabFrame(self):
        try:
            frame = self.currentFrame.copy()
            return frame
        except Exception as e:
            # Send a blank frame
            return np.zeros((720, 1280, 3), np.uint8)

    def copyFrame(self, yuv_frame):
        info = yuv_frame.info()

        height, width = (  # noqa
            info["raw"]["frame"]["info"]["height"],
            info["raw"]["frame"]["info"]["width"],
        )

        cv2_cvt_color_flag = {
            olympe.VDEF_I420: cv2.COLOR_YUV2BGR_I420,
            olympe.VDEF_NV12: cv2.COLOR_YUV2BGR_NV12,
        }[yuv_frame.format()]

        self.currentFrame = cv2.cvtColor(yuv_frame.as_ndarray(), cv2_cvt_color_flag)

    ''' Callbacks '''

    def yuvFrameCb(self, yuv_frame):
        """
        This function will be called by Olympe for each decoded YUV frame.

            :type yuv_frame: olympe.VideoFrame
        """
        yuv_frame.ref()
        fps = 30 // float(os.environ.get('FPS'))
        self.frames_recd += 1
        if self.frames_recd == fps:
            self.frame_queue.put_nowait(yuv_frame)
            self.frames_recd = 0
        else:
            yuv_frame.unref()

    def flushCb(self, stream):
        if stream["vdef_format"] != olympe.VDEF_I420:
            return True
        while not self.frame_queue.empty():
            self.frame_queue.get_nowait().unref()
        return True

    def startCb(self):
        pass

    def endCb(self):
        pass

    def h264FrameCb(self, h264_frame):
        pass

    def stop(self):
        self.isRunning = False
        # Properly stop the video stream and disconnect
        assert self.drone.streaming.stop()
