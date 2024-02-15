# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import asyncio
from abc import ABC, abstractmethod

class DroneItf(ABC):

    ''' Connection methods '''
    
    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def isConnected(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass
    
    ''' Streaming methods '''
    
    @abstractmethod
    async def startStreaming(self, **kwargs):
        pass
    
    @abstractmethod
    async def getVideoFrame(self):
        pass
    
    @abstractmethod
    async def stopStreaming(self):
        pass

    ''' Take off/ Landing methods '''

    @abstractmethod
    async def takeOff(self):
        pass

    @abstractmethod
    async def land(self):
        pass

    @abstractmethod
    async def setHome(self, lat, lng):
        pass

    @abstractmethod
    async def rth(self):
        pass
    
    ''' Movement methods '''

    @abstractmethod
    async def PCMD(self, pitch, yaw, roll, gaz, rot):
        pass

    @abstractmethod
    async def moveTo(self, lat, lng, alt):
        pass
    
    @abstractmethod
    async def moveBy(self, x, y, z, t):
        pass

    @abstractmethod
    async def rotateTo(self, theta):
        pass

    @abstractmethod
    async def setGimbalPose(self, yaw_theta, pitch_theta, roll_theta):
        pass

    @abstractmethod
    async def hover(self):
        pass

    ''' Photography methods ''' 

    @abstractmethod
    async def takePhoto(self):
        pass

    @abstractmethod
    async def toggleThermal(self, on):
        pass

    ''' Status methods '''

    @abstractmethod
    async def getName(self):
        pass

    @abstractmethod
    async def getLat(self):
        pass

    @abstractmethod
    async def getLng(self):
        pass
    
    @abstractmethod
    async def getHeading(self):
        pass

    @abstractmethod
    async def getRelAlt(self):
        pass

    @abstractmethod
    async def getExactAlt(self):
        pass
    
    @abstractmethod
    async def getRSSI(self):
        pass

    @abstractmethod
    async def getBatteryPercentage(self):
        pass

    @abstractmethod
    async def getMagnetometerReading(self):
        pass

    @abstractmethod
    async def getSatellites(self):
        pass

    @abstractmethod
    def getGimbalPitch(self):
        pass
    
    ''' Control methods '''

    @abstractmethod
    async def kill(self):
        pass
