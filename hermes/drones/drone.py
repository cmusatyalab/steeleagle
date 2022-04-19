#/usr/bin/python3

from abc import abstractmethod

class Drone:

    def __init__(self):
        pass

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def takeOff(self):
        pass

    @abstractmethod
    def land(self):
        pass

    @abstractmethod
    def setHome(self, lat, lng):
        pass

    @abstractmethod
    def moveTo(self, lat, lng, alt):
        pass

    @abstractmethod
    def moveBy(self, x, y, z):
        pass

    @abstractmethod
    def rotateBy(self, theta):
        pass

    @abstractmethod
    def rotateTo(self, theta):
        pass

    @abstractmethod
    def gimbalSetPose(self, yaw_theta, pitch_theta, roll_theta):
        pass

    @abstractmethod
    def takePhoto(self):
        pass

    @abstractmethod
    def getVideoFrame(self):
        pass

    @abstractmethod
    def getStatus(self):
        pass

    @abstractmethod
    def cancel(self):
        pass

    

