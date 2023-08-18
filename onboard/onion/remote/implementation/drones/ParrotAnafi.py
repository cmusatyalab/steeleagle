from interfaces import DroneItf
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.ardrone3.PilotingState import moveToChanged
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged
from olympe.messages.gimbal import set_target, attitude
from olympe.messages.wifi import rssi_changed
from olympe.messages.battery import capacity
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
import olympe.enums.move as move_mode
import olympe.enums.gimbal as gimbal_mode
import math


def killprotected(f):
    def wrapper(*args):
        if args[0].active:
            f(*args)
        else:
            raise RuntimeError("Cannot execute command, this drone is not active!")
    return wrapper


class ParrotAnafi(DroneItf.DroneItf):
    
    def __init__(self, **kwargs):
        self.ip = kwargs['ip']
        self.drone = Drone(self.ip)
        self.active = False

    ''' Connection methods '''

    def connect(self):
        self.drone.connect()
        self.active = True

    def isConnected(self):
        return self.drone.connection_state()

    def disconnect(self):
        self.drone.disconnect()
        self.active = False

    ''' Streaming methods '''

    def startStreaming(self, resolution):
        self.streamingThread = StreamingThread(self.drone, self.ip)
        self.streamingThread.start()

    def getVideoFrame(self):
        return self.streamingThread.grabFrame() 

    def stopStreaming(self):
        self.streamingThread.stop()

    ''' Take off / Landing methods '''

    @killprotected
    def takeOff(self):
        self.drone(TakeOff()).wait().success()

    def land(self):
        self.drone(Landing()).wait().success()

    def setHome(self):
        # TODO: Set the new RTH destination
        pass

    ''' Movement methods '''

    @killprotected
    def PCMD(self, roll, pitch, yaw, gaz):
        self.drone(
            PCMD(1, roll, pitch, yaw, gaz, timestampAndSeqNum=0)
            >> FlyingStateChanged(state="hovering", _timeout=5)
        )

    @killprotected
    def moveTo(self, lat, lng, alt):
        self.drone(
            moveTo(lat, lng, alt, move_mode.orientation_mode.to_target, 0.0)
            >> moveToChanged(status='DONE')
            >> FlyingStateChanged(state="hovering", _timeout=5)
        ).wait().success()

    @killprotected
    def moveBy(self, x, y, z, t):
        self.drone(
            moveBy(x, y, z, t) 
            >> FlyingStateChanged(state="hovering", _timeout=5)
        ).wait().success()

    @killprotected
    def rotateTo(self, theta):
        # TODO: Rotate to exact heading
        pass

    @killprotected
    def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
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
            roll=roll_theta,
        )
        >> attitude(pitch_absolute=pitch_theta, _policy="wait", _float_tol=(1e-3, 1e-1))).wait().success()

    def hover(self):
        self.moveBy(0.0, 0.0, 0.0, 0.0)

    ''' Photography methods '''

    def takePhoto(self):
        # TODO: Take a photo and save it to the local drone folder
        pass

    def toggleThermal(self, on):
        from olympe.messages.thermal import set_mode
        if on:
            self.drone(set_mode(mode="blended")).wait().success()
        else:
            self.drone(set_mode(mode="disabled")).wait().success()

    ''' Status methods '''

    def getName(self):
        return self.drone._device_name

    def getLat(self):
        return self.drone.get_state(GpsLocationChanged)["latitude"]

    def getLng(self):
        return self.drone.get_state(GpsLocationChanged)["longitude"]

    def getHeading(self):
        return self.drone.get_state(AttitudeChanged)["yaw"] * (180 / math.pi)

    def getRelAlt(self):
        return self.drone.get_state(AltitudeChanged)["altitude"]

    def getExactAlt(self):
        pass

    def getRSSI(self):
        return self.drone.get_state(rssi_changed)["rssi"]

    def getBatteryPercentage(self):
        #cap = self.drone.get_state(capacity)
        #return cap["remaining"] / cap["full_charge"]
        return 100

    def getMagnetometerReading(self):
        return self.drone.get_state(MagnetoCalibrationRequiredState)["required"] 

    def kill(self):
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
