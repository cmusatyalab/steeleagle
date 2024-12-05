import asyncio
import logging
import os
import zmq
from cnc_protocol import cnc_pb2
from enum import Enum
from util.utils import setup_socket
from util.utils import SocketOperation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

context = zmq.Context()
cmd_front_usr_sock = context.socket(zmq.DEALER)
sock_identity = b'usr'
cmd_front_usr_sock.setsockopt(zmq.IDENTITY, sock_identity)
setup_socket(cmd_front_usr_sock, SocketOperation.CONNECT, 'CMD_FRONT_USR_PORT', 'Created command frontend socket endpoint', os.environ.get("CMD_ENDPOINT"))

######################################################## DriverRespond ############################################################ 
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


######################################################## DroneStub ############################################################
class DroneStub:

    ######################################################## Common ############################################################
    def __init__(self):
        self.seqNum = 1 # set the initial seqNum to 1 caz cnc proto does not support to show 0
        self.seqNum_res = {}

    def sender(self, request, driverRespond):
        seqNum = self.seqNum
        logger.info(f"Sending request with seqNum: {seqNum}")
        request.seqNum = seqNum
        self.seqNum += 1
        self.seqNum_res[seqNum] = driverRespond
        serialized_request = request.SerializeToString()
        cmd_front_usr_sock.send_multipart([serialized_request])

    def receiver(self, response_parts):
        response = response_parts[0]
        result = cnc_pb2.Driver()
        result.ParseFromString(response)
        seqNum = result.seqNum
        driverRespond = self.seqNum_res[seqNum]

        if not driverRespond:
            logger.warning("Unrecognized seqNum")
            return

        status = result.resp
        if status == cnc_pb2.ResponseStatus.OK:
            logger.info("STAGE 1: OK")
        elif status == cnc_pb2.ResponseStatus.NOTSUPPORTED:
            logger.info("STAGE 1: NOTSUPPORTED")
            driverRespond.set()
        elif status == cnc_pb2.ResponseStatus.DENIED:
            logger.info("STAGE 1: DENIED")
            driverRespond.set()
        else:
            if status == cnc_pb2.ResponseStatus.FAILED:
                logger.error("STAGE 2: FAILED")
            elif status == cnc_pb2.ResponseStatus.COMPLETED:
                logger.info("STAGE 2: COMPLETED")    
            driverRespond.grantPermission()
            driverRespond.putResult(result)
            driverRespond.set()   
    
    async def run(self):
        while True:
            try:
                response_parts = cmd_front_usr_sock.recv_multipart(flags=zmq.NOBLOCK)
                self.receiver(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                break
            await asyncio.sleep(0)
    

    ######################################################## RPC ############################################################
    '''Helper method to send a request and wait for a response'''
    async def send_and_wait(self, request):
        driverRespond = DriverRespond()
        self.sender(request, driverRespond)
        await driverRespond.wait()
        return driverRespond.getResult() if driverRespond.checkPermission() else None
    
    ''' Preemptive methods '''
    async def takeOff(self):
        logger.info("takeOff")
        request = cnc_pb2.Driver(takeOff=True)
        result = await self.send_and_wait(request)
        return result.takeOff if result else False

    async def land(self):
        logger.info("land")
        request = cnc_pb2.Driver(land=True)
        result = await self.send_and_wait(request)
        return result.land if result else False

    async def rth(self):
        logger.info("rth")
        request = cnc_pb2.Driver(rth=True)
        result = await self.send_and_wait(request)
        return result.rth if result else False
    
    async def hover(self):
        logger.info("hover")
        request = cnc_pb2.Driver(hover=True)
        result = await self.send_and_wait(request)
        return result.hover if result else False

    ''' Location methods '''
    async def setHome(self, name, lat, lng, alt):
        logger.info("setHome")
        location = cnc_pb2.Location(name=name, latitude=lat, longitude=lng, altitude=alt)
        request = cnc_pb2.Driver(setHome=location)
        result = await self.send_and_wait(request)
        return result.setHome if result else False

    async def getHome(self):
        pass
    
        # logger.info("getHome")
        # request = cnc_pb2.Driver(getHome=cnc_pb2.Location())
        # result = await self.send_and_wait(request)
        # if result:
        #     return [result.getHome.name, result.getHome.lat, result.getHome.lng, result.getHome.alt]
        # else:
        #     return False

    ''' Attitude methods '''
    async def setAttitude(self, yaw, pitch, roll, thrust):
        logger.info("setAttitude")
        attitude = cnc_pb2.Attitude(yaw = yaw, pitch = pitch, roll = roll, thrust = thrust)
        request = cnc_pb2.Driver(setAttitude=attitude)
        
        result = await self.send_and_wait(request)
        return result.setAttitude if result else False
    
    ''' Position methods '''
    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info("setVelocity")
        velocity = cnc_pb2.Velocity(forward_vel=forward_vel, right_vel=right_vel, up_vel=up_vel, angle_vel=angle_vel)
        request = cnc_pb2.Driver(setVelocity=velocity)
        result = await self.send_and_wait(request)
        return result.setVelocity if result else False
    
    async def setRelativePosition(self, forward, right, up, angle):
        logger.info("setRelativePosition")
        position = cnc_pb2.Position(forward=forward, right=right, up=up, angle=angle)
        request = cnc_pb2.Driver(setRelativePosition=position)
        result = await self.send_and_wait(request)
        return result.setRelativePosition if result else False
    
    
    async def setTranslatedPosition(self, forward, right, up, angle):
        logger.info("setTranslatedPosition")
        position = cnc_pb2.Position(forward=forward, right=right, up=up, angle=angle)
        request = cnc_pb2.Driver(setTranslatedPosition=position)
        result = await self.send_and_wait(request)
        return result.setTranslatedPosition if result else False
    
    async def setGPSLocation(self, latitude, longitude, altitude, bearing):
        logger.info("setGPSLocation")
        location = cnc_pb2.Location(latitude=latitude, longitude=longitude, altitude=altitude, bearing=bearing)
        request = cnc_pb2.Driver(setGPSLocation=location)
        result = await self.send_and_wait(request)
        return result.setGPSLocation if result else False
    
    
    ''' Camera methods '''
    # define a camera type enum
    class CameraType(Enum):
        RGB = cnc_pb2.CameraType.RGB
        STEREO = cnc_pb2.CameraType.STEREO
        THERMAL = cnc_pb2.CameraType.THERMAL
        NIGHT = cnc_pb2.CameraType.NIGHT
    
        
    async def getCameras(self):
        logger.info("getCameras")
        request = cnc_pb2.Driver(getCameras=cnc_pb2.Camera())
        result = await self.send_and_wait(request)
        if result:
            id = result.getCameras.id
            type = self.CameraType(result.getCameras.type)
            
            return [id, type]
        else:    
            return False

    async def switchCamera(self, camera_id):
        logger.info("switchCamera")
        request = cnc_pb2.Driver(switchCamera=camera_id)
        result = await self.send_and_wait(request)
        return result.switchCameras if result else False    
