# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import asyncio
import logging
import zmq

from cnc_protocol import cnc_pb2


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class DroneStub():

    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:5001")
        
    
    async def run(self):
        response = self.socket.recv()
        
        
        
    ''' Streaming methods '''
    async def getCameras(self):
        driver_req = cnc_pb2.Driver()
        driver_req.getCameras.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response

    
    async def switchCameras(self):
        driver_req = cnc_pb2.Driver()
        driver_req.switchCameras.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response
       
    
    ''' Movement methods '''
    async def takeOff(self):
        

        
        
        
        logger.info("DroneStub: takeOff")
        driver_req = cnc_pb2.Driver()
        logger.info("DroneStub: sending the request")
        driver_req.takeOff = True
        serialized_req = driver_req.SerializeToString()
        
        
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response

    async def setAttitude(self):
        driver_req = cnc_pb2.Driver()
        driver_req.setAttitude.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response
       
    
    async def setVelocity(self):
        driver_req = cnc_pb2.Driver()
        driver_req.setVelocity.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response
    
    async def setRelativePosition(self):
        driver_req = cnc_pb2.Driver()
        driver_req.setRelativePosition.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response
    
    async def setTranslation(self):
        driver_req = cnc_pb2.Driver()
        driver_req.setTranslation.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response
    
    async def setGlobalPosition(self):
        driver_req = cnc_pb2.Driver()
        driver_req.setGlobalPosition.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response
    
    async def hover(self):
        driver_req = cnc_pb2.Driver()
        driver_req.hover.SetInParent()
        serialized_req = driver_req.SerializeToString()
        self.socket.send(serialized_req)
        response = self.socket.recv()
        print("Received response:", response)
        
        return response
