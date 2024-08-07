import asyncio
import logging
import zmq

from cnc_protocol import cnc_pb2


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DriverRespond():
    def __init__(self):
        self.event = asyncio.Event()
        
    def putStatus(self, status):
        self.status = status
    
    def getStatus(self):
        return self.status  
    
    def putResult(self, result):
        self.result = result
        
    def getResult (self):
        return self.result

    def set(self):
        self.event.set()

    async def wait(self):
        await self.event.wait()
        

class DroneStub():

    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.DEALER)
        self.socket.bind("tcp://127.0.0.1:5001")
        self.socket.send("Hello".encode())
        self.seqNum = 0
        self.seqNum_res = {}
    
    
    def sender (self, request, driverRespond):
        # sequence number
        seqNum = self.seqNum
        self.seqNum += 1
        request.seqNum = seqNum
        
        # map the sequence number with event
        self.seqNum_res[seqNum] = driverRespond
        
        # serialize the request and send it
        serialized_request = request.SerializeToString()
        self.socket.send(serialized_request)
        
    
    async def run(self):
        
        # constantly listen for the response
        while True:
            try:
                # Receive a request
                response = self.socket.recv(flags=zmq.NOBLOCK)
                result = cnc_pb2.Driver()
                result.ParseFromString(response)
                
                seqNum = result.seqNum
                driverRespond = self.seqNum_res[seqNum]
                
                
                driverRespond.putResult(result)
                driverRespond.putStatus(result.status)
                driverRespond.set()
                

            except zmq.Again:
                pass
            
            await asyncio.sleep(0)
                

        
        
        
    ''' Streaming methods '''
    async def getCameras(self):
        pass

    
    async def switchCameras(self):
        pass
    
    ''' Movement methods '''
    async def takeOff(self):
        
        # drone 
        logger.info("DroneStub: takeOff")
        request = cnc_pb2.Driver()
        logger.info("DroneStub: sending the request")
        request.takeOff = True
        
        # create a asyncio event
        driverRespond = DriverRespond()
        self.sender(request, driverRespond)
        
        # wait for the event to be set
        await driverRespond.wait()
        
        res = driverRespond.getResult()
        status = driverRespond.getStatus()
        
        if status == cnc_pb2.SUCCESS:
            logger.info("DroneStub: takeOff success")
        else:
            logger.info("DroneStub: takeOff failed")
            
        return res.takeOff

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
