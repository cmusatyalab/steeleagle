import asyncio
import logging
import os
import zmq
from enum import Enum
from util.utils import setup_socket
from util.utils import SocketOperation
import controlplane_pb2 as control_protocol

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

context = zmq.Context()
drone_control_sock = context.socket(zmq.DEALER)
sock_identity = b'usr'
drone_control_sock.setsockopt(zmq.IDENTITY, sock_identity)
setup_socket(drone_control_sock, SocketOperation.CONNECT, 'hub.network.controlplane.mission_to_hub')

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
        self.seq_num = 1 # set the initial seq_num to 1 caz cnc proto does not support to show 0
        self.request_map = {}

    def sender(self, request, driverRespond):
        seq_num = self.seq_num
        logger.info(f"Sending request with seq_num: {seq_num}")
        request.seq_num = seq_num
        self.seq_num += 1
        self.request_map[seq_num] = driverRespond
        serialized_request = request.SerializeToString()
        drone_control_sock.send_multipart([serialized_request])

    def receiver(self, response_parts):
        response = response_parts[0]
        driver_rep = control_protocol.Response()
        driver_rep.ParseFromString(response)
        seq_num = driver_rep.seq_num
        driverRespond = self.request_map[seq_num]

        if not driverRespond:
            logger.warning("Unrecognized seq_num")
            return

        status = driver_rep.resp
        if status == control_protocol.ResponseStatus.OK:
            logger.info("STAGE 1: OK")
        elif status == control_protocol.ResponseStatus.NOTSUPPORTED:
            logger.info("STAGE 1: NOTSUPPORTED")
            driverRespond.set()
        elif status == control_protocol.ResponseStatus.FAILED:
            logger.error("STAGE 2: FAILED")
            driverRespond.set()
        elif status == control_protocol.ResponseStatus.COMPLETED:
            logger.info("STAGE 2: COMPLETED")    
            driverRespond.grantPermission()
            driverRespond.putResult(driver_rep)
            driverRespond.set()   
    
    async def run(self):
        while True:
            try:
                response_parts = drone_control_sock.recv_multipart(flags=zmq.NOBLOCK)
                self.receiver(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                break
            await asyncio.sleep(0)
    
    '''Helper method to send a request and wait for a response'''
    async def send_and_wait(self, request):
        driverRespond = DriverRespond()
        self.sender(request, driverRespond)
        await driverRespond.wait()
        return driverRespond.getResult() if driverRespond.checkPermission() else None
   
    ''' Vehicle methods '''
    async def takeOff(self):
        logger.info("takeOff")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleControl.TAKEOFF
        result = await self.send_and_wait(request)
        return result.resp if result else False

    async def land(self):
        logger.info("land")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleControl.LAND
        result = await self.send_and_wait(request)
        return result.resp if result else False

    async def rth(self):
        logger.info("rth")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleControl.RTH
        result = await self.send_and_wait(request)
        return result.resp if result else False
    
    async def hover(self):
        logger.info("hover")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleControl.HOVER
        result = await self.send_and_wait(request)
        return result.resp if result else False

    async def setVelocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info("setVelocity")
        request = control_protocol.Request()
        request.veh.velocity_body.forward_vel = forward_vel
        request.veh.velocity_body.right_vel = right_vel
        request.veh.velocity_body.up_vel = up_vel
        request.veh.velocity_body.angle_vel = angle_vel
        result = await self.send_and_wait(request)
        return result.resp if result else False
    
    async def setRelativePosition(self, forward, right, up, angle):
        pass
    
    
    async def setGPSLocation(self, latitude, longitude, altitude, bearing):
        logger.info("setGPSLocation")
        request = control_protocol.Request()
        request.veh.location.latitude = latitude
        request.veh.location.longitude = longitude
        request.veh.location.absolute_altitude = altitude
        request.veh.location.heading = bearing
        result = await self.send_and_wait(request)
        return result.resp if result else False
    
    
    ''' Camera methods '''
    async def getCameras(self):
        pass

    async def switchCamera(self, camera_id):
        pass
