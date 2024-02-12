# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from abc import ABC, abstractmethod

class DroneItf(ABC):

    ''' Connection methods '''

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def isConnected(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass
    
    ''' Streaming methods '''

    @abstractmethod
    def startStreaming(self, resolution):
        pass
    
    @abstractmethod
    def getVideoFrame(self):
        pass

    @abstractmethod
    def stopStreaming(self):
        pass

    ''' Take off/ Landing methods '''

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
    def rth(self):
        pass
    
    ''' Movement methods '''

    @abstractmethod
    def PCMD(self, pitch, yaw, roll, gaz, rot):
        pass

    @abstractmethod
    def moveTo(self, lat, lng, alt):
        pass
    
    @abstractmethod
    def moveBy(self, x, y, z, t):
        pass

    @abstractmethod
    def rotateTo(self, theta):
        pass

    @abstractmethod
    def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        pass

    @abstractmethod
    def hover(self):
        pass

    ''' Photography methods ''' 

    @abstractmethod
    def takePhoto(self):
        pass

    @abstractmethod
    def toggleThermal(self, on):
        pass

    ''' Status methods '''

    @abstractmethod
    def getName(self):
        pass

    @abstractmethod
    def getLat(self):
        pass

    @abstractmethod
    def getLng(self):
        pass
    
    @abstractmethod
    def getHeading(self):
        pass

    @abstractmethod
    def getRelAlt(self):
        pass

    @abstractmethod
    def getExactAlt(self):
        pass
    
    @abstractmethod
    def getRSSI(self):
        pass

    @abstractmethod
    def getBatteryPercentage(self):
        pass

    @abstractmethod
    def getMagnetometerReading(self):
        pass

    @abstractmethod
    def getSatellites(self):
        pass

    @abstractmethod
    def getGimbalPitch(self):
        pass
    
    ''' Control methods '''

    @abstractmethod
    def kill(self):
        pass
