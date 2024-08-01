# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import asyncio
import zmq

class DroneStub():

    def __init__(self):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://localhost:5555")
    
    ''' Streaming methods '''
    async def getCameras(self):
        pass
    
    async def switchCameras(self):
        pass
    
    ''' Movement methods '''

    async def setAttitude(self):
        pass
    
    async def setVelocity(self):
        pass
    
    async def setRelativePosition(self):
        pass
    
    async def setTranslation(self):
        pass
    
    async def setGlobalPosition(self):
        pass
    
    async def hover(self):
        pass

