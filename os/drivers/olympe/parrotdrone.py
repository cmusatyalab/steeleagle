# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import threading
import math
import logging
import time

import olympe
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.rth import set_custom_location, return_to_home
from olympe.messages.ardrone3.PilotingState import moveToChanged
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.ardrone3.PilotingSettingsState import MaxTiltChanged
from olympe.messages.ardrone3.SpeedSettingsState import MaxVerticalSpeedChanged, MaxRotationSpeedChanged
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged, SpeedChanged
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
from olympe.messages.wifi import rssi_changed
from olympe.messages.battery import capacity
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
import olympe.enums.move as move_mode
import olympe.enums.gimbal as gimbal_mode
from enum import Enum

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ArgumentOutOfBoundsException(Exception):
    pass

class ConnectionFailedException(Exception):
    pass

class ParrotDrone():

    
    class FlightMode(Enum):
        MANUAL = 1
        ATTITUDE = 2
        VELOCITY = 3
        GUIDED = 4
    
    def __init__(self, **kwargs):
        # Handle special arguments
        self.ip = '192.168.42.1'
        if 'sim' in kwargs and kwargs['sim']:
            self.ip = '10.202.0.1'
        if 'ip' in kwargs:
            self.ip = kwargs['ip']
        self.ffmpeg = False
        if 'ffmpeg' in kwargs and kwargs['ffmpeg']:
            self.ffmpeg = True
        # Create the drone object
        self.drone = Drone(self.ip)
        self.active = False
        # Drone flight modes and setpoints
        self.attitudeSP = None
        self.velocitySP = None
        self.PIDTask = None
        self.flightmode = ParrotDrone.FlightMode.MANUAL

    ''' Awaiting methods '''

    async def switchModes(self, mode):
        if self.flightmode == mode:
            return
        else:
            # Cancel the running PID task
            if self.PIDTask:
                self.PIDTask.cancel()
                await self.PIDTask
            self.PIDTask = None
            self.flightmode = mode

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
    
    ''' Background PID tasks '''

    async def _attitudePID(self):
        try:
            pitch_PID = {"Kp": 0.4, "Kd": 0.1, "Ki": 0.001, "PrevI": 0.0}
            roll_PID = {"Kp": 0.4, "Kd": 0.1, "Ki": 0.001, "PrevI": 0.0}
            yaw_PID = {"Kp": 2.2, "Kd": 1.0, "Ki": 0.001, "PrevI": 0.0}
            ep = {"pitch": 0.0, "roll": 0.0, "yaw": 0.0}
            tp = None
            prevVal = None

            tiltMax = self.drone.get_state(MaxTiltChanged)["max"]
            tiltMin = self.drone.get_state(MaxTiltChanged)["min"]
            
            def clamp(val, mini, maxi):
                return max(mini, min(val, maxi))

            def updatePID(e, ep, tp, ts, pidDict):
                P = pidDict["Kp"] * e
                I = pidDict["Ki"] * (ts - tp)
                if e < 0.0:
                    I *= -1
                elif e == 0.0 or I * pidDict["PrevI"] < 0:
                    I = 0.0
                D = pidDict["Kd"] * (e - ep) / (ts - tp)
                
                return P, I, D

            while self.flightmode == ParrotDrone.FlightMode.ATTITUDE:
                ts = round(time.time() * 1000)
                current = await self.getAttitude()
                pitch, roll, thrust, theta = self.attitudeSP
                if theta is None:
                    theta = current["yaw"]

                error = {}
                error["pitch"] = -1 * (pitch - current["pitch"])
                if abs(error["pitch"]) < 1.0:
                    error["pitch"] = 0.0
                error["roll"] = roll - current["roll"]
                if abs(error["roll"]) < 1.0:
                    error["roll"] = 0.0
                error["yaw"] = theta - current["yaw"]
                if abs(error["yaw"]) < 1.0:
                    error["yaw"] = 0.0

                # On first loop through, set previous timestamp and error
                # to dummy values.
                if tp is None or (ts - tp) > 1000:
                    tp = ts - 1
                    ep = error

                P, I, D = updatePID(error["pitch"], ep["pitch"], tp, ts, pitch_PID)
                pitch_PID["PrevI"] += I
                pitch = P + I + D
                
                P, I, D = updatePID(error["roll"], ep["roll"], tp, ts, roll_PID)
                roll_PID["PrevI"] += I
                roll = P + I + D

                P, I, D = updatePID(error["yaw"], ep["yaw"], tp, ts, yaw_PID)
                yaw_PID["PrevI"] += I
                yaw = P + I + D
                
                prevPitch = 0
                prevRoll = 0
                if prevVal is not None:
                    prevPitch = prevVal["pitch"]
                    prevRoll = prevVal["roll"]
                
                pitch = int(clamp(pitch + prevPitch, -100, 100)) 
                roll = int(clamp(roll + prevRoll, -100, 100)) 
                thrust = int(thrust * 100)
                yaw = int(clamp(yaw, -100, 100)) 
                
                self.drone(PCMD(1, roll, pitch, yaw, thrust, timestampAndSeqNum=0))
                
                if prevVal is None:
                    prevVal = {}
                prevVal["pitch"] = pitch
                prevVal["roll"] = roll
                
                # Set previous ts and error for next iteration
                tp = ts
                ep = error

                await asyncio.sleep(0.03)
        except asyncio.CancelledError:
            pass

    async def _velocityPID(self):
        try:
            forward_PID = {"Kp": 0.7, "Kd": 0.5, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
            right_PID = {"Kp": 0.7, "Kd": 0.5, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
            up_PID = {"Kp": 2.5, "Kd": 1.5, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
            ep = {"forward": 0.0, "right": 0.0, "up": 0.0}
            rotMax = self.drone.get_state(MaxRotationSpeedChanged)["max"]
            tp = None
            prevVal = None

            def clamp(val, mini, maxi):
                return max(mini, min(val, maxi))

            def updatePID(e, ep, tp, ts, pidDict):
                P = pidDict["Kp"] * e
                I = pidDict["Ki"] * (ts - tp)
                if e < 0.0:
                    I *= -1
                elif e == 0.0 or I * pidDict["PrevI"] < 0:
                    I = 0.0
                D = pidDict["Kd"] * (e - ep) / (ts - tp)
                
                return P, I, D
            
            while self.flightmode == ParrotDrone.FlightMode.VELOCITY:
                ts = round(time.time() * 1000)
                current = await self.getVelocityBody()
                forward, right, up, ang = self.velocitySP

                error = {}
                error["forward"] = forward - current["forward"]
                if error["forward"] < 1:
                    error["forward"] = 0
                error["right"] = right - current["right"]
                if error["right"] < 1:
                    error["right"] = 0
                error["up"] = up - current["up"]
                if error["up"] < 1:
                    error["up"] = 0

                # On first loop through, set previous timestamp and error
                # to dummy values.
                if tp is None or (ts - tp) > 1000:
                    tp = ts - 1
                    ep = error

                P, I, D = updatePID(error["forward"], ep["forward"], tp, ts, forward_PID)
                forward_PID["PrevI"] += I
                forward = P + I + D
                
                P, I, D = updatePID(error["right"], ep["right"], tp, ts, right_PID)
                right_PID["PrevI"] += I
                right = P + I + D
                 
                P, I, D = updatePID(error["up"], ep["up"], tp, ts, up_PID)
                up_PID["PrevI"] += I
                up = P + I + D
                
                prevForward = 0
                prevRight = 0
                prevUp = 0
                if prevVal is not None:
                    prevForward = prevVal["forward"]
                    prevRight = prevVal["right"]
                    prevUp = prevVal["up"]
                
                forward = int(clamp(forward + prevForward, -100, 100)) 
                right = int(clamp(right + prevRight, -100, 100)) 
                up = int(clamp(up + prevUp, -100, 100))
                ang = int(clamp((ang / rotMax) * 100, -100, 100)) 
                
                self.drone(PCMD(1, right, forward, ang, up, timestampAndSeqNum=0))
                
                if prevVal is None:
                    prevVal = {}
                prevVal["forward"] = forward
                prevVal["right"] = right
                prevVal["up"] = up
                
                # Set previous ts and error for next iteration
                tp = ts
                ep = error
                
                await asyncio.sleep(0.03)
        except asyncio.CancelledError:
            pass

    ''' Connection methods '''

    async def connect(self):
        self.active = self.drone.connect()
        if not self.active:
            raise ConnectionFailedException("Cannot connect to drone")

    def isConnected(self):
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
        await self.switchModes(ParrotDrone.FlightMode.MANUAL)
        self.drone(TakeOff())
        await self.hovering()

    async def land(self):
        await self.switchModes(ParrotDrone.FlightMode.MANUAL)
        self.drone(Landing()).wait().success()

    async def setHome(self, lat, lng, alt):
        self.drone(set_custom_location(lat, lng, alt)).wait().success()

    async def rth(self):
        await self.hover()
        await self.switchModes(ParrotDrone.FlightMode.MANUAL)
        self.drone(return_to_home())
    
    ''' Camera methods '''

    async def getCameras(self):
        pass

    async def switchCameras(self, camID):
        from olympe.messages.thermal import set_mode
        if on:
            self.drone(set_mode(mode="blended")).wait().success()
        else:
            self.drone(set_mode(mode="disabled")).wait().success()

    ''' Movement methods '''
    
    async def setAttitude(self, pitch, roll, thrust, yaw):
        await self.switchModes(ParrotDrone.FlightMode.ATTITUDE)
        # Get attitude bounds from the drone
        tiltMax = self.drone.get_state(MaxTiltChanged)["max"]

        if abs(roll) > tiltMax or abs(pitch) > tiltMax:
            raise ArgumentOutOfBoundsException("Roll or pitch angle outside bounds")

        self.attitudeSP = (pitch, roll, thrust, yaw)
        if self.PIDTask is None:
            self.PIDTask = asyncio.create_task(self._attitudePID())
    
    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        await self.switchModes(ParrotDrone.FlightMode.VELOCITY)
        
        rotMax = self.drone.get_state(MaxRotationSpeedChanged)["max"]
        vertMax = self.drone.get_state(MaxVerticalSpeedChanged)["max"]

        if abs(angle_vel) > rotMax:
            raise ArgumentOutOfBoundsException("Rotation speed outside bound")
        if abs(up_vel) > vertMax:
            raise ArgumentOutOfBoundsException("Vertical speed outside bound")

        self.velocitySP = (forward_vel, right_vel, up_vel, angle_vel)
        if self.PIDTask is None:
            self.PIDTask = asyncio.create_task(self._velocityPID())

    async def setGPSLocation(self, lat, lng, alt, bearing):
        await self.switchModes(ParrotDrone.FlightMode.GUIDED)
        if bearing is None:
            self.drone(
                moveTo(lat, lng, alt, move_mode.orientation_mode.to_target, 0.0)
            )
        else:
            self.drone(
                moveTo(lat, lng, alt, move_mode.orientation_mode.heading_during, bearing)
            )
        await self.hovering()

    async def setTranslatedPosition(self, forward, right, up, angle):
        await self.switchModes(ParrotDrone.FlightMode.GUIDED)
        self.drone(
            moveBy(forward, right, -1 * up, angle)
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
        await self.switchModes(ParrotDrone.FlightMode.MANUAL)
        self.drone(PCMD(1, 0, 0, 0, 0, timestampAndSeqNum=0))
    
    ''' Status methods '''

    async def getTelemetry(self):
        telDict = {}
        telDict["gps"] = await self.getGPS()
        telDict["relAlt"] = await self.getAltitudeRel()
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
        try:
            return (self.drone.get_state(GpsLocationChanged)["latitude"],
                self.drone.get_state(GpsLocationChanged)["longitude"],
                self.drone.get_state(GpsLocationChanged)["altitude"])
        except Exception as e:
            # If there is no GPS fix, return default values
            return (500.0, 500.0, 0.0)
    
    async def getSatellites(self):
        return self.drone.get_state(NumberOfSatelliteChanged)["numberOfSatellite"]

    async def getHeading(self):
        return self.drone.get_state(AttitudeChanged)["yaw"] * (180 / math.pi)

    async def getAltitudeRel(self):
        return self.drone.get_state(AltitudeChanged)["altitude"]

    async def getAltitudeAbs(self):
        return self.drone.get_state(GpsLocationChanged)["altitude"]

    async def getVelocityNEU(self):
        NED = self.drone.get_state(SpeedChanged)
        return {"north": NED["speedX"], "east": NED["speedY"], "up": NED["speedZ"] * -1}

    async def getVelocityBody(self):
        NEU = await self.getVelocityNEU()
        vec = np.array([NEU["north"], NEU["east"]], dtype=float)
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

        res = {"forward": np.dot(vec, vecf) * -1, "right": np.dot(vec, vecr) * -1, \
                "up": NEU["up"]}
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
            logger.error(e)

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
        self.frame_queue.put_nowait(yuv_frame)

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
