import asyncio
import logging
import zmq

from cnc_protocol import cnc_pb2


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DriverRespond():
    def __init__(self):
        self.event = asyncio.Event()
        self.permission = False
    
    def putResult(self, result):
        self.result = result
        
    def getResult (self):
        return self.result

    def set(self):
        self.event.set()
    
    def grantPermission(self):
        self.permission = True
        
    def checkPermission(self):
        return self.permission

    async def wait(self):
        await self.event.wait()
        
        

class DroneStub():

    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.DEALER)
        self.socket.bind("tcp://127.0.0.1:5001")
        self.seqNum = 0
        self.seqNum_res = {}
    
    
    ''' Common '''
    def sender (self, request, driverRespond):
        # sequence number
        seqNum = self.seqNum
        self.seqNum += 1
        request.seqNum = seqNum
        
        # map the sequence number with event
        self.seqNum_res[seqNum] = driverRespond
        
        # serialize the request and send it
        serialized_request = request.SerializeToString()
        self.socket.send_multipart([b'', serialized_request])
        
    
    async def run(self):
        # constantly listen for the response
        while True:
            # logger.info("DroneStub: waiting for the response")
            try:
                # Receive a request
                response_parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                
                # Ensure response_parts has the expected number of elements
                if len(response_parts) < 2:
                    logger.info("DroneStub: Incomplete message received, skipping...")
                    continue  # skip to the next iteration of the loop
                
                response = response_parts[1]
               
                logger.info("DroneStub: received the response")
                result = cnc_pb2.Driver()
                result.ParseFromString(response)
                status = result.resp
                seqNum = result.seqNum
                driverRespond = self.seqNum_res[seqNum]
                
                if (status == cnc_pb2.ResponseStatus.OK):
                    logger.info("DroneStub: STAGE 1: OK")
                    
                elif (status == cnc_pb2.ResponseStatus.DENIED):
                    logger.info("DroneStub: STAGE 1: DENIED")
                    driverRespond.set()
                    
                elif (status == cnc_pb2.ResponseStatus.NOTSUPPORTED):
                    logger.info("DroneStub: STAGE 1: NOTSUPPORTED")
                    driverRespond.set()
                    
                else:
                    # implicitly grant the permission
                    driverRespond.grantPermission()
                    
                    # report the status
                    if status == cnc_pb2.ResponseStatus.FAILED:
                        logger.info("DroneStub: STAGE 2: FAILED")
                        driverRespond.putResult(result)
                        driverRespond.set()

                    elif status == cnc_pb2.ResponseStatus.COMPLETED:
                        logger.info("DroneStub: STAGE 2: COMPLETED")
                        driverRespond.putResult(result)
                        driverRespond.set()
                
                
            except zmq.Again:
                pass
            
            except Exception as e:
                logger.info(f"DroneStub: Failed to parse message: {e}")
                break
            
            await asyncio.sleep(0)
                
    
    ''' Movement methods '''
    async def takeOff(self):
        # drone 
        logger.info("DroneStub: takeOff")
        request = cnc_pb2.Driver()
        logger.info("DroneStub: sending the request")
        request.takeOff = True
        
        # create a asyncio event
        driverRespond = DriverRespond()
        self.sender(request,driverRespond)
        
        # wait for the event to be set
        await driverRespond.wait()
        
        # return the result
        if (driverRespond.checkPermission()):
            res = driverRespond.getResult()
            return res.takeOff
        else:
            logger.info("DroneStub: permission not granted")
            return False
        
    

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
    
        ''' Streaming methods '''
    async def getCameras(self):
        pass

    
    async def switchCameras(self):
        pass
