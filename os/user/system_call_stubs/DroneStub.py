import asyncio
import logging
import zmq
from cnc_protocol import cnc_pb2
from enum import Enum

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DriverRespond:
    def __init__(self):
        self.event = asyncio.Event()
        self.permission = False
        self.result = None
    
    def putResult(self, result):
        self.result = result
        
    def getResult(self):
        return self.result

    def set(self):
        self.event.set()
    
    def grantPermission(self):
        self.permission = True
        
    def checkPermission(self):
        return self.permission

    async def wait(self):
        await self.event.wait()


class DroneStub:

    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.DEALER)
        self.socket.bind("tcp://127.0.0.1:5001")
        self.seqNum = 0
        self.seqNum_res = {}

    def sender(self, request, driverRespond):
        seqNum = self.seqNum
        request.seqNum = seqNum
        self.seqNum += 1
        self.seqNum_res[seqNum] = driverRespond
        serialized_request = request.SerializeToString()
        self.socket.send_multipart([serialized_request])

    def process_response(self, response_parts):
        response = response_parts[0]
        result = cnc_pb2.Driver()
        result.ParseFromString(response)
        seqNum = result.seqNum
        driverRespond = self.seqNum_res[seqNum]

        if not driverRespond:
            logger.warning("DroneStub: Unrecognized seqNum")
            return

        status = result.resp
        if status == cnc_pb2.ResponseStatus.OK:
            logger.info("DroneStub: STAGE 1: OK")
        elif status in (cnc_pb2.ResponseStatus.DENIED, 
                        cnc_pb2.ResponseStatus.NOTSUPPORTED):
            logger.info(f"DroneStub: STAGE 1: {status.name}")
            driverRespond.set()
        else:
            driverRespond.grantPermission()
            if status in (cnc_pb2.ResponseStatus.FAILED, 
                          cnc_pb2.ResponseStatus.COMPLETED):
                logger.info(f"DroneStub: STAGE 2: {status.name}")
                driverRespond.putResult(result)
                driverRespond.set()

    async def run(self):
        while True:
            try:
                response_parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                self.process_response(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"DroneStub: Failed to parse message: {e}")
                break
            await asyncio.sleep(0)

    async def send_and_wait(self, request):
        driverRespond = DriverRespond()
        self.sender(request, driverRespond)
        await driverRespond.wait()
        return driverRespond.getResult() if driverRespond.checkPermission() else None

    ''' Preemptive methods '''
    async def takeOff(self):
        logger.info("DroneStub: takeOff")
        request = cnc_pb2.Driver(takeOff=True)
        result = await self.send_and_wait(request)
        return result.takeOff if result else False

    async def land(self):
        logger.info("DroneStub: land")
        request = cnc_pb2.Driver(land=True)
        result = await self.send_and_wait(request)
        return result.land if result else False

    async def rth(self):
        logger.info("DroneStub: rth")
        request = cnc_pb2.Driver(rth=True)
        result = await self.send_and_wait(request)
        return result.rth if result else False
    
    async def hover(self):
        logger.info("DroneStub: hover")
        request = cnc_pb2.Driver(hover=True)
        result = await self.send_and_wait(request)
        return result.hover if result else False

    ''' Location methods '''
    async def setHome(self, name, lat, lng, alt):
        logger.info("DroneStub: setHome")
        location = cnc_pb2.Location(name=name, lat=lat, lng=lng, alt=alt)
        request = cnc_pb2.Driver(setHome=location)
        result = await self.send_and_wait(request)
        return result.setHome if result else False

    async def getHome(self):
        logger.info("DroneStub: getHome")
        request = cnc_pb2.Driver(getHome=True)
        result = await self.send_and_wait(request)
        if result:
            return [result.getHome.name, result.getHome.lat, result.getHome.lng, result.getHome.alt]
        else:
            return False

    ''' Position methods '''
    async def setAttitude(self, yall, pitch, roll, thrust):
        logger.info("DroneStub: setAttitude")
        attitude = cnc_pb2.Attitude(yall, pitch, roll, thrust)
        request = cnc_pb2.Driver(setAttitude=attitude)
        
        result = await self.send_and_wait(request)
        return result.setAttitude if result else False
    
    async def setVelocity(self):
        logger.info("DroneStub: setVelocity")
        request = cnc_pb2.Driver(setVelocity=None)
        result = await self.send_and_wait(request)
        return result.setVelocity if result else False
    
    async def setRelativePosition(self, x, y, z, theta):
        logger.info("DroneStub: setRelativePosition")
        position = cnc_pb2.Position(x=x, y=y, z=z, theta=theta)
        request = cnc_pb2.Driver(setRelativePosition=True)
        result = await self.send_and_wait(request)
        return result.setRelativePosition if result else False
    
    
    async def setTranslatedPosition(self, x, y, z, theta):
        logger.info("DroneStub: setTranslation")
        position = cnc_pb2.Position(x=x, y=y, z=z, theta=theta)
        request = cnc_pb2.Driver(setTranslatedPosition=True)
        result = await self.send_and_wait(request)
        return result.setTranslatedPosition if result else False
    
    async def setGlobalPosition(self, x, y, z, theta):
        logger.info("DroneStub: setGlobalPosition")
        position = cnc_pb2.Position(x=x, y=y, z=z, theta=theta)
        request = cnc_pb2.Driver(setGlobalPosition=True)
        result = await self.send_and_wait(request)
        return result.setGlobalPosition if result else False
    
    
    ''' Camera methods '''
    # define a camera type enum
    class CameraType(Enum):
        RGB = cnc_pb2.CameraType.RGB
        STEREO = cnc_pb2.CameraType.STEREO
        THERMAL = cnc_pb2.CameraType.THERMAL
        NIGHT = cnc_pb2.CameraType.NIGHT
    
        
    async def getCameras(self):
        logger.info("DroneStub: getCameras")
        request = cnc_pb2.Driver(getCameras=None)
        result = await self.send_and_wait(request)
        if result:
            id = result.getCameras.id
            type = self.CameraType(result.getCameras.type)
            
            return [id, type]
        else:    
            return False

    
    async def switchCameras(self, camera_id):
        logger.info("DroneStub: switchCameras")
        request = cnc_pb2.Driver(switchCameras=camera_id)
        result = await self.send_and_wait(request)
        return result.switchCameras if result else False    
