# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import logging
import math
import os
import queue
import threading
import time

import cv2
import numpy as np
import olympe
import olympe.enums.move as move_mode
from interfaces import DroneItf
from olympe import Drone
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.ardrone3.Piloting import PCMD, Landing, TakeOff, moveBy, moveTo
from olympe.messages.ardrone3.PilotingState import (
    AltitudeChanged,
    AttitudeChanged,
    FlyingStateChanged,
    GpsLocationChanged,
    SpeedChanged,
)
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.gimbal import attitude, set_target
from olympe.messages.rth import return_to_home, set_custom_location
from olympe.messages.wifi import rssi_changed

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ParrotAnafiDrone(DroneItf.DroneItf):

    def __init__(self, **kwargs):
        self.dronename = None
        if 'sim' in kwargs:
            self.ip = '10.202.0.1'
        elif 'droneip' in kwargs:
            self.ip = kwargs['droneip']
        else:
            self.ip = '192.168.42.1'
        if 'lowdelay' in kwargs:
            self.lowdelay = True
        else:
            self.lowdelay = False
        if 'dronename' in kwargs:
            self.dronename = kwargs['dronename']
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
        logging.info(f"Drone name is {self.dronename}")
        if self.dronename is not None:
            self.drone.set_device_name(self.dronename)
        self.active = True

    async def isConnected(self):
        return self.drone.connection_state()

    async def disconnect(self):
        self.drone.disconnect()
        self.active = False

    ''' Streaming methods '''

    async def startStreaming(self, **kwargs):
        if self.lowdelay:
            self.streamingThread = LowDelayStreamingThread(self.drone, self.ip)
        else:
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
        await self.hover()
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

    async def getSpeedNED(self):
        return self.drone.get_state(SpeedChanged)

    async def getSpeedRel(self):
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


class StreamingThread(threading.Thread):

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


class LowDelayStreamingThread(threading.Thread):

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
