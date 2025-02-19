# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import logging
import os
import zmq
from cnc_protocol import cnc_pb2
from util.utils import setup_socket
from util.utils import SocketOperation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

context = zmq.Context()
cpt_usr_sock = context.socket(zmq.DEALER)
sock_identity = b'usr'
cpt_usr_sock.setsockopt(zmq.IDENTITY, sock_identity)
setup_socket(cpt_usr_sock, SocketOperation.CONNECT, 'CPT_USR_PORT', 'Created command frontend socket endpoint', os.environ.get("DATA_ENDPOINT"))

class ComputeRespond:
    def __init__(self):
        self.event = asyncio.Event()
        self.permission = False
        self.result = None
    
    def putResult(self, result):
        self.result = result
        
    def getResult(self):
        return self.result
    
    async def wait(self):
        await self.event.wait()
        
    def set (self):
        self.event.set()
        
class ComputeStub():
    def __init__(self):
        self.seqNum = 1 # set the initial seqNum to 1 caz cnc proto does not support to show 0
        self.seqNum_res = {}
    
    def sender(self, request, computeRespond):
        seqNum = self.seqNum
        logger.info(f"Sending request with seqNum: {seqNum}")
        request.seqNum = seqNum
        self.seqNum += 1
        self.seqNum_res[seqNum] = computeRespond
        serialized_request = request.SerializeToString()
        cpt_usr_sock.send_multipart([serialized_request])
    
    def receiver(self, response_parts):
        response = response_parts[0]
        cpt_rep = cnc_pb2.Compute()
        cpt_rep.ParseFromString(response)
        seqNum = cpt_rep.seqNum
        computeRespond = self.seqNum_res[seqNum]
        
        if not computeRespond:
            logger.error(f"Received response with seqNum: {seqNum} but no corresponding request found")
            return
        
        status = cpt_rep.resp
        if status == cnc_pb2.ResponseStatus.FAILED:
            logger.error("STAGE 2: FAILED")
        elif status == cnc_pb2.ResponseStatus.COMPLETED:
            logger.info("STAGE 2: COMPLETED")
        computeRespond.putResult(cpt_rep.getter.result)
        computeRespond.set()
    
    async def run(self):
        while True:
            try:
                response_parts = cpt_usr_sock.recv_multipart(flags=zmq.NOBLOCK)
                self.receiver(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                break
            await asyncio.sleep(0)
        
    '''Helper method to send a request and wait for a response'''
    async def send_and_wait(self, request):
        computeRespond = ComputeRespond()
        self.sender(request, computeRespond)
        await computeRespond.wait()
        return computeRespond.getResult()
    
    # Get results for a compute engine
    async def getResults(self, compute_type):
        logger.info(f"Getting results for compute type: {compute_type}")
        cpt_req = cnc_pb2.Compute()
        cpt_req.getter.compute_type = compute_type
        
        result = await self.send_and_wait(cpt_req)
        return result
    
    async def clearResults(self):
        logger.info("Clearing results")
        cpt_req = cnc_pb2.Compute()
        cpt_req.clear = True
        await self.send_and_wait(cpt_req)


    ''' Telemetry methods '''
    async def getTelemetry(self):
        request = cnc_pb2.Driver(getTelemetry=cnc_pb2.Telemetry())
        result = await self.send_and_wait(request)
        telDict = {}
        if result:
            telDict["name"] = result.drone_name
            telDict["battery"] = result.battery
            telDict["attitude"]["yaw"] = result.drone_attitude.yaw 
            telDict["attitude"]["pitch"] = result.drone_attitude.pitch
            telDict["attitude"]["roll"] = result.drone_attitude.roll
            telDict["satellites"] = result.satellites
            telDict["gps"]["latitude"] = result.global_position.latitude
            telDict["gps"]["longitude"] = result.global_position.longitude
            telDict["gps"]["altitude"] = result.global_position.altitude
            telDict["relAlt"] = result.relative_position.up
            telDict["imu"]["forward"] = result.velocity.forward_vel
            telDict["imu"]["right"] = result.velocity.right_vel
            telDict["imu"]["up"] = result.velocity.up_vel 
            return telDict
        else:
            logger.error("Failed to get telemetry")    
            return None