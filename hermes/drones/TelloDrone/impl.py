#/usr/bin/python3

# Compatible: Parrot ANAFI / Parrot ANAFI USA/ Parrot ANAFI AI (Untested)
# 
# This is an implementation of the standard MCFCS interface for drones
# compatible with Parrot's Olympe API.
#
# Author: Mihir Bala

from drones.drone import Drone

import math
import time
import queue
import cv2
import threading

# Tello specific imports
from djitellopy import Tello


class TelloDrone(Drone):

    def __init__(self):
        pass

    def connect(self):
        self.drone = Tello()
        self.drone.connect()

    def disconnect(self):
        pass

    def takeOff(self):
        self.drone.takeoff()

    def land(self):
        self.drone.land()

    def setHome(self, lat, lng):
        raise Exception("ERROR: Unsupported method for platform Tello")

    def moveTo(self, lat, lng, alt):
        raise Exception("ERROR: Unsupported method for platform Tello")

    def moveBy(self, x, y, z):
        x *= 100
        y *= -100
        z *= 100
        self.drone.go_xyz_speed(x, y, z, 50)

    def rotateBy(self, theta):
        self.drone.rotate_clockwise(theta)
    
    def rotateTo(self, theta):
        raise Exception("ERROR: Unsupported method for platform Tello")

    def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        raise Exception("ERROR: Unsupported method for platform Tello")

    def takePhoto(self):
        raise Exception("ERROR: Unsupported method for platform Tello")

    def getStatus(self):
        airspeed = self.drone.query_speed()
        loc = {}
        state = ""

        payload = {"location": loc, "state" : state["state"].name, "airspeed" : airspeed}
        return payload

    def cancel(self):
        raise Exception("ERROR: Unsupported method for platform Tello")

    # *** STREAMING CODE ***
    def startStreaming(self, q_size=10, sr=2):
        self.drone.streamon()

    def stopStreaming(self):
        self.drone.streamoff()

    def getVideoFrame(self):
        self.drone.get_frame_read()
    
